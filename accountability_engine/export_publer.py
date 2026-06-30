"""Export approved drafts into a Publer-ready bulk-upload CSV.

Reads the posting calendar (which slot -> which draft file + which section) and
pulls the actual post text out of each Markdown draft, emitting one row per
scheduled post. Only the platforms you pass in are included, so you can export
just the accounts you've connected so far (e.g. TikTok + LinkedIn) and add the
rest later.

This is the first reusable piece of the app: drafts in -> a file you import into
Publer once. It does NOT post anything.

Usage:
    python -m accountability_engine.export_publer \
        --calendar drafts/pending_review/posting_calendar.csv \
        --drafts-dir drafts/pending_review \
        --out drafts/pending_review/publer_bulk.csv \
        --platforms tiktok linkedin
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional

# Map the calendar's platform labels to a simple canonical name + the Publer
# account type a non-expert will recognise.
_PLATFORM_CANON = {
    "tiktok/reels/shorts": "tiktok",
    "tiktok": "tiktok",
    "linkedin/substack": "linkedin",
    "linkedin": "linkedin",
    "x": "x",
    "instagram": "instagram",
    "instagram_reels": "instagram",
    "youtube/shorts": "youtube",
}

# Map the calendar's "Section" value to the heading used inside the draft files.
_SECTION_KEYWORDS = {
    "short video caption": "short video",
    "x thread": "x thread",
    "substack / linkedin": "substack / linkedin",
    "longform": "substack / linkedin",
}


def canon_platform(label: str) -> str:
    return _PLATFORM_CANON.get(label.strip().lower(), label.strip().lower())


def extract_section(markdown: str, section_label: str) -> Optional[str]:
    """Return the body text of the draft section matching ``section_label``."""
    keyword = _SECTION_KEYWORDS.get(section_label.strip().lower())
    if keyword is None:
        keyword = section_label.strip().lower()

    lines = markdown.splitlines()
    capture: List[str] = []
    capturing = False
    for line in lines:
        if line.startswith("## "):
            if capturing:
                break  # reached the next section
            if keyword in line.lower():
                capturing = True
            continue
        if capturing:
            capture.append(line)

    if not capture:
        return None

    text = "\n".join(capture).strip()
    # Trim a trailing horizontal rule that precedes the Sources block.
    text = re.sub(r"\n-{3,}\s*$", "", text).strip()
    return text or None


def find_draft_file(drafts_dir: Path, source_file: str) -> Optional[Path]:
    """Find the draft markdown for a calendar Source_File stem (date-prefixed)."""
    exact = drafts_dir / f"{source_file}.md"
    if exact.exists():
        return exact
    matches = sorted(drafts_dir.glob(f"*{source_file}.md"))
    return matches[0] if matches else None


def build_rows(calendar_csv: Path, drafts_dir: Path,
               platforms: List[str]) -> List[Dict[str, str]]:
    wanted = {canon_platform(p) for p in platforms}
    rows: List[Dict[str, str]] = []
    skipped: List[str] = []

    with calendar_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            platform = canon_platform(row.get("Platform", ""))
            if platform not in wanted:
                continue
            draft = find_draft_file(drafts_dir, row.get("Source_File", "").strip())
            if not draft:
                skipped.append(f"{row.get('Source_File')} (file not found)")
                continue
            content = extract_section(draft.read_text(encoding="utf-8"),
                                      row.get("Section", ""))
            if not content:
                skipped.append(f"{draft.name} / {row.get('Section')} (section not found)")
                continue
            rows.append({
                "Platform": platform,
                "Date": row.get("Date", "").strip(),
                "Time": row.get("Time", "").strip(),
                "Content": content,
            })

    if skipped:
        print("Skipped (review manually):")
        for s in skipped:
            print(f"  - {s}")
    return rows


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Platform", "Date", "Time", "Content"])
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export approved drafts to a Publer bulk CSV.")
    parser.add_argument("--calendar", type=Path,
                        default=Path("drafts/pending_review/posting_calendar.csv"))
    parser.add_argument("--drafts-dir", type=Path,
                        default=Path("drafts/pending_review"))
    parser.add_argument("--out", type=Path,
                        default=Path("drafts/pending_review/publer_bulk.csv"))
    parser.add_argument("--platforms", nargs="+", default=["tiktok", "linkedin"],
                        help="Which connected platforms to include (default: tiktok linkedin).")
    args = parser.parse_args(argv)

    rows = build_rows(args.calendar, args.drafts_dir, args.platforms)
    if not rows:
        print("No matching scheduled posts found for platforms:", args.platforms)
        return 1
    write_csv(rows, args.out)
    print(f"\nWrote {len(rows)} post(s) to {args.out}")
    for r in rows:
        preview = " ".join(r["Content"].split())[:70]
        print(f"  - {r['Date']} {r['Time']}  {r['Platform']:9}  {preview}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
