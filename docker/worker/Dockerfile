FROM python:3.11-slim

# Security: non-root user
RUN groupadd -r aegis && useradd -r -g aegis aegis

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (needed for scraping tasks)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/

# Create evidence directories
RUN mkdir -p /app/evidence /tmp && \
    chown -R aegis:aegis /app /tmp

# Switch to non-root user
USER aegis

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD celery -A src.worker inspect ping || exit 1

# Run Celery worker
CMD ["celery", "-A", "src.worker", "worker", "--loglevel=info", "--concurrency=4", "--prefetch-multiplier=1"]
