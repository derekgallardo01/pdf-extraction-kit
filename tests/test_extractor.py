"""Tests for the regex extractor against the bundled fixtures."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pdfkit import schemas, pdf_reader  # noqa: E402
from pdfkit.extractor import Extractor  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _extract(schema_name: str, fixture: str):
    text = pdf_reader.read_text(FIXTURES / fixture)
    return Extractor(backend="regex").extract(text, schemas.get(schema_name))


# ---------- Invoice extraction ---------------------------------------------

def test_invoice_001_extracts_number_date_total():
    r = _extract("invoice", "invoice-001.pdf")
    assert r.fields["invoice_number"].value == "INV-2026-00482"
    assert r.fields["invoice_date"].value == "2026-06-15"
    assert r.fields["total"].value == 922.80


def test_invoice_001_does_not_confuse_total_with_subtotal():
    r = _extract("invoice", "invoice-001.pdf")
    assert r.fields["total"].value == 922.80
    assert r.fields["subtotal"].value == 769.00


def test_invoice_001_pulls_line_items():
    r = _extract("invoice", "invoice-001.pdf")
    items = r.fields["line_items"].value
    assert items is not None
    assert len(items) >= 3
    assert any("Steel ball bearings" in i["description"] for i in items)


def test_invoice_002_pulls_currency():
    r = _extract("invoice", "invoice-002.pdf")
    assert r.fields["currency"].value == "USD"


def test_invoice_002_skips_header_row_in_line_items():
    r = _extract("invoice", "invoice-002.pdf")
    items = r.fields["line_items"].value or []
    # The header row "Description ... 4 x 25.00 = 100.00" must NOT show up.
    for item in items:
        assert item["description"].lower() != "description"


# ---------- Contract extraction --------------------------------------------

def test_contract_001_extracts_parties_and_term():
    r = _extract("contract", "contract-001.pdf")
    assert r.fields["effective_date"].value == "2026-01-15"
    assert r.fields["term_months"].value == 36
    assert r.fields["notice_period_days"].value == 90
    assert "New York" in r.fields["governing_law"].value


def test_contract_002_handles_different_label_style():
    r = _extract("contract", "contract-002.pdf")
    assert r.fields["effective_date"].value == "2026-03-01"
    assert r.fields["term_months"].value == 24
    assert r.fields["notice_period_days"].value == 60


# ---------- Bank statement extraction --------------------------------------

def test_statement_001_extracts_balances():
    r = _extract("bank_statement", "statement-001.pdf")
    assert r.fields["opening_balance"].value == 45230.00
    assert r.fields["closing_balance"].value == 41118.50
    assert r.fields["account_holder"].value == "Northwind Trading Co."


def test_statement_001_pulls_transactions():
    r = _extract("bank_statement", "statement-001.pdf")
    txns = r.fields["transactions"].value
    assert txns is not None
    assert len(txns) >= 5
    assert all("date" in t and "amount" in t for t in txns)


def test_statement_002_handles_combined_period_label():
    """'Statement Period: From X To Y' is a different format than statement-001."""
    r = _extract("bank_statement", "statement-002.pdf")
    assert r.fields["period_start"].value == "2026-04-01"
    assert r.fields["period_end"].value == "2026-04-30"


def test_statement_002_currency_is_eur():
    r = _extract("bank_statement", "statement-002.pdf")
    assert r.fields["currency"].value == "EUR"


# ---------- Coverage / confidence shape ------------------------------------

def test_coverage_is_100pct_on_well_formed_invoice():
    r = _extract("invoice", "invoice-001.pdf")
    assert r.coverage == 1.0


def test_extraction_result_carries_backend_name():
    r = _extract("invoice", "invoice-001.pdf")
    assert r.backend == "regex"


def test_missing_required_field_lowers_coverage():
    # Empty text -> nothing extractable
    r = Extractor(backend="regex").extract("blank document", schemas.get("invoice"))
    assert r.coverage == 0.0
    assert r.avg_confidence == 0.0


def test_evidence_is_recorded_for_extracted_fields():
    r = _extract("invoice", "invoice-001.pdf")
    inv_num = r.fields["invoice_number"]
    assert inv_num.evidence is not None
    assert "INV-2026-00482" in inv_num.evidence
