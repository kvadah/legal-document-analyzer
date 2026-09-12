# Legal Document Analyzer

A multi-tenant contract intelligence platform. Upload legal documents, run them through an OCR → parsing → embedding pipeline, get AI-powered clause and risk analysis with citation-grounded navigation, search across your entire corpus, ask grounded questions with cited answers, compare contract versions word-by-word, and export professional analysis reports.

> **Disclaimer:** This platform provides document analysis tools, not legal advice. All AI-generated output must be reviewed by qualified legal professionals.

---

## Features

### Multi-Tenant Security
- Organization-scoped tenancy with strict data isolation, verified by explicit cross-tenant tests
- JWT authentication with httpOnly refresh-token cookies (access tokens kept in memory only)
- Role-based access control — **admin**, **reviewer**, and **viewer** roles enforced across every endpoint
- Org-scoped repository pattern ensuring no query can leak data across tenants

### Document Ingestion
- Multipart single/batch upload with drag-and-drop UI and live status badges
- Object storage (S3/MinIO) with local-filesystem fallback
- Content validation, magic-byte sniffing, and SHA-256 deduplication
- OCR via PaddleOCR (primary) with Tesseract fallback, plus skip-if-text-layer detection for native PDFs
- Structural parsing → intelligent chunking → embedding generation → vector store indexing
- Status state machine with Redis pub/sub and server-sent event streaming for live progress

### AI-Powered Analysis
- Provider-abstracted LLM layer (Gemini, Claude, OpenAI) — switching providers is a config change, not a code change; mock providers let the full pipeline run in tests and keyless dev without external APIs
- Metadata extraction: parties, dates, financial terms, governing law, and more
- Clause detection across all tracked clause types, with confidence scores and not-found tracking
- Risk detection combining deterministic rule-based checks with LLM judgment
- Contract Score and AI Confidence Score with a transparent risk-deduction breakdown
- Persistent AI disclaimers and low-confidence warnings throughout the UI

### Analysis Workspace
- Split-pane document viewer with page-by-page navigation
- **Summary** — score rings, parties, key fields, top risks
- **Clauses** — per-clause cards with confidence, summary, and expandable source text
- **Risks** — severity-sorted cards with triage controls (flagged / acknowledged / dismissed)
- **Obligations** — timeline view with deadlines and status badges
- **Entities** — grouped by type, click-to-navigate to source occurrences
- **Q&A** — streaming chat grounded in the document (see below)
- Shared `CitationLink` component: every citation, in any tab, jumps the viewer to the exact page and highlights the anchor text

### Search
- Keyword, semantic, and hybrid search (merged with Reciprocal Rank Fusion)
- Results grouped by document with highlighted snippets and source badges
- Filters: document type, date range, document
- Deep-links from results directly into the Analysis viewer at the matched page

### Grounded Q&A
- **Single-document** (`/documents/{id}/ask`): streaming answers with sentence-level citations, multi-turn conversation history, and grounding validation — citations whose quotes aren't verbatim in the source are dropped
- **Cross-document** (`/ask`): ask questions across the entire org corpus or a selected subset; answers attribute each point to the document it came from
- Similarity threshold check *before* the LLM call — un-groundable questions get an honest "couldn't find it" instead of a hallucination
- Non-advisory framing: requests for legal advice are declined with an explanation

### Clause Comparison
- Compare any two analyzed documents side by side
- Clauses aligned by type, then by textual similarity; classified as **added / removed / modified / unchanged**
- Server-computed word-level diffs rendered with color-coded highlights
- "Other Changes" catches edits outside tracked clause types without double-reporting
- Async job pipeline with live polling; side-by-side and unified view modes

### Relationships & Versioning
- Link related documents — amendments, exhibits, related agreements, supersessions
- System-inferred relationship suggestions (from cross-references in document text) that require user confirmation — never created silently
- Version-aware upload: new uploads can be registered as versions of existing documents
- Version history panel with one-click "compare to previous version" routing into the Comparison view
- Every version retains its own complete analysis history for auditability

### Export
- Analysis reports as **PDF**, **DOCX**, or **JSON**, each carrying the persistent AI disclaimer
- Download directly from the Analysis view header

### Administration
- Member management: invite, role changes, deactivate/reactivate — with self-lockout prevention
- Usage dashboard: document, analysis, and storage stats, upload trends, pipeline health
- Deactivated members are locked out immediately at login and token refresh

