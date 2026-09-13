# Legal Doc AI

A multi-tenant contract intelligence platform. Upload legal documents, run them through an OCR → parsing → embedding pipeline, get AI-powered clause and risk analysis with citation-grounded navigation, search your entire corpus, ask grounded questions with cited answers, compare contract versions word-by-word, and export professional reports.

> **Disclaimer:** This platform provides document analysis tools, not legal advice. All AI-generated output must be reviewed by qualified legal professionals.

---

## Highlights

- **Citation-grounded AI analysis** — every clause, risk, and answer links back to the exact page and highlighted text in the source document
- **Grounded Q&A, not hallucination** — answers stream with sentence-level citations; citations whose quotes aren't verbatim in the source are dropped, and un-groundable questions get an honest "couldn't find it"
- **Multi-tenant by design** — organization-scoped data isolation with role-based access control, verified by an explicit cross-tenant test suite
- **Provider-agnostic LLM layer** — Gemini, Claude, or OpenAI behind one abstraction; switching providers is a config change, not a code change
- **Runs keyless** — mock LLM/embedding providers let the entire pipeline run in development and CI without external API keys

---

## Features

### Document Ingestion
- Drag-and-drop single/batch upload with live pipeline status streaming (SSE)
- Object storage (S3/MinIO) with local-filesystem fallback
- Content validation, magic-byte sniffing, and SHA-256 deduplication
- OCR (PaddleOCR primary, Tesseract fallback) with skip-if-text-layer detection for native PDFs
- Structural parsing → intelligent chunking → embedding generation → vector indexing

### AI-Powered Analysis
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
- **Comments** — threaded review discussion with a resolution workflow
- **Q&A** — streaming chat grounded in the document; the conversation persists across tab switches and page revisits
- Every citation, in any tab, jumps the viewer to the exact page and highlights the anchor text
- Responsive from phone to ultrawide

### Search
- Keyword, semantic, and hybrid search (merged with Reciprocal Rank Fusion)
- Results grouped by document with highlighted snippets and source badges
- Filters: document type, date range, specific documents
- Deep-links from results directly into the viewer at the matched page

### Grounded Q&A
- **Single-document**: streaming answers with sentence-level citations and multi-turn conversation history
- **Cross-document**: ask across the entire corpus or a selected subset; answers attribute each point to the document it came from and surface conflicting terms rather than blending them
- Similarity threshold checked *before* the LLM call — un-groundable questions get "couldn't find it" instead of a hallucination
- Non-advisory framing: requests for legal advice are declined with an explanation

### Clause Comparison
- Compare any two analyzed documents side by side
- Clauses aligned by type, then by textual similarity; classified as **added / removed / modified / unchanged**
- Server-computed word-level diffs rendered with color-coded highlights
- "Other Changes" catches edits outside tracked clause types without double-reporting
- Async job pipeline with live polling; side-by-side and unified view modes

### Relationships & Versioning
- Link related documents — amendments, exhibits, related agreements, supersessions
- System-inferred relationship suggestions that require user confirmation — never created silently
- Version-aware upload: every version retains its own complete analysis history for auditability
- One-click "compare to previous version" routing into the Comparison view

### Collaboration
- Threaded review comments, document-scoped or page-anchored, with resolve/reopen workflow
- Text-highlight annotations with configurable colors and optional notes, rendered inline in the viewer
- Annotations panel filterable by color and author, with click-to-navigate
- Viewer-role members participate read-only

### Reports & Export
- **Portfolio Risk Report**: risk counts by type/severity, score distribution, critical-risk focus list
- **Obligation Calendar Report**: all obligations bucketed into overdue / due soon / upcoming
- Async generation with status polling; export as **XLSX**, **PDF**, **DOCX**, or **JSON**
- Single-document analysis export as **PDF**, **DOCX**, or **JSON** from the Analysis view

