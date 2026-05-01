"""Generate a per-subreddit post brief: tone analysis, skeleton, rules checklist.

This is intentionally template-based, not LLM-driven. The point is to
surface the constraints (rules, allowed types, best post times) and
patterns from top posts so the user can write a post that won't get
auto-removed and that fits the sub's culture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import praw

from .analyze import analyze_subreddit


@dataclass
class PostBrief:
    subreddit: str
    topic: str
    suggested_flair: str | None
    title_style: str  # "question" | "listicle" | "statement"
    median_title_chars: int
    uses_brackets: bool
    title_skeleton: str
    body_skeleton: str
    checklist: list[str]
    rules: list[str]
    best_hours_utc: list[int]
    best_weekdays: list[str]
    allowed_post_types: list[str]


_BRACKET_RE = re.compile(r"\[[^\]]+\]|\([^\)]+\)")
_NUMBER_RE = re.compile(r"\b\d+\b")


def _detect_title_style(titles: list[str]) -> tuple[str, int, bool]:
    if not titles:
        return "statement", 60, False
    chars = sorted(len(t) for t in titles)
    median_len = chars[len(chars) // 2]
    questions = sum(1 for t in titles if t.rstrip().endswith("?"))
    listicles = sum(1 for t in titles if _NUMBER_RE.search(t))
    bracketed = sum(1 for t in titles if _BRACKET_RE.search(t))

    if questions / len(titles) >= 0.4:
        style = "question"
    elif listicles / len(titles) >= 0.4:
        style = "listicle"
    else:
        style = "statement"
    return style, median_len, bracketed / len(titles) >= 0.4


def _title_skeleton(style: str, topic: str, median_len: int, uses_brackets: bool) -> str:
    prefix = "[Your tag] " if uses_brackets else ""
    if style == "question":
        body = f"What's the best {topic} for [your specific situation]?"
    elif style == "listicle":
        body = f"5 things I learned about {topic} after [time/experience]"
    else:
        body = f"My experience with {topic}: [the specific angle]"
    skeleton = f"{prefix}{body}"
    return f"{skeleton}    (aim for ~{median_len} chars, max 100)"


def _body_skeleton(style: str, topic: str) -> str:
    if style == "question":
        return (
            "Hook (1-2 sentences): your specific situation, what makes it different.\n"
            "    e.g. \"I have [skin type / hair type / budget / constraint] and "
            "I've been struggling with [problem].\"\n\n"
            "Context (2-4 sentences): what you've already tried, why it didn't work,\n"
            "    what you're looking for that's different. Be specific — vague\n"
            "    posts get vague answers.\n\n"
            f"The ask: a clear, specific question about {topic}. Not 'any tips?' —\n"
            "    instead 'has anyone with [trait] had luck with [category]?'\n\n"
            "Close: 'thanks in advance, happy to share what works.'"
        )
    if style == "listicle":
        return (
            "Intro (2-3 sentences): the situation that led to these lessons.\n"
            "    e.g. \"After 6 months of trying every [category], here's what stuck.\"\n\n"
            "Numbered list (5-7 items): each item one bold takeaway + 1-2\n"
            "    sentences of detail. Be specific — name products / techniques /\n"
            "    concrete numbers.\n\n"
            "Closing thought: what you'd tell past-you, or what you're still\n"
            "    figuring out. Invites comments."
        )
    return (
        "Hook (1-2 sentences): the specific moment / product / change.\n\n"
        f"The story (4-6 sentences): your before, what you did with {topic},\n"
        "    your after. Specific products, dosages, timeframes. Photos help if\n"
        "    the sub allows them and you have flair for it.\n\n"
        "Caveats (1-2 sentences): what didn't work, what you're still tweaking.\n"
        "    Honest > polished.\n\n"
        "Open question: invite the comment section to share their version."
    )


def _checklist(report, suggested_flair: str | None) -> list[str]:
    items: list[str] = []
    items.append("Title under 100 chars (Reddit hard limit is 300, but tight wins)")
    if suggested_flair:
        items.append(f'Set flair to "{suggested_flair}" (most common in top posts)')
    else:
        items.append("Pick a flair if the sub requires one (check rules)")
    if report.allowed_post_types:
        items.append(f"Post type is one of: {', '.join(report.allowed_post_types)}")
    if report.best_hours_utc:
        hrs = ", ".join(f"{h:02d}:00 UTC" for h in report.best_hours_utc)
        items.append(f"Posting in a strong hour window ({hrs})")
    if report.best_weekdays:
        items.append(f"Posting on a strong weekday ({', '.join(report.best_weekdays)})")
    items.append("No links to your own sub in the body (most subs ban this)")
    items.append("Re-read every rule below before hitting submit")
    return items


def draft_post(reddit: praw.Reddit, subreddit: str, topic: str) -> PostBrief:
    report = analyze_subreddit(reddit, subreddit)
    titles = [p.title for p in report.top_posts_week]
    style, median_len, uses_brackets = _detect_title_style(titles)
    suggested_flair = report.common_flairs[0][0] if report.common_flairs else None

    return PostBrief(
        subreddit=report.name,
        topic=topic,
        suggested_flair=suggested_flair,
        title_style=style,
        median_title_chars=median_len,
        uses_brackets=uses_brackets,
        title_skeleton=_title_skeleton(style, topic, median_len, uses_brackets),
        body_skeleton=_body_skeleton(style, topic),
        checklist=_checklist(report, suggested_flair),
        rules=report.rules,
        best_hours_utc=report.best_hours_utc,
        best_weekdays=report.best_weekdays,
        allowed_post_types=report.allowed_post_types,
    )
