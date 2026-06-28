"""Command-line interface for the Accountability Content Engine (Phase 1).

Usage examples:
    python -m accountability_engine extract
    python -m accountability_engine extract --dry-run
    python -m accountability_engine extract --case-dir ./case_files
    python -m accountability_engine list-pending

Designed for a non-expert: clear output, sensible errors, a --dry-run mode.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import Config, load_config
from .extraction import ContradictionUnit
from .pipeline import run_phase1


def _eprint(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def _print_units(units: List[ContradictionUnit]) -> None:
    if not units:
        print("\nNo contradiction units found.")
        print(
            "Tip: Phase 1 looks for contradictory dollar amounts, reversed "
            "court orders, and affirm-vs-negate pairs that share wording.\n"
            "If you expected hits, check that your documents are in the "
            "case-files folder and are PDF/DOCX/TXT."
        )
        return

    print(f"\nFound {len(units)} candidate contradiction unit(s):\n")
    for i, unit in enumerate(units, start=1):
        print(f"  [{i}] {unit.kind}  (confidence {unit.confidence})  topic: {unit.topic}")
        print(f"      CLAIM   : {_short(unit.claim)}")
        print(f"        └─ {unit.source_A.cite()}")
        print(f"      COUNTER : {_short(unit.counter)}")
        print(f"        └─ {unit.source_B.cite()}")
        print()


def _short(text: str, width: int = 100) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def cmd_extract(args: argparse.Namespace, config: Config) -> int:
    case_dir = config.path("case_files")
    print(f"Reading case files from: {case_dir}")

    try:
        result = run_phase1(config, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        _eprint(f"\nError: {exc}")
        return 2

    print(f"Loaded {len(result.documents)} document(s):")
    for doc in result.documents:
        date = doc.doc_date.isoformat() if doc.doc_date else "unknown date"
        print(f"  - {doc.name}  ({len(doc.pages)} page(s), {date})")

    _print_units(result.units)

    if not result.units:
        return 0

    if args.dry_run:
        print("DRY RUN — no files written. Drafts that WOULD be created:\n")
        for ordinal, draft in enumerate(result.drafts, start=1):
            from .drafting import draft_filename
            print(f"  - {draft_filename(draft, ordinal)}  ({draft.word_count} words)")
        print(
            "\nRe-run without --dry-run to write these to the review queue:\n"
            f"  {config.path('pending_review')}"
        )
        return 0

    print(f"Wrote {len(result.written)} draft(s) to the review queue:")
    for path in result.written:
        print(f"  - {path}")

    print(
        "\n" + "=" * 70 + "\n"
        "HUMAN APPROVAL REQUIRED.\n"
        "Nothing has been published. Review each draft in:\n"
        f"  {config.path('pending_review')}\n"
        "Verify every source. To approve, move the file to:\n"
        f"  {config.path('approved')}\n"
        "Posting is Phase 3 and is intentionally not built yet.\n"
        + "=" * 70
    )
    return 0


def cmd_list_pending(args: argparse.Namespace, config: Config) -> int:
    pending = config.path("pending_review")
    if not pending.exists():
        print(f"No review queue yet: {pending}")
        return 0
    drafts = sorted(pending.glob("*.md"))
    if not drafts:
        print(f"Review queue is empty: {pending}")
        return 0
    print(f"{len(drafts)} draft(s) awaiting review in {pending}:")
    for path in drafts:
        print(f"  - {path.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accountability_engine",
        description=(
            "Accountability Content Engine — Phase 1 (Case-to-Script). "
            "Drafts source-cited scripts from documented contradictions. "
            "A human must review and approve every draft before anything is "
            "published."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to config.yaml (default: ./config.yaml).",
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Project root for resolving relative paths (default: cwd).",
    )

    sub = parser.add_subparsers(dest="command")

    p_extract = sub.add_parser(
        "extract",
        help="Read case files, extract contradictions, draft scripts to the review queue.",
    )
    p_extract.add_argument(
        "--case-dir", type=Path, default=None,
        help="Override the case-files folder for this run.",
    )
    p_extract.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be produced without writing any files.",
    )
    p_extract.set_defaults(func=cmd_extract)

    p_list = sub.add_parser("list-pending", help="List drafts awaiting human review.")
    p_list.set_defaults(func=cmd_list_pending)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    try:
        config = load_config(config_path=args.config, root=args.root)
    except Exception as exc:
        _eprint(f"Error loading configuration: {exc}")
        return 2

    # Per-command path overrides.
    if getattr(args, "case_dir", None):
        config._data.setdefault("paths", {})["case_files"] = str(args.case_dir)

    return args.func(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
