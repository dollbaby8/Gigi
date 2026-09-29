"""Citation-verified authority bank keyed to docket targets.

A playbook is JSON:

    {
      "case_number": "...", "judge": "...", "updated": "YYYY-MM-DD",
      "targets": {"ECF 200": {"title": "...", "ask": "..."}},
      "in_case_orders": [{"ecf", "date", "title", "excerpt", "verbatim", "use", "targets"}],
      "authorities":    [{"id", "kind", "case_name", "citation", "date", "holding", "quote",
                          "pin", "use", "targets", "source_url", "verified", "verification",
                          "issue"}],
      "adverse":        [same shape as authorities],
      "unverified_leads": [{"case_name", "why"}]
    }

``kind`` is one of KINDS. ``judge`` means a decision by the presiding judge.
Only ``verified: true`` entries render into briefs by default: an unverified
citation in a filing is a Rule 11 problem, not a style problem.
"""

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

KINDS = ("judge", "scotus", "fifth_cir", "texas", "sdtx", "other_district", "rule", "statute", "policy")
KIND_LABELS = {
    "judge": "This Court's prior decisions",
    "scotus": "Supreme Court",
    "fifth_cir": "Fifth Circuit",
    "texas": "Texas law",
    "sdtx": "Other S.D. Tex. decisions",
    "other_district": "Other persuasive authority",
    "rule": "Rules",
    "statute": "Statutes",
    "policy": "Policies and procedures",
}
KIND_ALIASES = {"ellison": "judge", "presiding_judge": "judge", "fifth": "fifth_cir", "ca5": "fifth_cir"}
REQUIRED = ("id", "kind", "case_name", "citation", "holding", "use", "targets", "verified")


def empty(case_number: str = "", judge: str = "") -> dict:
    return {
        "case_number": case_number,
        "judge": judge,
        "updated": "",
        "targets": {},
        "in_case_orders": [],
        "authorities": [],
        "adverse": [],
        "unverified_leads": [],
    }


def load(path) -> dict:
    pb = json.loads(Path(path).read_text(encoding="utf-8"))
    for key, default in empty().items():
        pb.setdefault(key, default)
    return pb


def save(pb: dict, path) -> None:
    Path(path).write_text(json.dumps(pb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def validate(pb: dict) -> List[str]:
    """Return a list of problems; empty means the playbook is internally sound."""
    problems: List[str] = []
    seen = set()
    targets = set(pb.get("targets", {}))
    for section in ("authorities", "adverse"):
        for i, a in enumerate(pb.get(section, [])):
            where = f"{section}[{i}] {a.get('id') or a.get('case_name') or '?'}"
            for key in REQUIRED:
                if a.get(key) in (None, "", []) and not (key == "verified" and a.get(key) is False):
                    problems.append(f"{where}: missing '{key}'")
            if a.get("id") in seen:
                problems.append(f"{where}: duplicate id")
            seen.add(a.get("id"))
            if a.get("kind") not in KINDS:
                problems.append(f"{where}: unknown kind '{a.get('kind')}'")
            if a.get("verified") and not a.get("verification"):
                problems.append(f"{where}: verified without a verification note")
            if a.get("quote") and not a.get("verified"):
                problems.append(f"{where}: quotation is unverified; do not use it until checked")
            for t in a.get("targets") or []:
                if targets and t not in targets:
                    problems.append(f"{where}: target '{t}' is not defined in 'targets'")
    for i, o in enumerate(pb.get("in_case_orders", [])):
        if not o.get("ecf") or not o.get("use"):
            problems.append(f"in_case_orders[{i}]: needs 'ecf' and 'use'")
    return problems


def select(
    pb: dict,
    *,
    target: Optional[str] = None,
    kinds: Optional[Iterable[str]] = None,
    verified_only: bool = True,
    section: str = "authorities",
) -> List[dict]:
    kinds = set(kinds) if kinds else None
    out = []
    for a in pb.get(section, []):
        if target and target not in (a.get("targets") or []):
            continue
        if kinds and a.get("kind") not in kinds:
            continue
        if verified_only and not a.get("verified"):
            continue
        out.append(a)
    return sorted(out, key=lambda a: (KINDS.index(a["kind"]) if a.get("kind") in KINDS else 99,
                                      a.get("date") or ""), reverse=False)


def orders_for(pb: dict, target: Optional[str] = None) -> List[dict]:
    return [o for o in pb.get("in_case_orders", []) if not target or target in (o.get("targets") or [])]


def stats(pb: dict) -> Dict[str, int]:
    out = {"total": 0, "verified": 0, "judge_verified": 0, "adverse": len(pb.get("adverse", [])),
           "unverified_leads": len(pb.get("unverified_leads", [])), "in_case_orders": len(pb.get("in_case_orders", []))}
    for a in pb.get("authorities", []):
        out["total"] += 1
        if a.get("verified"):
            out["verified"] += 1
            if a.get("kind") == "judge":
                out["judge_verified"] += 1
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def merge(pb: dict, research: dict, issue: Optional[str] = None) -> Dict[str, int]:
    """Merge a research file (same authority shape) into the playbook.

    Deduplicates on normalized citation (falling back to case name); a
    verified copy replaces an unverified one, never the reverse.
    """
    counts = {"added": 0, "upgraded": 0, "skipped": 0, "leads": 0}
    for section in ("authorities", "adverse"):
        index = {}
        for i, a in enumerate(pb.get(section, [])):
            index[_norm(a.get("citation")) or _norm(a.get("case_name"))] = i
        ids = {a.get("id") for a in pb.get(section, [])}
        for raw in research.get(section, []) or []:
            a = dict(raw)
            a["kind"] = KIND_ALIASES.get(a.get("kind"), a.get("kind"))
            if issue and not a.get("issue"):
                a["issue"] = issue
            key = _norm(a.get("citation")) or _norm(a.get("case_name"))
            if key in index:
                cur = pb[section][index[key]]
                if a.get("verified") and not cur.get("verified"):
                    a["targets"] = sorted(set(cur.get("targets") or []) | set(a.get("targets") or []))
                    pb[section][index[key]] = a
                    counts["upgraded"] += 1
                else:
                    cur["targets"] = sorted(set(cur.get("targets") or []) | set(a.get("targets") or []))
                    counts["skipped"] += 1
                continue
            base, n = a.get("id") or _norm(a.get("case_name"))[:40], 2
            while a.get("id") in ids or not a.get("id"):
                a["id"] = f"{base}-{n}"
                n += 1
            ids.add(a["id"])
            pb.setdefault(section, []).append(a)
            index[key] = len(pb[section]) - 1
            counts["added"] += 1
    for lead in research.get("unverified_leads", []) or []:
        pb.setdefault("unverified_leads", []).append(lead)
        counts["leads"] += 1
    return counts
