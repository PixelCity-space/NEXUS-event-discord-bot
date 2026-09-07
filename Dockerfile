# ==============================================================================
# Nexus Discord Event Bot - Production Docker Image
# Multi-stage optimized, secure, non-root container with built-in healthchecks
# ==============================================================================

FROM python:3.12-slim AS base

# Python runtime configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HEALTH_SERVER_PORT=8080 \
    HEALTH_SERVER_HOST=0.0.0.0

WORKDIR /app

# Install runtime system packages (curl for container healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 nexus && \
    useradd -u 10001 -g nexus -s /bin/bash -m nexus

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=nexus:nexus . .

# Ensure data and logs directories exist with correct permissions
RUN mkdir -p /app/logs /app/data && chown -R nexus:nexus /app

# Switch to non-root user
USER nexus

# Expose HTTP healthcheck and Prometheus metrics port
EXPOSE 8080

# Built-in Docker healthcheck probe using internal /healthz endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Start bot
CMD ["python", "main.py"]
