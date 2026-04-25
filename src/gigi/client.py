"""Reddit API client. Read-only PRAW wrapper with a small on-disk cache."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import praw
from dotenv import load_dotenv

CACHE_DIR = Path(os.environ.get("GIGI_CACHE_DIR", ".gigi-cache"))
DEFAULT_TTL_SECONDS = 60 * 60 * 6  # 6 hours


class MissingCredentials(RuntimeError):
    pass


def _load_env() -> tuple[str, str, str]:
    load_dotenv()
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    ua = os.environ.get("REDDIT_USER_AGENT")
    missing = [n for n, v in [("REDDIT_CLIENT_ID", cid), ("REDDIT_CLIENT_SECRET", secret), ("REDDIT_USER_AGENT", ua)] if not v]
    if missing:
        raise MissingCredentials(
            f"Missing env vars: {', '.join(missing)}. Copy .env.example to .env and fill it in."
        )
    return cid, secret, ua  # type: ignore[return-value]


def get_reddit() -> praw.Reddit:
    cid, secret, ua = _load_env()
    return praw.Reddit(
        client_id=cid,
        client_secret=secret,
        user_agent=ua,
        check_for_async=False,
    )


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{digest}.json"


def cached(key: str, fn: Callable[[], Any], ttl: int = DEFAULT_TTL_SECONDS) -> Any:
    """Disk-cache the JSON-serializable result of `fn()` under `key`."""
    path = _cache_path(key)
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        with path.open() as f:
            return json.load(f)
    value = fn()
    with path.open("w") as f:
        json.dump(value, f)
    return value
