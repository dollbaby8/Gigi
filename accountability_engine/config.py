"""Configuration loading for the Accountability Content Engine.

Loads ``config.yaml`` (voice, cadence, platform settings, extraction tuning)
and ``.env`` (secrets — never hardcoded). Everything has a sane default so the
tool runs out of the box with zero setup for Phase 1.
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # PyYAML is a declared dependency, but degrade gracefully if missing.
    import yaml
except Exception:  # pragma: no cover - exercised only without the dependency
    yaml = None  # type: ignore[assignment]


# Defaults are intentionally complete: the engine is fully functional even if
# the user never writes a config.yaml. config.yaml only *overrides* these.
DEFAULTS: Dict[str, Any] = {
    "paths": {
        "case_files": "./case_files",
        "pending_review": "./drafts/pending_review",
        "approved": "./drafts/approved",
    },
    "platforms": {
        # Where drafts are *targeted*. Posting itself is Phase 3 and gated.
        "targets": ["tiktok", "instagram_reels", "youtube_shorts", "x", "substack"],
    },
    "cadence": {
        # ToS-compliant, human-paced. Enforced in Phase 3; recorded here so the
        # limit is configured from day one.
        "max_posts_per_day_per_platform": 2,
    },
    "voice": {
        "name": "neutral_factual",
        "max_words": 200,
        # Templates keep the tone neutral and factual. Placeholders available:
        #   {topic} {claim} {counter} {source_a} {source_b}
        #   {date_a} {date_b} {kind_label}
        "templates": {
            "monetary": (
                "The record shows a contradiction on {topic}.\n\n"
                "Earlier ({date_a}), the claim was:\n"
                "“{claim}”\n"
                "Source: {source_a}.\n\n"
                "Later ({date_b}), the record shows:\n"
                "“{counter}”\n"
                "Source: {source_b}.\n\n"
                "Two figures. One record. The documents speak for themselves."
            ),
            "status_reversal": (
                "A reversal in the record on {topic}.\n\n"
                "On {date_a}:\n“{claim}”\n"
                "Source: {source_a}.\n\n"
                "On {date_b}:\n“{counter}”\n"
                "Source: {source_b}.\n\n"
                "What was entered was later undone. Read the orders yourself."
            ),
            "negation": (
                "On {topic}, the record contradicts itself.\n\n"
                "First ({date_a}):\n“{claim}”\n"
                "Source: {source_a}.\n\n"
                "Then ({date_b}):\n“{counter}”\n"
                "Source: {source_b}.\n\n"
                "Both statements are in the file. They cannot both be true."
            ),
            "default": (
                "Documented contradiction on {topic}.\n\n"
                "Claim ({date_a}): “{claim}” — {source_a}.\n\n"
                "Counter ({date_b}): “{counter}” — {source_b}.\n\n"
                "The case record speaks for itself."
            ),
        },
    },
    "extraction": {
        # Minimum number of shared significant words two sentences must have to
        # be considered "about the same thing".
        "overlap_min": 2,
        "negation_overlap_min": 3,
        # Monetary contradiction: a contradiction is flagged when one amount is
        # zero and the other is positive, or when the larger is this many times
        # the smaller.
        "material_ratio": 5.0,
        # Words ignored when computing topical overlap.
        "stopwords": [],  # merged with the built-in stoplist
        # Short but meaningful domain tokens to keep despite the length filter.
        "keep_short": ["tro", "no"],
        # Negation cues used by the negation detector.
        "negation_cues": [
            "no", "not", "never", "without", "denies", "denied", "deny",
            "failed", "lacked", "absence", "zero", "none", "neither", "nor",
        ],
        # Status-reversal verb groups. A pair is flagged when one sentence
        # contains an "assert" word and the matching one contains a "retract".
        "status_reversals": [
            {
                "topic": "court order",
                "assert": ["grant", "grants", "granted", "granting", "issue",
                           "issued", "enter", "entered", "uphold", "upheld"],
                "retract": ["dissolve", "dissolves", "dissolved", "vacate",
                            "vacated", "lift", "lifted", "deny", "denied",
                            "dismiss", "dismissed", "overturn", "overturned",
                            "reverse", "reversed", "withdraw", "withdrawn"],
            },
            {
                "topic": "allegation",
                "assert": ["alleged", "alleges", "asserted", "asserts",
                           "claimed", "claims"],
                "retract": ["withdrew", "withdrawn", "retracted", "recanted",
                            "abandoned", "conceded"],
            },
        ],
    },
}

# A compact, general-purpose English stoplist. Kept inline to avoid a
# dependency. Significant legal/topical words are deliberately *not* here.
_BUILTIN_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "has", "had",
    "was", "were", "are", "but", "not", "you", "your", "his", "her", "him",
    "she", "they", "them", "their", "our", "out", "any", "all", "can", "will",
    "would", "could", "should", "been", "being", "into", "than", "then", "upon",
    "which", "what", "when", "where", "who", "whom", "whose", "there", "here",
    "such", "also", "more", "most", "some", "each", "other", "about", "after",
    "before", "between", "under", "over", "again", "further", "once", "during",
    "shall", "may", "must", "said", "per", "its", "it's", "as", "at", "by",
    "of", "on", "to", "in", "is", "be", "or", "an", "a",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Does not overwrite real env vars."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    """Resolved configuration with convenient typed accessors."""

    def __init__(self, data: Dict[str, Any], root: Path):
        self._data = data
        self.root = root

    # -- generic access -------------------------------------------------
    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    # -- typed helpers --------------------------------------------------
    def path(self, name: str) -> Path:
        rel = self.get("paths", name, default=DEFAULTS["paths"].get(name, "."))
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    @property
    def platform_targets(self) -> List[str]:
        return list(self.get("platforms", "targets", default=[]))

    @property
    def max_words(self) -> int:
        return int(self.get("voice", "max_words", default=200))

    @property
    def templates(self) -> Dict[str, str]:
        return dict(self.get("voice", "templates", default={}))

    @property
    def voice_name(self) -> str:
        return str(self.get("voice", "name", default="neutral_factual"))

    @property
    def stopwords(self) -> set:
        extra = self.get("extraction", "stopwords", default=[]) or []
        return set(_BUILTIN_STOPWORDS) | {w.lower() for w in extra}

    @property
    def keep_short(self) -> set:
        return {w.lower() for w in self.get("extraction", "keep_short", default=[])}

    @property
    def negation_cues(self) -> set:
        return {w.lower() for w in self.get("extraction", "negation_cues", default=[])}

    @property
    def status_reversals(self) -> List[Dict[str, Any]]:
        return list(self.get("extraction", "status_reversals", default=[]))

    def secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Read a secret from the environment (.env already loaded)."""
        return os.environ.get(name, default)


def load_config(
    config_path: Optional[os.PathLike] = None,
    root: Optional[os.PathLike] = None,
) -> Config:
    """Load configuration, merging ``config.yaml`` over the built-in defaults.

    ``root`` is the project root used to resolve relative paths. If omitted it
    is the current working directory.
    """
    root_path = Path(root).resolve() if root else Path.cwd()

    if config_path is None:
        config_path = root_path / "config.yaml"
    config_path = Path(config_path)

    _load_dotenv(root_path / ".env")

    user_data: Dict[str, Any] = {}
    if config_path.exists():
        if yaml is None:
            raise RuntimeError(
                "config.yaml exists but PyYAML is not installed. "
                "Run: pip install -r requirements.txt"
            )
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if loaded:
            user_data = loaded

    merged = _deep_merge(DEFAULTS, user_data)
    return Config(merged, root_path)
