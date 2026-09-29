"""Self-contained HTML case dashboard (no external assets; phone-friendly)."""

import re
from datetime import date
from html import escape
from typing import List

from gigi import __version__
from gigi import playbook as pbk
from gigi.casefile import Case, case_deadlines, extra_holidays, state_holidays

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--muted:#5f6368;--line:#e3e3df;--accent:#1f4e79;
--urgent:#b3261e;--urgent-bg:#fdecea;--warn:#8a5a00;--warn-bg:#fff4dc;--ok:#1e6b3a;--ok-bg:#e7f5ec;--chip:#eef2f7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121416;--card:#1b1e21;--ink:#e8eaed;
--muted:#a0a6ad;--line:#2c3136;--accent:#8ab4f8;--urgent:#f28b82;--urgent-bg:#3a1f1d;--warn:#fdd663;--warn-bg:#3a3217;
--ok:#81c995;--ok-bg:#1d3325;--chip:#243040}}
:root[data-theme="dark"]{--bg:#121416;--card:#1b1e21;--ink:#e8eaed;--muted:#a0a6ad;--line:#2c3136;--accent:#8ab4f8;
--urgent:#f28b82;--urgent-bg:#3a1f1d;--warn:#fdd663;--warn-bg:#3a3217;--ok:#81c995;--ok-bg:#1d3325;--chip:#243040}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:1.45rem;margin:0 0 4px;line-height:1.25}h2{font-size:1.08rem;margin:0 0 12px}
h3{font-size:.98rem;margin:0 0 6px}.sub{color:var(--muted);font-size:.9rem}
.banner{margin:14px 0;padding:10px 12px;border-radius:10px;background:var(--warn-bg);color:var(--warn);font-size:.85rem;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}
.alert{border-radius:10px;padding:10px 12px;margin:8px 0;font-size:.92rem}
.alert.urgent{background:var(--urgent-bg);color:var(--urgent)}.alert.warn{background:var(--warn-bg);color:var(--warn)}
.alert.info{background:var(--chip);color:var(--ink)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.stat b{display:block;font-size:1.5rem;line-height:1.2}.stat span{color:var(--muted);font-size:.82rem}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.scroll table{min-width:560px}
table{width:100%;border-collapse:collapse;font-size:.88rem}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}
td:first-child{white-space:nowrap}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--chip);font-size:.75rem;margin:1px 4px 1px 0;white-space:nowrap}
.chip.urgent{background:var(--urgent-bg);color:var(--urgent)}.chip.warn{background:var(--warn-bg);color:var(--warn)}
.chip.ok{background:var(--ok-bg);color:var(--ok)}
.due{white-space:nowrap;font-variant-numeric:tabular-nums}
details{border-top:1px solid var(--line);padding:8px 0}details:first-of-type{border-top:0}
summary{cursor:pointer;font-weight:600}summary::marker{color:var(--accent)}
.auth{margin:10px 0 0;padding-left:12px;border-left:3px solid var(--line)}
.auth p{margin:2px 0}.muted{color:var(--muted)}a{color:var(--accent)}
blockquote{margin:4px 0;padding:4px 10px;border-left:3px solid var(--accent);color:var(--ink);font-style:italic}
footer{color:var(--muted);font-size:.78rem;margin-top:24px}
"""


def _s(value) -> str:
    """Escape anything, including None and non-strings."""
    return escape("" if value is None else str(value))


def _href(url) -> str:
    """Only http(s) links are rendered clickable."""
    url = "" if url is None else str(url)
    return escape(url) if re.match(r"^https?://", url, re.IGNORECASE) else ""


def _urgency(days: int) -> str:
    if days <= 7:
        return "urgent"
    if days <= 21:
        return "warn"
    return "ok"


def render(case: Case, as_of: date, window_days: int = 90) -> str:
    cfg, docket, pb = case.cfg, case.docket, case.playbook
    e = _s
    deadlines = [d for d in case_deadlines(case, as_of) if d.days_from(as_of) <= window_days]
    pending = docket.pending_motions(as_of, extra_holidays(cfg), state_holidays(cfg))
    orders = docket.orders()
    hearings = docket.hearing_settings()
    st = pbk.stats(pb)
    parts: List[str] = []
    title = cfg.get("caption") or cfg.get("case_number") or "Case dashboard"
    sub = " · ".join(filter(None, [cfg.get("case_number"), cfg.get("court"), cfg.get("judge") and f"Judge {cfg['judge']}",
                                   f"as of {as_of.isoformat()}"]))
    parts.append(f"<header><h1>{e(title)}</h1><div class='sub'>{e(sub)}</div></header>")
    parts.append("<div class='banner'>Privileged &amp; confidential — attorney work product. Do not publish or forward.</div>")

    for alert in cfg.get("alerts", []):
        if isinstance(alert, str):
            alert = {"level": "info", "text": alert}
        level = alert.get("level") if alert.get("level") in ("urgent", "warn", "info") else "info"
        parts.append(f"<div class='alert {level}'>{e(alert.get('text'))}</div>")

    nxt = deadlines[0] if deadlines else None
    parts.append("<section class='stats'>")
    parts.append(f"<div class='stat'><b>{len(pending)}</b><span>motions with no ruling found</span></div>")
    if nxt:
        label = nxt.label if len(nxt.label) <= 60 else nxt.label[:59] + "…"
        parts.append(f"<div class='stat'><b>{nxt.days_from(as_of)}d</b><span>to next: {e(label)}</span></div>")
    parts.append(f"<div class='stat'><b>{len(orders)}</b><span>orders by the Court</span></div>")
    parts.append(f"<div class='stat'><b>{st['judge_verified']}</b><span>verified prior rulings by this judge</span></div>")
    parts.append(f"<div class='stat'><b>{st['verified']}</b><span>verified authorities total</span></div>")
    parts.append("</section>")

    rows = []
    for d in deadlines:
        days = d.days_from(as_of)
        rows.append(
            f"<tr><td class='due'>{e(d.due.strftime('%a %b %d, %Y'))}</td><td><span class='chip {_urgency(days)}'>{days}d</span></td>"
            f"<td>{e(d.label)}<div class='muted'>{e(' · '.join(filter(None, [d.rule, d.source])))}</div></td></tr>"
        )
    parts.append(
        f"<section class='card'><h2>Next {window_days} days</h2><div class='scroll'><table><thead><tr><th>Date</th><th>In</th>"
        f"<th>What</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=3>Nothing scheduled.</td></tr>'}</tbody></table></div></section>"
    )

    rows = []
    for r in pending:
        ent = r["entry"]
        flags = []
        if r["emergency"]:
            flags.append("<span class='chip urgent'>emergency</span>")
        if r["cjra_candidate"]:
            flags.append("<span class='chip warn'>CJRA 6-month list</span>")
        rows.append(
            f"<tr><td>{e(ent.label)}</td><td class='due'>{e(ent.date.isoformat() if ent.date else 'unknown')}</td>"
            f"<td class='due'>{e(r['submission_day'].isoformat() if r['submission_day'] else 'unknown')}</td>"
            f"<td>{e(str(r['age_days']) + 'd' if r['age_days'] is not None else '?')}</td><td>{e(ent.short(140))} {''.join(flags)}</td></tr>"
        )
    parts.append(
        "<section class='card'><h2>Motions with no ruling found in the docket text</h2>"
        "<p class='muted'>Heuristic: a bare “ORDER” entry may have resolved a motion without naming it. Confirm on PACER.</p>"
        f"<div class='scroll'><table><thead><tr><th>ECF</th><th>Filed</th><th>Submission</th><th>Age</th><th>Motion</th></tr></thead>"
        f"<tbody>{''.join(rows) or '<tr><td colspan=5>None.</td></tr>'}</tbody></table></div></section>"
    )

    if hearings:
        modes = {}
        for h in hearings:
            if h["status"] in ("held", "scheduled"):
                modes[h["mode"]] = modes.get(h["mode"], 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in sorted(modes.items()))
        status_chip = {"held": "ok", "scheduled": "warn", "superseded": "", "cancelled": ""}
        rows = "".join(
            f"<tr><td class='due'>{e(h['date'].isoformat() if h['date'] else '')}</td><td>{e(h['what'])}</td>"
            f"<td><span class='chip'>{e(h['mode'])}</span></td>"
            f"<td><span class='chip {status_chip.get(h['status'], '')}'>{e(h['status'])}</span>"
            f"{(' ' + e(h['changed_by'])) if h['changed_by'] else ''}</td><td>{e(h['entry'].label)}</td></tr>"
            for h in hearings
        )
        parts.append(
            f"<section class='card'><h2>Hearing settings (held or scheduled: {e(summary)})</h2><div class='scroll'><table><thead>"
            f"<tr><th>Date</th><th>Setting</th><th>Mode</th><th>Status</th><th>Source</th></tr></thead><tbody>{rows}</tbody>"
            f"</table></div></section>"
        )

    rows = "".join(
        f"<tr><td class='due'>{e(o.date.isoformat() if o.date else '')}</td><td>{e(o.label)}</td><td>{e(o.short(220))}</td></tr>"
        for o in reversed(orders)
    )
    parts.append(
        f"<section class='card'><h2>The Court's orders in this case</h2><div class='scroll'><table><thead><tr><th>Date</th>"
        f"<th>ECF</th><th>Docket text</th></tr></thead><tbody>{rows or '<tr><td colspan=3>None.</td></tr>'}</tbody></table></div></section>"
    )

    if pb.get("targets"):
        parts.append("<section class='card'><h2>Playbook — the Court's own words, by target</h2>")
        for tgt, info in pb["targets"].items():
            auths = pbk.select(pb, target=tgt)
            ords = pbk.orders_for(pb, tgt)
            parts.append(
                f"<details><summary>{e(tgt)} — {e((info or {}).get('title'))} "
                f"<span class='chip'>{len(ords)} in-case orders</span><span class='chip ok'>{len(auths)} verified</span></summary>"
            )
            if (info or {}).get("ask"):
                parts.append(f"<p><b>Ask:</b> {e(info['ask'])}</p>")
            for o in ords:
                quote = f"<blockquote>{e(o.get('excerpt'))}</blockquote>" if o.get("excerpt") and o.get("verbatim") else ""
                parts.append(f"<div class='auth'><p><b>{e(o.get('ecf'))}</b> {e(o.get('date'))} {e(o.get('title'))}</p>{quote}"
                             f"<p class='muted'>{e(o.get('use'))}</p></div>")
            for a in auths:
                href = _href(a.get("source_url"))
                link = f" <a href='{href}' rel='noopener noreferrer'>source</a>" if href else ""
                quote = f"<blockquote>{e(a.get('quote'))}</blockquote>" if a.get("quote") else ""
                parts.append(
                    f"<div class='auth'><p><span class='chip'>{e(pbk.KIND_LABELS.get(a.get('kind'), a.get('kind')))}</span>"
                    f"<b>{e(a.get('case_name'))}</b>, {e(a.get('citation'))}{link}</p>{quote}<p class='muted'>{e(a.get('use'))}</p></div>"
                )
            parts.append("</details>")
        parts.append("</section>")

    returned = docket.mail_returned()
    if returned:
        items = "".join(f"<li>{e(r.date.isoformat() if r.date else '')} — {e(r.label)}: {e(r.short(160))}</li>" for r in returned)
        parts.append(f"<section class='card'><h2>Mail returned undeliverable ({len(returned)})</h2>"
                     f"<p class='muted'>Service and notice problems. Consider these in any notice or prejudice argument.</p><ul>{items}</ul></section>")

    parts.append(f"<footer>Generated by gigi {e(__version__)} on {e(as_of.isoformat())}. Docket classification is heuristic; "
                 "deadlines must be confirmed against the rules and orders. Not legal advice.</footer>")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(cfg.get('case_number') or 'Case')} dashboard</title><style>{CSS}</style></head>"
        f"<body><main>{''.join(parts)}</main></body></html>\n"
    )
