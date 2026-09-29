"""CourtListener REST v4 client for judge-specific research.

Finds a judge's own opinions (type ``o``) and the orders in cases assigned to
that judge (RECAP documents, type ``rd``), so a brief can hold the court to
its own prior rulings.

Set COURTLISTENER_TOKEN (free account at courtlistener.com) for sane rate
limits. Standard library only; the HTTP opener is injectable for tests.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

API_ROOT = "https://www.courtlistener.com/api/rest/v4/"
SITE = "https://www.courtlistener.com"

# Issue presets: CourtListener/Lucene query strings for recurring fights.
ISSUES: Dict[str, dict] = {
    "rule41b": {
        "title": "Rule 41(b) dismissal; lesser sanctions; dismissal without prejudice",
        "q": '"41(b)" AND ("lesser sanction" OR "lesser sanctions" OR "without prejudice") AND ("contumacious" OR "clear record of delay")',
    },
    "pro-se-warning": {
        "title": "Pro se litigant warned before dismissal / opportunity to cure",
        "q": '"pro se" AND ("warned" OR "warning") AND ("failure to comply" OR "41(b)") AND "dismiss"',
    },
    "reconsider-interlocutory": {
        "title": "Reconsidering interlocutory orders under Rule 54(b)",
        "q": '"54(b)" AND ("as justice requires" OR "interlocutory order") AND reconsider*',
    },
    "rule54b-certification": {
        "title": "Rule 54(b) partial final judgment; no just reason for delay",
        "q": '"54(b)" AND "no just reason for delay"',
    },
    "remote-testimony": {
        "title": "Remote/video testimony or appearance (FRCP 43(a))",
        "q": '"43(a)" AND ("video" OR "remote" OR "videoconference" OR "contemporaneous transmission")',
    },
    "prior-restraint": {
        "title": "Injunctions restricting speech; prior restraint",
        "q": '"prior restraint" AND (injunction OR enjoin*)',
    },
    "civil-contempt": {
        "title": "Civil contempt: clear and convincing evidence of a definite and specific order",
        "q": '"civil contempt" AND "clear and convincing" AND ("definite and specific" OR "specific")',
    },
    "pi-dissolve": {
        "title": "Dissolving or modifying a preliminary injunction",
        "q": '("dissolve" OR "dissolution" OR "modify") AND "preliminary injunction" AND ("changed circumstances" OR "significant change")',
    },
    "protective-order": {
        "title": "Rule 26(c) good cause: particular and specific facts",
        "q": '"26(c)" AND "good cause" AND ("particular and specific" OR "conclusory statements")',
    },
    "anonymous-speaker": {
        "title": "Subpoenas to unmask anonymous online speakers",
        "q": 'subpoena AND anonymous AND ("First Amendment" OR "anonymous speech") AND (identity OR unmask*)',
    },
    "rule37-fees": {
        "title": "Rule 37(a)(5) mandatory expenses on motions to compel",
        "q": '"37(a)(5)" AND ("reasonable expenses" OR "attorney\'s fees")',
    },
    "iied-gap-filler": {
        "title": "IIED as a gap-filler tort (Texas)",
        "q": '"intentional infliction of emotional distress" AND "gap-filler"',
    },
    "civil-conspiracy": {
        "title": "Civil conspiracy is derivative of an underlying tort (Texas)",
        "q": '"civil conspiracy" AND ("derivative tort" OR "underlying tort")',
    },
    "tutsa": {
        "title": "Texas Uniform Trade Secrets Act",
        "q": '"Texas Uniform Trade Secrets Act" OR "TUTSA"',
    },
    "ada-retaliation": {
        "title": "ADA retaliation / failure to accommodate at the pleading stage",
        "q": '"Americans with Disabilities Act" AND retaliation AND ("motion to dismiss" OR "12(b)(6)")',
    },
}


class CourtListenerError(RuntimeError):
    pass


class CourtListener:
    def __init__(
        self,
        token: Optional[str] = None,
        api_root: str = API_ROOT,
        opener: Optional[Callable] = None,
        pause: float = 0.5,
    ):
        self.token = token if token is not None else os.environ.get("COURTLISTENER_TOKEN")
        self.api_root = api_root
        self.opener = opener or urllib.request.urlopen
        self.pause = pause

    def _get(self, path: str, params: dict) -> dict:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        url = f"{self.api_root}{path}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "gigi-sdtx/0.1"})
        if self.token:
            req.add_header("Authorization", f"Token {self.token}")
        try:
            with self.opener(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network, HTTP, or JSON errors
            raise CourtListenerError(f"CourtListener request failed: {url}: {exc}") from exc
        if self.pause:
            time.sleep(self.pause)
        return payload

    def search(
        self,
        q: str,
        *,
        kind: str = "o",
        court: str = "txsd",
        judge: Optional[str] = None,
        filed_after: Optional[str] = None,
        filed_before: Optional[str] = None,
        order_by: str = "score desc",
        limit: int = 20,
    ) -> List[dict]:
        """Search opinions (kind='o') or RECAP documents (kind='rd')."""
        # For RECAP documents, filter on the document's entry date, not the case filing date.
        after_key, before_key = ("entry_date_filed_after", "entry_date_filed_before") if kind == "rd" else (
            "filed_after", "filed_before")
        params = {
            "type": kind,
            "q": q,
            "court": court,
            "order_by": order_by,
            after_key: filed_after,
            before_key: filed_before,
        }
        if judge:
            params["judge" if kind == "o" else "assigned_to"] = judge
        hits: List[dict] = []
        path, page_params = "search/", params
        while len(hits) < limit:
            data = self._get(path, page_params)
            hits.extend(data.get("results", []))
            nxt = data.get("next")
            if not nxt:
                break
            parsed = urllib.parse.urlparse(nxt)
            path = parsed.path.split("/api/rest/v4/", 1)[-1]
            page_params = dict(urllib.parse.parse_qsl(parsed.query))
        return [normalize_hit(h, kind) for h in hits[:limit]]


def normalize_hit(hit: dict, kind: str = "o") -> dict:
    snippet = hit.get("snippet") or ""
    opinions = hit.get("opinions") or []
    if not snippet and opinions:
        snippet = opinions[0].get("snippet") or ""
    citation = hit.get("citation") or []
    if isinstance(citation, list):
        citation = "; ".join(c for c in citation if c)
    url = hit.get("absolute_url") or ""
    return {
        "case_name": hit.get("caseName") or hit.get("case_name") or "",
        "date": (hit.get("entry_date_filed") or hit.get("dateFiled") if kind == "rd"
                 else hit.get("dateFiled") or hit.get("entry_date_filed")) or hit.get("date_filed") or "",
        "docket_number": hit.get("docketNumber") or hit.get("docket_number") or "",
        "court": hit.get("court_citation_string") or hit.get("court") or "",
        "judge": hit.get("judge") or hit.get("assignedTo") or "",
        "citation": citation or "",
        "description": hit.get("description") or hit.get("short_description") or "",
        "snippet": " ".join(snippet.replace("<mark>", "**").replace("</mark>", "**").split()),
        "url": f"{SITE}{url}" if url.startswith("/") else url,
        "kind": kind,
    }


def to_markdown(hits: List[dict], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "> Research leads only: read each opinion and verify every quotation and pin cite before citing it.",
        "",
    ]
    if not hits:
        lines.append("_No results._")
    for i, h in enumerate(hits, 1):
        name = h["case_name"] or "(untitled)"
        bits = [b for b in (h["docket_number"], h["court"], h["date"]) if b]
        lines.append(f"{i}. **{name}**" + (f", {h['citation']}" if h["citation"] else "") + f" ({', '.join(bits)})")
        if h["description"]:
            lines.append(f"   - Document: {h['description']}")
        if h["judge"]:
            lines.append(f"   - Judge: {h['judge']}")
        if h["snippet"]:
            lines.append(f"   - …{h['snippet']}…")
        if h["url"]:
            lines.append(f"   - {h['url']}")
    return "\n".join(lines) + "\n"
