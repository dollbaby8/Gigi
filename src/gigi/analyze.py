"""Analyze a single subreddit: rules, posting cadence, top content, best post times."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import praw

from .client import cached


@dataclass
class TopPost:
    title: str
    score: int
    num_comments: int
    url: str
    flair: str | None


@dataclass
class SubredditReport:
    name: str
    subscribers: int
    active_users: int | None
    description: str
    rules: list[str]
    allowed_post_types: list[str]
    posts_per_day: float
    median_score_for_top_quartile: int
    best_hours_utc: list[int]
    best_weekdays: list[str]
    common_flairs: list[tuple[str, int]]
    top_posts_week: list[TopPost]


_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _allowed_post_types(sub: praw.models.Subreddit) -> list[str]:
    types = []
    if getattr(sub, "submission_type", "any") in ("any", "self"):
        types.append("text")
    if getattr(sub, "submission_type", "any") in ("any", "link"):
        types.append("link")
    if getattr(sub, "allow_images", False):
        types.append("image")
    if getattr(sub, "allow_videos", False):
        types.append("video")
    if getattr(sub, "allow_polls", False):
        types.append("poll")
    return types


def analyze_subreddit(reddit: praw.Reddit, name: str, sample_size: int = 200) -> SubredditReport:
    """Pull recent + top posts from a subreddit and summarize patterns."""
    key = f"analyze::{name.lower()}::{sample_size}"

    def fetch() -> dict:
        sub = reddit.subreddit(name)
        # Force a fetch so attributes are populated.
        _ = sub.id

        rules = [r.short_name + (": " + r.description if r.description else "") for r in sub.rules]

        recent = list(sub.new(limit=sample_size))
        top_week = list(sub.top(time_filter="week", limit=10))

        # Posting cadence
        if recent:
            span_seconds = recent[0].created_utc - recent[-1].created_utc
            posts_per_day = len(recent) / max(span_seconds / 86400.0, 1e-9)
        else:
            posts_per_day = 0.0

        # Best hours/weekdays from top quartile of recent posts by score
        scored = sorted(recent, key=lambda p: p.score, reverse=True)
        cutoff = max(1, len(scored) // 4)
        top_quartile = scored[:cutoff]
        median_score = sorted(p.score for p in top_quartile)[len(top_quartile) // 2] if top_quartile else 0

        hour_hist: Counter[int] = Counter()
        wday_hist: Counter[int] = Counter()
        for p in top_quartile:
            dt = datetime.fromtimestamp(p.created_utc, tz=timezone.utc)
            hour_hist[dt.hour] += 1
            wday_hist[dt.weekday()] += 1

        best_hours = [h for h, _ in hour_hist.most_common(3)]
        best_weekdays = [_WEEKDAYS[d] for d, _ in wday_hist.most_common(3)]

        # Common flairs across recent posts
        flair_hist: Counter[str] = Counter()
        for p in recent:
            if p.link_flair_text:
                flair_hist[p.link_flair_text] += 1

        top_posts = [
            {
                "title": p.title,
                "score": int(p.score),
                "num_comments": int(p.num_comments),
                "url": f"https://reddit.com{p.permalink}",
                "flair": p.link_flair_text,
            }
            for p in top_week
        ]

        active = sub.active_user_count
        return {
            "name": sub.display_name,
            "subscribers": int(sub.subscribers or 0),
            "active_users": int(active) if active is not None else None,
            "description": (sub.public_description or "").strip(),
            "rules": rules,
            "allowed_post_types": _allowed_post_types(sub),
            "posts_per_day": round(posts_per_day, 1),
            "median_score_for_top_quartile": int(median_score),
            "best_hours_utc": best_hours,
            "best_weekdays": best_weekdays,
            "common_flairs": flair_hist.most_common(5),
            "top_posts_week": top_posts,
        }

    data = cached(key, fetch, ttl=60 * 60 * 3)  # 3-hour cache for analyses
    return SubredditReport(
        name=data["name"],
        subscribers=data["subscribers"],
        active_users=data["active_users"],
        description=data["description"],
        rules=data["rules"],
        allowed_post_types=data["allowed_post_types"],
        posts_per_day=data["posts_per_day"],
        median_score_for_top_quartile=data["median_score_for_top_quartile"],
        best_hours_utc=data["best_hours_utc"],
        best_weekdays=data["best_weekdays"],
        common_flairs=[tuple(item) for item in data["common_flairs"]],
        top_posts_week=[TopPost(**p) for p in data["top_posts_week"]],
    )
