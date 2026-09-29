"""Render brief-ready Markdown argument inserts from a playbook."""

from datetime import date
from typing import List, Optional

from gigi import playbook as pbk

BANNER = (
    "> **PRIVILEGED & CONFIDENTIAL — ATTORNEY WORK PRODUCT — DRAFT.** "
    "Read every authority and cite-check every quotation and pin cite before filing "
    "(FRCP 11(b)(2)). Unverified authorities are excluded unless explicitly requested."
)


def _authority_block(a: dict) -> List[str]:
    lines = [f"**{a.get('case_name') or '(unnamed authority)'}**" + (f", {a['citation']}" if a.get("citation") else "")]
    if a.get("holding"):
        lines.append(f"- *Holding:* {a['holding']}")
    if a.get("quote"):
        pin = f" ({a['pin']})" if a.get("pin") else ""
        lines.append(f"- *Quote:* “{a['quote']}”{pin}")
    if a.get("use"):
        lines.append(f"- *Use:* {a['use']}")
    if not a.get("verified"):
        lines.append("- ⚠️ **UNVERIFIED — do not cite until checked.**")
    lines.append("")
    return lines


def render_insert(
    pb: dict,
    target: str,
    *,
    include_unverified: bool = False,
    as_of: Optional[date] = None,
) -> str:
    info = pb.get("targets", {}).get(target, {})
    title = info.get("title", "")
    out: List[str] = [
        f"# Draft argument insert — {target}" + (f": {title}" if title else ""),
        "",
        BANNER,
        "",
    ]
    meta = []
    if pb.get("case_number"):
        meta.append(f"Case No. {pb['case_number']}")
    if pb.get("judge"):
        meta.append(f"Presiding: {pb['judge']}")
    meta.append(f"Generated {(as_of or date.today()).isoformat()}")
    out += [" · ".join(meta), ""]
    if info.get("posture"):
        out += [f"**Posture:** {info['posture']}", ""]
    if info.get("ask"):
        out += [f"**Relief to request:** {info['ask']}", ""]
    if info.get("theme"):
        out += [f"**Theme:** {info['theme']}", ""]

    section = 1
    orders = pbk.orders_for(pb, target)
    if orders:
        out += [f"## {section}. The Court's own orders in this case", ""]
        for o in orders:
            head = f"**{o.get('ecf') or '(ECF ?)'}**" + (f" ({o['date']})" if o.get("date") else "") + (f" — {o['title']}" if o.get("title") else "")
            out.append(head)
            if o.get("excerpt"):
                label = "Verbatim" if o.get("verbatim") else "Docket text / summary"
                out.append(f"- *{label}:* “{o['excerpt']}”" if o.get("verbatim") else f"- *{label}:* {o['excerpt']}")
            if o.get("use"):
                out.append(f"- *Use:* {o['use']}")
            out.append("")
        section += 1

    used: List[dict] = []
    for kind in pbk.KINDS:
        items = pbk.select(pb, target=target, kinds=[kind], verified_only=not include_unverified)
        if not items:
            continue
        out += [f"## {section}. {pbk.KIND_LABELS[kind]}", ""]
        for a in items:
            out += _authority_block(a)
        used += items
        section += 1

    adverse = pbk.select(pb, target=target, verified_only=False, section="adverse")
    if adverse:
        out += [f"## {section}. Adverse authority to confront", ""]
        for a in adverse:
            out += _authority_block(a)
        section += 1

    if used:
        out += ["## Cite-check table", "", "| # | Authority | Kind | Verified | How verified | Source |", "|---|---|---|---|---|---|"]
        for i, a in enumerate(used, 1):
            cite = f"{a.get('case_name', '')}, {a.get('citation', '')}".replace("|", "\\|")
            how = (a.get("verification") or "").replace("|", "\\|").replace("\n", " ")
            src = a.get("source_url") or ""
            out.append(f"| {i} | {cite} | {a.get('kind', '')} | {'yes' if a.get('verified') else 'NO'} | {how} | {src} |")
        out.append("")

    if not include_unverified:
        skipped = [a for a in pb.get("authorities", []) if target in (a.get("targets") or []) and not a.get("verified")]
        if skipped:
            out += ["## Excluded — unverified (do not cite)", ""]
            out += [f"- {a.get('case_name', '')}, {a.get('citation', '')}" for a in skipped]
            out.append("")

    if not orders and not used:
        out += ["_No verified material is mapped to this target yet._", ""]
    return "\n".join(out)
