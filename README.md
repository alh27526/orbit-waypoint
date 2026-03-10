# 🛰️ Orbit — CRM & AI Assistant for Waypoint Analytical

> Territory intelligence platform for environmental testing services.
> Built with Flask, SQLAlchemy, and Claude AI.

[![CI](https://github.com/alh27526/orbit-waypoint/actions/workflows/ci.yml/badge.svg)](https://github.com/alh27526/orbit-waypoint/actions/workflows/ci.yml)

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/alh27526/orbit-waypoint.git
cd orbit-waypoint
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY (optional for dev)

# Seed & run
make seed
make run          # → http://localhost:5000
```

## Architecture

```
orbit-waypoint/
├── app.py                 # Flask API (all routes, middleware, rate limiting)
├── models.py              # SQLAlchemy ORM models (6 tables)
├── wsgi.py                # Gunicorn production entry point
├── seed_data.py           # Local dev database seeder
├── seed_production.py     # Production PostgreSQL seeder (idempotent)
├── render.yaml            # Render Blueprint — one-click deploy
├── Dockerfile             # Production container (python:3.12-slim)
├── requirements.txt       # Pinned dependencies
├── Makefile               # Developer convenience commands
├── tests/
│   └── test_api.py        # 19-test integration suite
├── templates/
│   └── index.html         # SPA frontend
├── static/                # CSS, JS, images
├── vault/                 # Obsidian knowledge vault (RAG source)
└── bot/                   # Discord bot + Pinecone ingestion
```

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| `GET`  | `/api/health` | Health check (DB connectivity, version) | exempt |
| `GET`  | `/api/accounts` | List all CRM accounts | 200/day |
| `GET`  | `/api/accounts/:id` | Account detail | 200/day |
| `GET`  | `/api/accounts/:id/contacts` | Contacts for account | 200/day |
| `GET`  | `/api/accounts/:id/quotes` | Quotes for account | 200/day |
| `GET`  | `/api/accounts/:id/activities` | Activity log | 200/day |
| `GET`  | `/api/accounts/:id/edd` | EDD submissions | 200/day |
| `GET`  | `/api/pipeline/summary` | Pipeline by stage | 200/day |
| `GET`  | `/api/territory/health` | Territory health metrics | 200/day |
| `GET`  | `/api/user/roles` | User role lookup | 200/day |
| `POST` | `/api/activities` | Create activity | 10/min |
| `POST` | `/api/quotes` | Create quote | 10/min |
| `POST` | `/api/wizard/query` | AI assistant (SSE stream) | 20/hour |

## Database

Orbit uses SQLAlchemy ORM and supports **both SQLite and PostgreSQL**:

```bash
# Local development (SQLite — no setup needed)
DATABASE_URL=sqlite:///orbit.db    # default

# Production (PostgreSQL — set in Render/Heroku)
DATABASE_URL=postgresql://user:pass@host/orbit
```

### Models

| Table | Key Columns |
|-------|-------------|
| `accounts` | name, industry, territory, pipeline_stage, health_score, ytd_revenue |
| `contacts` | name, title, email, phone → belongs to account |
| `quotes` | quote_number, services, amount, status → belongs to account |
| `activities` | activity_type, summary, outcome → belongs to account |
| `edd_submissions` | form_type, field_flags → belongs to account |
| `users` | username, email, role, permissions |

## Testing

```bash
make test              # 19 tests, ~1.2s
make test-cov          # With coverage report
```

Tests run against a temp SQLite copy — safe, isolated, won't touch production data.

## Deploy to Render

1. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
2. Connect the `alh27526/orbit-waypoint` repository
3. Render reads `render.yaml` and provisions:
   - **orbit-web** — Docker web service (Gunicorn, auto-deploy)
   - **orbit-db** — PostgreSQL 16 database
   - **orbit-vault-sync** — Nightly Pinecone cron job
4. Add secrets in dashboard: `ANTHROPIC_API_KEY`, `PINECONE_API_KEY`
5. After first deploy, seed production data:
   ```bash
   # In Render Shell tab:
   python seed_production.py
   python seed_users.py
   ```

## Security

- **Rate limiting** — flask-limiter with per-endpoint tiers
- **Input validation** — 400 errors with specific field messages
- **Security headers** — X-Content-Type-Options, X-Frame-Options
- **Request tracing** — X-Request-ID on every response
- **Secret scanning** — gitleaks in CI
- **Non-root container** — Dockerfile runs as `orbit` user

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///orbit.db` | Database connection URI |
| `FLASK_SECRET_KEY` | No | auto-generated on Render | Session encryption key |
| `ANTHROPIC_API_KEY` | No | — | Enables Wizard AI (falls back to offline mode) |
| `PINECONE_API_KEY` | No | — | Enables vault vector search |
| `VAULT_PATH` | No | `./vault` | Path to Obsidian knowledge vault |

## Make Commands

```bash
make run        # Dev server (port 5000)
make serve      # Gunicorn (port 5007)
make test       # Run test suite
make test-cov   # Tests with coverage
make seed       # Seed local dev DB
make seed-prod  # Seed production PostgreSQL
make ingest     # Sync vault → Pinecone
make clean      # Remove DB + caches
make install    # pip install requirements
```

## License

Private — Waypoint Analytical © 2026
