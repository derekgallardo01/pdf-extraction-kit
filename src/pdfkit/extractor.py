"""Schema-driven field extractor with a pluggable backend.

Default backend is regex-based - deterministic, no API keys, runs in CI.
Set PDFKIT_EXTRACTOR=llm to route through Claude (one method swap).

For each field in the schema, the extractor runs the appropriate
backend-specific extraction routine and emits:

    {
        "value": <extracted value or None>,
        "confidence": <float between 0 and 1>,
        "evidence": <substring that produced the value, or None>,
    }

The shape is identical regardless of backend - tests, evals, and the
Pages demo don't know which path produced it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .schemas import Schema, Field


@dataclass
class FieldResult:
    value: Any
    confidence: float
    evidence: str | None


@dataclass
class ExtractionResult:
    schema: str
    fields: dict[str, FieldResult]
    backend: str

    @property
    def coverage(self) -> float:
        """Fraction of required fields that got a value."""
        from .schemas import get
        required = get(self.schema).required_fields()
        if not required:
            return 1.0
        present = sum(1 for f in required if self.fields.get(f.name) and self.fields[f.name].value is not None)
        return present / len(required)

    @property
    def avg_confidence(self) -> float:
        vals = [f.confidence for f in self.fields.values() if f.value is not None]
        return sum(vals) / len(vals) if vals else 0.0


class Extractor:
    """The thing that converts text into a structured dict per schema."""

    def __init__(self, backend: str | None = None):
        self.backend = backend or os.environ.get("PDFKIT_EXTRACTOR", "regex")

    def extract(self, text: str, schema: Schema) -> ExtractionResult:
        """Run the extractor against `text` for the given schema."""
        if self.backend == "llm":
            return self._extract_llm(text, schema)
        return self._extract_regex(text, schema)

    # ----- The provider seam -----------------------------------------------

    def _extract_regex(self, text: str, schema: Schema) -> ExtractionResult:
        """Deterministic regex-based extractor.

        Hand-tuned per schema. Confidence is heuristic: 0.95 when the
        regex matches cleanly, 0.5 for fuzzy matches, 0.0 when missing.
        Good enough for the demo + CI; production should use the LLM path.
        """
        results: dict[str, FieldResult] = {}
        for f in schema.fields:
            results[f.name] = _regex_for_field(schema.name, f, text)
        return ExtractionResult(schema=schema.name, fields=results, backend="regex")

    def _extract_llm(self, text: str, schema: Schema) -> ExtractionResult:
        """LLM-based extractor (production swap point).

        Implementation sketch - uncomment and adapt to your LLM SDK:

            from anthropic import Anthropic
            client = Anthropic()
            prompt = build_extraction_prompt(text, schema)
            response = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = json.loads(response.content[0].text)
            return _result_from_llm_json(parsed, schema)

        The prompt asks Claude to return JSON shaped like:
            {"field_name": {"value": ..., "confidence": 0-1, "evidence": "..."}}

        Until wired, fall back to regex so the kit still runs.
        """
        return self._extract_regex(text, schema)


# ----- Per-schema regex routines --------------------------------------------

# Common patterns shared across schemas.
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),
    re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b", re.I),
]
_AMOUNT = re.compile(r"\$?\s*([\d,]+\.\d{2})", re.I)
_CURRENCY = re.compile(r"\b(USD|EUR|GBP|JPY|CHF|CAD|AUD)\b", re.I)


def _miss(reason: str = "") -> FieldResult:
    return FieldResult(value=None, confidence=0.0, evidence=None)


def _normalise_date(parts: tuple[str, ...]) -> str | None:
    if len(parts) != 3:
        return None
    try:
        # YYYY-MM-DD
        if len(parts[0]) == 4:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        # DD MMM YYYY
        if parts[1][:3].isalpha():
            month_idx = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                         "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}[parts[1][:3].lower()]
            return f"{int(parts[2])}-{month_idx:02d}-{int(parts[0]):02d}"
        # MM/DD/YYYY
        return f"{int(parts[2])}-{int(parts[0]):02d}-{int(parts[1]):02d}"
    except (KeyError, ValueError):
        return None


def _find_date_after_label(text: str, labels: list[str]) -> tuple[str | None, str | None]:
    """Find a date that follows any of the given labels (case-insensitive)."""
    for label in labels:
        m = re.search(rf"(?i){re.escape(label)}\s*:?\s*([^\n]+)", text)
        if not m:
            continue
        window = m.group(1)
        for pat in _DATE_PATTERNS:
            d = pat.search(window)
            if d:
                normalised = _normalise_date(d.groups())
                if normalised:
                    return normalised, m.group(0).strip()
    return None, None


def _find_amount_after_label(text: str, labels: list[str]) -> tuple[float | None, str | None]:
    for label in labels:
        m = re.search(rf"(?i){re.escape(label)}\s*:?\s*\$?\s*([\d,]+\.\d{{2}})", text)
        if m:
            try:
                return float(m.group(1).replace(",", "")), m.group(0).strip()
            except ValueError:
                continue
    return None, None


def _find_str_after_label(text: str, labels: list[str], max_chars: int = 80) -> tuple[str | None, str | None]:
    for label in labels:
        m = re.search(rf"(?i){re.escape(label)}\s*:?\s*([^\n]+)", text)
        if m:
            value = m.group(1).strip()[:max_chars]
            if value:
                return value, m.group(0).strip()
    return None, None


def _regex_for_field(schema_name: str, f: Field, text: str) -> FieldResult:
    """Dispatch per (schema, field) - the table of extraction rules."""
    # INVOICE
    if schema_name == "invoice":
        if f.name == "invoice_number":
            v, ev = _find_str_after_label(text, ["Invoice #", "Invoice Number", "Invoice No"])
            return FieldResult(v, 0.95 if v else 0.0, ev)
        if f.name in ("invoice_date", "due_date"):
            labels = (["Invoice Date", "Date"] if f.name == "invoice_date"
                      else ["Due Date", "Payment Due"])
            v, ev = _find_date_after_label(text, labels)
            return FieldResult(v, 0.95 if v else 0.0, ev)
        if f.name == "vendor_name":
            v, ev = _find_str_after_label(text, ["From:", "Vendor:", "Issued by"])
            return FieldResult(v, 0.85 if v else 0.0, ev)
        if f.name == "vendor_address":
            v, ev = _find_str_after_label(text, ["Vendor Address:", "From Address:"], max_chars=150)
            return FieldResult(v, 0.85 if v else 0.0, ev)
        if f.name == "bill_to_name":
            v, ev = _find_str_after_label(text, ["Bill To:", "To:"])
            return FieldResult(v, 0.85 if v else 0.0, ev)
        if f.name == "subtotal":
            v, ev = _find_amount_after_label(text, ["Subtotal"])
            return FieldResult(v, 0.95 if v is not None else 0.0, ev)
        if f.name == "tax":
            v, ev = _find_amount_after_label(text, ["Sales Tax", "VAT", "Tax"])
            return FieldResult(v, 0.95 if v is not None else 0.0, ev)
        if f.name == "total":
            # Total must NOT match Subtotal. Use a left word-boundary regex.
            for label in ["Grand Total", "Amount Due", "Total"]:
                m = re.search(rf"(?im)(?<![A-Za-z]){re.escape(label)}\s*:?\s*\$?\s*([\d,]+\.\d{{2}})", text)
                if m:
                    try:
                        return FieldResult(float(m.group(1).replace(",", "")), 0.95, m.group(0).strip())
                    except ValueError:
                        continue
            return _miss()
        if f.name == "currency":
            m = _CURRENCY.search(text)
            if m:
                return FieldResult(m.group(1).upper(), 0.95, m.group(0))
            return _miss()
        if f.name == "line_items":
            items = _extract_line_items(text)
            return FieldResult(items if items else None,
                               0.7 if items else 0.0,
                               f"{len(items)} line items" if items else None)

    # CONTRACT
    if schema_name == "contract":
        if f.name == "title":
            v, ev = _find_str_after_label(text, ["Contract Title:", "Subject:", "Re:"])
            return FieldResult(v, 0.9 if v else 0.0, ev)
        if f.name == "party_a":
            v, ev = _find_str_after_label(text, ["Party A:", "Between:", "Provider:"])
            return FieldResult(v, 0.9 if v else 0.0, ev)
        if f.name == "party_b":
            v, ev = _find_str_after_label(text, ["Party B:", "And:", "Customer:", "Client:"])
            return FieldResult(v, 0.9 if v else 0.0, ev)
        if f.name == "effective_date":
            v, ev = _find_date_after_label(text, ["Effective Date", "Start Date", "Commencement"])
            return FieldResult(v, 0.95 if v else 0.0, ev)
        if f.name == "term_months":
            m = re.search(r"(?i)term[^.]*?(\d+)\s*month", text)
            if m:
                return FieldResult(int(m.group(1)), 0.85, m.group(0))
            return _miss()
        if f.name == "renewal":
            v, ev = _find_str_after_label(text, ["Renewal:", "Renewal Clause:"])
            return FieldResult(v, 0.8 if v else 0.0, ev)
        if f.name == "notice_period_days":
            m = re.search(r"(?i)(\d+)\s*day[^.]*?notice", text)
            if m:
                return FieldResult(int(m.group(1)), 0.85, m.group(0))
            return _miss()
        if f.name == "governing_law":
            v, ev = _find_str_after_label(text, ["Governing Law:", "Jurisdiction:"])
            return FieldResult(v, 0.9 if v else 0.0, ev)

    # BANK STATEMENT
    if schema_name == "bank_statement":
        if f.name == "account_holder":
            v, ev = _find_str_after_label(text, ["Account Holder:", "Statement For:", "Customer:"])
            return FieldResult(v, 0.9 if v else 0.0, ev)
        if f.name == "account_number":
            v, ev = _find_str_after_label(text, ["Account Number:", "Account #:"])
            return FieldResult(v, 0.95 if v else 0.0, ev)
        if f.name in ("period_start", "period_end"):
            # First try the labelled form ("Period Start: ...").
            labels = (["Period Start", "Statement Period: From"]
                      if f.name == "period_start"
                      else ["Period End", "Statement Period: To"])
            v, ev = _find_date_after_label(text, labels)
            if v:
                return FieldResult(v, 0.95, ev)
            # Fallback: "Statement Period: From <date> To <date>" - pull
            # whichever date the field name asks for.
            m = re.search(r"(?i)Statement\s+Period\s*:?\s*From\s+(\d{4}-\d{2}-\d{2})\s+To\s+(\d{4}-\d{2}-\d{2})", text)
            if m:
                return FieldResult(
                    m.group(1) if f.name == "period_start" else m.group(2),
                    0.9, m.group(0).strip())
            return _miss()
        if f.name in ("opening_balance", "closing_balance"):
            labels = (["Opening Balance"] if f.name == "opening_balance"
                      else ["Closing Balance", "Ending Balance"])
            v, ev = _find_amount_after_label(text, labels)
            return FieldResult(v, 0.95 if v is not None else 0.0, ev)
        if f.name == "currency":
            m = _CURRENCY.search(text)
            if m:
                return FieldResult(m.group(1).upper(), 0.95, m.group(0))
            return _miss()
        if f.name == "transactions":
            txns = _extract_transactions(text)
            return FieldResult(txns if txns else None,
                               0.7 if txns else 0.0,
                               f"{len(txns)} transactions" if txns else None)

    return _miss()


# ----- Composite extractors (lists) -----------------------------------------

def _extract_line_items(text: str) -> list[dict]:
    """Pull invoice line items - 'description ... qty x unit = total' style."""
    items = []
    # Look for lines that look like: "Description | qty | unit_price | line_total"
    # Or freeform: "Description 4 x 25.00 = 100.00"
    for line in text.splitlines():
        line = line.strip()
        # Pattern 1: pipe-delimited
        if "|" in line and line.count("|") >= 3:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and any(re.match(r"^\d", p) for p in parts[1:]):
                try:
                    items.append({
                        "description": parts[0],
                        "quantity": _maybe_number(parts[1]),
                        "unit_price": _maybe_number(parts[2]),
                        "line_total": _maybe_number(parts[3]),
                    })
                except (ValueError, IndexError):
                    pass
        # Pattern 2: "description qty x unit = total"
        m = re.match(r"^(.+?)\s+(\d+)\s*[xX×]\s*\$?(\d+(?:\.\d{2})?)\s*=\s*\$?(\d+(?:\.\d{2})?)$", line)
        if m:
            desc = m.group(1).strip()
            # Skip obvious header rows.
            if desc.lower() in {"description", "item", "items", "line item"}:
                continue
            items.append({
                "description": desc,
                "quantity": int(m.group(2)),
                "unit_price": float(m.group(3)),
                "line_total": float(m.group(4)),
            })
    return items


def _extract_transactions(text: str) -> list[dict]:
    """Pull bank statement transactions - 'date description amount balance' style."""
    txns = []
    # Match lines that start with a date, then text, then 2 amounts.
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})\s+(\$?[\d,]+\.\d{2})$", line)
        if m:
            txns.append({
                "date": m.group(1),
                "description": m.group(2).strip(),
                "amount": float(m.group(3).replace("$", "").replace(",", "")),
                "balance": float(m.group(4).replace("$", "").replace(",", "")),
            })
    return txns


def _maybe_number(s: str) -> float | int | str:
    s = s.strip().replace("$", "").replace(",", "")
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return s
