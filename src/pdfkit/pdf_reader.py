"""PDF -> text reader, with a fixtures-based fallback for the demo.

Default path reads pre-extracted text fixtures (`.txt` next to each
`.pdf` in fixtures/). Set PDFKIT_PDF_READER=pypdf with `pip install -e ".[pdf]"`
to use the real pypdf reader against actual PDF binaries.

The fixtures-based default keeps the kit clone-and-runnable on any
machine without a PDF parser dependency, and keeps the eval suite
deterministic (no parser-version drift).
"""

from __future__ import annotations

import os
from pathlib import Path


def read_text(path: str | Path) -> str:
    """Return the text of a PDF.

    If a `<path>.txt` fixture exists next to the file, use that. This is
    the deterministic default - good for CI + Pages demos.

    If PDFKIT_PDF_READER=pypdf is set, use the real parser (requires
    `pip install -e ".[pdf]"`).
    """
    path = Path(path)
    txt_fixture = path.with_suffix(path.suffix + ".txt") if path.suffix else path.with_suffix(".txt")
    if not path.suffix:
        # Caller passed a stem - try .pdf.txt directly
        txt_fixture = path.with_suffix(".pdf.txt")

    if txt_fixture.exists():
        return txt_fixture.read_text(encoding="utf-8")

    if os.environ.get("PDFKIT_PDF_READER") == "pypdf":
        return _read_with_pypdf(path)

    raise FileNotFoundError(
        f"No text fixture found at {txt_fixture}. "
        f"Either provide the fixture or set PDFKIT_PDF_READER=pypdf "
        f"and install with `pip install -e \".[pdf]\"`."
    )


def _read_with_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as ex:
        raise RuntimeError(
            "pypdf is not installed. Run `pip install -e \".[pdf]\"` first."
        ) from ex
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
