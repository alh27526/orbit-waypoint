import os
import json
import time
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Arize Phoenix tracing imports
try:
    import phoenix as px
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from opentelemetry import trace as trace_api
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    HAS_PHOENIX = True
except ImportError:
    HAS_PHOENIX = False

# Optional: Anthropic for Wizard
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Vault RAG retrieval
try:
    from vault_ingest import query_vault
    HAS_RAG = True
except ImportError:
    HAS_RAG = False

load_dotenv()

# SQLAlchemy models — all tables now managed here
from models import db, User, Account, Contact, Quote, Activity, EddSubmission

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_demo_key")
CORS(app)

# ---------------------------------------------------------------------------
# Database — SQLite for dev, PostgreSQL for production
# Set DATABASE_URL in .env or Render environment variables:
#   SQLite (local):   sqlite:////absolute/path/to/orbit.db
#   PostgreSQL (prod): postgresql://user:pass@host/dbname
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orbit.db')
_default_db_uri = f"sqlite:///{DB_PATH}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_db_uri)

# Render provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,   # reconnect on stale connections
    "pool_recycle": 300,     # recycle connections every 5 min
}
db.init_app(app)

with app.app_context():
    db.create_all()

VAULT_PATH = os.getenv("VAULT_PATH", os.path.join(os.path.dirname(__file__), 'vault'))

# Launch Phoenix locally (optional tracing)
if HAS_ANTHROPIC and HAS_PHOENIX:
    try:
        px.launch_app()
        tracer_provider = trace_sdk.TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006")))
        trace_api.set_tracer_provider(tracer_provider)
        AnthropicInstrumentor().instrument()
    except Exception:
        pass  # Phoenix is optional, don't crash on failure


# ---------------------------------------------------------------------------
# Routes: Users
# ---------------------------------------------------------------------------

@app.route('/api/user/roles', methods=['GET'])
def get_user_roles():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "No username provided"}), 400
    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify(user.to_dict())
    return jsonify({"error": "User not found"}), 404


