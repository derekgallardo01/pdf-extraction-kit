"""PDF extraction kit - structured data from messy real-world PDFs.

Default backend is a regex-based stub so the kit runs anywhere without
keys or a PDF parser dependency. Set PDFKIT_EXTRACTOR=llm (with
ANTHROPIC_API_KEY) to route extraction through Claude.
"""
__version__ = "1.0.0"
