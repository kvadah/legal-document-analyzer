# Legal Document Analyzer

A multi-tenant contract intelligence platform: upload legal documents, run them through an OCR/parsing/embedding pipeline, AI-based clause & risk analysis, review results in a rich analysis UI with citation-grounded navigation, search across the whole corpus, ask grounded questions with cited answers, and export analysis reports.

**Status: Phases 0–5 complete (full MVP scope per `00-overview.md` §8).**

## ✅ Completed Phases

### Phase 0 — Project Skeleton
- FastAPI backend with health checks (`/health/live`, `/health/ready`), Pydantic Settings config, SQLAlchemy + Alembic wired to Postgres
- Next.js (App Router) frontend with the global layout/nav shell, Tailwind CSS
- Docker Compose with 7 services (api, worker, frontend, postgres, redis, qdrant, minio), health checks with WSL2-tolerant timeouts, volumes, dependency ordering
- Full data model: 11 core tables as SQLAlchemy models + initial Alembic migration
- Idempotent Qdrant collection init

### Phase 1 — Auth & Multi-Tenancy
- `/auth/*` endpoints: register (org + admin), login, refresh, logout, invite, accept-invite
- JWT auth with httpOnly refresh-token cookie flow (frontend keeps access token in memory only)
- RBAC roles (admin / reviewer / viewer) and org-scoped repository pattern
- Frontend: login/register pages, protected route wrapper, auth context with silent session restore
- Tests: register/login lifecycle, RBAC, and explicit cross-tenant isolation tests

### Phase 2 — Ingestion Pipeline
- Multipart upload (single/batch) → object storage (S3/MinIO with local-fs fallback)
- Content validation, malware/magic-byte sniffing, SHA-256 dedup check
- OCR integration (PaddleOCR primary, Tesseract fallback) with skip-if-text-layer logic
- Structural parsing → chunking → embedding generation → Qdrant write
- Status state machine + Redis pub/sub, SSE status streaming endpoint
- Frontend Upload page with drag-and-drop, multi-file, live status badges

### Phase 3 — AI Pipeline
- `LLMProvider` abstraction with Claude, OpenAI, and Mock providers (mock used in tests/dev)
- Full metadata extraction (parties, dates, financial terms, governing law…)
- Clause detection for all 10 clause types (+ not-found tracking)
- Risk detection: deterministic rule-based checks + LLM-judgment checks
- Summary generation, Contract Score + AI Confidence Score (v-scored, with risk deduction breakdown)
- Mock LLM + mock embeddings so the whole pipeline runs end-to-end in tests without external APIs

### Phase 4 — Analysis UI (MVP milestone)
- **Analysis view** (`/documents/{id}`): document viewer pane + tabbed analysis pane
  - Viewer renders extracted/OCR'd text page-by-page with page navigation, jump-to-page and highlight-span-on-citation-click
  - **Summary tab**: score rings (Contract Score + AI Confidence) with clickable risk-deduction breakdown, parties, key fields, top-risks preview
  - **Clauses tab**: per-clause cards with confidence, summary, expandable extracted text, and "Not found" section
  - **Risks tab**: severity-sorted cards with optimistic triage control (flagged / acknowledged / dismissed) and rollback on failure
  - **Obligations tab**: timeline-style list with deadline type/date and status badges
  - **Entities tab**: grouped by type, click-to-navigate to source page
- **`CitationLink`** shared component (single implementation reused across all tabs — jumps the viewer to the cited page and highlights the anchor text)
- Low-AI-confidence persistent banner, inline AI disclaimer (plus the layout-level persistent disclaimer)
- Processing state: live polling while a document is mid-pipeline, error state with retry, "queue analysis" for ingested-but-not-analyzed docs
- Contracts list rows now deep-link into the Analysis view
- New backend endpoint: `GET /documents/{id}/text` — extracted/OCR'd text with page/position metadata (api-spec §2), with tests

