# Legal Document Analyzer

A document-intelligence platform for **contract review**. It ingests legal documents
(contracts, NDAs, leases, employment agreements, procurement docs, insurance, policies,
ToS) and uses OCR, layout-aware parsing, and LLM analysis to produce structured, **cited**,
searchable intelligence: smart summaries, clause detection, risk flags, obligations,
entities, and grounded RAG Q&A.

> **Not legal advice.** Every AI-generated output is framed as *"this is what the document
> says,"* never *"this is what you should do,"* is grounded in a source citation, and carries
> a confidence score. This framing is a hard, product-wide requirement — see
> `../11-security-compliance.md` §8.

## Specifications

The authoritative product/technical spec lives in the **parent directory** (`../`), docs
`00`–`13`. Read order: `00` → `01` → `02` → `03`, then `04`–`12` as needed. The build
sequence is defined in `../13-roadmap-build-order.md`.

## Monorepo layout

```
legal-doc-analyzer/
├── backend/            FastAPI API + Arq workers + processing/AI pipelines
│   ├── app/
│   │   ├── api/v1/         HTTP routes (versioned under /api/v1)
│   │   ├── core/           config (Pydantic Settings), security
│   │   ├── db/             async SQLAlchemy engine/session, Base
│   │   ├── models/         SQLAlchemy ORM models (03-data-model.md)
│   │   ├── schemas/        Pydantic request/response + internal DTOs
│   │   ├── repositories/   org-scoped base repository pattern
│   │   ├── services/       business logic
│   │   ├── llm/            LLMProvider abstraction (Claude primary, OpenAI fallback)
│   │   ├── pipelines/
│   │   │   ├── ingestion/  upload→OCR→parse→chunk→embed→metadata (04-ingestion-pipeline.md)
│   │   │   └── ai/         clause→risk→summary→score (05-ai-pipeline.md)
│   │   ├── workers/        Arq worker entrypoints & task defs
│   │   └── utils/
│   ├── alembic/           migrations
│   └── tests/
└── frontend/           Next.js 15 (App Router) + Tailwind + shadcn/ui + TanStack Query
    └── src/{app,components,lib,hooks,types}
```

## Tech stack

- **Backend:** FastAPI · SQLAlchemy 2.0 (async) + Alembic · Arq · Pydantic v2 · PostgreSQL 16 · Redis 7 · Qdrant · S3/MinIO
- **Processing:** PaddleOCR (Tesseract fallback) · Docling (Unstructured fallback) · BGE-large embeddings + BGE reranker
- **LLM:** Claude (primary) / OpenAI (fallback) behind an `LLMProvider` interface; schema-constrained (tool-calling) output only
- **Frontend:** Next.js · TypeScript · Tailwind · shadcn/ui · TanStack Query · Recharts
- **Infra:** Docker Compose · Traefik · structlog · Sentry

See `../02-tech-stack.md` for the full list.

## Prerequisites

- Python **3.12+** and [uv](https://docs.astral.sh/uv/)
- Node **20+** and [pnpm](https://pnpm.io/) 9+
- Docker + Docker Compose (for the full stack: Postgres, Redis, Qdrant, MinIO)
- System libraries for processing: `libmagic`, `tesseract-ocr`, `poppler-utils` (provided in
  the worker image; needed locally only if running the pipeline outside Docker)

## Getting started

Nothing runs yet — this is the **repo skeleton** (dependency manifests, configs, env
templates). Application code, migrations, and Docker Compose land in the next steps
(Phase 0 in the roadmap).

```bash
# Backend deps (creates .venv + uv.lock)
cd backend && uv sync --extra dev            # add --extra processing for OCR/parse/embed

# Frontend deps
cd frontend && pnpm install
```

Copy the env templates before running anything:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

## Status

**Phase 0 — Project skeleton.** Current step: repo structure + tooling. Next: backend
foundation (config, DB session, health checks), the data model as SQLAlchemy models +
initial Alembic migration, Qdrant init, then the frontend shell and Docker Compose.
