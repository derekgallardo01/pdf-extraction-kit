# FAQ

## Is regex really good enough for real PDFs?

For about 80% of fields on well-formed business documents, yes.
Invoice numbers, dates, totals, party names — these are highly
patterned and regex handles them deterministically + free + at
scale.

For the other 20% (long-tail formats, scanned docs, unusual
layouts, semantic fields), you swap to the LLM backend. The kit is
designed so you can do this **per field**, not all-or-nothing.

The hybrid pattern is what production teams actually run: regex
first for speed and cost; LLM for the long tail. The kit just gives
you the eval harness to know which fields belong in which bucket.

## Why fixtures instead of real PDFs?

Three reasons:

1. **Determinism in CI.** Real PDFs from different parsers produce
   different text (different whitespace, occasional reordering).
   Fixtures eliminate that variance so the eval suite is reliable.
2. **No parser dependency.** The kit clone-and-runs without
   `pypdf`. The fixtures are the agreed-on "text the parser
   produces" — testing the extractor against them is testing the
   logic in isolation.
3. **Easy to add your own.** Drop a `<your-doc>.pdf.txt` file in
   `fixtures/`; reference it in the CLI or eval. No parser config
   needed.

If you want to run against real PDFs, set `PDFKIT_PDF_READER=pypdf`
and `pip install -e ".[pdf]"`. The kit uses `pypdf` then.

## Why not just use the Anthropic API directly?

Three reasons:

1. **Cost control.** Hitting Claude per page across a 10,000-PDF
   archive adds up. Regex first means you only pay for the long
   tail.
2. **Determinism for CI.** LLM responses vary across runs. You can't
   gate CI on exact extracted values with an LLM-only kit.
3. **No eval harness.** Most "Claude reads PDFs" examples skip the
   evaluation story entirely — you discover wrong extractions when
   downstream systems break. This kit's golden eval catches them
   before merge.

That said, the LLM backend IS the production target for hard
extractions. The kit is the **scaffold** that makes it safe to wire
the LLM in.

## How is this different from Azure Document Intelligence (Form Recognizer)?

Azure's hosted service is great for:

- **OCR + layout** — actual scanned documents with multi-page tables
- **Prebuilt models** — invoices, receipts, IDs out of the box
- **Multi-language** — handles 70+ languages

This kit is great for:

- **Custom schemas** — anything Azure doesn't have a prebuilt model
  for (contracts, internal documents, regulatory filings)
- **Cost** — runs locally; no per-page Azure billing
- **Determinism + CI gating** — Azure's responses change across model
  versions; this kit's regex backend doesn't
- **Customization speed** — add a field in 10 lines of Python; with
  Azure you'd need a custom model + training data

In practice, many production deployments use both: Azure for the
PDF-to-structured-text stage, this kit for the post-processing
(schema validation, custom fields, confidence-routing).

## Can I extract scanned PDFs?

Not directly — the kit operates on already-parsed text. For scanned
PDFs you need an OCR step upstream:

- **Tesseract** (free, local) — `tesseract input.pdf output.txt`
- **AWS Textract** (per-page billing, high quality)
- **Azure Document Intelligence** (per-page billing, layout-aware)
- **Anthropic vision** — pass the page as an image to Claude

Whichever you use, feed the resulting text into `pdf_reader.read_text()`
(via a fixture, or by adding a third reader mode) and the kit's
extraction works as normal.

## Why split schemas from extractor?

So a new schema is **declarative**:

```python
INVOICE = Schema(name="invoice", fields=[
    Field("invoice_number", "str"),
    Field("total", "amount", required=True),
    ...
])
```

That `Schema` object can be inspected, validated, listed in the CLI,
fed to an LLM prompt builder, and referenced in eval cases — all
without mentioning regex. The extractor logic for that schema
lives in a separate file.

This split is what makes the LLM swap clean: the LLM backend takes
the same `Schema` and produces the same `ExtractionResult` shape.
No backend-specific schema definitions to maintain in parallel.

## How do I handle multi-column or table-heavy invoices?

The kit's regex `_extract_line_items` handles pipe-delimited and
"qty x price = total" formats. For more complex tables:

1. Use `pdfplumber` upstream to convert tables to 2D arrays.
2. Write a custom line-items extractor that processes the 2D array.
3. Wire it into the `line_items` field in `_regex_for_field`.

```python
import pdfplumber

def extract_line_items_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = []
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table[1:])  # skip header
        return [{"description": r[0], "qty": int(r[1]),
                 "unit_price": float(r[2]), "line_total": float(r[3])}
                for r in rows if len(r) >= 4]
```

That function returns the same shape `_extract_line_items` returns,
so the rest of the kit doesn't change.

## How long until the LLM backend sketch is fully implemented?

Deliberately left as an exercise — about 30 lines of Anthropic SDK
glue. Implementing it would tie the kit to a specific SDK version
and a specific prompt strategy, both of which depend on what you're
extracting and how much accuracy you need.

The seam is one method. The shape it returns is documented in
`_extract_llm`'s docstring. Wire it once, evals tell you if the
prompt is right.

## Can I use this for production at high volume?

Yes for the regex backend — it's pure Python, runs in microseconds
per field, scales horizontally. Bottleneck will be the PDF parser
(pypdf or whatever), not the extractor.

For the LLM backend, follow Anthropic's batching guidance and use
the batch API for large jobs (50% discount on async work). The kit's
shape is per-document, but you can call it in a loop with
`concurrent.futures.ThreadPoolExecutor` or async wrappers without
changing the extractor.

## What's the cost story for the LLM backend?

Rough estimate at Claude Haiku prices (~$0.25/M input tokens):

- 1 invoice ≈ 1,500 tokens of input + 500 tokens output ≈ $0.0005 / invoice
- 10,000 invoices ≈ $5
- 1,000,000 invoices ≈ $500

For Opus (~$15/M input tokens) it's 60x that. Most production
deployments use Haiku for extraction (it's calibrated well for this
shape) and reserve Opus for genuinely hard semantic fields.
