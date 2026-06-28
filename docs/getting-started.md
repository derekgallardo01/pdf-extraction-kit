# Getting started

Five minutes to running extraction against your own PDFs.

## Install

```bash
git clone https://github.com/derekgallardo01/pdf-extraction-kit.git
cd pdf-extraction-kit
pip install -e .
```

Stdlib-only on the default path. Optional extras for real PDF parsing
(`pip install -e ".[pdf]"`) and the LLM backend (`pip install -e ".[llm]"`).

## Run the demo

```bash
pdfkit demo
```

Six bundled fixtures across three schemas (invoice, contract, bank
statement). For each one you'll see required-field coverage, average
per-field confidence, and the extracted values.

## Extract one document

```bash
pdfkit extract invoice fixtures/invoice-001.pdf
```

Outputs per-field value + confidence + evidence. Append `--json` for
the machine-readable shape.

## List the schemas

```bash
pdfkit list-schemas
```

Shows the three built-in schemas and which fields each one extracts
(required vs optional, plus a description).

## Run the tests

```bash
python -m pytest -q
```

23 tests across schemas, extractor rules, and the PDF reader. Stub
backend is deterministic — no network — runs in under a second.

## Run the evals

```bash
python evals/run.py
```

12 golden cases that assert the **exact** extracted value per fixture
per field. CI gates on a 100% pass rate. This is what catches "we
tweaked the regex and now `total` is the wrong number".

## Extract from a real PDF (not a fixture)

```bash
pip install -e ".[pdf]"
export PDFKIT_PDF_READER=pypdf
pdfkit extract invoice path/to/your-invoice.pdf
```

`pypdf` is the parser. If your invoices have unusual formatting, the
regex backend will miss fields — that's the cue to swap to the LLM
backend (next section) or add a fixture + rule for your format.

## Swap to the LLM backend

1. Install the optional extra:
   ```bash
   pip install -e ".[llm]"
   ```

2. Set your key:
   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export PDFKIT_EXTRACTOR=llm
   ```

3. Implement `_extract_llm` in [src/pdfkit/extractor.py](../src/pdfkit/extractor.py)
   per the docstring sketch — about 30 lines of glue against the
   Anthropic SDK. The kit's regex backend keeps working for fields
   the LLM can't handle, so you can roll out the LLM backend per-field
   if you want.

4. Re-run `pdfkit demo` or your real extractions — they'll now route
   through the LLM.

The tests stay green because they pin the backend to `regex` explicitly.

## Next steps

- [Architecture](architecture.md) — extractor design + backend seam
- [Customization](customization.md) — add a schema, field, or backend
- [Evaluation](evaluation.md) — gate CI on extraction accuracy
