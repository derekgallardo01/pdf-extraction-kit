"""Eval harness for the PDF extraction kit.

Runs every case in golden.json against the bundled fixtures and asserts
the exact extracted value matches. Default uses the regex backend so
results are deterministic and CI can gate on it.

Usage:
    python evals/run.py                       # uses regex backend
    PDFKIT_EXTRACTOR=llm python evals/run.py  # uses LLM backend (once wired)

Pass rate is printed at the end. Non-zero exit code if any case fails.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdfkit import schemas, pdf_reader  # noqa: E402
from pdfkit.extractor import Extractor  # noqa: E402


FIXTURES = ROOT / "fixtures"


def load_cases() -> list[dict]:
    with open(Path(__file__).parent / "golden.json") as f:
        return json.load(f)["cases"]


def run_case(extractor: Extractor, case: dict) -> dict:
    text = pdf_reader.read_text(FIXTURES / case["fixture"])
    schema = schemas.get(case["schema"])
    result = extractor.extract(text, schema)
    actual = result.fields[case["field"]].value
    expected = case["expected_value"]

    # Allow float fuzzy match (small rounding tolerance).
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        passed = abs(float(actual) - expected) < 0.01
    else:
        passed = actual == expected

    return {"id": case["id"], "passed": passed,
            "actual": actual, "expected": expected}


def main() -> int:
    cases = load_cases()
    extractor = Extractor()
    print(f"Running {len(cases)} eval cases against backend={extractor.backend}\n")

    results = [run_case(extractor, c) for c in cases]
    passed = sum(1 for r in results if r["passed"])

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}  {r['id']:40s}", end="")
        if not r["passed"]:
            print(f"\n        expected: {r['expected']!r}\n        actual:   {r['actual']!r}")
        else:
            print()

    rate = passed / len(cases) if cases else 0.0
    print(f"\n{passed}/{len(cases)} passed ({rate:.0%})")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
