"""Tests for the PDF reader's fixture fallback path."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from pdfkit import pdf_reader  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_reads_text_fixture_when_pdf_missing():
    txt = pdf_reader.read_text(FIXTURES / "invoice-001.pdf")
    assert "INV-2026-00482" in txt


def test_raises_clear_error_when_fixture_missing(tmp_path):
    bogus = tmp_path / "nope.pdf"
    with pytest.raises(FileNotFoundError, match="No text fixture"):
        pdf_reader.read_text(bogus)