### Phase 5 — Search & Basic Export (MVP complete)
- **Search** (`POST /search`): keyword (SQL-side LIKE narrowing; Postgres tsvector is the noted upgrade path), semantic (query embedded with the ingestion model, searched against the vector store, org-filtered), and **hybrid** (both merged with Reciprocal Rank Fusion) — with `document_type` / date-range / document-id filters
- **Vector store abstraction** (`QdrantVectorStore` / `InMemoryVectorStore`): production uses Qdrant; tests and keyless dev use an in-process brute-force store (`VECTOR_SEARCH_BACKEND=memory`), mirroring the mock-LLM pattern
- **Search page** rewritten: mode toggle (Hybrid default), debounced auto-search, results grouped by document with highlighted snippets + keyword/semantic/both source badges, deep-links into the Analysis viewer at the matched page, and an "ask a question instead" heuristic that routes question-shaped queries into document Q&A with the question prefilled
- **Grounded RAG Q&A** (`POST /documents/{id}/ask`, SSE): question embedded → retrieval scoped to the document and org → similarity threshold check **before** the LLM call (un-groundable questions get "couldn't find" instead of a hallucination) → structured answer with sentence-level citations → grounding validation drops any citation whose quote isn't verbatim in the cited chunk → conversation history in Redis for multi-turn follow-ups
- **Q&A tab** in the Analysis view: chat UI with streaming answers, inline `[n]` citation markers rendered as clickable references that jump + highlight the document viewer, and source-quote chips; non-advisory framing (asks for legal advice are declined with an explanation)
- **Export** (`GET /documents/{id}/export?format=pdf|docx|json`): analysis report as PDF (hand-rolled stdlib PDF writer — no new dependencies), DOCX (minimal OOXML package via stdlib zipfile), or JSON — every export carries the persistent AI disclaimer; Export menu in the Analysis header downloads directly
- Q&A prompts enforce the non-advisory rules from the security spec; mock LLM implements a heuristic grounded-QA path so tests run without API keys

