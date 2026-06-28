"""Document schemas - what fields each document type produces.

A schema declares the expected output shape for a category of PDF
(invoice, contract, bank statement). The extractor is schema-driven,
so adding support for a new document type = adding a new schema entry +
extractor rules. The agent loop doesn't change.

Each field declares:
  - name (key in the output dict)
  - kind (str | number | date | amount | list)
  - required (whether the eval should fail when missing)
  - description (human-readable, used in LLM prompts and docs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Field:
    name: str
    kind: str
    required: bool = True
    description: str = ""


@dataclass
class Schema:
    """Expected output shape for a category of document."""
    name: str
    description: str
    fields: list[Field]

    def required_fields(self) -> list[Field]:
        return [f for f in self.fields if f.required]

    def field_names(self) -> set[str]:
        return {f.name for f in self.fields}


# ----- Built-in schemas -----------------------------------------------------

INVOICE = Schema(
    name="invoice",
    description="Vendor invoice with line items and a total.",
    fields=[
        Field("invoice_number", "str", description="Vendor's invoice ID."),
        Field("invoice_date", "date", description="Date the invoice was issued."),
        Field("due_date", "date", required=False, description="When payment is due."),
        Field("vendor_name", "str", description="Issuing company name."),
        Field("vendor_address", "str", required=False, description="Vendor's mailing address."),
        Field("bill_to_name", "str", description="Recipient company name."),
        Field("subtotal", "amount", required=False, description="Pre-tax line-item sum."),
        Field("tax", "amount", required=False, description="Tax amount."),
        Field("total", "amount", description="Total amount due."),
        Field("currency", "str", required=False, description="ISO currency code (USD, EUR, etc.)."),
        Field("line_items", "list", required=False,
              description="Per-line: description, quantity, unit_price, line_total."),
    ],
)


CONTRACT = Schema(
    name="contract",
    description="Service or supply contract with named parties.",
    fields=[
        Field("title", "str", description="Contract title or subject."),
        Field("party_a", "str", description="First named party."),
        Field("party_b", "str", description="Second named party."),
        Field("effective_date", "date", description="Date the contract takes effect."),
        Field("term_months", "number", required=False, description="Initial term length."),
        Field("renewal", "str", required=False,
              description="Renewal clause (auto / on-notice / none)."),
        Field("notice_period_days", "number", required=False,
              description="Days of notice required for termination or non-renewal."),
        Field("governing_law", "str", required=False, description="Jurisdiction."),
    ],
)


BANK_STATEMENT = Schema(
    name="bank_statement",
    description="Bank account statement with transaction list.",
    fields=[
        Field("account_holder", "str", description="Name on the account."),
        Field("account_number", "str", description="Account identifier (masked OK)."),
        Field("period_start", "date", description="Statement period start."),
        Field("period_end", "date", description="Statement period end."),
        Field("opening_balance", "amount", description="Balance at period start."),
        Field("closing_balance", "amount", description="Balance at period end."),
        Field("currency", "str", required=False, description="ISO currency code."),
        Field("transactions", "list", required=False,
              description="Per-line: date, description, amount, balance."),
    ],
)


REGISTRY = {
    "invoice": INVOICE,
    "contract": CONTRACT,
    "bank_statement": BANK_STATEMENT,
}


def get(schema_name: str) -> Schema:
    if schema_name not in REGISTRY:
        raise KeyError(f"Unknown schema '{schema_name}'. Available: {sorted(REGISTRY)}")
    return REGISTRY[schema_name]
