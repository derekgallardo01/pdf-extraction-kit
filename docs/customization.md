# Customization

How to extend the kit for a real engagement.

## Add a new schema

Three steps:

1. **Declare the schema** in `src/pdfkit/schemas.py`:

```python
PURCHASE_ORDER = Schema(
    name="purchase_order",
    description="Buyer-side PO with ship-to address.",
    fields=[
        Field("po_number", "str", description="PO identifier."),
        Field("po_date", "date", description="Date PO was issued."),
        Field("supplier", "str", description="Supplier name."),
        Field("ship_to", "str", description="Ship-to address."),
        Field("total", "amount", description="Total committed amount."),
        Field("line_items", "list", required=False),
    ],
)

REGISTRY = {
    "invoice": INVOICE,
    "contract": CONTRACT,
    "bank_statement": BANK_STATEMENT,
    "purchase_order": PURCHASE_ORDER,
}
```

2. **Add extraction rules** in `src/pdfkit/extractor.py::_regex_for_field`:

```python
if schema_name == "purchase_order":
    if f.name == "po_number":
        v, ev = _find_str_after_label(text, ["PO #", "Purchase Order", "Order Number"])
        return FieldResult(v, 0.95 if v else 0.0, ev)
    if f.name == "po_date":
        v, ev = _find_date_after_label(text, ["PO Date", "Order Date"])
        return FieldResult(v, 0.95 if v else 0.0, ev)
    # ... etc
```

3. **Add a fixture + eval cases** to verify it works:

```bash
# Drop a real PDF (or a .pdf.txt fixture) into fixtures/po-001.pdf.txt
# Then add to evals/golden.json:
{
  "id": "po-001-total",
  "fixture": "po-001.pdf",
  "schema": "purchase_order",
  "field": "total",
  "expected_value": 5000.00
}
```

Run `pdfkit list-schemas` to confirm the new schema shows. Run
`python evals/run.py` to verify the new cases pass.

## Add a new field to an existing schema

Two steps:

1. **Declare the field** in the schema (add a `Field(...)` entry).
2. **Add an extraction rule** in `_regex_for_field` for that field.

Optionally add a fixture + eval case. The rest of the kit
(`coverage`, `avg_confidence`, the CLI, the demo) picks it up
automatically.

## Improve extraction for a specific format

Two paths:

### Path 1: Add a more specific regex variant

If you have a PDF format where the label is "Total Due" instead of
"Total" or "Grand Total":

```python
# In _regex_for_field, the `total` block already has:
for label in ["Grand Total", "Amount Due", "Total"]:
    ...

# Add "Total Due" to the front (more specific first):
for label in ["Total Due", "Grand Total", "Amount Due", "Total"]:
    ...
```

Most format-handling is "add a label variant to the list". Cheap;
deterministic; testable.

### Path 2: Swap that one field to the LLM backend

For fields where regex is hopeless (semantic clauses, free-form
descriptions, multi-line items in inconsistent layouts), implement a
per-field LLM fallback:

```python
def _extract_regex(self, text, schema):
    results = {}
    for f in schema.fields:
        r = _regex_for_field(schema.name, f, text)
        if r.value is None and f.required and self.backend == "hybrid":
            r = self._extract_one_field_llm(text, f)
        results[f.name] = r
    return ExtractionResult(schema=schema.name, fields=results, backend="hybrid")
```

This is the recommended production pattern: regex first (cheap,
fast, deterministic), LLM only for the long tail. The kit doesn't
ship this as a default because the LLM path is a stub; once you
wire `_extract_llm`, the hybrid pattern is a 5-line addition.

## Add a new backend (not LLM, not regex)

Examples: Azure Document Intelligence, AWS Textract, a fine-tuned
local model. Three steps:

1. Add a third branch in `Extractor.extract`:

```python
def extract(self, text, schema):
    if self.backend == "llm":
        return self._extract_llm(text, schema)
    if self.backend == "azure":
        return self._extract_azure(text, schema)
    return self._extract_regex(text, schema)
```

2. Implement `_extract_azure(text, schema)` — call the Azure SDK,
   parse its response, map each field to a `FieldResult` with the
   service's confidence score.

3. Add `PDFKIT_EXTRACTOR=azure` to your environment.

The shape returned must match (`ExtractionResult` with `FieldResult`
per field). Tests, evals, and CLI don't need to change.

## Calibrate confidence scores

The regex backend's confidence numbers are heuristics, not
calibrated probabilities. To calibrate them against your real-world
data:

1. Collect 100+ extracted fields with ground-truth labels.
2. Group by the kit's reported confidence (0.7, 0.85, 0.9, 0.95).
3. Compute actual accuracy per group.
4. Adjust the per-rule confidence in `_regex_for_field` so the
   reported number matches the empirical accuracy.

This becomes important when you're routing low-confidence fields to
human review — the threshold has to mean something.

## Handle multi-page tables

Tables that span pages are out of scope for the simple regex line-by-
line approach. Two options:

1. **Use pdfplumber upstream** — it tracks table cells across pages
   and returns them as a single 2D array. Feed that into a custom
   extractor:

```python
import pdfplumber
def extract_invoice_tables(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = []
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
        return rows
```

2. **Use Azure Document Intelligence** — it has a dedicated invoice
   model that handles multi-page tables natively. Wire it as a
   custom backend (see above).

## Persist extracted data

The kit returns Python objects; it's storage-agnostic. Common
post-processing:

```python
import json
from dataclasses import asdict

result = extractor.extract(text, schema)
record = {
    "doc_id": pdf_path.name,
    "extracted_at": datetime.utcnow().isoformat(),
    "schema": result.schema,
    "fields": {k: asdict(v) for k, v in result.fields.items()},
    "coverage": result.coverage,
    "avg_confidence": result.avg_confidence,
}
# Insert into Postgres, Cosmos, Elastic, etc.
```

Confidence + coverage are the columns you'll want to filter on when
building a "needs human review" queue.
