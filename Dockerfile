# Orbit — Dockerfile
# Multi-stage slim Python image for production
FROM python:3.12-slim

# System dependencies for psycopg2 (PostgreSQL client library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root app user for security
RUN useradd -m -u 1000 orbit
WORKDIR /app
RUN chown orbit:orbit /app

# Install Python dependencies first (layer cached separately from code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir psycopg2-binary gunicorn

# Copy application code
COPY --chown=orbit:orbit . .

# Switch to non-root user
USER orbit

# Expose the port Render expects
EXPOSE 10000

# Health check — Render will use this to confirm the service is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:10000/ || exit 1

# Production command: Gunicorn with 2 workers, bound to Render's expected port
CMD ["gunicorn", \
     "--bind", "0.0.0.0:10000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]
