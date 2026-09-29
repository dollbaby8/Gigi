"""Command-line interface: ``gigi <command> ...`` (or ``python -m gigi``)."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from gigi import __version__
from gigi import brief as brief_mod
from gigi import courtlistener as cl
from gigi import dashboard as dash
from gigi import docket as dk
from gigi import ics
from gigi import playbook as pbk
from gigi.casefile import case_deadlines, extra_holidays, init_case, load_case, state_holidays
from gigi.deadlines import compute, post_judgment, reply_day, submission_day


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}")


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text).strip("-").lower()


def _write(path, text: str, newline: Optional[str] = None) -> None:
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)


def _holidays(args):
    return tuple(args.holiday or ()), tuple(args.state_holiday or ())


def _print_deadline(label: str, due: date, notes: List[str]) -> None:
    print(f"{label}: {due.isoformat()} ({due.strftime('%A')})")
    for n in notes:
        print(f"  - {n}")


# ---- commands --------------------------------------------------------------
def cmd_deadline(args) -> int:
    extra, state = _holidays(args)
    due, notes = compute(args.start, args.days, mail_service=args.mail, backward=args.backward, extra=extra, state=state)
    _print_deadline("Deadline", due, notes)
    return 0


def cmd_submission(args) -> int:
    due, notes = submission_day(args.filed, *_holidays(args))
    _print_deadline("Submission / response day", due, notes)
    return 0


def cmd_reply(args) -> int:
    due, notes = reply_day(args.response_filed, *_holidays(args))
    _print_deadline("Reply due", due, notes)
    return 0


def cmd_post_judgment(args) -> int:
    extra, state = _holidays(args)
    for dl in post_judgment(args.entered, us_party=args.us_party, extra=extra, state=state):
        _print_deadline(f"{dl.label} [{dl.rule}]", dl.due, dl.notes)
    return 0


def cmd_init(args) -> int:
    existed = (Path(args.case_dir) / "case.json").exists()
    root = init_case(args.case_dir, case_number=args.case_number, caption=args.caption, judge=args.judge, court=args.court)
    if existed:
        print(f"Updated {root / 'case.json'} with the given fields; everything else was kept.")
    else:
        print(f"Initialized {root} (case.json, playbook.json). Add docket.json with `gigi import-docket`.")
    return 0


def cmd_import_docket(args) -> int:
    docket = dk.load(args.source)
    Path(args.case_dir).mkdir(parents=True, exist_ok=True)
    dk.save(docket, Path(args.case_dir) / "docket.json")
    print(f"Imported {len(docket.entries)} entries into {Path(args.case_dir) / 'docket.json'}")
    return 0


def cmd_docket(args) -> int:
    case = load_case(args.case_dir)
    d, as_of = case.docket, args.as_of
    if args.view == "orders":
        for e in d.orders():
            print(f"{e.label:>8}  {e.date}  {e.short(150)}")
    elif args.view == "motions":
        ruled = d.dispositions()
        for e in d.motions():
            status = "; ".join(
                r.get("ruling", "ruled") + (f" (ECF {r['order']})" if r.get("order") else "")
                for r in ruled.get(e.number, [])
            ) or "NO RULING FOUND"
            print(f"{e.label:>8}  {e.date}  [{status}]  {e.short(110)}")
    elif args.view == "pending":
        rows = d.pending_motions(as_of, extra_holidays(case.cfg), state_holidays(case.cfg))
        for r in rows:
            e = r["entry"]
            flags = (" EMERGENCY" if r["emergency"] else "") + (" CJRA-6mo" if r["cjra_candidate"] else "")
            age = f"{r['age_days']:>3}d" if r["age_days"] is not None else "  ?d"
            print(f"{e.label:>8}  filed {e.date or 'unknown'}  submission {r['submission_day'] or 'unknown'}  "
                  f"age {age}{flags}  {e.short(90)}")
        print(f"\n{len(rows)} motion(s) with no ruling found in docket text as of {as_of}. Confirm on PACER.")
    elif args.view == "hearings":
        for h in d.hearing_settings():
            changed = f" by {h['changed_by']}" if h["changed_by"] else ""
            print(f"{h['date']}  {h['time']:>8}  {h['mode']:<9}  {h['status'] + changed:<22}  {h['what']}  ({h['entry'].label})")
    elif args.view == "mail":
        for e in d.mail_returned():
            print(f"{e.label:>8}  {e.date}  {e.short(150)}")
    else:
        for e in d.entries:
            print(f"{e.label:>8}  {e.date}  {e.kind:<13} {e.short(120)}")
    return 0


def cmd_deadlines(args) -> int:
    case = load_case(args.case_dir)
    items = [d for d in case_deadlines(case, args.as_of) if d.days_from(args.as_of) <= args.window]
    for d in items:
        print(f"{d.due.isoformat()}  {d.days_from(args.as_of):>4}d  {d.kind:<10} {d.label}  [{d.rule or d.source}]")
    if args.ics:
        name = f"{case.cfg.get('case_number') or 'Case'} deadlines"
        _write(args.ics, ics.to_ics(case_deadlines(case, args.as_of), name), newline="")
        print(f"\nWrote calendar: {args.ics}")
    return 0


def cmd_issues(args) -> int:
    for key, spec in cl.ISSUES.items():
        print(f"{key:<26} {spec['title']}")
    return 0


def cmd_research(args) -> int:
    if not args.q and not args.issue:
        print("Provide --q QUERY or --issue KEY (see `gigi issues`).", file=sys.stderr)
        return 2
    if args.issue and args.issue not in cl.ISSUES:
        print(f"Unknown issue {args.issue!r}. Run `gigi issues`.", file=sys.stderr)
        return 2
    q = args.q or cl.ISSUES[args.issue]["q"]
    client = cl.CourtListener()
    try:
        hits = client.search(q, kind=args.type, court=args.court, judge=args.judge, filed_after=args.after,
                             filed_before=args.before, limit=args.limit)
    except cl.CourtListenerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    title = f"{args.judge or 'All judges'} — {cl.ISSUES[args.issue]['title'] if args.issue else q}"
    text = json.dumps(hits, indent=1) if (args.out or "").endswith(".json") else cl.to_markdown(hits, title)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote {len(hits)} result(s) to {args.out}")
    else:
        print(text)
    return 0


def cmd_playbook(args) -> int:
    case = load_case(args.case_dir)
    pb = case.playbook
    problems = pbk.validate(pb)
    if args.check:
        for p in problems:
            print(f"PROBLEM: {p}")
        print(f"{len(problems)} problem(s).")
        return 1 if problems else 0
    st = pbk.stats(pb)
    print(f"Authorities: {st['total']} ({st['verified']} verified; {st['judge_verified']} verified rulings by the presiding judge); "
          f"adverse: {st['adverse']}; in-case orders: {st['in_case_orders']}; unverified leads: {st['unverified_leads']}")
    targets = [args.target] if args.target else list(pb.get("targets", {}))
    for t in targets:
        info = pb.get("targets", {}).get(t, {})
        print(f"\n== {t}: {info.get('title', '')}")
        for o in pbk.orders_for(pb, t):
            print(f"  [order] {o.get('ecf', '?')} {o.get('date') or ''}: {o.get('use', '')}")
        for a in pbk.select(pb, target=t, verified_only=not args.all):
            flag = "" if a.get("verified") else " (UNVERIFIED)"
            print(f"  [{a.get('kind', '?')}] {a.get('case_name', '?')}, {a.get('citation', '')}{flag}")
    if problems:
        print(f"\n{len(problems)} validation problem(s); run with --check to list them.")
    return 0


def cmd_merge(args) -> int:
    case = load_case(args.case_dir)
    research = json.loads(Path(args.research).read_text(encoding="utf-8"))
    if isinstance(research, list):
        # `gigi research --out x.json` writes raw search hits: import them as unverified leads only.
        research = {"unverified_leads": [
            {"case_name": h.get("case_name") or "(untitled)", "why": "CourtListener search hit; read and verify",
             "url": h.get("url")} for h in research if isinstance(h, dict)
        ]}
        print("Search results are leads, not authorities: imported as unverified_leads.")
    counts = pbk.merge(case.playbook, research, issue=args.issue)
    pbk.save(case.playbook, Path(args.case_dir) / "playbook.json")
    print(f"Merged {args.research}: {counts}")
    return 0


def cmd_brief(args) -> int:
    case = load_case(args.case_dir)
    text = brief_mod.render_insert(case.playbook, args.target, include_unverified=args.include_unverified, as_of=args.as_of)
    out = Path(args.out) if args.out else case.out_dir / f"brief_{_slug(args.target)}.md"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_dashboard(args) -> int:
    case = load_case(args.case_dir)
    out = Path(args.out) if args.out else case.out_dir / "dashboard.html"
    out.write_text(dash.render(case, args.as_of, args.window), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_build(args) -> int:
    """Regenerate every output for a case: briefs, calendar, dashboard."""
    case = load_case(args.case_dir)
    outd = case.out_dir
    for t in case.playbook.get("targets", {}):
        (outd / f"brief_{_slug(t)}.md").write_text(brief_mod.render_insert(case.playbook, t, as_of=args.as_of), encoding="utf-8")
    name = f"{case.cfg.get('case_number') or 'Case'} deadlines"
    _write(outd / "deadlines.ics", ics.to_ics(case_deadlines(case, args.as_of), name), newline="")
    (outd / "dashboard.html").write_text(dash.render(case, args.as_of, args.window), encoding="utf-8")
    problems = pbk.validate(case.playbook)
    print(f"Built {outd}: {len(case.playbook.get('targets', {}))} brief insert(s), deadlines.ics, dashboard.html")
    if problems:
        print(f"Playbook has {len(problems)} validation problem(s); run `gigi playbook {args.case_dir} --check`.")
    return 0


def _holiday_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--holiday", type=_date, action="append", metavar="YYYY-MM-DD",
                        help="court-declared holiday or clerk's-office closure (repeatable; both directions)")
    parser.add_argument("--state-holiday", type=_date, action="append", metavar="YYYY-MM-DD",
                        help="state-declared holiday, FRCP 6(a)(6)(C) (repeatable; forward periods only)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gigi", description="S.D. Tex. litigation assistant.")
    p.add_argument("--version", action="version", version=f"gigi {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    today = date.today()

    s = sub.add_parser("deadline", help="FRCP 6 computation from a trigger date")
    s.add_argument("--from", dest="start", type=_date, required=True)
    s.add_argument("--days", type=int, required=True)
    s.add_argument("--mail", action="store_true", help="add 3 days under FRCP 6(d)")
    s.add_argument("--backward", action="store_true", help="count backward from the trigger")
    _holiday_flags(s)
    s.set_defaults(func=cmd_deadline)

    s = sub.add_parser("submission", help="S.D. Tex. LR 7.3 submission/response day for a motion")
    s.add_argument("--filed", type=_date, required=True)
    _holiday_flags(s)
    s.set_defaults(func=cmd_submission)

    s = sub.add_parser("reply", help="S.D. Tex. LR 7.4(E) reply deadline from the response filing date")
    s.add_argument("--response-filed", type=_date, required=True)
    _holiday_flags(s)
    s.set_defaults(func=cmd_reply)

    s = sub.add_parser("post-judgment", help="Rule 59/60/54(d) and FRAP 4 deadlines from entry of judgment")
    s.add_argument("--entered", type=_date, required=True)
    s.add_argument("--us-party", action="store_true", help="United States is a party (60-day appeal time)")
    _holiday_flags(s)
    s.set_defaults(func=cmd_post_judgment)

    s = sub.add_parser("init", help="scaffold a case directory")
    s.add_argument("case_dir")
    s.add_argument("--case-number")
    s.add_argument("--caption")
    s.add_argument("--judge")
    s.add_argument("--court", default="S.D. Tex.")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("import-docket", help="normalize a DocketBird/CourtListener docket export into a case dir")
    s.add_argument("source")
    s.add_argument("case_dir")
    s.set_defaults(func=cmd_import_docket)

    s = sub.add_parser("docket", help="analyze the docket")
    s.add_argument("case_dir")
    s.add_argument("view", nargs="?", default="all", choices=["all", "orders", "motions", "pending", "hearings", "mail"])
    s.add_argument("--as-of", type=_date, default=today)
    s.set_defaults(func=cmd_docket)

    s = sub.add_parser("deadlines", help="upcoming deadlines, submission days, and hearings")
    s.add_argument("case_dir")
    s.add_argument("--as-of", type=_date, default=today)
    s.add_argument("--window", type=int, default=120, help="days ahead to list")
    s.add_argument("--ics", help="also write an .ics calendar to this path")
    s.set_defaults(func=cmd_deadlines)

    s = sub.add_parser("issues", help="list research issue presets")
    s.set_defaults(func=cmd_issues)

    s = sub.add_parser("research", help="search a judge's opinions/orders on CourtListener")
    s.add_argument("--judge", help="e.g. 'Keith P. Ellison'")
    s.add_argument("--court", default="txsd")
    s.add_argument("--issue", help="preset key from `gigi issues`")
    s.add_argument("--q", help="raw CourtListener query (overrides --issue)")
    s.add_argument("--type", default="o", choices=["o", "rd"], help="o=opinions, rd=RECAP documents (orders)")
    s.add_argument("--after")
    s.add_argument("--before")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--out", help=".md or .json output path")
    s.set_defaults(func=cmd_research)

    s = sub.add_parser("playbook", help="summarize or validate a case playbook")
    s.add_argument("case_dir")
    s.add_argument("--target")
    s.add_argument("--all", action="store_true", help="include unverified authorities")
    s.add_argument("--check", action="store_true", help="validate and exit non-zero on problems")
    s.set_defaults(func=cmd_playbook)

    s = sub.add_parser("merge", help="merge a research JSON file into the case playbook")
    s.add_argument("case_dir")
    s.add_argument("research")
    s.add_argument("--issue")
    s.set_defaults(func=cmd_merge)

    s = sub.add_parser("brief", help="render a brief-ready Markdown insert for a target")
    s.add_argument("case_dir")
    s.add_argument("--target", required=True, help="e.g. 'ECF 200'")
    s.add_argument("--out")
    s.add_argument("--include-unverified", action="store_true")
    s.add_argument("--as-of", type=_date, default=today)
    s.set_defaults(func=cmd_brief)

    s = sub.add_parser("dashboard", help="write a self-contained HTML dashboard")
    s.add_argument("case_dir")
    s.add_argument("--out")
    s.add_argument("--as-of", type=_date, default=today)
    s.add_argument("--window", type=int, default=120)
    s.set_defaults(func=cmd_dashboard)

    s = sub.add_parser("build", help="regenerate all briefs, the calendar, and the dashboard")
    s.add_argument("case_dir")
    s.add_argument("--as-of", type=_date, default=today)
    s.add_argument("--window", type=int, default=120)
    s.set_defaults(func=cmd_build)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
