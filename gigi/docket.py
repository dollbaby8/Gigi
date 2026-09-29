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
    r"\b(granting in part and denying in part|denying as moot|dismissing as moot|finding as moot|"
    r"granting|denying|mooting|terminating|striking|withdrawing)"
    r"(?:\s+(?:without prejudice|with prejudice|in part|as moot|as unopposed|as premature))?\s+"
    # CM/ECF shows "[51]"; some exports drop the brackets ("denying 8 Motion for ..."). A bare
    # number only counts when a motion-type word follows within a few words, so dates and
    # counts ("re: 4/1/2026 hearing", "3 exhibits") are never read as ECF numbers.
    r"(?:\[(\d+)\]|(\d+)(?=\s+(?:[\w'-]+\s+){0,4}?(?:Motion|Petition|Application|Objection|Request)\b))",
    re.IGNORECASE,
)
MOTION_DOCKET_DATE_RE = re.compile(r"Motion Docket Date:?\s*(\d{1,2}/\d{1,2}/\d{4})")
MOTION_START_RE = re.compile(
    r"^(?:(?:Opposed|Unopposed|Agreed|Joint|Emergency|Amended|Renewed|Cross|Sealed|Supplemental|Expedited|"
    r"Partial|Verified|Corrected|First|Second|Third)[\s-]+)*MOTION\b(?!\s+Hearing)",
    re.IGNORECASE,
)
_MOD = (r"(?:Initial|Status|Scheduling|Pretrial|Final|Docket|Motion|Evidentiary|Show Cause|Settlement|"
        r"Telephone|Telephonic|Rule 16|Preliminary Injunction|Contempt|Discovery|Bench|Jury|Oral)")
