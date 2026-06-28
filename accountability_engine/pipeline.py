"""Phase 1 pipeline: case files → contradiction units → drafts in review queue.

This wires the pieces together and is the single entry point used by the CLI.
It never publishes. Its only side effect (outside dry-run) is writing Markdown
drafts into the pending-review folder.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .config import Config
from .documents import Document, load_documents
from .drafting import Draft, draft_script, write_draft
from .extraction import ContradictionUnit, extract_contradictions


@dataclass
class PipelineResult:
    documents: List[Document]
    units: List[ContradictionUnit]
    drafts: List[Draft]
    written: List[Path] = field(default_factory=list)
    dry_run: bool = False


def run_phase1(
    config: Config,
    dry_run: bool = False,
    today: _dt.date | None = None,
) -> PipelineResult:
    """Load case files, extract contradictions, draft scripts, queue for review."""
    today = today or _dt.date.today()

    case_dir = config.path("case_files")
    documents = load_documents(case_dir)

    units = extract_contradictions(documents, config)
    drafts = [draft_script(unit, config, today=today) for unit in units]

    written: List[Path] = []
    if not dry_run:
        out_dir = config.path("pending_review")
        for ordinal, draft in enumerate(drafts, start=1):
            written.append(write_draft(draft, out_dir, ordinal))

    return PipelineResult(
        documents=documents,
        units=units,
        drafts=drafts,
        written=written,
        dry_run=dry_run,
    )
