---
name: court-opinion-scraper
description: Pull the newest published opinions straight from court websites (Supreme Court of Texas, Texas Courts of Appeals, Court of Criminal Appeals, Texas Business Court, Texas AG opinions, Fifth Circuit, U.S. Supreme Court, plus 200+ other courts) using Free Law Project's juriscraper. Use when the user asks "what did the Texas Supreme Court / Fifth Circuit / 14th or 1st Court of Appeals release", wants new opinions on a topic (retaliation, Sabine Pilot, TCHRA, Title VII, insurance bad faith, Rule 91a), or wants a recent-opinions sweep before filing.
---

# Court Opinion Scraper (juriscraper)

Pulls the **latest opinions posted on each court's own website** — the current release page, typically the last few weeks. It is a freshness tool, not a full-text case-law search. For older cases, citations, or full-text keyword research, use CourtListener (which is fed by this same library) or another research connector.

## How to run

```bash
python scripts/scrape.py <court> [<court> ...] [--keyword a,b] [--days N] [--json]
python scripts/scrape.py --list <term>      # find a court's scraper id
```

The script installs `juriscraper` (Python 3.11+) on first run if it is missing.

Aliases built in:

| Alias | Court |
|---|---|
| `tex` | Supreme Court of Texas |
| `texapp` | Texas Courts of Appeals (all districts; `lower_court` shows the district, e.g. 1st/14th = Houston) |
| `texcrimapp` | Texas Court of Criminal Appeals |
| `texbizct` | Texas Business Court |
| `texag` | Texas Attorney General opinions |
| `ca5` | U.S. Court of Appeals, Fifth Circuit |
| `scotus` | U.S. Supreme Court slip opinions |

Any other court: run `--list <state or name>` and pass the returned path (e.g. `state.cal`, `federal_appellate.ca9_p`).

`--keyword` is an OR match across case name, docket number, summary, judge, and lower court — useful for party names or "Harris County". Case captions rarely contain doctrine words, so for topic searches (e.g. "retaliation") scrape without a keyword, then open the likely PDFs and read them.

## Workflow

1. Map the user's request to courts (Houston employment matter → `tex texapp ca5`).
2. Run the script with `--json` so results are easy to filter.
3. Present a tight table: date, court, case name, docket no., published/unpublished, PDF link. Newest first.
4. If the user wants substance, download the relevant PDFs and summarize holdings — flag anything that helps or hurts the user's active matters.
5. Report any per-court errors plainly (sites change; juriscraper updates often — `pip install -U juriscraper` fixes most breakage).

## Limits — say these when relevant

- **No federal district courts** (S.D. Tex. included) and **no Harris County district court** dockets. Use PACER/RECAP via CourtListener for S.D. Tex.
- Results cover only what the court's website currently lists.
- Network access: the sandbox must be allowed to reach court domains (txcourts.gov, ca5.uscourts.gov, supremecourt.gov, etc.). If you get a proxy/403/connection error, tell the user their code-execution network setting must allow these domains (claude.ai: Settings → Capabilities → code execution / network egress; org admins control this on Team/Enterprise plans).
- Always verify a case from the official PDF before citing it.
