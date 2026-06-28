"""CLI entry point - extract structured data from PDFs.

Usage:
    pdfkit extract <schema> <pdf-path>       # extract one document
    pdfkit demo                              # scripted run across all fixtures
    pdfkit list-schemas                      # show available schemas + fields
    pdfkit --json extract <schema> <path>    # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import schemas, pdf_reader
from .extractor import Extractor


def cmd_list_schemas(_args) -> int:
    print(f"Available schemas ({len(schemas.REGISTRY)}):\n")
    for name, sch in schemas.REGISTRY.items():
        print(f"  {name}  - {sch.description}")
        for f in sch.fields:
            req = "required" if f.required else "optional"
            print(f"    - {f.name:22s} {f.kind:8s} ({req})  {f.description}")
        print()
    return 0


def cmd_extract(args) -> int:
    schema = schemas.get(args.schema)
    text = pdf_reader.read_text(args.pdf_path)
    extractor = Extractor()
    result = extractor.extract(text, schema)

    out = {
        "schema": result.schema,
        "backend": result.backend,
        "coverage_required": round(result.coverage, 2),
        "avg_confidence": round(result.avg_confidence, 2),
        "fields": {k: asdict(v) for k, v in result.fields.items()},
    }
    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"\nExtraction result ({result.schema}, backend={result.backend}):")
    print(f"  Required-field coverage: {result.coverage:.0%}")
    print(f"  Avg confidence:          {result.avg_confidence:.2f}")
    print(f"\n  Fields:")
    for name, fr in result.fields.items():
        val_repr = json.dumps(fr.value, default=str) if fr.value is not None else "(missing)"
        if len(val_repr) > 80:
            val_repr = val_repr[:77] + "..."
        print(f"    {name:22s} {fr.confidence:>5.2f}  {val_repr}")
    return 0


def cmd_demo(args) -> int:
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    runs = [
        ("invoice", fixtures / "invoice-001.pdf"),
        ("invoice", fixtures / "invoice-002.pdf"),
        ("contract", fixtures / "contract-001.pdf"),
        ("contract", fixtures / "contract-002.pdf"),
        ("bank_statement", fixtures / "statement-001.pdf"),
        ("bank_statement", fixtures / "statement-002.pdf"),
    ]
    extractor = Extractor()
    results = []
    for schema_name, path in runs:
        schema = schemas.get(schema_name)
        try:
            text = pdf_reader.read_text(path)
        except FileNotFoundError as ex:
            print(f"  SKIP  {path.name} ({ex})")
            continue
        r = extractor.extract(text, schema)
        results.append({"schema": schema_name, "doc": path.name,
                        "coverage": r.coverage, "confidence": r.avg_confidence,
                        "fields": {k: asdict(v) for k, v in r.fields.items()}})
        if not args.json:
            print(f"\n[{schema_name}] {path.name}")
            print(f"  coverage: {r.coverage:.0%}  confidence: {r.avg_confidence:.2f}")
            for fname, fr in r.fields.items():
                if fr.value is not None:
                    v = json.dumps(fr.value, default=str)
                    if len(v) > 60:
                        v = v[:57] + "..."
                    print(f"    {fname:22s} {v}")

    if args.json:
        print(json.dumps({"backend": extractor.backend, "runs": results}, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PDF extraction kit CLI.")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-schemas")

    p_ext = sub.add_parser("extract")
    p_ext.add_argument("schema", choices=sorted(schemas.REGISTRY))
    p_ext.add_argument("pdf_path")

    sub.add_parser("demo")

    args = parser.parse_args(argv)
    handlers = {"list-schemas": cmd_list_schemas, "extract": cmd_extract, "demo": cmd_demo}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
