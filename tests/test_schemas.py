"""Tests for the schema definitions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from pdfkit import schemas  # noqa: E402


def test_registry_has_three_schemas():
    assert set(schemas.REGISTRY) == {"invoice", "contract", "bank_statement"}


def test_get_known_schema_returns_schema():
    s = schemas.get("invoice")
    assert s.name == "invoice"
    assert "invoice_number" in s.field_names()


def test_get_unknown_schema_raises():
    with pytest.raises(KeyError):
        schemas.get("does-not-exist")


def test_invoice_required_fields_include_total():
    s = schemas.get("invoice")
    req_names = {f.name for f in s.required_fields()}
    assert "total" in req_names
    assert "invoice_number" in req_names


def test_contract_optional_fields_marked_optional():
    s = schemas.get("contract")
    by_name = {f.name: f for f in s.fields}
    assert by_name["renewal"].required is False
    assert by_name["governing_law"].required is False


def test_bank_statement_has_period_dates_required():
    s = schemas.get("bank_statement")
    req_names = {f.name for f in s.required_fields()}
    assert "period_start" in req_names
    assert "period_end" in req_names
    assert "opening_balance" in req_names
    assert "closing_balance" in req_names
