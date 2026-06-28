"""Batch-process a directory of invoices into a structured CSV/JSON report.

The shape of the common Upwork ask: "We have a folder of PDF invoices.
Get them into a spreadsheet."

This script:
  1. Walks a directory of invoice PDFs (or .pdf.txt fixtures)
  2. Extracts each with the invoice schema
  3. Routes low-confidence extractions to a review queue
  4. Writes a CSV of cleanly-extracted invoices
  5. Writes a separate JSON of items needing review
  6. Prints a summary: total extracted $, total in review queue, by vendor

Default runs against the bundled fixtures (invoice-001.pdf, invoice-002.pdf).
Point --input at your own directory to process real invoices.

Usage:
    python examples/batch_invoice_processor.py
    python examples/batch_invoice_processor.py --input ./invoices --csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfkit import schemas, pdf_reader  # noqa: E402
from pdfkit.extractor import Extractor  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Confidence threshold for "needs review" vs "auto-process"
REVIEW_THRESHOLD = 0.85
# Coverage threshold for "needs review" vs "auto-process"
COVERAGE_THRESHOLD = 0.90


def process_directory(input_dir: Path, schema_name: str = "invoice") -> dict:
    """Extract every PDF/text file in input_dir. Returns clean + review buckets."""
    extractor = Extractor()
    schema = schemas.get(schema_name)

    files = sorted(
        list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.pdf.txt"))
    )
    # Deduplicate: if both invoice-001.pdf and invoice-001.pdf.txt exist, prefer
    # the .pdf (the reader fixture-falls-back automatically).
    seen_stems = set()
    deduped = []
    for f in files:
        stem = f.name.replace(".pdf.txt", ".pdf")
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        # Re-point .pdf.txt files at the synthetic .pdf path so the reader uses the fixture
        if f.suffix == ".txt":
            f = f.parent / stem
        deduped.append(f)

    clean: list[dict] = []
    review: list[dict] = []

    for pdf_path in deduped:
        try:
            text = pdf_reader.read_text(pdf_path)
        except FileNotFoundError as ex:
            review.append({"file": pdf_path.name,
                           "reason": f"unreadable: {ex}",
                           "fields": {}})
            continue

        result = extractor.extract(text, schema)
        record = {
            "file": pdf_path.name,
            "coverage": result.coverage,
            "avg_confidence": result.avg_confidence,
            "fields": {k: v.value for k, v in result.fields.items()},
        }

        if (result.coverage < COVERAGE_THRESHOLD or
            result.avg_confidence < REVIEW_THRESHOLD):
            record["reason"] = (
                f"coverage={result.coverage:.0%} (<{int(COVERAGE_THRESHOLD * 100)}%) "
                f"or confidence={result.avg_confidence:.2f} (<{REVIEW_THRESHOLD})"
            )
            review.append(record)
        else:
            clean.append(record)

    return {"clean": clean, "review": review}


def write_csv(records: list[dict], path: Path) -> None:
    """Write clean records to a flat CSV."""
    if not records:
        path.write_text("")
        return
    # Use the keys from the first record (all have the same schema)
    field_names = list(records[0]["fields"].keys())
    headers = ["file", "coverage", "avg_confidence"] + field_names
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in records:
            row = [r["file"], f"{r['coverage']:.2f}", f"{r['avg_confidence']:.2f}"]
            for fld in field_names:
                v = r["fields"].get(fld)
                # Stringify lists / dicts
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                row.append(v if v is not None else "")
            writer.writerow(row)


def write_review_queue(records: list[dict], path: Path) -> None:
    """Write the review queue as JSON (richer than CSV for review UIs)."""
    path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def summarize(buckets: dict) -> dict:
    """Build a short summary of the run."""
    total = len(buckets["clean"]) + len(buckets["review"])

    by_vendor: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_amount": 0.0})
    sum_clean = 0.0
    sum_review = 0.0
    for r in buckets["clean"]:
        vendor = r["fields"].get("vendor_name") or "(unknown)"
        amount = r["fields"].get("total") or 0
        by_vendor[vendor]["count"] += 1
        by_vendor[vendor]["total_amount"] += float(amount)
        sum_clean += float(amount)
    for r in buckets["review"]:
        amount = r["fields"].get("total") or 0
        try:
            sum_review += float(amount)
        except (TypeError, ValueError):
            pass

    return {
        "total_files": total,
        "auto_processed": len(buckets["clean"]),
        "needs_review": len(buckets["review"]),
        "total_amount_auto": round(sum_clean, 2),
        "total_amount_in_review": round(sum_review, 2),
        "by_vendor": {v: {"count": d["count"], "total": round(d["total_amount"], 2)}
                       for v, d in by_vendor.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch invoice extraction -> CSV + review queue.")
    parser.add_argument("--input", default=str(FIXTURES),
                        help="Directory of PDF / .pdf.txt files. Default: bundled fixtures.")
    parser.add_argument("--csv", default="invoices.csv",
                        help="Where to write the clean-records CSV.")
    parser.add_argument("--review", default="invoices-review.json",
                        help="Where to write the review-queue JSON.")
    parser.add_argument("--summary-only", action="store_true",
                        help="Skip the CSV/JSON output; only print the summary.")
    args = parser.parse_args(argv)

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"Input directory {input_dir} not found.", file=sys.stderr)
        return 1

    print(f"Processing invoices from {input_dir}...\n")
    buckets = process_directory(input_dir)
    summary = summarize(buckets)

    print(f"Files processed:    {summary['total_files']}")
    print(f"  Auto-processed:   {summary['auto_processed']}")
    print(f"  Needs review:     {summary['needs_review']}")
    print(f"\n  Total $ auto:      ${summary['total_amount_auto']:,.2f}")
    print(f"  Total $ in review: ${summary['total_amount_in_review']:,.2f}")
    print(f"\n  By vendor:")
    for vendor, data in sorted(summary["by_vendor"].items(),
                                key=lambda kv: -kv[1]["total"]):
        print(f"    {vendor:30s}  count={data['count']:>3d}  total=${data['total']:,.2f}")

    if not args.summary_only:
        csv_path = Path(args.csv)
        review_path = Path(args.review)
        write_csv(buckets["clean"], csv_path)
        write_review_queue(buckets["review"], review_path)
        print(f"\nWrote {len(buckets['clean'])} clean records to {csv_path}")
        print(f"Wrote {len(buckets['review'])} review records to {review_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
