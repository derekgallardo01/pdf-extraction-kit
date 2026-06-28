# Changelog

Notable changes to the PDF extraction kit. Dates are when the change
landed on `main`.

## 2026-06-28 — Initial public release (v1.0.0)
- `schemas.py` — declarative `Schema` + `Field` types + 3 built-in
  schemas (invoice, contract, bank statement) with typed fields
- `extractor.py` — schema-driven regex backend with per-field
  confidence + evidence; documented LLM backend swap point
- `pdf_reader.py` — fixture-based reader by default; `pypdf` fallback
  via `PDFKIT_PDF_READER=pypdf`
- `cli.py` — `pdfkit extract`, `pdfkit demo`, `pdfkit list-schemas`,
  with `--json` for machine-readable output
- 6 bundled fixtures (2 per schema) with varied label formats and
  layouts so the extractor's robustness is exercised
- 23 pytest tests (schemas + extractor + reader)
- 12 golden eval cases asserting exact extracted values; CI gates on
  100% pass
- CI on Python 3.10/3.11/3.12 (tests + evals + CLI smoke)
- `pyproject.toml` with `[pdf]` (pypdf) and `[llm]` (anthropic)
  optional extras
- Docs trio: `getting-started`, `architecture`, `customization`,
  `evaluation`, `diagrams`, `faq`
- OSS niceties: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`,
  `CITATION.cff`, `.editorconfig`, `.devcontainer/devcontainer.json`,
  `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/dependabot.yml`
- `Dockerfile`, `pages.yml` (live demo with confidence-coloured
  field table per fixture), `screenshots.yml`, `portfolio.yml`
- README badges: CI + License (MIT) + Python (3.10+) + Open in
  Codespaces
- Theme: teal (extraction / data)