SETTING_RE = re.compile(
    rf"\b(?P<what>(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing|Trial|Call)"
    rf"(?:\s+and\s+(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing))?)\s+(?P<re>re)?set for\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+at\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\s+in\s+"
    r"(?P<where>.*?)(?=\s+before\b|[,.(]|$)"
)
HELD_RE = re.compile(
    rf"\b(?P<what>(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing|Trial)"
    rf"(?:\s+and\s+(?:{_MOD}\s+){{0,2}}(?:Conference|Hearing))?)\s+held on\s+(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{4}})",
    re.IGNORECASE,
)
CANCEL_RE = re.compile(
    r"\b(cancel(?:l)?(?:ing|ed|s)?|cancellation|terminated|vacat(?:ed|ing)|to be rescheduled|off the calendar)\b",
    re.IGNORECASE,
)
RESET_RE = re.compile(r"\b(reset|resetting|rescheduled?)\b", re.IGNORECASE)
SUPPORT_RE = re.compile(
    r"^((First |Second |Third |Fourth )?(Supplemental|SUPPLEMENTAL) )?(BRIEF|Brief|EXHIBITS?|Exhibits?|APPENDIX|Appendix|"
    r"DECLARATION|Declaration|AFFIDAVIT|Affidavit|CERTIFICATE|Certificate|Proposed Order|PROPOSED ORDER)\b"
    r"|^(First |Second |Third |Fourth )?(SUPPLEMENT|Supplement)\b"
    r"|^(MEMORANDUM|Memorandum) (of Law )?in Support\b"
)
ORDER_START_RE = re.compile(
    r"^(ORDER|Order\b|MEMORANDUM (AND|&) (ORDER|OPINION)|Memorandum and Order|MEMORANDUM OPINION|"
    r"OPINION|SCHEDULING/DOCKET CONTROL ORDER|Scheduling Order|FINAL JUDGMENT|Final Judgment|JUDGMENT|"
    r"Striking Document|(MEMORANDUM|REPORT) AND RECOMMENDATIONS?)"
    r"|^(?![A-Z /&]*PROPOSED)[A-Z][A-Z /&]*\bORDER\b"
)
SIGNED_RE = re.compile(r"\(\s*Signed by (?:[\w.]+ )*Judge", re.IGNORECASE)


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
    if re.match(r"^NOTICE of (Re)?setting", t, re.IGNORECASE):
        return "setting"
    if re.match(r"^Minute (Entry|Order)", t, re.IGNORECASE) or t in {
        "Motion Hearing", "Status Conference", "Motion Hearing AND Scheduling Conference",
    }:
        return "minute"
    if re.match(r"^(TRANSCRIPT|Transcript|Notice of Filing of Official Transcript)", t):
        return "transcript"
    if ORDER_START_RE.match(t) or SIGNED_RE.search(t):
        return "order"
    if re.match(r"^(Opposed |Supplemental |Agreed |Unopposed )?(RESPONSE|Response)", t) or re.match(
        r"^(MEMORANDUM|Memorandum) (of Law )?in Opposition\b", t
    ):
        return "response"
    if re.match(r"^(REPLY|Reply|SURREPLY|Surreply|SUR-REPLY|Sur-Reply|Sur-reply)", t):
        return "reply"
    if SUPPORT_RE.match(t):
        return "support"
    if re.match(r"^(NOTICE|Notice|CLERKS NOTICE|Clerks Notice|ADVISORY)\b", t) and not re.match(r"^NOTICE OF MOTION", t, re.I):
        return "notice"
    # A motion is an entry whose own event is MOTION, not a filing that merely mentions one
    # ("MEMORANDUM in Opposition to [5] MOTION", "Joint STATUS REPORT re: [5] MOTION").
    if MOTION_START_RE.match(t) or (t and all(p.strip() in MOTION_CATEGORIES for p in t.split(" AND "))):
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
            # Unnumbered CM/ECF entries are clerk/minute entries even without a "Minute Entry" prefix.
            if self.kind == "other" and self.number is None:
                self.kind = "minute"

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
        """Map motion ECF number -> rulings found in order/minute docket text.

        Only explicit "<verb> [N]" rulings count. Rulings that a bare "ORDER" entry
        does not name belong in ``manual_dispositions`` (case.json).
        """
        out: Dict[int, List[dict]] = {}
        for e in self.by_kind("order", "minute"):
            seen = set()
            for m in DISPOSITION_RE.finditer(e.text):
                key = (m.group(1).lower(), int(m.group(2) or m.group(3)))
                if key in seen:
                    continue
                seen.add(key)
                out.setdefault(key[1], []).append(
                    {"ruling": key[0], "order": e.number, "date": e.date.isoformat() if e.date else None}
                )
        for num, rulings in self.manual_dispositions.items():
            out.setdefault(int(num), []).extend(rulings)
        return out

    def pending_motions(self, as_of: date, extra: Iterable[date] = (), state: Iterable[date] = ()) -> List[dict]:
        """Motions with no ruling found in docket text as of ``as_of``, oldest first.

        Undated motions (e.g. added through case.json overrides) are listed last with an
        unknown submission day rather than silently dropped.
        """
        ruled = set()
        for num, rulings in self.dispositions().items():
            if any(not r.get("date") or _parse_date(r["date"]) <= as_of for r in rulings):
                ruled.add(num)
        rows = []
        for e in self.motions():
            if e.number is None or e.number in ruled or (e.date is not None and e.date > as_of):
                continue
            listed = e.motion_docket_date()
            if e.date is None:
                submission, source, age = listed, "docket text" if listed else "unknown (no filing date)", None
            else:
                computed, _ = submission_day(e.date, extra, state)
                submission = listed or computed
                source = "docket text" if listed else "computed (LR 7.3)"
                age = (as_of - e.date).days
            rows.append(
                {
                    "entry": e,
                    "submission_day": submission,
                    "submission_source": source,
                    "age_days": age,
                    "emergency": bool(re.search(r"emergency", e.text, re.IGNORECASE)),
                    "cjra_candidate": is_cjra_candidate(e.date, as_of),
                }
            )
        return sorted(rows, key=lambda r: (r["entry"].date is None, r["entry"].date or date.max))

    def mail_returned(self) -> List[Entry]:
        return self.by_kind("mail_returned")

    def hearing_settings(self) -> List[dict]:
        """Every hearing/conference setting, with what later happened to it.

        ``status`` is ``scheduled``, ``held`` (a minute entry says so), ``superseded`` (a
        later reset of the same event before it occurred), or ``cancelled`` (a later
        cancel/vacate/terminate entry before it occurred). Only ``scheduled`` settings belong
        on a calendar.
        """
        rows: List[dict] = []
        for e in self.by_kind("setting", "order", "minute", "notice"):
            when = e.date or date.min
            nouns = {n.lower() for n in re.findall(r"\b(Conference|Hearing|Trial)\b", e.text, re.IGNORECASE)}
            if CANCEL_RE.search(e.text) and nouns:
                for noun in nouns:
                    for r in reversed(rows):
                        if (r["status"] == "scheduled" and r["entry"] is not e and r["date"]
                                and r["date"] >= when and any(c.endswith(noun) for c in r["components"])):
                            r["status"], r["changed_by"] = "cancelled", e.label
                            break
            for m in HELD_RE.finditer(e.text):
                held_on, comps = _parse_date(m.group("date")), _components(m.group("what"))
                for r in rows:
                    if r["date"] == held_on and r["components"] & comps and r["status"] in ("scheduled", "cancelled"):
                        r["status"], r["changed_by"] = "held", e.label
            is_reset = bool(RESET_RE.search(e.text))
            for m in SETTING_RE.finditer(e.text):
                comps = _components(m.group("what"))
                if m.group("re") or is_reset:
                    for r in rows:
                        if (r["status"] == "scheduled" and r["entry"] is not e and r["components"] & comps
                                and r["date"] and r["date"] >= when):
                            r["status"], r["changed_by"] = "superseded", e.label
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
                        "components": comps,
                        "date": _parse_date(m.group("date")),
                        "time": m.group("time"),
                        "mode": mode,
                        "where": where,
                        "status": "scheduled",
                        "changed_by": None,
                    }
                )
        return rows


