# Gigi — S.D. Tex. litigation assistant

Gigi is a small command-line tool for litigating in the Southern District of Texas. It does five things:

1. **Analyzes a docket.** It pulls out the judge's orders, rulings on each motion, motions with no ruling found, hearing settings (telephone vs. in person), and returned mail.
2. **Computes deadlines.** It follows FRCP 6(a)/(d), S.D. Tex. LR 7.3/7.4 submission days, federal legal holidays, and the post-judgment and appeal clocks (Rules 54(d)(2), 59, 60(c); FRAP 4(a)). Every date comes with the arithmetic that produced it.
3. **Researches your judge.** It searches CourtListener for the presiding judge's own opinions and orders, by issue, so a brief can hold the court to its own prior rulings.
4. **Keeps a citation-verified playbook.** Authorities and the court's own in-case orders are mapped to docket targets (e.g. `ECF 200`). Only entries marked verified render into briefs.
5. **Builds outputs.** It generates brief-ready Markdown argument inserts, an `.ics` deadline calendar with reminders, and a self-contained HTML dashboard that works on a phone.

Standard library only (Python 3.9+). No accounts are needed except an optional free CourtListener API token.

## Privacy: read this first

Case files are attorney work product. They live under `cases/<slug>/`, which is **git-ignored**, along with `out/` and `*.ics`. Do not commit them to a public repository. If you want case files under version control, make the repository private first, then `git add -f cases/<slug>`. `examples/sample-case/` is fictional.

## Install

```bash
pip install -e .        # installs the `gigi` command
# or, without installing:
python -m gigi --help
```

## Quick start (fictional sample case)

```bash
gigi docket examples/sample-case pending --as-of 2026-03-25
gigi deadlines examples/sample-case --as-of 2026-03-25 --ics /tmp/sample.ics
gigi build examples/sample-case --as-of 2026-03-25     # writes examples/sample-case/out/
```

## A real case

```bash
gigi init cases/my-case --case-number 4:25-cv-00000 --judge "Judge Name" --caption "A v. B"
gigi import-docket docket_export.json cases/my-case   # DocketBird or CourtListener JSON
gigi docket cases/my-case pending        # motions with no ruling found, submission days, CJRA flags
gigi docket cases/my-case hearings       # every setting, telephone vs. in person
gigi deadlines cases/my-case --ics cases/my-case/out/deadlines.ics
gigi build cases/my-case                 # briefs for every target + calendar + dashboard
```

`case.json` holds:
- scheduling-order deadlines
- custom deadlines
- dashboard alerts
- `entry_overrides`, for entries missing from the docket index
- `manual_dispositions`, for rulings that a bare "ORDER" entry does not name
- `judgment_entered`: set it the day a judgment is entered and the post-judgment clocks appear everywhere

## Deadline math

```bash
gigi submission --filed 2025-09-22            # LR 7.3: 21 days -> Columbus Day -> 2025-10-14
gigi deadline --from 2026-10-02 --days 14 --mail   # FRCP 6(d) adds 3 days after the 6(a) period
gigi post-judgment --entered 2026-10-05       # 54(d)(2), 59(e), FRAP 4(a)(1)(A), 4(a)(5), 60(c)(1)
```

The LR 7.3 computation is tested against clerk-generated "Motion Docket Date" entries. That includes a date that rolls past Columbus Day and dates that roll past weekends.

Presidential and congressional holiday declarations and clerk's-office closures cannot be predicted. Add them to `extra_holidays` in `case.json`.

## Holding the court to its own rulings

```bash
export COURTLISTENER_TOKEN=...            # free at courtlistener.com; raises rate limits
gigi issues                                # list issue presets (rule41b, rule54b-certification, ...)
gigi research --judge "Keith P. Ellison" --issue rule41b --out leads.md
gigi research --judge "Keith P. Ellison" --issue protective-order --type rd --out orders.md  # RECAP orders
```

Results are **leads**. Read each opinion, confirm authorship and the quote, then add it to the playbook. You can add it by hand or with `gigi merge cases/my-case research.json --issue rule41b`. Then check the playbook:

```bash
gigi playbook cases/my-case --check        # non-zero exit on missing fields, duplicate ids,
                                           # unverified quotations, unknown targets
gigi brief cases/my-case --target "ECF 200"
```

### Playbook entry shape

```json
{"id": "berry-v-cigna", "kind": "fifth_cir", "case_name": "...", "citation": "... (5th Cir. 1992)",
 "holding": "...", "quote": "verbatim or null", "pin": "at 1191", "use": "how to deploy it",
 "targets": ["ECF 200"], "source_url": "...", "verified": true, "verification": "how it was checked"}
```

`kind` is one of `judge` (the presiding judge's own decisions), `scotus`, `fifth_cir`, `texas`, `sdtx`, `other_district`, `rule`, `statute`, or `policy`.

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Limits

- Docket classification is heuristic and keyed to CM/ECF text conventions. A bare "ORDER" entry may resolve a motion without naming it; record those in `manual_dispositions`.
- Deadlines must be confirmed against the rules and any case-specific order.
- Gigi is a research and organization tool, not legal advice.