### Infra hardening (post-Phase 5)
- **Docker build caching fixed** (backend `Dockerfile` + `Dockerfile.worker`): dependencies are now installed from `pyproject.toml` in a layer *before* source is copied, with a BuildKit pip cache mount — code edits no longer re-download every Python package (previously `COPY . .` preceded `pip install`, invalidating the dependency layer on every code change)
- **Healthchecks hardened** (`docker-compose.yml`):
  - Qdrant + API use `127.0.0.1` instead of `localhost` — the current `qdrant/qdrant:latest` and `python:3.12-slim` images ship glibc 2.41 (Debian trixie), where `localhost` resolution is flaky under Docker Desktop/WSL2; bash's `/dev/tcp/localhost:6333` fails with a misleading "No such file or directory" and permanently marks the container unhealthy, which blocks every service that `depends_on` it
  - Postgres: `retries: 30` + `start_period: 120s` so crash recovery after an unclean shutdown (which can take minutes on WSL2's filesystem) isn't mistaken for a dead database

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Installation & Startup

1. **Start all services:**
```bash
chmod +x scripts/startup.sh
./scripts/startup.sh
```

Or start manually with Docker Compose:
```bash
cd legal-doc-analyzer
docker compose up -d --build
```

2. **Verify services are healthy:**
```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Next.js UI |
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| MinIO Console | http://localhost:9001 | Object storage UI |
| Qdrant | http://localhost:6333/dashboard | Vector DB dashboard |
| Postgres | localhost:5432 | Database (internal) |
| Redis | localhost:6379 | Cache/Queue (internal) |

### Default Credentials
- **MinIO**: `minioadmin` / `minioadmin`
- **Database**: `postgres` / `postgres`
- **App**: register a new org + admin user at http://localhost:3000/register

## 🧪 Testing

Backend (uses SQLite + mock LLM/embeddings + local storage — no external services needed):

```bash
cd legal-doc-analyzer/backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd legal-doc-analyzer/frontend
pnpm test          # unit (vitest)
pnpm type-check    # tsc --noEmit
pnpm lint
pnpm test:e2e      # playwright
```

## 📁 Project Structure

```
legal-document-analyzer/
├── legal-doc-analyzer/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/               # API routes (health, v1: auth, documents, analysis)
│   │   │   ├── core/              # Config, security, deps
│   │   │   ├── db/                # Database session, base, Qdrant init
│   │   │   ├── llm/               # LLM provider abstraction (Claude/OpenAI/Mock)
│   │   │   ├── models/            # SQLAlchemy models
│   │   │   ├── pipelines/         # Ingestion + AI pipelines
│   │   │   ├── providers/         # Embedding providers
│   │   │   ├── repositories/      # Org-scoped data access layer
│   │   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── services/          # Business logic (search, Q&A, export, vector store)
│   │   │   ├── workers/           # Background jobs (Arq)
│   │   │   └── main.py            # App factory
│   │   ├── alembic/               # Database migrations
│   │   ├── tests/                 # Unit/integration tests
│   │   └── Dockerfile(.worker)
│   └── frontend/
│       ├── src/
│       │   ├── app/               # Next.js App Router (landing, auth, contracts,
│       │   │                      #   upload, search, reports, documents/[id] analysis)
│       │   ├── components/
│       │   │   ├── analysis/      # Analysis view components (viewer, tabs,
│       │   │   │                  #   CitationLink, ScoreCards, QaTab, ExportMenu)
│       │   │   ├── layout/        # Sidebar, TopBar, Disclaimer
│       │   │   └── ui/            # Shared UI primitives
│       │   ├── context/           # AuthContext
│       │   └── lib/               # api-client, format helpers, analysis metadata
│       └── package.json
├── docker-compose.yml             # Service orchestration
├── .env / .env.example            # Environment variables
└── scripts/startup.sh             # Development startup script
```

## 📊 Database Schema

All tables use UUID primary keys, `created_at`/`updated_at` timestamps, FK relationships, and indexes on hot query paths.

**Core Tables:**
1. `organizations` — Tenant scoping
2. `users` — User accounts with roles
3. `documents` — Core document metadata (+ scores, status, storage paths)
4. `document_versions` — Version history
5. `chunks` — Document text chunks (source of the viewer text)
6. `clauses` — Detected contract clauses
7. `risks` — Risk flags with severity + triage status
8. `entities` — Extracted entities (companies, dates, money…)
9. `obligations` — Timeline items and obligations
10. `document_summaries` — AI-generated summaries
11. `comments` — User comments (annotations, reports, comparisons arrive in later phases)

## 📝 Next Steps (Phase 6 — Clause Comparison)

- Comparison backend (`POST /compare`, async diff job) + Compare page
- Clause alignment by type + word-level diff with added/removed/modified/unchanged classification
- Version history (Phase 7) integrates with the Compare feature

See [13-roadmap-build-order.md](13-roadmap-build-order.md) for the full phase plan
(Phases 6–11: comparison, cross-document features, reports, collaboration,
administration, deployment hardening). The MVP checkpoint is complete —
demo and gather feedback before continuing.

## 🐛 Troubleshooting

### Services fail to start
- Ensure Docker is running: `docker ps`
- Check port availability: `lsof -i :3000,8000,5432,6379,6333,9000`
- View logs: `docker compose logs <service_name>`

### api / worker / frontend stuck in "Created"
They wait (`depends_on: condition: service_healthy`) for postgres/redis/qdrant/minio — and the worker also waits for the API. If any dependency is `unhealthy`, compose never starts them:
```bash
docker ps -a                                  # look for (unhealthy) containers
docker inspect legal-doc-qdrant --format '{{json .State.Health.Log}}' | python3 -m json.tool
```
Recreate the unhealthy service (`docker compose up -d <service>`), then `docker compose up -d` again.

### A container is unhealthy but the service inside is fine
Known issue: current images (qdrant 1.19, python:3.12-slim) ship glibc 2.41, where `localhost` name resolution is unreliable under Docker Desktop/WSL2. Healthchecks in this repo therefore use `127.0.0.1` — don't "fix" them back to `localhost`. If you add new healthchecks, use the IP literal.

### Postgres takes minutes to start ("automatic recovery in progress")
This happens after an unclean shutdown (killing Docker Desktop, hard reboot). Postgres runs crash recovery and fsyncs its data directory, which is slow on the WSL2 filesystem. The healthcheck allows 120s for this. Avoid it entirely by shutting down cleanly:
```bash
docker compose down    # not Ctrl-C on the logs, not quitting Docker Desktop mid-write
```

### Every rebuild re-downloads all dependencies
The backend Dockerfiles install dependencies from `pyproject.toml` *before* copying source, with a pip BuildKit cache mount — so code-only changes rebuild in seconds. If you see full re-downloads, check that `pyproject.toml` (or `package.json` on the frontend) actually changed; if not, a previous build populated the cache and the next one will be fast. Never move `COPY . .` above the dependency-install layer.

### Gemini 429 / quota errors in the AI pipeline
The interim LLM is Google Gemini on a free-tier key. The free-tier quota is **per model, per day** (~20 requests/day/model for generateContent). Two safeguards keep this workable:
- **Batched pipeline** (~6 LLM calls per document, not ~15): clause detection and risk judgment each run as a single call covering all types.
- **429-aware retry + pacing** (`app/llm/gemini_provider.py`): retries follow the server's `retryDelay`, and `GEMINI_MIN_REQUEST_INTERVAL` (default 6s) paces requests.

If a document still fails with a "rate limit exceeded" error, the daily quota for that model is spent — options:
1. Wait for the daily reset (~midnight Pacific) and retry the document (`POST /documents/{id}/retry`).
2. Point `GEMINI_LLM_MODEL`/`GEMINI_LLM_FAST_MODEL` at a different model with remaining quota (each model has its own daily budget) and restart `api` + `worker`.
3. Enable billing on the Google project, or switch providers (`DEFAULT_LLM_PROVIDER=anthropic|openai` + the matching key) — the provider abstraction makes this a config change, not a code change.

Note: `gemini-2.5-*` models are unavailable to keys created recently — use the `gemini-3.x` family.

### Database connection errors
- Check Postgres is healthy: `docker compose ps postgres`
- Verify DATABASE_URL in .env
- Check port 5432 is not in use

### Frontend not loading
- Clear Next.js cache: `rm -rf legal-doc-analyzer/frontend/.next`
- Reinstall dependencies: `pnpm install`
- Check NEXT_PUBLIC_API_BASE_URL in .env matches backend port

### Frontend build fails on lint errors
`next build` runs ESLint by default — unused variables and `any` types are errors. Run `pnpm lint` locally before rebuilding Docker.

## 📚 Documentation

- [00-overview.md](00-overview.md) — Project overview & MVP scope
- [01-architecture.md](01-architecture.md) — System architecture
- [03-data-model.md](03-data-model.md) — Data model specification
- [04-ingestion-pipeline.md](04-ingestion-pipeline.md) — Ingestion pipeline spec
- [05-ai-pipeline.md](05-ai-pipeline.md) — AI pipeline spec
- [06-feature-spec-analysis.md](06-feature-spec-analysis.md) — Analysis feature spec
- [07-feature-spec-comparison-search.md](07-feature-spec-comparison-search.md) — Search, RAG Q&A, comparison spec
- [09-api-spec.md](09-api-spec.md) — API specification
- [10-frontend-spec.md](10-frontend-spec.md) — Frontend specification
- [11-security-compliance.md](11-security-compliance.md) — Security & compliance
- [12-deployment-infra.md](12-deployment-infra.md) — Deployment guide
- [13-roadmap-build-order.md](13-roadmap-build-order.md) — Build roadmap

## 📄 License

Proprietary — See LICENSE file

## 🤝 Contributing

This is an internal project. Follow the roadmap in [13-roadmap-build-order.md](13-roadmap-build-order.md) for sequencing.
