"""
Orbit API Integration Test Suite
Run with: ./venv/bin/pytest tests/ -v
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import pytest

# Ensure the project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Path to the real seeded database
REAL_DB = os.path.join(PROJECT_ROOT, "orbit.db")


@pytest.fixture(scope="session")
def app():
    """
    Create a test Flask app backed by a temp COPY of orbit.db.
    This means:
      - All CRM tables (accounts, quotes, etc.) exist and are pre-seeded.
      - Writes go to the temp copy, never touching production.
      - SQLAlchemy (users table) is also pointed at the same temp DB.
    """
    import app as app_module

    # Create a temp copy of the real database so CRM tables are present
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    if os.path.exists(REAL_DB):
        shutil.copy2(REAL_DB, tmp.name)

    # Patch the module-level DB_PATH used by raw sqlite3 calls
    app_module.DB_PATH = tmp.name

    flask_app = app_module.app
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp.name}"

    with flask_app.app_context():
        try:
            from models import db
            db.create_all()
        except Exception:
            pass

    yield flask_app

    # Cleanup temp DB after all tests
    os.unlink(tmp.name)


@pytest.fixture()
def client(app):
    return app.test_client()


# --------------------------------------------------------------------------- #
# 1. SMOKE — Is the server up?
# --------------------------------------------------------------------------- #
class TestSmoke:
    def test_index_serves_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        data = res.data.decode()
        # Must contain the Orbit brand
        assert "Orbit" in data or "orbit" in data.lower()


# --------------------------------------------------------------------------- #
# 2. ACCOUNTS — Core CRM data routes
# --------------------------------------------------------------------------- #
class TestAccounts:
    def test_get_accounts_returns_list(self, client):
        res = client.get("/api/accounts")
        assert res.status_code == 200
        body = json.loads(res.data)
        assert isinstance(body, list), "Expected a JSON list of accounts"

    def test_get_account_detail_missing(self, client):
        res = client.get("/api/accounts/999999")
        assert res.status_code == 404

    def test_get_first_account_if_exists(self, client):
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded — skipping detail test")
        acc_id = accounts[0]["id"]
        res = client.get(f"/api/accounts/{acc_id}")
        assert res.status_code == 200
        body = json.loads(res.data)
        assert "name" in body
        assert "health_score" in body

    def test_get_contacts_for_account(self, client):
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded")
        acc_id = accounts[0]["id"]
        res = client.get(f"/api/accounts/{acc_id}/contacts")
        assert res.status_code == 200
        assert isinstance(json.loads(res.data), list)

    def test_get_quotes_for_account(self, client):
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded")
        acc_id = accounts[0]["id"]
        res = client.get(f"/api/accounts/{acc_id}/quotes")
        assert res.status_code == 200
        assert isinstance(json.loads(res.data), list)

    def test_get_activities_for_account(self, client):
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded")
        acc_id = accounts[0]["id"]
        res = client.get(f"/api/accounts/{acc_id}/activities")
        assert res.status_code == 200


# --------------------------------------------------------------------------- #
# 3. TERRITORY & PIPELINE — Dashboard metrics
# --------------------------------------------------------------------------- #
class TestTerritoryAndPipeline:
    def test_territory_health_shape(self, client):
        res = client.get("/api/territory/health")
        assert res.status_code == 200
        body = json.loads(res.data)
        for key in ("total_accounts", "at_risk_accounts", "ytd_revenue", "open_quotes"):
            assert key in body, f"Missing key: {key}"

    def test_at_risk_is_non_negative(self, client):
        body = json.loads(client.get("/api/territory/health").data)
        assert body["at_risk_accounts"] >= 0

    def test_pipeline_summary_returns_list(self, client):
        res = client.get("/api/pipeline/summary")
        assert res.status_code == 200
        assert isinstance(json.loads(res.data), list)


# --------------------------------------------------------------------------- #
# 4. WIZARD — Fallback mode (no API key required)
# --------------------------------------------------------------------------- #
class TestWizard:
    def test_wizard_rejects_empty_query(self, client):
        res = client.post(
            "/api/wizard/query",
            json={"query": ""},
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_wizard_fallback_streams_when_no_api_key(self, client):
        """Without an Anthropic key the wizard should stream a fallback response."""
        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            res = client.post(
                "/api/wizard/query",
                json={"query": "What accounts are at risk?"},
                content_type="application/json",
            )
            assert res.status_code == 200
            # SSE response must have correct content type
            assert "text/event-stream" in res.content_type
            raw = res.data.decode()
            assert "data:" in raw
        finally:
            if saved_key:
                os.environ["ANTHROPIC_API_KEY"] = saved_key


# --------------------------------------------------------------------------- #
# 5. WRITES — Activity & Quote creation
# --------------------------------------------------------------------------- #
class TestWrites:
    def test_create_activity_missing_fields_still_200(self, client):
        """App currently accepts sparse payloads — test that it doesn't crash."""
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded")
        acc_id = accounts[0]["id"]
        res = client.post(
            "/api/activities",
            json={
                "account_id": acc_id,
                "activity_type": "call",
                "summary": "Test activity from pytest",
                "activity_date": "2026-03-09",
            },
            content_type="application/json",
        )
        assert res.status_code == 201
        body = json.loads(res.data)
        assert body.get("status") == "success"
        assert "id" in body

    def test_create_quote(self, client):
        accounts = json.loads(client.get("/api/accounts").data)
        if not accounts:
            pytest.skip("No accounts seeded")
        acc_id = accounts[0]["id"]
        res = client.post(
            "/api/quotes",
            json={
                "account_id": acc_id,
                "quote_number": "TEST-9999",
                "services": ["Metals", "Organics"],
                "amount": 5500.00,
                "status": "Draft",
                "sent_date": "2026-03-09",
            },
            content_type="application/json",
        )
        assert res.status_code == 201
        body = json.loads(res.data)
        assert body.get("status") == "success"


# --------------------------------------------------------------------------- #
# 6. USER / AUTH — Role lookup
# --------------------------------------------------------------------------- #
class TestUsers:
    def test_user_roles_missing_param(self, client):
        res = client.get("/api/user/roles")
        assert res.status_code == 400

    def test_user_roles_unknown_user(self, client):
        res = client.get("/api/user/roles?username=nobody_real")
        assert res.status_code == 404


# --------------------------------------------------------------------------- #
# 7. HEALTH CHECK — Production readiness
# --------------------------------------------------------------------------- #
class TestHealth:
    def test_health_returns_200(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        body = json.loads(res.data)
        assert body["status"] == "healthy"
        assert body["database"] == "connected"
        assert "version" in body
        assert "timestamp" in body


# --------------------------------------------------------------------------- #
# 8. INPUT VALIDATION — Write endpoints reject bad data
# --------------------------------------------------------------------------- #
class TestValidation:
    def test_activity_rejects_missing_account_id(self, client):
        res = client.post("/api/activities", json={"summary": "no account"},
                          content_type="application/json")
        assert res.status_code == 400
        assert "account_id" in json.loads(res.data).get("error", "")

    def test_quote_rejects_missing_quote_number(self, client):
        res = client.post("/api/quotes", json={"account_id": 1},
                          content_type="application/json")
        assert res.status_code == 400
        assert "quote_number" in json.loads(res.data).get("error", "")
