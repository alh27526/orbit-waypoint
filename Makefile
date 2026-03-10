# Orbit — Developer Convenience Commands

.PHONY: run test seed clean

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

# Seed the database (idempotent)
seed:
	./venv/bin/python seed_data.py
	./venv/bin/python seed_users.py

# Sync Obsidian vault to Pinecone
ingest:
	./venv/bin/python bot/ingest_to_pinecone.py

# Install dependencies
install:
	pip install -r requirements.txt
