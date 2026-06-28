"""Drafting: turn contradiction units into review-ready script drafts.

Each draft is a short (configurable, default <=200 words) neutral script with
its sources attached, written to ``./drafts/pending_review/`` as Markdown with
a YAML front-matter header (date, topic, platform_targets, sources, status).

Nothing here publishes anything. Output lands in the review queue and waits for
a human. That is the mandatory approval gate.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .config import Config
from .extraction import ContradictionUnit, Source

_KIND_LABELS = {
    "monetary": "Contradictory figures",
    "status_reversal": "Reversed in the record",
    "negation": "Self-contradiction",
}


@dataclass
class Draft:
    """A single drafted script awaiting human review."""

    topic: str
    body: str
    sources: List[Source]
    platform_targets: List[str]
    kind: str
    confidence: float
    created: _dt.date
    word_count: int = 0
    truncated: bool = False
    extra_notes: List[str] = field(default_factory=list)


def _slugify(text: str, max_len: int = 50) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_len].strip("-")) or "draft"


def _enforce_word_limit(body: str, max_words: int) -> tuple[str, int, bool]:
    words = body.split()
    if len(words) <= max_words:
        return body, len(words), False
    # Truncate on a word boundary and flag it for the reviewer.
    trimmed = " ".join(words[:max_words])
    return trimmed + " […]", max_words, True


def draft_script(unit: ContradictionUnit, config: Config,
                 today: _dt.date | None = None) -> Draft:
    """Render one contradiction unit into a Draft using the configured voice."""
    today = today or _dt.date.today()
    templates = config.templates
    template = templates.get(unit.kind) or templates.get("default", "")

    date_a = unit.source_A.doc_date.isoformat() if unit.source_A.doc_date else "an earlier filing"
    date_b = unit.source_B.doc_date.isoformat() if unit.source_B.doc_date else "a later filing"

    body = template.format(
        topic=unit.topic,
        claim=unit.claim,
        counter=unit.counter,
        source_a=unit.source_A.cite(),
        source_b=unit.source_B.cite(),
        date_a=date_a,
        date_b=date_b,
        kind_label=_KIND_LABELS.get(unit.kind, "Documented contradiction"),
    )

    body, word_count, truncated = _enforce_word_limit(body, config.max_words)

    notes: List[str] = []
    if truncated:
        notes.append(
            "Script exceeded the configured word limit and was truncated. "
            "Tighten it during review."
        )

    return Draft(
        topic=unit.topic,
        body=body,
        sources=[unit.source_A, unit.source_B],
        platform_targets=config.platform_targets,
        kind=unit.kind,
        confidence=unit.confidence,
        created=today,
        word_count=word_count,
        truncated=truncated,
        extra_notes=notes,
    )


def _yaml_escape(value: str) -> str:
    """Quote a scalar for YAML safely (double-quote + escape)."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_markdown(draft: Draft) -> str:
    """Render a Draft as Markdown with a YAML front-matter header."""
    lines: List[str] = ["---"]
    lines.append(f"date: {draft.created.isoformat()}")
    lines.append(f"topic: {_yaml_escape(draft.topic)}")
    lines.append(f"status: pending_review")
    lines.append(f"contradiction_kind: {draft.kind}")
    lines.append(f"confidence: {draft.confidence}")
    lines.append(f"word_count: {draft.word_count}")
    lines.append("platform_targets:")
    for target in draft.platform_targets:
        lines.append(f"  - {target}")
    lines.append("sources:")
    for src in draft.sources:
        lines.append(f"  - doc: {_yaml_escape(src.doc)}")
        lines.append(f"    page: {src.page}")
        lines.append(f"    line: {src.line}")
        if src.doc_date:
            lines.append(f"    date: {src.doc_date.isoformat()}")
        lines.append(f"    quote: {_yaml_escape(src.quote)}")
    if draft.extra_notes:
        lines.append("review_notes:")
        for note in draft.extra_notes:
            lines.append(f"  - {_yaml_escape(note)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {_KIND_LABELS.get(draft.kind, 'Documented contradiction')}: {draft.topic}")
    lines.append("")
    lines.append(draft.body)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Sources (verify before approving)")
    lines.append("")
    for i, src in enumerate(draft.sources, start=1):
        lines.append(f"{i}. **{src.cite()}**")
        lines.append(f"   > {src.quote}")
    lines.append("")
    lines.append(
        "_Drafted automatically from the case record. Not reviewed. "
        "Do not publish until a human approves and verifies every source above._"
    )
    lines.append("")
    return "\n".join(lines)


def draft_filename(draft: Draft, ordinal: int) -> str:
    return f"{draft.created.isoformat()}_{ordinal:02d}_{draft.kind}_{_slugify(draft.topic)}.md"


def write_draft(draft: Draft, out_dir: Path, ordinal: int) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / draft_filename(draft, ordinal)
    path.write_text(render_markdown(draft), encoding="utf-8")
    return path
