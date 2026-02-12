# ── Build stage ──
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

# ── Runtime stage ──
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/codecustodian* /usr/local/bin/

# Copy source (for scanner data files)
COPY src/ ./src/

# Non-root user
RUN useradd --create-home --shell /bin/bash codecustodian
USER codecustodian

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD codecustodian version || exit 1

ENTRYPOINT ["codecustodian"]
CMD ["run"]
