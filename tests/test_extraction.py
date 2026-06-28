"""Tests for the contradiction extractor and document parsing."""

import datetime as dt

from accountability_engine.config import load_config
from accountability_engine.documents import Document, Page, infer_date
from accountability_engine.extraction import (
    parse_amounts,
    tokenize,
    extract_contradictions,
)


def _config(tmp_path):
    # Use built-in defaults; no config.yaml needed.
    return load_config(config_path=tmp_path / "missing.yaml", root=tmp_path)


def test_parse_amounts_handles_suffixes_and_commas():
    assert parse_amounts("a loss of $2,500,000 total") == (2_500_000.0,)
    assert parse_amounts("worth $3 million") == (3_000_000.0,)
    assert parse_amounts("the actual loss was $0") == (0.0,)
    assert parse_amounts("no dollars here") == ()


def test_tokenize_filters_stopwords_keeps_domain_terms():
    tokens = tokenize("The TRO was granted", stopwords={"the", "was"}, keep_short={"tro"})
    assert "tro" in tokens
    assert "granted" in tokens
    assert "the" not in tokens and "was" not in tokens


def test_infer_date_from_filename(tmp_path):
    p = tmp_path / "affidavit_2023-01-15.txt"
    p.write_text("x", encoding="utf-8")
    assert infer_date(p) == dt.date(2023, 1, 15)


def _doc(name, date, text):
    return Document(path=None, name=name, pages=[Page(1, text)], doc_date=date)


def test_monetary_contradiction_detected(tmp_path):
    config = _config(tmp_path)
    docs = [
        _doc("affidavit.txt", dt.date(2023, 1, 15),
             "Crestline suffered a financial loss of $2,500,000."),
        _doc("discovery.txt", dt.date(2023, 6, 20),
             "The documented financial loss attributable was $0."),
    ]
    units = extract_contradictions(docs, config)
    assert any(u.kind == "monetary" for u in units)
    unit = next(u for u in units if u.kind == "monetary")
    # Earlier doc is the claim, later doc the counter.
    assert unit.source_A.doc == "affidavit.txt"
    assert unit.source_B.doc == "discovery.txt"
    assert unit.source_A.page == 1
    assert "2,500,000" in unit.claim


def test_status_reversal_detected(tmp_path):
    config = _config(tmp_path)
    docs = [
        _doc("tro_order.txt", dt.date(2023, 2, 1),
             "The Court hereby GRANTS the temporary restraining order (TRO)."),
        _doc("tro_dissolve.txt", dt.date(2023, 4, 10),
             "The Court hereby DISSOLVES the temporary restraining order (TRO)."),
    ]
    units = extract_contradictions(docs, config)
    assert any(u.kind == "status_reversal" for u in units)


def test_no_false_positive_on_unrelated_sentences(tmp_path):
    config = _config(tmp_path)
    docs = [
        _doc("a.txt", dt.date(2023, 1, 1), "The weather today is sunny and warm."),
        _doc("b.txt", dt.date(2023, 2, 1), "The committee approved the annual budget."),
    ]
    units = extract_contradictions(docs, config)
    assert units == []


def test_units_carry_two_distinct_sources(tmp_path):
    config = _config(tmp_path)
    docs = [
        _doc("affidavit.txt", dt.date(2023, 1, 15),
             "Crestline suffered a financial loss of $2,500,000."),
        _doc("discovery.txt", dt.date(2023, 6, 20),
             "The documented financial loss attributable was $0."),
    ]
    units = extract_contradictions(docs, config)
    for unit in units:
        assert unit.source_A.quote and unit.source_B.quote
        assert (unit.source_A.doc, unit.source_A.page, unit.source_A.line) != (
            unit.source_B.doc, unit.source_B.page, unit.source_B.line
        )
