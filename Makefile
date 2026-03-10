# Orbit — Developer Convenience Commands

.PHONY: run serve test test-cov seed seed-prod ingest install clean

# Run the development server
run:
	./venv/bin/python app.py

# Run via Gunicorn (production-like)
serve:
	./venv/bin/gunicorn --bind 0.0.0.0:5007 --workers 2 wsgi:app

# Run the full test suite
test:
	./venv/bin/pytest tests/ -v

# Test with coverage
test-cov:
	./venv/bin/pytest tests/ -v --cov=app --cov-report=term-missing

# Seed local dev database
seed:
	./venv/bin/python seed_data.py
	./venv/bin/python seed_users.py

# Seed production PostgreSQL database (run once after first Render deploy)
# Usage: DATABASE_URL=postgresql://... make seed-prod
seed-prod:
	./venv/bin/python seed_production.py
	./venv/bin/python seed_users.py

# Sync vault docs to Pinecone vector store
ingest:
	./venv/bin/python bot/ingest_to_pinecone.py

# Install dependencies
install:
	pip install -r requirements.txt

# Remove local SQLite DB and caches (safe — git-ignored anyway)
clean:
	rm -f orbit.db
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