### Portfolio Dashboard
- Portfolio-wide risk, score, and obligation trend views across all contracts

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│  Next.js UI │────▶│                 FastAPI API                  │
│  (port 3000)│     │  auth · documents · analysis · search · Q&A  │
└─────────────┘     │  compare · relationships · export · admin    │
                    └──────┬───────────┬───────────┬───────────────┘
                           │           │           │
                    ┌──────▼───┐ ┌─────▼────┐ ┌────▼─────┐
                    │ Postgres │ │  Redis   │ │  MinIO   │
                    │  (data)  │ │ queue/   │ │  (files) │
                    └──────────┘ │ pub-sub  │ └──────────┘
                                 └─────┬────┘
                          ┌────────────▼────────────┐
                          │   Arq Worker            │
                          │   OCR · parsing · AI    │
                          │   pipeline · comparison │
                          └────┬───────────────┬────┘
                               │               │
                        ┌──────▼─────┐  ┌──────▼──────┐
                        │  Qdrant    │  │ LLM Provider │
                        │ (vectors)  │  │ (embeddings) │
                        └────────────┘  └─────────────┘
```

| Service | Technology | Role |
|---|---|---|
| API | FastAPI (Python 3.12) | REST API, auth, orchestration |
| Worker | FastAPI + Arq | Async ingestion & AI pipelines, comparison jobs |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS | Analysis workspace, search, admin |
| Database | PostgreSQL 16 | Documents, analyses, users, relationships |
| Vector Store | Qdrant | Chunk embeddings for semantic search & RAG |
| Cache / Queue | Redis 7 | Job queue, pub/sub, Q&A conversation history |
| Object Storage | MinIO (S3-compatible) | Original files, exports |

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Start the stack

```bash
cd legal-doc-analyzer
docker compose up -d --build
```

Verify the services are healthy:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Then register a new organization and admin user at [http://localhost:3000/register](http://localhost:3000/register).

### Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Application UI |
| API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| MinIO Console | http://localhost:9001 | Object storage browser |
| Qdrant | http://localhost:6333/dashboard | Vector DB dashboard |

### Default Credentials

| Service | Credentials |
|---|---|
| MinIO | `minioadmin` / `minioadmin` |
| PostgreSQL | `postgres` / `postgres` (internal) |
| Application | Self-register at `/register` |

---

## Configuration

All configuration lives in `.env` at the repository root. Key settings:

| Variable | Purpose |
|---|---|
| `DEFAULT_LLM_PROVIDER` | `gemini` \| `anthropic` \| `openai` |
| `GEMINI_LLM_MODEL` / `GEMINI_LLM_FAST_MODEL` | Gemini model names (use the `gemini-3.x` family — `2.5-*` is unavailable to recent keys) |
| `MOCK_LLM` / `MOCK_EMBEDDINGS` | Set `true` to run the full pipeline without any API keys |
| `VECTOR_SEARCH_BACKEND` | `qdrant` (default) or `memory` for keyless dev/tests |

The LLM provider abstraction means switching from the interim Gemini free-tier setup to Claude or OpenAI is a config change only.

---

## Testing

Backend tests run against SQLite with mock LLM/embeddings and local storage — no external services or API keys required:

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
pnpm test          # unit tests (vitest)
pnpm type-check    # tsc --noEmit
pnpm lint
pnpm test:e2e      # end-to-end (playwright)
```

The test suite covers the auth lifecycle, RBAC enforcement, explicit cross-tenant isolation, the ingestion and AI pipelines, search and grounded Q&A, clause comparison, document relationships, and versioning.

---

## Project Structure

```
legal-doc-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # Route handlers (auth, documents, analysis,
│   │   │                      #   search, compare, relationships, exports)
│   │   ├── core/              # Config, security, dependencies
│   │   ├── db/                # Session management, Qdrant init
│   │   ├── llm/               # LLM provider abstraction + prompts
│   │   ├── models/            # SQLAlchemy models
│   │   ├── pipelines/         # Ingestion, AI analysis, comparison
│   │   ├── providers/         # Embedding providers
│   │   ├── repositories/      # Org-scoped data access layer
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic (search, Q&A, export, ...)
│   │   └── workers/           # Arq background jobs
│   ├── alembic/               # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/               # App Router pages (contracts, upload, search,
│       │                      #   ask, compare, reports, admin, documents/[id])
│       ├── components/        # Analysis view, layout, shared UI
│       ├── context/           # Auth context
│       └── lib/               # API client, formatting helpers
└── docker-compose.yml
```

---

## Database Schema

All tables use UUID primary keys, `created_at`/`updated_at` timestamps, foreign keys, and indexes on hot query paths. Every tenant-owned table is scoped by `organization_id`.

| Table | Purpose |
|---|---|
| `organizations` | Tenant scoping |
| `users` | Accounts, roles, activation state |
| `documents` | Document metadata, status, scores, storage paths |
| `document_versions` | Version history |
| `document_relationships` | Links between related documents |
| `chunks` | Text chunks backing the viewer and search |
| `clauses` | Detected clauses with citations |
| `risks` | Risk flags with severity and triage state |
| `entities` | Extracted entities (companies, dates, money, ...) |
| `obligations` | Timeline items and deadlines |
| `document_summaries` | AI-generated summaries |
| `comparisons` | Structured comparison results |
| `comments` | Review comments (schema in place, UI in development) |

