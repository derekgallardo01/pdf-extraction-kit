# Walkthrough

Step-by-step tour of what the kit does when you run `pdfkit demo`.

## Step 1: Read the PDF text

```python
from pdfkit import pdf_reader
text = pdf_reader.read_text("fixtures/invoice-001.pdf")
# Returns the contents of fixtures/invoice-001.pdf.txt (the fixture mode)
# OR the parsed text if PDFKIT_PDF_READER=pypdf is set
```

## Step 2: Pick a schema

```python
from pdfkit import schemas
schema = schemas.get("invoice")
# Returns the INVOICE Schema object with 11 fields declared
```

## Step 3: Extract

```python
from pdfkit.extractor import Extractor
extractor = Extractor()  # backend defaults to "regex"
result = extractor.extract(text, schema)
```

`result` is an `ExtractionResult`:

```python
ExtractionResult(
    schema="invoice",
    backend="regex",
    fields={
        "invoice_number": FieldResult(value="INV-2026-00482", confidence=0.95, evidence="Invoice #: INV-2026-00482"),
        "invoice_date":   FieldResult(value="2026-06-15", confidence=0.95, evidence="Invoice Date: 2026-06-15"),
        "due_date":       FieldResult(value="2026-07-15", confidence=0.95, evidence="Due Date: 2026-07-15"),
        "vendor_name":    FieldResult(value="Acme Widgets Ltd.", confidence=0.85, evidence="From: Acme Widgets Ltd."),
        ...
        "total":          FieldResult(value=922.80, confidence=0.95, evidence="Total: 922.80"),
        "currency":       FieldResult(value="GBP", confidence=0.95, evidence="GBP"),
        "line_items":     FieldResult(value=[...3 items...], confidence=0.7, evidence="3 line items"),
    },
)
```

Helpers:

```python
result.coverage           # 1.0 — all required fields got a value
result.avg_confidence     # 0.90 — mean over non-null fields
```

## Step 4: Use the result

In a real pipeline, you'd:

```python
import json
from dataclasses import asdict

record = {
    "doc_id": "invoice-001.pdf",
    "extracted_at": "2026-06-28T15:00:00Z",
    "schema": result.schema,
    "fields": {k: asdict(v) for k, v in result.fields.items()},
    "coverage": result.coverage,
    "avg_confidence": result.avg_confidence,
}

# Decide what to do:
if record["avg_confidence"] < 0.7:
    queue_for_human_review(record)
elif record["coverage"] < 1.0:
    queue_for_human_review(record, reason="missing required fields")
else:
    save_to_database(record)
```

That's the loop. Read PDF → extract → confidence-route → save or
review.

## Step 5: When the regex misses

Run `pdfkit extract <schema> <pdf>` on the failing doc:

```
$ pdfkit extract invoice fixtures/weird-invoice.pdf

Extraction result (invoice, backend=regex):
  Required-field coverage: 70%
  Avg confidence:          0.62

  Fields:
    invoice_number          0.95  "INV-99999"
    invoice_date            0.95  "2026-06-28"
    due_date                 0.00  (missing)      <-- the gap
    vendor_name              0.85  "Acme"
    bill_to_name              0.00  (missing)     <-- the gap
    total                    0.95  1234.56
```

Two paths:

1. **Add a regex variant.** Open the fixture text, see what label
   format the PDF uses for `due_date` and `bill_to_name`, add it to
   the labels list in `_regex_for_field`.

2. **Route those fields to the LLM backend.** Once `_extract_llm` is
   wired, switch the backend per-call or per-field and re-run.

Either way, **add an eval case for the new fixture** so this
regression doesn't come back.
