"""End-to-end Phase 1 tests: drafting, rendering, and the approval gate."""

import datetime as dt

from accountability_engine.config import load_config
from accountability_engine.pipeline import run_phase1


SAMPLE_AFFIDAVIT = "Crestline suffered a financial loss of $2,500,000 from the breach."
SAMPLE_DISCOVERY = "The documented financial loss attributable to the defendant was $0."


def _project(tmp_path):
    case = tmp_path / "case_files"
    case.mkdir()
    (case / "01_affidavit_2023-01-15.txt").write_text(SAMPLE_AFFIDAVIT, encoding="utf-8")
    (case / "02_discovery_2023-06-20.txt").write_text(SAMPLE_DISCOVERY, encoding="utf-8")
    return load_config(config_path=tmp_path / "missing.yaml", root=tmp_path)


def test_dry_run_writes_nothing(tmp_path):
    config = _project(tmp_path)
    result = run_phase1(config, dry_run=True, today=dt.date(2026, 6, 28))
    assert result.units, "expected at least one contradiction unit"
    assert result.written == []
    pending = config.path("pending_review")
    # Dry run must not create the queue contents.
    assert not pending.exists() or not list(pending.glob("*.md"))


def test_real_run_writes_to_pending_review_only(tmp_path):
    config = _project(tmp_path)
    result = run_phase1(config, dry_run=False, today=dt.date(2026, 6, 28))
    assert result.written, "expected drafts to be written"

    pending = config.path("pending_review")
    approved = config.path("approved")

    written = list(pending.glob("*.md"))
    assert written, "drafts should land in pending_review"

    # The approval gate: nothing is auto-approved.
    assert not approved.exists() or not list(approved.glob("*.md"))


def test_draft_has_yaml_header_and_sources(tmp_path):
    config = _project(tmp_path)
    result = run_phase1(config, dry_run=False, today=dt.date(2026, 6, 28))
    content = result.written[0].read_text(encoding="utf-8")

    assert content.startswith("---")
    assert "status: pending_review" in content
    assert "platform_targets:" in content
    assert "sources:" in content
    assert "page:" in content
    # Both source documents must be cited somewhere in the draft.
    assert "affidavit" in content and "discovery" in content
    # The not-reviewed warning must be present.
    assert "Do not publish" in content


def test_draft_respects_word_limit(tmp_path):
    config = _project(tmp_path)
    result = run_phase1(config, dry_run=True, today=dt.date(2026, 6, 28))
    for draft in result.drafts:
        assert draft.word_count <= config.max_words
