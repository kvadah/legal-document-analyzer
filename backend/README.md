# Backend — Legal Document Analyzer

FastAPI API, Arq workers, and the ingestion + AI processing pipelines.

## Stack
FastAPI · SQLAlchemy 2.0 async + Alembic · Arq · Pydantic v2 · PostgreSQL · Redis ·
Qdrant · S3/MinIO · Claude/OpenAI (via `LLMProvider`). See `../../02-tech-stack.md`.

## Layout
```
app/
  api/v1/        routes under /api/v1
  core/          Pydantic Settings config, security/JWT helpers
  db/            async engine/session, declarative Base
  models/        ORM models (see ../../03-data-model.md)
  schemas/       Pydantic DTOs
  repositories/  org-scoped base repository (tenant isolation)
  services/      business logic
  llm/           LLMProvider abstraction + provider impls
  pipelines/
    ingestion/   04-ingestion-pipeline.md
    ai/          05-ai-pipeline.md
  workers/       Arq entrypoints & tasks
  utils/
alembic/         migrations
tests/
```

## Dependencies
```bash
uv sync --extra dev                    # core + dev tools
uv sync --extra dev --extra processing # also OCR fallback (pytesseract, pdf2image)
```
The `processing` extra needs system libs: `tesseract-ocr`, `poppler-utils`, `libmagic`.
These ship in the worker Docker image; install locally only for out-of-container runs.
Embeddings use the Gemini API (`GEMINI_API_KEY`, no local ML stack); set `MOCK_EMBEDDINGS=false` to enable.

## Common commands (available once app code lands)
```bash
uv run uvicorn app.main:app --reload            # API dev server
uv run arq app.workers.WorkerSettings           # background worker
uv run alembic upgrade head                     # apply migrations
uv run alembic revision --autogenerate -m "..." # new migration
uv run pytest                                   # tests
uv run ruff check . && uv run ruff format .     # lint + format
uv run mypy app                                 # type check
```

## Config
Copy `.env.example` → `.env`. All settings load via Pydantic Settings (`app/core`).
Set `MOCK_LLM=true` for fast, free local iteration without calling real LLM APIs.