### Administration
- Member management: invite, inline role changes, deactivate/reactivate, with self-lockout prevention
- Usage dashboard: document, analysis, and storage stats, upload trends, pipeline health
- Deactivated members are locked out immediately at login and token refresh

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│  Next.js UI │────▶│                 FastAPI API                  │
│  (port 3000)│     │  auth · documents · analysis · search · Q&A  │
└─────────────┘     │  compare · relationships · collaboration     │
                    │  reports · export · admin                    │
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
| Worker | FastAPI + Arq | Async ingestion & AI pipelines, comparison and report jobs |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS | Analysis workspace, search, admin |
| Database | PostgreSQL 16 | Documents, analyses, users, relationships |
| Vector Store | Qdrant | Chunk embeddings for semantic search & RAG |
| Cache / Queue | Redis 7 | Job queue, pub/sub, Q&A conversation history |
| Object Storage | MinIO (S3-compatible) | Original files, exports, reports |

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- An LLM API key (Gemini, Anthropic, or OpenAI) — or run keyless with mock providers (see [Configuration](#configuration))

### Start the stack

```bash
git clone <repository-url>
cd legal-doc-analyzer
cp .env.example .env   # add your API keys
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

All configuration lives in `.env`. Key settings:

| Variable | Purpose |
|---|---|
| `DEFAULT_LLM_PROVIDER` | `gemini` \| `anthropic` \| `openai` |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Provider API key (one required unless mocking) |
| `GEMINI_LLM_MODEL` / `GEMINI_LLM_FAST_MODEL` | Gemini model names (use the `gemini-3.x` family — `2.5-*` is unavailable to recent keys) |
| `MOCK_LLM` / `MOCK_EMBEDDINGS` | Set `true` to run the full pipeline without any API keys |
| `VECTOR_SEARCH_BACKEND` | `qdrant` (default) or `memory` for keyless dev/tests |

Switching LLM providers is a config change only — the provider abstraction handles the rest.

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

The suite covers the auth lifecycle, RBAC enforcement, explicit cross-tenant isolation, the ingestion and AI pipelines, search and grounded Q&A, clause comparison, document relationships, versioning, report generation, and collaboration.

---

## Project Structure

```
legal-doc-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # Route handlers (auth, documents, analysis,
│   │   │                      #   search, compare, relationships,
│   │   │                      #   collaboration, reports, exports)
│   │   ├── core/              # Config, security, dependencies
│   │   ├── db/                # Session management, Qdrant init
│   │   ├── llm/               # LLM provider abstraction + prompts
│   │   ├── models/            # SQLAlchemy models
│   │   ├── pipelines/         # Ingestion, AI analysis, comparison, reports
│   │   ├── providers/         # Embedding providers
│   │   ├── repositories/      # Org-scoped data access layer
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic (search, Q&A, export, ...)
│   │   ├── utils/             # Shared helpers
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
| `comments` | Threaded review comments with resolution state |
| `annotations` | Text-highlight annotations (verbatim span, color, note) |
| `reports` | Portfolio report jobs (type, format, status, storage path) |

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

### Frontend changes not showing up
The frontend container serves the `.next` build baked into its image — there is no bind mount, so edits on the host have no effect until you rebuild: `docker compose build frontend && docker compose up -d frontend`. After a rebuild, hard-refresh the browser (Ctrl+Shift+R) so cached JS chunks aren't reused.

### Every rebuild re-downloads dependencies
The backend Dockerfiles install dependencies from `pyproject.toml` *before* copying source, with a BuildKit pip cache mount — code-only changes rebuild in seconds. Never move `COPY . .` above the dependency-install layer.

### LLM rate-limit (429) errors
The Gemini free tier allows ~20 requests/day/model. The pipeline batches LLM calls (~6 per document) and the provider retries with server-advertised delays plus a configurable request interval (`GEMINI_MIN_REQUEST_INTERVAL`). If quota is exhausted: wait for the daily reset and retry the document (`POST /documents/{id}/retry`), point `GEMINI_LLM_MODEL` at a model with remaining quota, or switch providers — the abstraction makes it a config change.

---

## Security

- JWT access tokens kept in memory only; refresh tokens in httpOnly cookies
- Role-based access control (**admin / reviewer / viewer**) enforced at every endpoint
- Organization-scoped repository layer prevents cross-tenant queries by construction
- Deactivated members are locked out immediately at login and token refresh
- Every AI output carries the persistent "not legal advice" disclaimer

---

## License

Proprietary — see LICENSE file.

## Contributing

Internal project — see the maintainers for access and contribution guidelines.
