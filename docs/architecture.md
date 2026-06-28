# Architecture

The kit is built around two ideas:

1. **Schemas declare what to extract** (separate from how to extract it).
2. **Backend decides how to extract it** (regex deterministic by default;
   LLM swap is one method).

## The pipeline

```
PDF file
    -> pdf_reader.read_text()      # fixture or pypdf
        -> raw text
        -> Extractor.extract(text, schema)
            -> _extract_regex(...)  OR  _extract_llm(...)
            -> per-field results: {value, confidence, evidence}
        -> ExtractionResult (coverage_pct, avg_confidence, fields)
```

Each component is testable in isolation:

- `pdf_reader` — tested with the fixtures (no real PDFs needed)
- `schemas` — tested as pure data
- `extractor` — tested against the fixtures across all three schemas

## Schemas

[src/pdfkit/schemas.py](../src/pdfkit/schemas.py) exports `Field`,
`Schema`, and a `REGISTRY` of built-in schemas. Each `Field` declares:

- **name** — key in the output dict
- **kind** — `str | number | date | amount | list`
- **required** — whether the eval should fail when missing
- **description** — used in LLM prompts and the `list-schemas` output

Schemas are intentionally **flat dicts of typed fields**, not nested
trees. That matches what 90% of real-world extraction asks for and
keeps the eval surface tight (per-field assertions). For nested
hierarchies, use a list-valued field (e.g., `line_items` in invoices).

## The backend seam

```python
def extract(self, text, schema):
    if self.backend == "llm":
        return self._extract_llm(text, schema)
    return self._extract_regex(text, schema)
```

Both backends return the same `ExtractionResult` shape:

```python
ExtractionResult(
    schema="invoice",
    backend="regex",
    fields={
        "invoice_number": FieldResult(value="INV-2026-00482",
                                       confidence=0.95,
                                       evidence="Invoice #: INV-2026-00482"),
        ...
    },
)
```

Downstream code — the CLI, the eval harness, the Pages demo, your
own callers — never needs to know which backend produced the result.

### Why regex by default?

Three reasons:

1. **Deterministic CI.** The eval harness asserts **exact** extracted
   values. An LLM backend can't promise that across runs; regex can.
2. **Zero cost / zero keys.** Reviewers can clone-and-run in 60
   seconds. No `ANTHROPIC_API_KEY` blocker; no Azure setup.
3. **Forces good schema design.** If your regex can't extract the field
   reliably, that's the signal the field is poorly specified — fix the
   spec, not the LLM prompt.

### When to swap to LLM

- Document layouts vary too much for regex (scanned, OCR'd, multi-
  language)
- The field is semantic, not syntactic ("is this clause unusual?")
- You're hitting a long tail of edge cases that aren't worth a regex
  each

The kit makes this swap painless because the **shape doesn't change**.
Run the regex backend on the 80% of fields where it's accurate; route
the remaining 20% to the LLM backend; keep the same evals catching
regressions on both.

## Confidence scoring

The regex backend assigns confidence heuristically:

- **0.95** — clean labelled match (`"Invoice #: INV-..."`)
- **0.85-0.90** — soft match (e.g., `vendor_name` from "From:" line)
- **0.7-0.8** — composite extractions (line items, transactions)
- **0.0** — missing

The numbers are deliberately suggestive, not statistically calibrated.
Their job is to surface "this needs human review" to the caller. The
LLM backend should overwrite these with its own probabilities or
log-likelihood-derived scores.

## Evidence tracking

Each `FieldResult.evidence` is the substring of the source text that
produced the value. Two reasons it matters:

1. **Audit trail.** If someone asks "why does this invoice show $922?",
   you can point at "Total: 922.80" in the source.
2. **Debugging.** When a field comes out wrong, evidence tells you
   whether the regex matched the wrong place or just parsed
   incorrectly.

## Coverage

`ExtractionResult.coverage` is the fraction of **required** fields
that got a non-null value. The eval harness uses it as a quick health
check across many documents — you want this at or near 100% for the
fixtures you support. Drops indicate either:

- A regex needs updating for a new document variant
- A field should be marked `required=False` (your spec was over-strict)
- The LLM backend needs to take that field

## The PDF reader

`pdf_reader.read_text(path)` has two modes:

- **Fixture mode (default)** — looks for `<path>.txt` next to the PDF.
  Used by the kit's bundled fixtures, CI, and Pages demo. Deterministic
  and parser-free.
- **pypdf mode (`PDFKIT_PDF_READER=pypdf`)** — uses the `pypdf`
  library to extract text from real PDF binaries.

This split is on purpose. You can build, test, and CI the kit's
extraction logic without ever installing a PDF parser. Then you swap
to `pypdf` (or your preferred parser) for the production path.

## What's deliberately NOT in the kit

- **PDF OCR** — for scanned documents you need `tesseract` or a cloud
  OCR API. Out of scope; runs upstream of the kit.
- **Layout-aware parsing** — for tables that span pages or complex
  layouts, use `pdfplumber` or Azure Document Intelligence upstream
  and feed the structured output to this kit.
- **Form-field extraction** — for PDFs with actual AcroForm fields,
  `pypdf.get_fields()` gives you the values directly, no extraction
  needed.

The kit is the regex/LLM layer that converts **already-parsed text**
into typed fields. Pair it with whichever parser fits your input.
