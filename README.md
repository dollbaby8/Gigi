# Accountability Content Engine

A local Python tool that turns **documented contradictions in case files** into
**neutral, source-cited social-media script drafts** for a public-accountability
campaign tied to active litigation.

It does **not** post anything. It drafts. A human reviews and approves every
draft before anything could ever be published.

> **Status: Phase 1 (Case-to-Script) is built.** Phases 2 (formatting) and 3
> (scheduling/posting) are intentionally not built yet — see the roadmap below.

---

## The four rules this tool is built around

1. **Human-approval gate is mandatory.** The engine drafts; a person reviews and
   approves. Nothing is ever posted automatically. Drafts land in
   `./drafts/pending_review/`. *You* approve a draft by moving its file to
   `./drafts/approved/`. There is no auto-posting code in this project.
2. **Sourcing required on every claim.** Every drafted statement cites the exact
   source document and page/line it came from. If a claim can't be tied to a
   source, the tool doesn't assert it. Each draft carries a `sources` block.
3. **ToS-compliant cadence.** When posting is added (Phase 3), only official
   platform APIs / approved schedulers will be used, capped at a human cadence
   (configurable in `config.yaml`). No bots, no fake engagement, no scraping.
4. **Neutral, factual tone.** Drafts state what the record says and let it land.
   No name-calling, no speculation, no accusations beyond the documents.

---

## Quick start

You need **Python 3.9+**. Phase 1 works on `.txt` files with **no extra
packages at all**. PDF/DOCX support and `config.yaml` need a couple of small
libraries.

```bash
# 1. (Optional but recommended) install dependencies
pip install -r requirements.txt

# 2. Put your source documents in ./case_files/  (PDF, DOCX, or TXT)
#    Sample documents are already there so you can try it immediately.

# 3. See what the tool would produce — writes nothing:
python -m accountability_engine extract --dry-run

# 4. Generate drafts into the review queue:
python -m accountability_engine extract

# 5. Review the drafts a human must approve:
python -m accountability_engine list-pending
```

Then open each file in `./drafts/pending_review/`, **verify every source**, edit
the wording as you see fit, and — only when you're satisfied — **move the file**
into `./drafts/approved/`. That move is the approval action.

---

## What Phase 1 does (Case-to-Script)

1. **Reads** every PDF / DOCX / TXT in `./case_files/`, tracking page numbers.
2. **Extracts contradiction units** — a documented claim paired with a later
   document that undercuts it:

   ```
   { claim, source_A (doc + page + line), counter, source_B (doc + page + line) }
   ```

   Three detectors run, all rule-based (no API keys, no network):
   - **monetary** — the same topic with contradictory dollar figures (e.g. a
     `$2,500,000` loss vs. a later `$0`).
   - **status_reversal** — a court order or assertion that is later undone
     (e.g. a TRO *granted* then *dissolved*). Verb pairs are configurable.
   - **negation** — the same topic where one document affirms and a later one
     negates.

   Only contradictions **across different documents** are surfaced, and each
   unit is ranked by a confidence score. This is a *candidate generator for a
   human* — it errs toward surfacing pairs to review, never toward asserting
   them.
3. **Drafts a tight script** (≤ 200 words, configurable) per unit in a neutral,
   factual voice, with both sources attached.
4. **Writes** each draft to `./drafts/pending_review/` as Markdown with a YAML
   header (`date`, `topic`, `platform_targets`, `sources`, `status`,
   `confidence`). **Then it stops.** A human reviews.

### Example output

Running against the bundled sample case files produces drafts like:

```markdown
---
date: 2026-06-28
topic: "financial / loss"
status: pending_review
contradiction_kind: monetary
confidence: 0.75
platform_targets:
  - tiktok
  - x
  - substack
sources:
  - doc: "01_affidavit_of_loss_2023-01-15.txt"
    page: 1
    line: 16
    date: 2023-01-15
    quote: "... Crestline Partners suffered a financial loss of $2,500,000."
  - doc: "02_discovery_response_2023-06-20.txt"
    page: 1
    line: 13
    date: 2023-06-20
    quote: "... the documented financial loss attributable to the defendant is $0."
---

# Contradictory figures: financial / loss

The record shows a contradiction on financial / loss.

Earlier (2023-01-15), the claim was:
"... Crestline Partners suffered a financial loss of $2,500,000."
Source: 01_affidavit_of_loss_2023-01-15.txt, p.1 (line 16), 2023-01-15.

Later (2023-06-20), the record shows:
"... the documented financial loss attributable to the defendant is $0."
Source: 02_discovery_response_2023-06-20.txt, p.1 (line 13), 2023-06-20.

Two figures. One record. The documents speak for themselves.
```

> The bundled documents in `./case_files/` are **clearly-labeled, fictional
> samples** so you can see the pipeline work end-to-end. Replace them with your
> real case files.

---

## Configuration

Everything is configured in `config.yaml` (all keys are optional — sane defaults
live in code). Highlights:

- `paths` — where case files live and where drafts go.
- `platforms.targets` — which platforms drafts are tagged for.
- `cadence.max_posts_per_day_per_platform` — the human-paced cap (enforced in
  Phase 3, configured now).
- `voice` — the script's tone and word limit, via editable templates.
- `extraction` — detector tuning (overlap thresholds, the dollar-difference
  ratio, status-reversal verb groups, negation cues).

Secrets (only needed in Phase 3) go in a `.env` file — copy `.env.example` to
`.env`. `.env` is git-ignored; never commit real keys.

---

## CLI reference

```
python -m accountability_engine extract [--dry-run] [--case-dir DIR]
python -m accountability_engine list-pending
python -m accountability_engine --version
python -m accountability_engine --config path/to/config.yaml extract
```

- `--dry-run` shows the contradiction units and the drafts that *would* be
  written, without writing any files.
- `--case-dir` overrides the case-files folder for one run.

---

## Project layout

```
accountability_engine/
  config.py        # config.yaml + .env loading, with full defaults
  documents.py     # read PDF/DOCX/TXT with page tracking
  extraction.py    # contradiction detectors → contradiction units
  drafting.py      # units → neutral, sourced Markdown drafts
  pipeline.py      # orchestrates Phase 1 end-to-end
  cli.py           # command-line interface
case_files/        # drop your source documents here (samples included)
drafts/
  pending_review/  # drafts wait here for a human  ← the approval gate
  approved/        # you MOVE files here to approve them
tests/             # pytest suite
config.yaml        # voice / cadence / platform / extraction settings
requirements.txt
.env.example
```

---

## Roadmap

- **Phase 1 — Case-to-Script** ✅ *(this release)* — extract contradictions,
  draft sourced scripts, queue for human review.
- **Phase 2 — Format & Repurpose** — turn *approved* drafts into platform
  variants (short captions + hashtags; long form; an X thread; optional
  voiceover + on-screen-caption files for an external video tool). No in-house
  video generation.
- **Phase 3 — Schedule & Track** — pluggable posting API (Publer first;
  Later/Buffer/Metricool swappable), a watched `./manual_uploads/` folder that
  routes the owner's own content through the *same* approval gate, a local
  SQLite log, and a simple dashboard. Needs API keys and a host that stays
  running — the host is separate from this project.

Phases are gated: Phase 1 output must be approved before Phases 2–3 are built.

---

## Running the tests

```bash
pip install pytest
python -m pytest
```

---

## Important

This tool references real, named parties in active litigation. The mandatory
human-review gate exists to prevent defamation exposure and to avoid handing the
opposing side a "coordinated harassment / bot farm" narrative. **Do not route
around the approval gate, and verify every cited source before approving any
draft.**