---

## Roadmap

### Shipped
- Multi-tenant auth, RBAC, and data isolation
- Ingestion pipeline: upload, validation, dedup, OCR, parsing, chunking, embeddings
- AI analysis: metadata, clauses, risks, scores, summaries
- Analysis workspace with citation-grounded navigation
- Hybrid search across the corpus
- Grounded Q&A — single-document and cross-document
- Clause comparison with word-level diffs
- Document relationships (with inference suggestions) and versioning
- Export to PDF / DOCX / JSON
- Administration: user management, usage dashboard
- Portfolio dashboard

### In Development
- **Reports** — server-generated portfolio risk reports and obligation calendar reports (background job generation, stored outputs); Excel export format

### Planned
- **Collaboration** — threaded review comments (document- and page-scoped, with resolution workflow) and text annotations with configurable highlight colors rendered as viewer overlays
- **Administration & hardening** — audit logging across all action types, data retention with soft-delete/hard-delete jobs, API rate limiting, systematic RBAC verification across every endpoint
- **Deployment hardening** — CI/CD pipeline, structured logging and error tracking, metrics endpoint, backup restore drills, load testing of the ingestion pipeline

See the [build roadmap](../13-roadmap-build-order.md) for the full plan and acceptance criteria.

---

## Troubleshooting

### Services fail to start
- Ensure Docker is running: `docker ps`
- Check port availability: `lsof -i :3000,8000,5432,6379,6333,9000`
- View logs: `docker compose logs <service>`

### Containers stuck in "Created"
The `api`, `worker`, and `frontend` services wait for `postgres`/`redis`/`qdrant`/`minio` to be healthy. If a dependency is `unhealthy`, they never start:

```bash
docker ps -a    # look for (unhealthy) containers
docker compose up -d <unhealthy-service>   # recreate it
docker compose up -d                       # then bring up the rest
```

### Container unhealthy but the service inside is fine
Current `qdrant` and `python:3.12-slim` images ship glibc 2.41, where `localhost` resolution is unreliable under Docker Desktop/WSL2. Healthchecks in this repo use the `127.0.0.1` literal — keep it that way when adding new healthchecks.

### Postgres takes minutes to start ("automatic recovery in progress")
This follows an unclean shutdown (killing Docker Desktop, hard reboot). Postgres crash recovery is slow on the WSL2 filesystem; the healthcheck allows 120s for it. Shut down cleanly to avoid it: `docker compose down` rather than Ctrl-C or quitting Docker Desktop mid-write.

### Every rebuild re-downloads dependencies
The backend Dockerfiles install dependencies from `pyproject.toml` *before* copying source, with a BuildKit pip cache mount — code-only changes rebuild in seconds. Never move `COPY . .` above the dependency-install layer.

### Gemini 429 / quota errors
The interim LLM is Gemini on a free-tier key (~20 requests/day/model). The pipeline batches LLM calls (~6 per document) and the provider retries with server-advertised delays plus a configurable request interval (`GEMINI_MIN_REQUEST_INTERVAL`). If quota is exhausted: wait for the daily reset and retry the document (`POST /documents/{id}/retry`), point `GEMINI_LLM_MODEL` at a model with remaining quota, or switch providers (`DEFAULT_LLM_PROVIDER=anthropic|openai`).

### Frontend issues
- Clear the Next.js cache: `rm -rf frontend/.next`
- `next build` runs ESLint by default — run `pnpm lint` locally before rebuilding Docker

---

## Documentation

- [Project overview](../00-overview.md) — product scope and MVP definition
- [Architecture](../01-architecture.md) — system design
- [Tech stack](../02-tech-stack.md) — technology choices
- [Data model](../03-data-model.md) — schema specification
- [Ingestion pipeline](../04-ingestion-pipeline.md) — upload → OCR → chunking → embeddings
- [AI pipeline](../05-ai-pipeline.md) — extraction, clause/risk detection, scoring
- [Analysis features](../06-feature-spec-analysis.md) — analysis workspace specification
- [Comparison & search](../07-feature-spec-comparison-search.md) — diff engine, search, RAG Q&A
- [Collaboration features](../08-feature-spec-collaboration.md) — relationships, versioning, comments, annotations
- [API specification](../09-api-spec.md) — endpoint reference
- [Frontend specification](../10-frontend-spec.md) — UI specification
- [Security & compliance](../11-security-compliance.md) — RBAC, tenancy, disclaimers
- [Deployment](../12-deployment-infra.md) — infrastructure guide
- [Build roadmap](../13-roadmap-build-order.md) — sequencing and acceptance criteria

---

## License

Proprietary — see LICENSE file.
