# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this project is

The **Accountability Content Engine** — a local Python tool that turns
documented contradictions in litigation case files into neutral, source-cited
social-media script drafts, routed through a **mandatory human-approval gate**.
See `README.md` for the full product brief.

**Phase 1 (Case-to-Script) is implemented.** Phases 2 (formatting) and 3
(scheduling/posting) are intentionally not built yet and are gated on Phase 1
output being approved.

## Non-negotiable design rules (do not route around these)

1. **Human-approval gate is mandatory.** The code DRAFTS only. Drafts go to
   `./drafts/pending_review/`; a human approves by moving a file to
   `./drafts/approved/`. There is no auto-posting anywhere in this project, and
   none must be added without an explicit, reviewed approval step.
2. **Every claim is sourced.** Each contradiction unit and every draft carries
   the exact source document + page + line. Never emit an assertion that isn't
   tied to a source in the case files.
3. **ToS-compliant, human cadence** (Phase 3): official APIs/schedulers only,
   capped per `config.yaml`. No bots, fake engagement, or scraping.
4. **Neutral, factual tone.** State what the record says. No speculation.

## Commands

```bash
pip install -r requirements.txt          # PyYAML/pypdf/python-docx (Phase 1 TXT needs none)
python -m accountability_engine extract --dry-run   # show units + drafts, write nothing
python -m accountability_engine extract             # write drafts to the review queue
python -m accountability_engine list-pending        # list drafts awaiting review
python -m pytest                                     # run the test suite
python -m pytest tests/test_extraction.py::test_monetary_contradiction_detected  # single test
```

## Architecture (cross-file data flow)

The pipeline is a straight line, one module per stage:

```
case_files/ ──documents.py──▶ Document/Page ──extraction.py──▶ ContradictionUnit
   (PDF/DOCX/TXT)              (page-tracked)   (3 rule-based      (claim + counter,
                                                 detectors)         each sourced)
        │                                                              │
        └────────────── pipeline.run_phase1() orchestrates ───────────┘
                                     │
                          drafting.py ──▶ Draft ──▶ Markdown (YAML header)
                                     │
                          drafts/pending_review/   ← STOP. Human reviews.
```

- `config.py` — loads `config.yaml` over complete in-code `DEFAULTS` (deep
  merge) and reads `.env`. The tool runs fully on defaults with no config file.
  Access via the `Config` object's typed properties.
- `documents.py` — `load_documents()` returns `Document`s made of `Page`s.
  pypdf / python-docx are imported lazily so a TXT-only run needs no deps.
  Document dates come from a `YYYY-MM-DD` in the filename, else file mtime.
- `extraction.py` — `extract_contradictions()` segments documents into
  sentences (splitting on punctuation *and* blank lines), then runs three
  detectors over **cross-document** sentence pairs that share enough significant
  words: `monetary`, `status_reversal`, `negation`. Results are ranked by
  confidence and de-duplicated so no source sentence is reused.
- `drafting.py` — `draft_script()` renders a unit via a configurable voice
  template; `render_markdown()` emits the YAML-header Markdown; `write_draft()`
  writes it to the pending-review queue.
- `pipeline.py` / `cli.py` — orchestration and the CLI (`extract` supports
  `--dry-run`; `list-pending` inspects the queue).

## Conventions

- Minimal dependencies; secrets only in `.env` (git-ignored), never hardcoded.
- Detector tuning (overlap thresholds, dollar-ratio, reversal verb groups,
  negation cues) lives in `config.yaml` / `config.py` `DEFAULTS`, not in code
  branches — change behavior there.
- The `case_files/` samples are clearly-labeled fiction for the demo.
- Built for a non-expert: clear CLI output, a `--dry-run` mode, friendly errors.

## Working branch

Development happens on `claude/accountability-engine-phase-1-k6ugmu`. Commit and
push work to that branch.
