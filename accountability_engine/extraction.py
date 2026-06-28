"""Contradiction extraction.

Turns loaded documents into candidate *contradiction units*:

    { claim, source_A (doc + page), counter, source_B (doc + page) }

This is deliberately deterministic and rule-based: it needs no API keys and no
network (Phase 1 = "zero infrastructure"). It is a *candidate generator* — it
errs toward surfacing pairs for a human to review, never toward asserting them.

Three detectors run:
  * monetary       — same topic, contradictory dollar amounts (incl. $0)
  * status_reversal— configured assert/retract verb pairs (granted vs dissolved)
  * negation       — same topic, one side affirms and the other negates

Every unit records the exact sentence and its document + page so the draft can
cite the record. No claim is emitted without two sourced sentences.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config import Config
from .documents import Document

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """A citation pointing at a specific place in a specific document."""

    doc: str
    page: int
    line: int
    quote: str
    doc_date: Optional[_dt.date] = None

    def cite(self) -> str:
        date = f", {self.doc_date.isoformat()}" if self.doc_date else ""
        return f"{self.doc}, p.{self.page} (line {self.line}){date}"


@dataclass
class Segment:
    """A single sentence with everything needed to compare and cite it."""

    doc: str
    page: int
    line: int
    index: int
    text: str
    doc_date: Optional[_dt.date]
    tokens: frozenset
    amounts: Tuple[float, ...]
    has_negation: bool

    def as_source(self) -> Source:
        return Source(
            doc=self.doc,
            page=self.page,
            line=self.line,
            quote=clean_quote(self.text),
            doc_date=self.doc_date,
        )


@dataclass
class ContradictionUnit:
    """A documented contradiction between two sourced statements."""

    topic: str
    claim: str
    source_A: Source
    counter: str
    source_B: Source
    kind: str  # "monetary" | "status_reversal" | "negation"
    confidence: float


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_MONEY_RE = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s*(million|billion|thousand|m|b|k)?",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "thousand": 1_000.0, "k": 1_000.0,
    "million": 1_000_000.0, "m": 1_000_000.0,
    "billion": 1_000_000_000.0, "b": 1_000_000_000.0,
}


def _sentence_spans(text: str) -> List[Tuple[int, str]]:
    """Yield (start_offset, sentence_text) for each sentence in ``text``."""
    spans: List[Tuple[int, str]] = []
    start = 0

    def emit(chunk_start: int, chunk_end: int) -> None:
        raw = text[chunk_start:chunk_end]
        sentence = raw.strip()
        if sentence:
            # Offset of the first non-whitespace character, for line counting.
            lead = len(raw) - len(raw.lstrip())
            spans.append((chunk_start + lead, sentence))

    # Break on sentence punctuation OR on a blank line (paragraph break). The
    # blank-line break keeps unpunctuated structure — case captions, headings,
    # signature blocks — from bleeding into the neighbouring sentence.
    for m in re.finditer(r"[.!?]+(?=\s|$)|\n[ \t]*\n", text):
        if m.group().strip() == "":  # blank-line boundary: don't keep the gap
            emit(start, m.start())
        else:
            emit(start, m.end())
        start = m.end()
    emit(start, len(text))
    return spans


def clean_quote(text: str) -> str:
    """Normalize whitespace and strip leading list/enumeration artifacts.

    Sentence splitting on abbreviations like "NO. 7:" can leave a stray "7:" at
    the start of a quote; trim those so the cited text reads cleanly.
    """
    t = " ".join(text.split())
    t = re.sub(r"^\d+\s*[:.]\s*", "", t)  # leading "7:" or "2."
    return t


def tokenize(text: str, stopwords: set, keep_short: set) -> frozenset:
    """Significant lowercase word tokens for topical-overlap comparison."""
    out = set()
    for w in _WORD_RE.findall(text.lower()):
        w = w.strip("'-")
        if not w:
            continue
        if w in keep_short:
            out.add(w)
        elif len(w) >= 4 and w not in stopwords:
            out.add(w)
    return frozenset(out)


def parse_amounts(text: str) -> Tuple[float, ...]:
    """Extract dollar amounts (normalized to float) from ``text``."""
    amounts: List[float] = []
    for m in _MONEY_RE.finditer(text):
        num = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").lower()
        num *= _MULTIPLIERS.get(suffix, 1.0)
        amounts.append(num)
    return tuple(amounts)


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def segment_documents(documents: List[Document], config: Config) -> List[Segment]:
    stopwords = config.stopwords
    keep_short = config.keep_short
    negation_cues = config.negation_cues

    segments: List[Segment] = []
    for doc in documents:
        for page in doc.pages:
            for start, sentence in _sentence_spans(page.text):
                tokens = tokenize(sentence, stopwords, keep_short)
                if not tokens:
                    continue
                line = page.text.count("\n", 0, start) + 1
                has_neg = bool(tokens & negation_cues) or any(
                    cue in sentence.lower() for cue in negation_cues
                )
                segments.append(
                    Segment(
                        doc=doc.name,
                        page=page.number,
                        line=line,
                        index=len(segments),
                        text=sentence,
                        doc_date=doc.doc_date,
                        tokens=tokens,
                        amounts=parse_amounts(sentence),
                        has_negation=has_neg,
                    )
                )
    return segments


# ---------------------------------------------------------------------------
# Ordering + topic helpers
# ---------------------------------------------------------------------------


def _order(a: Segment, b: Segment) -> Tuple[Segment, Segment]:
    """Return (earlier, later) by document date, falling back to doc/index."""
    da, db = a.doc_date, b.doc_date
    if da and db and da != db:
        return (a, b) if da < db else (b, a)
    if (a.doc, a.index) <= (b.doc, b.index):
        return a, b
    return b, a


# Procedural / filler words that make poor topic labels even though they pass
# the significance filter. Used only for the human-readable topic string.
_TOPIC_STOP = {
    "having", "hereby", "matter", "come", "before", "court", "dated", "states",
    "state", "response", "responding", "party", "parties", "pursuant",
    "ordered", "order", "regarding", "concerning", "whether", "previously",
}


def _topic(shared: frozenset, fallback: str = "the record") -> str:
    if not shared:
        return fallback
    candidates = [w for w in shared if w not in _TOPIC_STOP] or list(shared)
    # Pick the longest few shared tokens as a human-readable topic label.
    words = sorted(candidates, key=lambda w: (-len(w), w))[:3]
    return " / ".join(words)


def _materially_different(amounts_a, amounts_b, ratio: float) -> bool:
    if not amounts_a or not amounts_b:
        return False
    a_max, b_max = max(amounts_a), max(amounts_b)
    lo, hi = sorted((a_max, b_max))
    if lo == 0 and hi > 0:
        return True
    if lo > 0 and hi / lo >= ratio:
        return True
    return False


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _make_unit(a: Segment, b: Segment, shared: frozenset, kind: str,
               confidence: float) -> ContradictionUnit:
    earlier, later = _order(a, b)
    source_a = earlier.as_source()
    source_b = later.as_source()
    return ContradictionUnit(
        topic=_topic(shared),
        claim=source_a.quote,
        source_A=source_a,
        counter=source_b.quote,
        source_B=source_b,
        kind=kind,
        confidence=round(confidence, 3),
    )


def extract_contradictions(
    documents: List[Document], config: Config
) -> List[ContradictionUnit]:
    """Run all detectors and return de-duplicated, ranked contradiction units."""
    segments = segment_documents(documents, config)

    overlap_min = int(config.get("extraction", "overlap_min", default=2))
    neg_overlap_min = int(config.get("extraction", "negation_overlap_min", default=3))
    ratio = float(config.get("extraction", "material_ratio", default=5.0))
    reversals = config.status_reversals

    units: List[ContradictionUnit] = []
    seen: set = set()

    def key(unit: ContradictionUnit) -> tuple:
        a, b = unit.source_A, unit.source_B
        pair = tuple(sorted([(a.doc, a.page, a.line), (b.doc, b.page, b.line)]))
        return pair

    def add(a: Segment, b: Segment, shared: frozenset, kind: str, conf: float):
        unit = _make_unit(a, b, shared, kind, conf)
        k = key(unit)
        if k in seen:
            return
        seen.add(k)
        units.append(unit)

    n = len(segments)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = segments[i], segments[j]
            # A contradiction unit pairs a claim in one document with a *later
            # document* that undercuts it (per the brief). Only compare across
            # documents — this also removes question/answer noise within a
            # single filing.
            if a.doc == b.doc:
                continue
            shared = a.tokens & b.tokens
            overlap = len(shared)
            if overlap < overlap_min:
                continue

            # 1) Monetary contradiction (strongest signal first).
            if _materially_different(a.amounts, b.amounts, ratio):
                conf = min(0.95, 0.65 + 0.05 * overlap)
                add(a, b, shared, "monetary", conf)
                continue

            # 2) Status reversal (assert vs retract verbs on a shared topic).
            reversal_hit = _status_reversal(a, b, reversals)
            if reversal_hit:
                conf = min(0.95, 0.6 + 0.05 * overlap)
                add(a, b, shared, "status_reversal", conf)
                continue

            # 3) Negation contradiction — one side affirms, the other negates.
            if overlap >= neg_overlap_min and (a.has_negation ^ b.has_negation):
                conf = min(0.85, 0.45 + 0.05 * overlap)
                add(a, b, shared, "negation", conf)

    units.sort(key=lambda u: (-u.confidence, u.source_A.doc, u.source_B.doc))

    # Secondary dedupe: if two candidates reuse the exact same source sentence,
    # they are near-duplicates of one contradiction. Keep the highest-confidence
    # one (we are iterating in descending confidence order) so the review queue
    # stays clean. A reviewer can always open the source document for more.
    consumed: set = set()
    deduped: List[ContradictionUnit] = []
    for unit in units:
        ka = (unit.source_A.doc, unit.source_A.page, unit.source_A.line)
        kb = (unit.source_B.doc, unit.source_B.page, unit.source_B.line)
        if ka in consumed or kb in consumed:
            continue
        consumed.add(ka)
        consumed.add(kb)
        deduped.append(unit)
    return deduped


def _status_reversal(a: Segment, b: Segment, reversals: List[dict]) -> bool:
    """True if one segment asserts and the other retracts the same kind of thing."""
    for group in reversals:
        assert_words = {w.lower() for w in group.get("assert", [])}
        retract_words = {w.lower() for w in group.get("retract", [])}
        a_assert = bool(a.tokens & assert_words)
        a_retract = bool(a.tokens & retract_words)
        b_assert = bool(b.tokens & assert_words)
        b_retract = bool(b.tokens & retract_words)
        if (a_assert and b_retract) or (b_assert and a_retract):
            return True
    return False
