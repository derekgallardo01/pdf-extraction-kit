# Diagrams

GitHub renders Mermaid natively. These render on the README and in this file.

## End-to-end pipeline

```mermaid
flowchart LR
    P[PDF file] --> R["pdf_reader.read_text()"]
    R -- "fixture .txt available" --> T[Pre-extracted text]
    R -. "PDFKIT_PDF_READER=pypdf" .-> Y[pypdf parse]
    T --> E["Extractor.extract(text, schema)"]
    Y --> E
    E --> B{Backend?}
    B -- "regex (default)" --> RX[per-field regex rules]
    B -. "llm" .-> LL[Claude JSON extraction]
    RX --> O["ExtractionResult"]
    LL --> O
    O --> Q[Caller: store / display / human review queue]
```

## Per-field extraction shape

```mermaid
flowchart TB
    F["Field schema entry<br/>(name, kind, required, description)"]
    F --> R["regex rules per (schema, field)"]
    R --> M{Match in text?}
    M -- yes --> V["FieldResult(value, confidence ~0.95, evidence)"]
    M -- no --> N["FieldResult(value=None, confidence=0, evidence=None)"]
    V --> D[ExtractionResult.fields]
    N --> D
    D --> CV[coverage_pct = present/required]
    D --> CONF[avg_confidence = mean over non-null]
```

## Schema -> evaluation

```mermaid
sequenceDiagram
    participant CI as CI
    participant E as Extractor
    participant F as Fixture
    participant G as golden.json

    CI->>G: load cases
    loop each case
        G->>CI: fixture + schema + field + expected
        CI->>F: pdf_reader.read_text(fixture)
        F-->>CI: text
        CI->>E: extract(text, schema)
        E-->>CI: ExtractionResult
        CI->>CI: assert fields[field].value == expected
    end
    CI->>CI: print pass rate
    CI-->>CI: exit non-zero on any failure
```

## Backend swap (regex vs LLM)

```mermaid
flowchart TB
    subgraph Regex["regex backend (default)"]
        direction TB
        R1[text] --> R2[per-field regex routine]
        R2 --> R3[FieldResult with heuristic confidence]
    end

    subgraph LLM["llm backend"]
        direction TB
        L1[text] --> L2["build prompt(text, schema)"]
        L2 --> L3["Claude messages.create()"]
        L3 --> L4["parse JSON response"]
        L4 --> L5[FieldResult with LLM-reported confidence]
    end

    Regex -. "same ExtractionResult shape" .- LLM
```

The caller (CLI, eval harness, your own code) never knows which
backend produced the result.

## When to use the LLM backend

```mermaid
flowchart TB
    Q[Need to extract a field] --> A{Format consistent across docs?}
    A -- yes --> R[Write a regex rule]
    A -- no --> B{Single semantic meaning across formats?}
    B -- yes --> L[LLM backend - 1 prompt covers all]
    B -- no --> S[Subdivide into multiple fields by sub-type]
    R --> E[Regex backend; deterministic + free + CI-gated]
    L --> E2[LLM backend; per-page cost; flag for periodic re-eval]
    S --> R
```

## Repo shape

```mermaid
flowchart TB
    R[pdf-extraction-kit]
    R --> SRC[src/pdfkit/]
    SRC --> S1[schemas.py — declarative]
    SRC --> S2[extractor.py — backend + rules]
    SRC --> S3[pdf_reader.py — fixture / pypdf]
    SRC --> S4[cli.py — extract/demo/list-schemas]
    R --> FIX[fixtures/]
    FIX --> F1[invoice-001.pdf.txt + invoice-002.pdf.txt]
    FIX --> F2[contract-001.pdf.txt + contract-002.pdf.txt]
    FIX --> F3[statement-001.pdf.txt + statement-002.pdf.txt]
    R --> T[tests/]
    T --> T1[test_schemas.py]
    T --> T2[test_extractor.py]
    T --> T3[test_pdf_reader.py]
    R --> EV[evals/]
    EV --> EG[golden.json]
    EV --> ER[run.py]
    R --> DOCS[docs/]
    R --> CI[.github/workflows/ci.yml]
    R --> DK[Dockerfile]
```
