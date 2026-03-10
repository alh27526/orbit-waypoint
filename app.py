import os
import sqlite3
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
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
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

# SQLAlchemy models
from models import db, User

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_demo_key")
CORS(app)

# SQLAlchemy Configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orbit.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

VAULT_PATH = os.getenv("VAULT_PATH", os.path.join(os.path.dirname(__file__), 'vault'))

# Launch Phoenix locally (optional tracing)
if HAS_ANTHROPIC and HAS_PHOENIX:
    try:
        px.launch_app()
        tracer_provider = trace_sdk.TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006/v1/traces")))
        trace_api.set_tracer_provider(tracer_provider)
        AnthropicInstrumentor().instrument()
    except Exception:
        pass  # Phoenix is optional, don't crash on failure

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Route: User Roles (DB-backed via SQLAlchemy) ---
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

# --- Route: Frontend Serve ---
@app.route('/')
def index():
    return send_from_directory("templates", "index.html")

# --- Routes: Accounts ---
@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    conn = get_db_connection()
    accs = conn.execute('SELECT * FROM accounts ORDER BY last_contact_date DESC').fetchall()
    conn.close()
    return jsonify([dict(a) for a in accs])

@app.route('/api/accounts/<int:acc_id>', methods=['GET'])
def get_account_detail(acc_id):
    conn = get_db_connection()
    acc = conn.execute('SELECT * FROM accounts WHERE id = ?', (acc_id,)).fetchone()
    conn.close()
    if acc:
        return jsonify(dict(acc))
    return jsonify({"error": "Account not found"}), 404

@app.route('/api/accounts/<int:acc_id>/contacts', methods=['GET'])
def get_contacts(acc_id):
    conn = get_db_connection()
    contacts = conn.execute('SELECT * FROM contacts WHERE account_id = ?', (acc_id,)).fetchall()
    conn.close()
    return jsonify([dict(c) for c in contacts])

@app.route('/api/accounts/<int:acc_id>/quotes', methods=['GET'])
def get_quotes(acc_id):
    conn = get_db_connection()
    quotes = conn.execute('SELECT * FROM quotes WHERE account_id = ? ORDER BY sent_date DESC', (acc_id,)).fetchall()
    conn.close()
    res = []
    for q in quotes:
        dq = dict(q)
        try:
            dq['services'] = json.loads(dq['services'])
        except (json.JSONDecodeError, TypeError):
            dq['services'] = []
        res.append(dq)
    return jsonify(res)

@app.route('/api/accounts/<int:acc_id>/activities', methods=['GET'])
def get_activities(acc_id):
    conn = get_db_connection()
    activities = conn.execute('SELECT * FROM activities WHERE account_id = ? ORDER BY activity_date DESC', (acc_id,)).fetchall()
    conn.close()
    return jsonify([dict(a) for a in activities])

@app.route('/api/accounts/<int:acc_id>/edd', methods=['GET'])
def get_edd(acc_id):
    conn = get_db_connection()
    edds = conn.execute('SELECT * FROM edd_submissions WHERE account_id = ? ORDER BY submission_date DESC', (acc_id,)).fetchall()
    conn.close()
    res = []
    for e in edds:
        de = dict(e)
        try:
            de['field_flags'] = json.loads(de['field_flags'])
        except (json.JSONDecodeError, TypeError):
            de['field_flags'] = []
        res.append(de)
    return jsonify(res)

# --- Routes: Pipeline & Territory ---
@app.route('/api/pipeline/summary', methods=['GET'])
def get_pipeline_summary():
    conn = get_db_connection()
    stages = conn.execute('SELECT pipeline_stage, COUNT(*) as count, SUM(ytd_revenue) as value FROM accounts GROUP BY pipeline_stage').fetchall()
    conn.close()
    return jsonify([dict(s) for s in stages])

@app.route('/api/territory/health', methods=['GET'])
def get_territory_health():
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) as count FROM accounts').fetchone()['count']
    at_risk = conn.execute('SELECT COUNT(*) as count FROM accounts WHERE health_score < 60').fetchone()['count']
    revenue = conn.execute('SELECT SUM(ytd_revenue) as total FROM accounts').fetchone()['total']
    quotes = conn.execute('SELECT COUNT(*) as count FROM quotes WHERE status != "Accepted" and status != "Declined"').fetchone()['count']
    conn.close()
    return jsonify({
        "total_accounts": total,
        "at_risk_accounts": at_risk,
        "ytd_revenue": revenue or 0,
        "open_quotes": quotes
    })

# --- Routes: Writes ---
@app.route('/api/activities', methods=['POST'])
def create_activity():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO activities (account_id, activity_type, summary, outcome, activity_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (data.get('account_id'), data.get('activity_type'), data.get('summary'), data.get('outcome', ''), data.get('activity_date', datetime.now().strftime('%Y-%m-%d'))))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "id": cur.lastrowid})

@app.route('/api/quotes', methods=['POST'])
def create_quote():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    services_json = json.dumps(data.get('services', []))
    cur.execute('''
        INSERT INTO quotes (account_id, quote_number, services, amount, status, sent_date, expiry_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data.get('account_id'), data.get('quote_number'), services_json, data.get('amount'), data.get('status', 'Draft'), data.get('sent_date'), data.get('expiry_date'), data.get('notes', '')))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "id": cur.lastrowid})

# --- Route: Wizard AI ---
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
        # Build database context
        context_str = "No specific account context provided."
        if account_id:
            conn = get_db_connection()
            acc = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
            if acc:
                acc_dict = dict(acc)
                edds = [dict(e) for e in conn.execute('SELECT * FROM edd_submissions WHERE account_id = ?', (account_id,)).fetchall()]
                quotes = [dict(q) for q in conn.execute('SELECT * FROM quotes WHERE account_id = ? AND status != "Accepted"', (account_id,)).fetchall()]
                activities = [dict(a) for a in conn.execute('SELECT * FROM activities WHERE account_id = ? ORDER BY activity_date DESC LIMIT 5', (account_id,)).fetchall()]
                contacts = [dict(c) for c in conn.execute('SELECT * FROM contacts WHERE account_id = ?', (account_id,)).fetchall()]
                context_str = f"Account Context: {json.dumps(acc_dict)}\nContacts: {json.dumps(contacts)}\nOpen Quotes: {json.dumps(quotes)}\nRecent EDDs: {json.dumps(edds)}\nRecent Activities: {json.dumps(activities)}"
            conn.close()

        # RAG: Retrieve relevant vault context from ChromaDB
        vault_context = "No vault context available."
        if HAS_RAG:
            try:
                vault_context = query_vault(query, n_results=5)
            except Exception as rag_err:
                print(f"RAG retrieval error: {rag_err}")
                vault_context = "Vault retrieval temporarily unavailable."

        # Context Engineering / Persona Routing
        persona_guardrail = ""
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
                model="claude-sonnet-4-6",
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
