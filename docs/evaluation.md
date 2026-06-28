# Evaluation

CI gates on **exact extracted values**, not just on whether the code
runs. The eval suite asserts specific field values from specific
fixtures.

## What gets checked

Per [evals/golden.json](../evals/golden.json), each case asserts:

- **fixture** — which bundled file to read
- **schema** — which schema to extract against
- **field** — which field to check
- **expected_value** — the exact value the extractor should return

A case passes when `extracted == expected` (with a 0.01 float
tolerance). CI fails on anything less than 100%.

## Running

```bash
python evals/run.py
```

Output:

```
Running 12 eval cases against backend=regex

  PASS  invoice-001-total
  PASS  invoice-001-subtotal-not-total
  PASS  invoice-001-number
  PASS  invoice-002-currency
  PASS  invoice-002-grand-total
  PASS  contract-001-effective-date
  PASS  contract-001-term-months
  PASS  contract-002-notice-period
  PASS  statement-001-opening-balance
  PASS  statement-001-closing-balance
  PASS  statement-002-period-start
  PASS  statement-002-period-end

12/12 passed (100%)
```

Non-zero exit code if any case fails — so it works straight in CI.

## Adding a new eval case

Edit `evals/golden.json`:

```json
{
  "id": "your-new-case",
  "fixture": "your-fixture.pdf",
  "schema": "invoice",
  "field": "total",
  "expected_value": 1234.56
}
```

Re-run `python evals/run.py`. If it fails, either the extractor
needs a rule, or your expectation is wrong. Both are productive
investigations.

## Why exact-value asserts (vs structural checks)

A test that says "extracted `total` is a float" passes even when the
extractor returns the wrong float. That's the whole class of bugs
production PDF extraction hits — the **shape** is right, the
**value** is wrong, and you find out from a downstream complaint.

Exact-value asserts catch that at PR time. The case that wins on
this is `invoice-001-subtotal-not-total` — a check that the regex
for `total` doesn't accidentally pick up `subtotal`. That's the
exact bug pattern this kit had to fix during development, and the
eval prevents it from coming back.

## Why a separate eval suite (vs just tests)

Tests verify the extractor **code** (regex matches the patterns it
should, helpers parse dates correctly, etc.). Evals verify the
**output** (the extracted value for `total` on `invoice-001` is
922.80).

These move on different cadences:

- **Tests** change when you refactor the extractor's internals.
- **Evals** change when you change which fields you extract or what
  values you expect.

A change to `_find_date_after_label` should break test_extractor.py
if it's wrong. A change to "what counts as the canonical date format"
should break evals if the new format differs from the expected
output. Mixing them makes both noisier.

## Running evals against the LLM backend

Once `_extract_llm` is wired:

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-...
PDFKIT_EXTRACTOR=llm python evals/run.py
```

Expect a few flips — the LLM might return "2026-06-15" vs
"15 June 2026", or "INV-2026-00482" vs "Invoice 482". Use those
flips as the signal for:

- **Tighten the LLM prompt** — force a specific date format
- **Add a normaliser** — convert all extracted dates to ISO before comparing
- **Update the expected value** — the LLM is right; the regex's
  literal extraction was just one valid representation

This is the same loop you'd run before every production deploy of a
new prompt or model version.

## Eval coverage strategy

The 12 bundled cases hit:

- **Different label styles** — `Invoice #` vs `Invoice Number`,
  `Total` vs `Grand Total`, `From:` vs `Statement Period: From`
- **Easy-to-confuse pairs** — `total` vs `subtotal`, `period_start`
  vs `period_end`
- **All three schemas** — invoice, contract, bank statement
- **Different value types** — strings, dates, amounts, integers
- **Edge case fixtures** — the bank statement with combined
  "Period: From X To Y" label vs the one with separate labels

For your own engagement, add an eval case for **every field a
downstream system reads**. That's the only set guaranteed to catch
regressions before someone notices in production.

## Performance

The full eval suite runs in <100ms on the regex backend. Adding 100
more cases would still be under a second. The LLM backend will be
slower (~1-3 seconds per case) — expect to run it on PRs that touch
extraction, not on every push.