def _components(what: str) -> set:
    """Normalize "Initial Conference and Motion Hearing" -> {"initial conference", "motion hearing"}."""
    out = set()
    for part in re.split(r"\s+and\s+", what.strip(), flags=re.IGNORECASE):
        p = part.lower()
        if "trial" in p:
            out.add("trial")
        elif "call" in p:
            out.add("docket call")
        elif "conference" in p:
            kind = "initial" if re.search(r"initial|scheduling|rule 16", p) else next(
                (k for k in ("status", "pretrial", "settlement", "discovery") if k in p), "")
            out.add(f"{kind} conference".strip())
        elif "hearing" in p:
            kind = next((k for k in ("evidentiary", "show cause", "preliminary injunction") if k in p), "motion")
            out.add(f"{kind} hearing")
    return out


def next_cjra_cutoff(as_of: date) -> date:
    """Next Civil Justice Reform Act reporting date (Mar 31 or Sep 30)."""
    for cutoff in (date(as_of.year, 3, 31), date(as_of.year, 9, 30)):
        if cutoff >= as_of:
            return cutoff
    return date(as_of.year + 1, 3, 31)


def is_cjra_candidate(filed: Optional[date], as_of: date) -> bool:
    """Approximate test: pending more than six months at the next CJRA cutoff."""
    return filed is not None and (next_cjra_cutoff(as_of) - filed) > timedelta(days=182)


# ---- loaders -------------------------------------------------------------
def _sort_key(e: Entry):
    """Chronological; unnumbered minute entries follow numbered ones filed the same day; undated last."""
    return (e.date or date.max, e.number is None, e.number or 0)


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