@app.route('/api/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


# ---------------------------------------------------------------------------
# Route: Frontend
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory("templates", "index.html")


# ---------------------------------------------------------------------------
# Routes: Accounts
# ---------------------------------------------------------------------------

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accs = Account.query.order_by(Account.last_contact_date.desc()).all()
    return jsonify([a.to_dict() for a in accs])


@app.route('/api/accounts/<int:acc_id>', methods=['GET'])
def get_account_detail(acc_id):
    acc = db.session.get(Account, acc_id)
    if acc:
        return jsonify(acc.to_dict())
    return jsonify({"error": "Account not found"}), 404


@app.route('/api/accounts/<int:acc_id>/contacts', methods=['GET'])
def get_contacts(acc_id):
    contacts = Contact.query.filter_by(account_id=acc_id).all()
    return jsonify([c.to_dict() for c in contacts])


@app.route('/api/accounts/<int:acc_id>/quotes', methods=['GET'])
def get_quotes(acc_id):
    quotes = Quote.query.filter_by(account_id=acc_id).order_by(Quote.sent_date.desc()).all()
    return jsonify([q.to_dict() for q in quotes])


@app.route('/api/accounts/<int:acc_id>/activities', methods=['GET'])
def get_activities(acc_id):
    activities = Activity.query.filter_by(account_id=acc_id).order_by(Activity.activity_date.desc()).all()
    return jsonify([a.to_dict() for a in activities])


@app.route('/api/accounts/<int:acc_id>/edd', methods=['GET'])
def get_edd(acc_id):
    edds = EddSubmission.query.filter_by(account_id=acc_id).order_by(EddSubmission.submission_date.desc()).all()
    return jsonify([e.to_dict() for e in edds])


# ---------------------------------------------------------------------------
# Routes: Pipeline & Territory
# ---------------------------------------------------------------------------

@app.route('/api/pipeline/summary', methods=['GET'])
def get_pipeline_summary():
    from sqlalchemy import func
    rows = (
        db.session.query(
            Account.pipeline_stage,
            func.count(Account.id).label("count"),
            func.sum(Account.ytd_revenue).label("value"),
        )
        .group_by(Account.pipeline_stage)
        .all()
    )
    return jsonify([
        {"pipeline_stage": r.pipeline_stage, "count": r.count, "value": r.value or 0}
        for r in rows
    ])


@app.route('/api/territory/health', methods=['GET'])
def get_territory_health():
    from sqlalchemy import func
    total = db.session.query(func.count(Account.id)).scalar() or 0
    at_risk = db.session.query(func.count(Account.id)).filter(Account.health_score < 60).scalar() or 0
    revenue = db.session.query(func.sum(Account.ytd_revenue)).scalar() or 0
    open_quotes = (
        Quote.query
        .filter(Quote.status.notin_(["Accepted", "Declined"]))
        .count()
    )
    return jsonify({
        "total_accounts": total,
        "at_risk_accounts": at_risk,
        "ytd_revenue": revenue,
        "open_quotes": open_quotes,
    })


# ---------------------------------------------------------------------------
# Routes: Writes
# ---------------------------------------------------------------------------

@app.route('/api/activities', methods=['POST'])
def create_activity():
    data = request.json
    activity = Activity(
        account_id=data.get('account_id'),
        activity_type=data.get('activity_type'),
        summary=data.get('summary'),
        outcome=data.get('outcome', ''),
        activity_date=data.get('activity_date', datetime.now().strftime('%Y-%m-%d')),
    )
    db.session.add(activity)
    db.session.commit()
    return jsonify({"status": "success", "id": activity.id})


@app.route('/api/quotes', methods=['POST'])
def create_quote():
    data = request.json
    quote = Quote(
        account_id=data.get('account_id'),
        quote_number=data.get('quote_number'),
        services=data.get('services', []),
        amount=data.get('amount'),
        status=data.get('status', 'Draft'),
        sent_date=data.get('sent_date'),
        expiry_date=data.get('expiry_date'),
        notes=data.get('notes', ''),
    )
    db.session.add(quote)
    db.session.commit()
    return jsonify({"status": "success", "id": quote.id})


# ---------------------------------------------------------------------------
# Route: Wizard AI
# ---------------------------------------------------------------------------

@app.route('/api/wizard/query', methods=['POST'])
def wizard_query():
    data = request.json
    query = data.get('query', '')
    account_id = data.get('account_id')
    user_persona = data.get('user_persona', 'Andrew')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    if not HAS_ANTHROPIC or not os.getenv("ANTHROPIC_API_KEY"):
        def simulate_stream():
            yield "data: {\"text\": \"[Fallback Mode] Anthropic API Key missing or not installed. \\n\"}\n\n"
            time.sleep(0.5)
            fallback = f"Your query was: {query}. The system is currently in local offline mode."
            yield f"data: {{\"text\": \"{fallback}\"}}\n\n"
            yield "data: {\"done\": true}\n\n"
        return Response(simulate_stream(), mimetype='text/event-stream')

    try:
        # Build database context via ORM
        context_str = "No specific account context provided."
        if account_id:
            acc = Account.query.get(account_id)
            if acc:
                contacts = [c.to_dict() for c in Contact.query.filter_by(account_id=account_id).all()]
                open_quotes = [q.to_dict() for q in Quote.query.filter_by(account_id=account_id).filter(Quote.status != "Accepted").all()]
                edds = [e.to_dict() for e in EddSubmission.query.filter_by(account_id=account_id).all()]
                recent_activities = [
                    a.to_dict() for a in
                    Activity.query.filter_by(account_id=account_id)
                    .order_by(Activity.activity_date.desc()).limit(5).all()
                ]
                context_str = (
                    f"Account Context: {json.dumps(acc.to_dict())}\n"
                    f"Contacts: {json.dumps(contacts)}\n"
                    f"Open Quotes: {json.dumps(open_quotes)}\n"
                    f"Recent EDDs: {json.dumps(edds)}\n"
                    f"Recent Activities: {json.dumps(recent_activities)}"
                )

        # RAG: Retrieve relevant vault context
        vault_context = "No vault context available."
        if HAS_RAG:
            try:
                vault_context = query_vault(query, n_results=5)
            except Exception as rag_err:
                print(f"RAG retrieval error: {rag_err}")
                vault_context = "Vault retrieval temporarily unavailable."

        # Persona routing
        if user_persona == "Ashley":
            persona_guardrail = """
[GUARDRAIL: STRATEGIC-EXECUTIVE]
You are communicating with Ashley, the VP of Sales.
- Focus on high-level value propositions, business metrics, and strategy.
- NEVER use code jargon or deep technical explanations.
- Keep the tone professional, executive, and focused on revenue and client relationships.
"""
        else:
            persona_guardrail = """
[GUARDRAIL: TECHNICAL-FIELD]
You are communicating with Andrew, the Regional Account Manager and Technical Lead.
- Provide precise technical detail: EPA method numbers, regulatory citations, pricing.
- Reference specific account data, contacts, and timelines.
- Be concise and direct. Cite sources from the vault when available.
"""

        system_prompt = f"""You are Orbit Wizard, an agentic AI assistant for Waypoint Analytical.

You have LIVE access to:
1. Account database (contacts, quotes, activity history, EDDs) — injected below as structured data
2. Waypoint's knowledge vault (account notes, Tier III fee schedule, regulatory references) — retrieved via RAG below
3. NCDEQ, EPA, and DWR regulatory reference documents

When answering:
- Always ground your answers in the provided context data. Do not invent account details.
- Cite specific vault sources when referencing pricing, regulatory requirements, or account history.
- If data is insufficient, say so explicitly and suggest what information is needed.
- Provide actionable recommendations, not just summaries.

{persona_guardrail}

Current user: {user_persona}

=== DATABASE CONTEXT ===
{context_str}

=== VAULT CONTEXT (Retrieved via RAG) ===
{vault_context}"""

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        def generate():
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": query}],
                stream=True,
            )
            for event in response:
                if event.type == "content_block_delta":
                    yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
            yield "data: {\"done\": true}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"Wizard Error: {str(e)}")
        def err_stream():
            yield f"data: {{\"text\": \"Error contacting Wizard: {str(e)}\"}}\n\n"
            yield "data: {\"done\": true}\n\n"
        return Response(err_stream(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=5000)

