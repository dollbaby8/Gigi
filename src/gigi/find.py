"""Find subreddits relevant to a topic and rank them by engagement potential."""

from __future__ import annotations

from dataclasses import dataclass

import praw

from .client import cached


@dataclass
class SubredditMatch:
    name: str
    subscribers: int
    active_users: int | None
    public_description: str
    over_18: bool
    activity_ratio: float  # active_users / subscribers, when available

    @classmethod
    def from_dict(cls, d: dict) -> "SubredditMatch":
        return cls(**d)


def _to_dict(sub: praw.models.Subreddit) -> dict:
    subs = int(sub.subscribers or 0)
    active = sub.active_user_count
    return {
        "name": sub.display_name,
        "subscribers": subs,
        "active_users": int(active) if active is not None else None,
        "public_description": (sub.public_description or "").strip(),
        "over_18": bool(sub.over18),
        "activity_ratio": (active / subs) if (active and subs) else 0.0,
    }


def find_subreddits(
    reddit: praw.Reddit,
    topic: str,
    limit: int = 25,
    min_subscribers: int = 1_000,
) -> list[SubredditMatch]:
    """Search Reddit for subreddits matching `topic` and rank by activity ratio.

    Activity ratio (active_users / subscribers) is a better signal of an
    engaged community than raw subscriber count — a 50k-sub niche with 500
    online beats a 5M default sub with 500 online.
    """
    key = f"find::{topic.lower()}::{limit}"

    def fetch() -> list[dict]:
        results: list[dict] = []
        seen: set[str] = set()
        for sub in reddit.subreddits.search(topic, limit=limit):
            if sub.display_name in seen:
                continue
            seen.add(sub.display_name)
            results.append(_to_dict(sub))
        return results

    raw = cached(key, fetch)
    matches = [SubredditMatch.from_dict(d) for d in raw if d["subscribers"] >= min_subscribers]
    matches.sort(key=lambda m: (m.activity_ratio, m.subscribers), reverse=True)
    return matches
