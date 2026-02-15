# ── Build stage ──
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

# ── Runtime stage ──
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and console scripts
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy source (for scanner data files)
COPY src/ ./src/

# Non-root user
RUN useradd --create-home --shell /bin/bash codecustodian
USER codecustodian

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD codecustodian version || exit 1

ENTRYPOINT ["codecustodian-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
