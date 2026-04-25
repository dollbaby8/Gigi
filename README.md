# Gigi

A small Python CLI for finding and analyzing Reddit communities, so you can
spend your engagement effort where it actually matters.

It is **read-only**. It does not post, vote, DM, or do anything that would
violate Reddit's API terms or look like spam. The premise is that "gaining
following" comes from engaging consistently in the right communities — Gigi
helps you find them and understand them.

## What it does

- `gigi find <topic>` — search subreddits matching a topic and rank them by
  the ratio of currently-online users to subscribers (a better signal of an
  engaged community than raw size).
- `gigi analyze <subreddit>` — pull rules, posting cadence, allowed post
  types, common flairs, top posts of the week, and the hours/weekdays where
  top posts tend to appear.

## Setup

```bash
pip install -e .
cp .env.example .env
# Edit .env and fill in your Reddit API credentials.
```

To get credentials: visit <https://www.reddit.com/prefs/apps>, create a
"script" app, and copy the client id and secret into `.env`. The user-agent
string should include your Reddit username, e.g. `gigi/0.1 by u/yourname`.

## Usage

```bash
gigi find "indie game dev"
gigi find rust --min-subscribers 5000
gigi analyze rust
gigi analyze learnprogramming --sample-size 500
```

Results are cached on disk under `.gigi-cache/` for a few hours so repeated
queries don't burn your API quota. Delete the directory to force a refresh.

## Layout

```
src/gigi/
  cli.py       # click entrypoint, rich-formatted output
  client.py    # PRAW client + disk cache
  find.py      # subreddit search + ranking
  analyze.py   # per-subreddit report (rules, cadence, top posts, best times)
```
