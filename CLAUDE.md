# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

Gigi is a Python CLI that helps the user find Reddit communities worth
engaging with, and understand each one's posting culture (rules, cadence,
flairs, best-performing post times). It is strictly **read-only** — it does
not post, vote, DM, or run multi-account flows. Don't add features that
automate engagement or anything else that would violate Reddit's API terms.

## Commands

```bash
pip install -e .                              # install in editable mode
gigi find <topic>                             # search & rank subreddits by active-user ratio
gigi analyze <subreddit>                      # rules, cadence, top posts, best post times
gigi draft <subreddit> --topic "your topic"   # post brief: tone, skeleton, rules checklist

# Run without installing:
PYTHONPATH=src python -m gigi.cli --help
```

There is no test suite or linter wired up yet. If one is added, document the
exact invocations here, including how to run a single test.

Credentials live in `.env` (see `.env.example`). Disk cache lives in
`.gigi-cache/` and is keyed by command + arguments — delete it to force a
refresh.

## Architecture

```
src/gigi/
  cli.py       # click entrypoint; rich tables/panels for output
  client.py    # PRAW factory + tiny JSON disk cache (cached(key, fn, ttl))
  find.py      # find_subreddits(): search, filter by min subs, rank by active%
  analyze.py   # analyze_subreddit(): pulls .new() + .top("week"), aggregates
  draft.py     # draft_post(): builds on analyze, detects title style, returns brief
```

Data flow: `cli.py` builds a `praw.Reddit` via `client.get_reddit()`, hands it
to `find.py` / `analyze.py`, those modules wrap their PRAW calls in
`client.cached(...)` so repeated queries are cheap. Everything returned from
`cached()` must be JSON-serializable, which is why the per-module functions
go through plain dicts before reconstructing dataclasses. `draft.py` is a
pure-Python layer on top of `analyze_subreddit()` — no extra API calls — so
its output is as fresh as the analyze cache.

`draft.py` is intentionally template-based, not LLM-driven. If you're tempted
to add an LLM call, talk to the user first — pulling in an external API
changes the project's threat model and offline behavior.

## Working branch

Development happens on `claude/reddit-community-tool-qoVfu`. Commit and push
work to that branch.
