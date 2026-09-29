"""Load, classify, and analyze federal docket sheets.

Supported inputs:
  * DocketBird ``get_docket_sheet`` JSON ({"documents": [...]})
  * CourtListener REST v4 docket-entries JSON ({"results": [...]} or a list)
  * Gigi's normalized docket JSON ({"entries": [...]}), written by ``save``

Classification is heuristic and keyed to CM/ECF docket-text conventions.
Anything it cannot place is ``other``; always read the underlying document.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from gigi.deadlines import submission_day

MOTION_CATEGORIES = {
    "Compel", "Sanctions", "Emergency", "Stay", "Dismiss", "Contempt", "Settlement", "Seal",
    "Referral to ADR", "Partial Summary Judgment", "Summary Judgment", "Jury Trial",
    "Miscellaneous Relief", "Leave to File Document", "Extension of Time", "Protective Order",
    "Interlocutory Appeal", "Reconsideration", "Strike", "Vacate", "Continuance",
    "Default Judgment", "Remand", "Transfer", "Intervene", "Withdraw as Attorney",
    "Clarification", "Leave to File", "Expedite", "Disqualify", "Judgment",
}
DISPOSITION_RE = re.compile(
    r"(granting in part and denying in part|denying as moot|dismissing as moot|finding as moot|"
    r"granting|denying|mooting|terminating|striking|withdrawing)\s+"
    # CM/ECF shows "[51]"; some exports drop the brackets ("denying 8 Motion for ...").
    r"(?:\[(\d+)\]|(\d+)(?=\s+(?:(?:Opposed|Unopposed|Agreed|Amended|Emergency|Sealed|Supplemental|First|Second)\s+)*"
    r"(?:Motion|Petition|Application|Objection|Request)\b))",
    re.IGNORECASE,
)
DISPOSITION_RE_LOOSE = re.compile(r"\b(granting|denying)\b[^\[\];]{0,80}?\bre:\s*\[?(\d+)\]?", re.IGNORECASE)
MOTION_DOCKET_DATE_RE = re.compile(r"Motion Docket Date:?\s*(\d{1,2}/\d{1,2}/\d{4})")
_MOD = (r"(?:Initial|Status|Scheduling|Pretrial|Final|Docket|Motion|Evidentiary|Show Cause|Settlement|"
        r"Telephone|Telephonic|Rule 16|Preliminary Injunction|Contempt|Discovery|Bench|Jury|Oral)")
SETTING_RE = re.compile(
    rf"\b(?P<what>(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing|Trial|Call)"
    rf"(?:\s+and\s+(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing))?)\s+(?:re)?set for\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\s+in\s+"
    r"(?P<where>.*?)(?=\s+before\b|[,.(]|$)"
)
SUPPORT_RE = re.compile(
    r"^((First |Second |Third |Fourth )?(Supplemental|SUPPLEMENTAL) )?(BRIEF|Brief|EXHIBITS?|Exhibits?|APPENDIX|Appendix|"
    r"DECLARATION|Declaration|AFFIDAVIT|Affidavit|CERTIFICATE|Certificate|Proposed Order|PROPOSED ORDER)\b"
    r"|^(First |Second |Third |Fourth )?(SUPPLEMENT|Supplement)\b"
)
ORDER_START_RE = re.compile(
    r"^(ORDER|Order\b|MEMORANDUM (AND|&) (ORDER|OPINION)|Memorandum and Order|MEMORANDUM OPINION|"
    r"OPINION|SCHEDULING/DOCKET CONTROL ORDER|Scheduling Order|FINAL JUDGMENT|Final Judgment|JUDGMENT|"
    r"Striking Document)"
)


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def classify(text: str) -> str:
    t = (text or "").strip()
    if "Mail Returned Undeliverable" in t:
        return "mail_returned"
    if re.match(r"^NOTICE of Setting|^Notice of Setting", t):
        return "setting"
    if re.match(r"^Minute (Entry|Order)", t) or t in {
        "Motion Hearing", "Status Conference", "Motion Hearing AND Scheduling Conference",
    }:
        return "minute"
    if re.match(r"^(TRANSCRIPT|Transcript|Notice of Filing of Official Transcript)", t):
        return "transcript"
    if ORDER_START_RE.match(t) or "(Signed by Judge" in t:
        return "order"
    if re.match(r"^(Opposed |Supplemental |Agreed |Unopposed )?(RESPONSE|Response)", t):
        return "response"
    if re.match(r"^(REPLY|Reply)", t):
        return "reply"
    if SUPPORT_RE.match(t):
        return "support"
    if re.match(r"^(NOTICE|Notice|CLERKS NOTICE|Clerks Notice|ADVISORY)\b", t) and not re.match(r"^NOTICE OF MOTION", t, re.I):
        return "notice"
    if re.search(r"\bMOTION\b", t) or (t and all(p.strip() in MOTION_CATEGORIES for p in t.split(" AND "))):
        return "motion"
    if re.match(r"^((First |Second |Third )?AMENDED COMPLAINT|COMPLAINT|Original Complaint)", t):
        return "complaint"
    if re.match(r"^(NOTICE|Notice|CLERKS NOTICE|Clerks Notice|ADVISORY|Other Notice)", t):
        return "notice"
    return "other"


@dataclass
class Entry:
    number: Optional[int]
    date: Optional[date]
    text: str
    kind: str = ""
    attachments: List[str] = field(default_factory=list)
    available: bool = False
    restricted: bool = False
    source_id: Optional[str] = None

    def __post_init__(self):
        if not self.kind:
            self.kind = classify(self.text)

    @property
    def label(self) -> str:
        return f"ECF {self.number}" if self.number is not None else "(unnumbered)"

    def short(self, width: int = 110) -> str:
        t = " ".join(self.text.split())
        return t if len(t) <= width else t[: width - 1] + "…"

    def motion_docket_date(self) -> Optional[date]:
        m = MOTION_DOCKET_DATE_RE.search(self.text)
        return _parse_date(m.group(1)) if m else None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d


@dataclass
class Docket:
    case_number: str = ""
    court: str = ""
    caption: str = ""
    judge: str = ""
    entries: List[Entry] = field(default_factory=list)
    # Rulings the docket text does not name (e.g. a bare "ORDER"), keyed by motion number.
    manual_dispositions: Dict[int, List[dict]] = field(default_factory=dict)

    # ---- queries -------------------------------------------------------
    def by_kind(self, *kinds: str) -> List[Entry]:
        return [e for e in self.entries if e.kind in kinds]

    def orders(self) -> List[Entry]:
        return self.by_kind("order")

    def motions(self) -> List[Entry]:
        return self.by_kind("motion")

    def get(self, number: int) -> Optional[Entry]:
        for e in self.entries:
            if e.number == number:
                return e
        return None

    def dispositions(self) -> Dict[int, List[dict]]:
        """Map motion ECF number -> rulings found in order/minute docket text."""
        out: Dict[int, List[dict]] = {}
        for e in self.by_kind("order", "minute"):
            seen = set()
            for rx in (DISPOSITION_RE, DISPOSITION_RE_LOOSE):
                for m in rx.finditer(e.text):
                    key = (m.group(1).lower(), int(next(g for g in m.groups()[1:] if g)))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.setdefault(key[1], []).append(
                        {"ruling": key[0], "order": e.number, "date": e.date.isoformat() if e.date else None}
                    )
        for num, rulings in self.manual_dispositions.items():
            out.setdefault(int(num), []).extend(rulings)
        return out

    def pending_motions(self, as_of: date) -> List[dict]:
        """Motions with no ruling found in docket text, oldest first."""
        ruled = self.dispositions()
        rows = []
        for e in self.motions():
            if e.number is None or e.number in ruled or e.date is None or e.date > as_of:
                continue
            listed = e.motion_docket_date()
            computed, _ = submission_day(e.date)
            rows.append(
                {
                    "entry": e,
                    "submission_day": listed or computed,
                    "submission_source": "docket text" if listed else "computed (LR 7.3)",
                    "age_days": (as_of - e.date).days,
                    "emergency": bool(re.search(r"emergency", e.text, re.IGNORECASE)),
                    "cjra_candidate": is_cjra_candidate(e.date, as_of),
                }
            )
        return sorted(rows, key=lambda r: r["entry"].date)

    def mail_returned(self) -> List[Entry]:
        return self.by_kind("mail_returned")

    def hearing_settings(self) -> List[dict]:
        """Hearings/conferences parsed from settings, orders, and minute entries."""
        rows = []
        for e in self.by_kind("setting", "order", "minute"):
            for m in SETTING_RE.finditer(e.text):
                where = m.group("where").strip()
                if "telephone" in where.lower():
                    mode = "telephone"
                elif re.search(r"video|zoom|teams", where, re.IGNORECASE):
                    mode = "video"
                elif "courtroom" in where.lower():
                    mode = "in person"
                else:
                    mode = "unknown"
                rows.append(
                    {
                        "entry": e,
                        "what": m.group("what").strip(),
                        "date": _parse_date(m.group("date")),
                        "time": m.group("time"),
                        "mode": mode,
                        "where": where,
                    }
                )
        return rows


def next_cjra_cutoff(as_of: date) -> date:
    """Next Civil Justice Reform Act reporting date (Mar 31 or Sep 30)."""
    for cutoff in (date(as_of.year, 3, 31), date(as_of.year, 9, 30)):
        if cutoff >= as_of:
            return cutoff
    return date(as_of.year + 1, 3, 31)


def is_cjra_candidate(filed: date, as_of: date) -> bool:
    """Approximate test: pending more than six months at the next CJRA cutoff."""
    return (next_cjra_cutoff(as_of) - filed) > timedelta(days=182)


# ---- loaders -------------------------------------------------------------
def _sort_key(e: Entry):
    """Chronological; unnumbered minute entries follow numbered ones filed the same day."""
    return (e.date or date.min, e.number is None, e.number or 0)


def _from_docketbird(data: dict) -> Docket:
    grouped: Dict[object, Entry] = {}
    order: List[object] = []
    for i, doc in enumerate(data.get("documents", [])):
        num = doc.get("primary_docket_sheet_number")
        key = num if num is not None else f"u{i}"
        title = doc.get("title") or ""
        if key in grouped:
            grouped[key].attachments.append(title)
            continue
        grouped[key] = Entry(
            number=num,
            date=_parse_date(doc.get("filing_date")),
            text=title,
            available=bool(doc.get("downloaded")),
            restricted=bool(doc.get("restricted")),
            source_id=doc.get("id"),
        )
        order.append(key)
    return Docket(entries=[grouped[k] for k in order])


def _from_courtlistener(rows: Iterable[dict]) -> Docket:
    entries = []
    for row in rows:
        docs = row.get("recap_documents") or []
        main = next((d for d in docs if not d.get("attachment_number")), docs[0] if docs else {})
        text = row.get("description") or main.get("description") or ""
        entries.append(
            Entry(
                number=row.get("entry_number"),
                date=_parse_date(row.get("date_filed")),
                text=text,
                attachments=[d.get("description") or "" for d in docs if d.get("attachment_number")],
                available=bool(main.get("is_available")),
                source_id=str(main.get("pacer_doc_id") or main.get("document_id") or main.get("id") or "") or None,
            )
        )
    return Docket(entries=entries)


def load(path) -> Docket:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "documents" in data:
        docket = _from_docketbird(data)
    elif isinstance(data, list):
        docket = _from_courtlistener(data)
    elif isinstance(data, dict) and isinstance(data.get("results"), list):
        docket = _from_courtlistener(data["results"])
    elif isinstance(data, dict) and isinstance(data.get("entries"), dict):
        docket = _from_courtlistener(data["entries"].get("entries", []))
    elif isinstance(data, dict) and isinstance(data.get("entries"), list):
        docket = Docket(
            case_number=data.get("case_number", ""),
            court=data.get("court", ""),
            caption=data.get("caption", ""),
            judge=data.get("judge", ""),
            entries=[
                Entry(
                    number=e.get("number"),
                    date=_parse_date(e.get("date")),
                    text=e.get("text", ""),  # kind is re-derived so classifier fixes apply
                    attachments=e.get("attachments", []),
                    available=e.get("available", False),
                    restricted=e.get("restricted", False),
                    source_id=e.get("source_id"),
                )
                for e in data["entries"]
            ],
        )
    else:
        raise ValueError(f"Unrecognized docket format: {path}")
    docket.entries.sort(key=_sort_key)
    return docket


def apply_overrides(docket: Docket, overrides: dict) -> Docket:
    """Add or patch entries the source index is missing, keyed by ECF number."""
    for num_text, patch in (overrides or {}).items():
        num = int(num_text)
        entry = docket.get(num)
        if entry is None:
            entry = Entry(number=num, date=_parse_date(patch.get("date")), text=patch.get("text", ""),
                          kind=patch.get("kind", ""))
            docket.entries.append(entry)
        else:
            if "text" in patch:
                entry.text = patch["text"]
            if "date" in patch:
                entry.date = _parse_date(patch["date"])
            entry.kind = patch.get("kind") or classify(entry.text)
    docket.entries.sort(key=_sort_key)
    return docket


def save(docket: Docket, path) -> None:
    payload = {
        "case_number": docket.case_number,
        "court": docket.court,
        "caption": docket.caption,
        "judge": docket.judge,
        "entries": [e.to_dict() for e in docket.entries],
    }
    Path(path).write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
