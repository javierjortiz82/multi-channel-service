# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project files for installation
COPY pyproject.toml README.md ./
COPY src ./src

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Production
FROM python:3.12-slim AS production

# Security: Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup src/telegram_bot ./telegram_bot

# Create logs directory
RUN mkdir -p /app/logs && chown appuser:appgroup /app/logs

# Switch to non-root user
USER appuser

# Environment variables (defaults, override in docker-compose or runtime)
# Webhook: WEBHOOK_MAX_CONNECTIONS, WEBHOOK_IP_FILTER_ENABLED, WEBHOOK_DROP_PENDING_UPDATES
# Concurrency: WORKERS, LIMIT_CONCURRENCY, LIMIT_MAX_REQUESTS, BACKLOG
# Timeouts: TIMEOUT_KEEP_ALIVE, TIMEOUT_GRACEFUL_SHUTDOWN
# Performance: HTTP_IMPLEMENTATION, LOOP_IMPLEMENTATION
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8002 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    LOG_TO_FILE=true \
    LOG_DIR=/app/logs \
    LOG_MAX_SIZE_MB=10 \
    LOG_BACKUP_COUNT=5 \
    WEBHOOK_MAX_CONNECTIONS=100 \
    WEBHOOK_IP_FILTER_ENABLED=true \
    WEBHOOK_DROP_PENDING_UPDATES=true \
    WORKERS=4 \
    LIMIT_CONCURRENCY=100 \
    LIMIT_MAX_REQUESTS=10000 \
    BACKLOG=2048 \
    TIMEOUT_KEEP_ALIVE=5 \
    TIMEOUT_GRACEFUL_SHUTDOWN=30 \
    HTTP_IMPLEMENTATION=auto \
    LOOP_IMPLEMENTATION=auto

# Expose port
EXPOSE 8002

# Health check (uses default port 8002, override in docker-compose if needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

# Run with uvicorn and workers for concurrency
CMD ["sh", "-c", "uvicorn telegram_bot.app:create_app --factory --host ${SERVER_HOST} --port ${SERVER_PORT} --workers ${WORKERS}"]
