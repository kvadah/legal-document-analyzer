FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code and install dependencies
COPY . .
RUN pip install --no-cache-dir --timeout 600 --retries 20 .

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Run migrations and start the application
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
