# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`gigi` is a standard-library-only Python CLI for S.D. Tex. litigation. It handles:
- docket analysis
- FRCP/Local Rule deadline computation
- judge-specific precedent research via CourtListener
- a citation-verified "playbook" that renders into brief inserts, an `.ics` calendar, and an HTML dashboard

See README.md for user-facing usage.

## Commands

- Run all tests: `python -m unittest discover -s tests -t .`
- Run one test: `python -m unittest tests.test_deadlines.SubmissionDayTests.test_matches_clerk_dates`
- The suite must pass on Python 3.9 (the minimum in pyproject). Avoid 3.10+-only APIs, e.g. `Path.write_text(newline=...)`.
- Run the CLI without installing: `python -m gigi --help`. Or `pip install -e .`, then `gigi --help`.
- Smoke test on the fictional sample: `python -m gigi build examples/sample-case --as-of 2026-03-25`

There is no linter configured. Match the surrounding style: type hints, dataclasses, short docstrings that explain the legal rule being implemented.

## Architecture

### Data flow

`cli.py` → `casefile.load_case(dir)` → `Case(cfg, docket, playbook)`.

`casefile.load_case` reads `case.json`. It loads `docket.json` via `docket.load`, which auto-detects three formats: DocketBird `{"documents": [...]}`, CourtListener v4 `{"results": [...]}`, or Gigi's normalized `{"entries": [...]}`. It then applies `entry_overrides` and `manual_dispositions` from `case.json` and loads `playbook.json`.

### Modules

- **`holidays.py` → `deadlines.py`.** FRCP 6(a) counting with roll-forward (roll-backward for backward periods), the FRCP 6(d) +3 days, LR 7.3's 21-day submission day, LR 7.4(E) replies, and post-judgment clocks. `extra` (court closures) counts in both directions; `state` (FRCP 6(a)(6)(C)) counts only going forward. Every function returns explanatory notes alongside dates. Keep that property: attorneys must be able to audit the arithmetic.
- **`docket.py`.**
  - `classify()` assigns each entry a kind from CM/ECF text. Order of checks matters: mail-returned, then settings, minutes, transcripts, orders, responses/replies, support filings, motions.
  - `Docket.dispositions()` parses explicit "<verb> [51]" rulings (or bare numbers directly followed by a motion word) and merges `manual_dispositions`. There is intentionally no looser matching: a false "ruled" hides a live motion, which is the dangerous direction.
  - `pending_motions(as_of)` is "motions with no ruling found as of that date", not a guarantee.
  - `hearing_settings()` tracks each setting's status: scheduled, held, superseded (by a reset), or cancelled. Only `scheduled` settings reach calendars.
  - Kinds are re-derived from text on every load, so stored `kind` values never go stale.
- **`courtlistener.py`.** REST v4 search client with an injectable opener (tests never touch the network). `ISSUES` holds reusable Lucene queries. For opinions (`type=o`) the judge filter is `judge`; for RECAP documents (`type=rd`) it is `assigned_to`.
- **`playbook.py`.**
  - Authority bank. `validate()` enforces the verification gate.
  - `merge()` dedupes on normalized citation. A verified copy replaces an unverified one, never the reverse.
  - `kind: "judge"` means the presiding judge's own decisions; the alias `"ellison"` maps to it.
- **`brief.py`, `ics.py`, `dashboard.py`.** Renderers. The brief excludes unverified authorities unless `include_unverified=True`. The dashboard is a single self-contained HTML file with light and dark themes.

## Conventions and guardrails

- **Never commit real case data.** `cases/`, `out/`, and `*.ics` are git-ignored. `tests/test_cli.py::RepoHygieneTests` asserts that. The repository is public. `examples/sample-case/` must stay fictional.
- **Never add an authority to a playbook as `verified: true` without having read its text.** Quotations must be verbatim, and the `verification` note must say how the authority was checked. Fabricated or unverified citations are a Rule 11 problem.
- **Tests use fixtures only.** Deadline tests cite real clerk-generated LR 7.3 dates (dates only, no case data).
- The default branch is `claude/add-claude-documentation-dGkHI`. Feature work goes on `claude/*` branches.
