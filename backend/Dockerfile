FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first — this layer is cached unless
# pyproject.toml changes, so code edits never trigger a full re-download.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 600 --retries 20 \
    $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

# Copy application code (only layers from here on rebuild on code changes)
COPY . .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --timeout 600 --retries 20 .

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Run migrations and start the application
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
