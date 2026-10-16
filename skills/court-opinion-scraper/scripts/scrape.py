#!/usr/bin/env python3
"""Pull recent court opinions with Free Law Project's juriscraper.

Examples:
  python scrape.py --list texas
  python scrape.py tex texapp ca5 --keyword retaliation --days 30
  python scrape.py ca5 --json
"""

import argparse
import asyncio
import importlib
import json
import os
import pkgutil
import subprocess
import sys
from datetime import date, datetime, timedelta

os.environ.setdefault("JURISCRAPER_LOG", os.devnull)

# Friendly aliases for the courts this practice uses most.
ALIASES = {
    "tex": "state.tex",  # Supreme Court of Texas
    "texapp": "state.texapp",  # Texas Courts of Appeals (all 15)
    "texcrimapp": "state.texcrimapp",  # Texas Court of Criminal Appeals
    "texbizct": "state.texbizct",  # Texas Business Court
    "texag": "state.texag",  # Texas Attorney General opinions
    "ca5": "federal_appellate.ca5",  # Fifth Circuit
    "scotus": "federal_appellate.scotus_slip",  # U.S. Supreme Court slip opinions
}
BASE = "juriscraper.opinions.united_states"
FIELDS = [
    "case_dates", "case_names", "docket_numbers", "precedential_statuses",
    "judges", "lower_courts", "summaries", "download_urls",
]


def ensure_juriscraper():
    try:
        import juriscraper  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "juriscraper"]
        )


def list_courts(term):
    pkg = importlib.import_module(BASE)
    out = []
    for info in pkgutil.walk_packages(pkg.__path__, BASE + "."):
        if info.ispkg:
            continue
        short = info.name[len(BASE) + 1:]
        if term.lower() in short.lower():
            out.append(short)
    alias_of = {v: k for k, v in ALIASES.items()}
    for s in sorted(out):
        tag = f"  (alias: {alias_of[s]})" if s in alias_of else ""
        print(s + tag)


async def scrape(court, mock_file=None):
    module = importlib.import_module(f"{BASE}.{ALIASES.get(court, court)}")
    site = module.Site()
    if mock_file:
        site.enable_test_mode()
        site.mock_url = mock_file
    await site.parse()
    rows = []
    for case in site:
        row = {"court": court}
        for f in FIELDS:
            v = case.get(f)
            if isinstance(v, (date, datetime)):
                v = v.isoformat()
            if v not in (None, ""):
                row[f.rstrip("s") if f != "precedential_statuses" else "status"] = v
        rows.append(row)
    return rows


def keep(row, keyword, since):
    if since and row.get("case_date") and row["case_date"][:10] < since:
        return False
    if keyword:
        hay = " ".join(str(v) for v in row.values()).lower()
        return any(k.strip().lower() in hay for k in keyword.split(","))
    return True


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("courts", nargs="*", help="Court aliases or module paths")
    p.add_argument("--list", metavar="TERM", help="List scrapers matching TERM")
    p.add_argument("--keyword", help="Comma-separated terms (OR match on name/summary/docket)")
    p.add_argument("--days", type=int, help="Only opinions from the last N days")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    p.add_argument("--mock", help="Parse a saved HTML/JSON page instead of the live site")
    a = p.parse_args()

    ensure_juriscraper()
    if a.list is not None:
        list_courts(a.list)
        return
    if not a.courts:
        p.error("name at least one court, or use --list")

    since = (date.today() - timedelta(days=a.days)).isoformat() if a.days else None
    results, errors = [], {}
    for court in a.courts:
        try:
            rows = await scrape(court, a.mock)
            results += [r for r in rows if keep(r, a.keyword, since)]
        except Exception as e:  # report and keep going with the other courts
            errors[court] = f"{type(e).__name__}: {e}"
    results.sort(key=lambda r: r.get("case_date", ""), reverse=True)

    if a.json:
        print(json.dumps({"results": results, "errors": errors}, indent=2))
        return
    for r in results:
        print(f"{r.get('case_date', '')[:10]}  [{r['court']}]  {r.get('case_name', '')}")
        print(f"    No. {r.get('docket_number', '-')}  |  {r.get('status', '')}")
        if r.get("lower_court"):
            print(f"    From: {r['lower_court']}")
        print(f"    {r.get('download_url', '')}")
    print(f"\n{len(results)} opinion(s).")
    for court, err in errors.items():
        print(f"ERROR {court}: {err}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
