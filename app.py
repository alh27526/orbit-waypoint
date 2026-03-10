import os
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
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
from models import db, User, Account, Contact, Quote, Activity, EddSubmission, Task

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_demo_key")
CORS(app)

# ---------------------------------------------------------------------------
# Rate Limiting — protects Anthropic API key and prevents abuse
# Disabled automatically in TESTING mode (no changes needed to test suite)
# ---------------------------------------------------------------------------
_TESTING = os.getenv("TESTING", "0") == "1"
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    enabled=not _TESTING,
    storage_uri="memory://",   # swap for redis:// in production if desired
)

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

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger("orbit")


# ---------------------------------------------------------------------------
# Middleware: Request ID tracing
# ---------------------------------------------------------------------------

@app.before_request
def attach_request_id():
    request.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])


@app.after_request
def add_response_headers(response):
    response.headers["X-Request-ID"] = getattr(request, "request_id", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# ---------------------------------------------------------------------------
# Centralized error handlers — API never returns HTML error pages
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e.description) if hasattr(e, 'description') else "Bad request"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


@app.errorhandler(500)
def internal_error(e):
    log.exception("Unhandled 500 error")
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Route: Health Check (used by Render, uptime monitors, and SRE dashboards)
# ---------------------------------------------------------------------------

@app.route('/api/health', methods=['GET'])
@limiter.exempt
def health_check():
    """Returns 200 if the app + database are reachable."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status_code = 200 if db_ok else 503
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "version": "1.0.0",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }), status_code


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
@limiter.limit("10 per minute")
def create_activity():
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    if not data.get('account_id'):
        return jsonify({"error": "account_id is required"}), 400
    if not data.get('activity_type'):
        return jsonify({"error": "activity_type is required"}), 400
    activity = Activity(
        account_id=data['account_id'],
        activity_type=data['activity_type'],
        summary=data.get('summary', ''),
        outcome=data.get('outcome', ''),
        activity_date=data.get('activity_date', datetime.now().strftime('%Y-%m-%d')),
    )
    db.session.add(activity)
    db.session.commit()
    log.info(f"Activity {activity.id} created for account {activity.account_id}")
    return jsonify({"status": "success", "id": activity.id}), 201


@app.route('/api/quotes', methods=['POST'])
@limiter.limit("10 per minute")
def create_quote():
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    if not data.get('account_id'):
        return jsonify({"error": "account_id is required"}), 400
    if not data.get('quote_number'):
        return jsonify({"error": "quote_number is required"}), 400
    quote = Quote(
        account_id=data['account_id'],
        quote_number=data['quote_number'],
        services=data.get('services', []),
        amount=data.get('amount'),
        status=data.get('status', 'Draft'),
        sent_date=data.get('sent_date'),
        expiry_date=data.get('expiry_date'),
        notes=data.get('notes', ''),
    )
    db.session.add(quote)
    db.session.commit()
    log.info(f"Quote {quote.id} ({quote.quote_number}) created for account {quote.account_id}")
    return jsonify({"status": "success", "id": quote.id}), 201


# ---------------------------------------------------------------------------
# Routes: Tasks
# ---------------------------------------------------------------------------

@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    status_filter = request.args.get('status')
    query = Task.query.order_by(Task.due_date.asc())
    if status_filter:
        query = query.filter(Task.status == status_filter)
    return jsonify([t.to_dict() for t in query.all()])


@app.route('/api/accounts/<int:acc_id>/tasks', methods=['GET'])
def get_account_tasks(acc_id):
    tasks = Task.query.filter_by(account_id=acc_id).order_by(Task.due_date.asc()).all()
    return jsonify([t.to_dict() for t in tasks])


@app.route('/api/tasks', methods=['POST'])
@limiter.limit("10 per minute")
def create_task():
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    if not data.get('title'):
        return jsonify({"error": "title is required"}), 400
    task = Task(
        account_id=data.get('account_id'),
        title=data['title'],
        description=data.get('description', ''),
        due_date=data.get('due_date'),
        status=data.get('status', 'Open'),
        priority=data.get('priority', 'Medium'),
        assigned_to=data.get('assigned_to', 'Andrew Harris'),
    )
    db.session.add(task)
    db.session.commit()
    log.info(f"Task {task.id} created: {task.title}")
    return jsonify({"status": "success", "id": task.id}), 201


@app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
@limiter.limit("20 per minute")
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.json or {}
    for field in ('title', 'description', 'due_date', 'status', 'priority', 'assigned_to'):
        if field in data:
            setattr(task, field, data[field])
    db.session.commit()
    return jsonify(task.to_dict())


# ---------------------------------------------------------------------------
# Routes: Contacts (with duplicate detection)
# ---------------------------------------------------------------------------

@app.route('/api/contacts', methods=['POST'])
@limiter.limit("10 per minute")
def create_contact():
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    if not data.get('account_id'):
        return jsonify({"error": "account_id is required"}), 400
    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400

    # --- Duplicate detection (fuzzy match on name + email) ---
    duplicates = []
    name_lower = data['name'].strip().lower()
    email_lower = (data.get('email') or '').strip().lower()

    existing = Contact.query.filter_by(account_id=data['account_id']).all()
    for c in existing:
        score = 0
        # Exact name match
        if c.name.strip().lower() == name_lower:
            score += 60
        # Partial name match (first or last name overlap)
        elif any(part in c.name.strip().lower().split() for part in name_lower.split() if len(part) > 2):
            score += 30
        # Email match
        if email_lower and c.email and c.email.strip().lower() == email_lower:
            score += 50
        if score >= 50:
            duplicates.append({"id": c.id, "name": c.name, "email": c.email, "score": score})

    contact = Contact(
        account_id=data['account_id'],
        name=data['name'],
        title=data.get('title', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        last_contact_date=data.get('last_contact_date'),
        tags=data.get('tags', []),
    )

    if duplicates and not data.get('force'):
        return jsonify({
            "warning": "Potential duplicate contact(s) detected",
            "duplicates": duplicates,
            "hint": "Send again with force: true to create anyway",
        }), 409

    db.session.add(contact)
    db.session.commit()
    log.info(f"Contact {contact.id} ({contact.name}) created for account {contact.account_id}")
    return jsonify({"status": "success", "id": contact.id}), 201


# ---------------------------------------------------------------------------
# Routes: Quote PDF Export
# ---------------------------------------------------------------------------

@app.route('/api/quotes/<int:quote_id>/pdf', methods=['GET'])
def export_quote_pdf(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    account = Account.query.get(quote.account_id)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        import io

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
        styles = getSampleStyleSheet()
        
        # Custom styles
        header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, alignment=1)
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, spaceAfter=20)
        label_style = ParagraphStyle('LabelStyle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
        val_style = ParagraphStyle('ValStyle', parent=styles['Normal'], fontSize=9)
        
        elements = []

        # 1. Greenville Header Info
        elements.append(Paragraph("Waypoint Analytical \u2022 Greenville, NC (GNC) \u2022 114 Oakmont Drive, Greenville, NC 27858 \u2022 252-756-6208 | 252-756-0633 fax", header_style))
        elements.append(Spacer(1, 0.3*inch))

        # 2. Title & Total
        # Create a table for the top section to align Total to the right
        top_data = [
            [Paragraph("Waypoint Analytical \u2014 Quotation", title_style), 
             Table([["Total:", f"${quote.amount:,.2f}"]], colWidths=[0.8*inch, 1.2*inch], 
                   style=[('GRID', (0,0), (-1,-1), 1, colors.black), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 12), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')])]
        ]
        t_top = Table(top_data, colWidths=[4.5*inch, 2.5*inch])
        t_top.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        elements.append(t_top)
        elements.append(Spacer(1, 0.2*inch))

        # 3. Client / Project Info
        info_data = [
            [Paragraph("<b>Client</b>", label_style), Paragraph(account.name if account else "N/A", val_style), 
             Paragraph("<b>Quote No.</b>", label_style), Paragraph(quote.quote_number, val_style)],
            [Paragraph("<b>Project</b>", label_style), Paragraph(quote.notes[:40] if quote.notes else "Environmental Testing", val_style),
             Paragraph("<b>Date / Valid</b>", label_style), Paragraph(f"{quote.sent_date or 'N/A'} / 30 Days", val_style)],
            [Paragraph("<b>PM / AM</b>", label_style), Paragraph("Andrew L. Harris (AM)", val_style),
             Paragraph("<b>Level / TAT</b>", label_style), Paragraph("Level 1 \u2022 10 BD", val_style)],
        ]
        t_info = Table(info_data, colWidths=[1*inch, 3*inch, 1*inch, 2*inch])
        t_info.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(t_info)
        elements.append(Spacer(1, 0.3*inch))

        # 4. Services Table
        services = quote.services or []
        # Header: Category, Type (Service), Qty, Unit, Extended
        table_data = [["Category", "Type (Service)", "Qty", "Unit", "Extended"]]
        for svc in services:
            # Mocking qty/unit for the demo look
            table_data.append(["Testing", svc, "1", f"${quote.amount:,.2f}", f"${quote.amount:,.2f}"])
        
        # Add empty rows to match template look
        for _ in range(max(0, 15 - len(services))):
            table_data.append(["", "", "", "$0.00", "$0.00"])

        t_service = Table(table_data, colWidths=[1.2*inch, 2.8*inch, 0.8*inch, 1.1*inch, 1.1*inch])
        t_service.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ]))
        elements.append(t_service)
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph(f"Annual Program Total: <b>${quote.amount:,.2f}</b>", ParagraphStyle('TotalStyle', parent=styles['Normal'], alignment=2, fontSize=10)))
        elements.append(Spacer(1, 0.4*inch))

        # 5. Signatures
        sig_data = [
            [Paragraph("<b>Prepared by</b>", label_style), Paragraph("Andrew L. Harris", val_style), 
             Paragraph("<b>Acceptance</b>", label_style), Paragraph("________________________", val_style)],
            ["", Paragraph("Eastern Carolinas \u2014 Regional Account Manager", ParagraphStyle('Small', fontSize=7)), 
             "", Paragraph("Authorized Signature", ParagraphStyle('Small', fontSize=7))],
            ["", Paragraph("Cell: 984.332.2588  |  aharris@waypointanalytical.com", ParagraphStyle('Small', fontSize=7)), 
             "", Paragraph("Date: ________________________", val_style)],
        ]
        t_sig = Table(sig_data, colWidths=[1*inch, 3*inch, 1*inch, 2*inch])
        t_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(t_sig)
        
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<font size=7>* Total Nitrogen = NO3-N + TKN (calculated).</font>", styles['Normal']))
        elements.append(Paragraph("<font size=8>Page 1</font>", ParagraphStyle('Page', alignment=1)))

        # 6. Terms & Conditions Page
        elements.append(PageBreak())
        elements.append(Paragraph("Waypoint Analytical \u2014 Terms & Conditions", styles['Title']))
        elements.append(Paragraph("<b>General Information</b>", label_style))
        elements.append(Paragraph("The pricing listed in this schedule is based on standard TAT, normally 7-10 business days.", val_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Turnaround Time</b>", label_style))
        elements.append(Paragraph("Turnaround time (TAT) is defined as the time elapsing from validated time of sample receipt to the issuance of the report.", val_style))
        # ... more terms could be added here to match the screenshot ...
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("<font size=8>Page 2</font>", ParagraphStyle('Page', alignment=1)))

        doc.build(elements)
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=quote_{quote.quote_number}.pdf'}
        )
    except ImportError:
        return jsonify({"error": "reportlab not installed \u2014 run: pip install reportlab"}), 500


# ---------------------------------------------------------------------------
# Routes: Account/Contact Tags Update
# ---------------------------------------------------------------------------

@app.route('/api/accounts/<int:acc_id>/tags', methods=['PATCH'])
@limiter.limit("20 per minute")
def update_account_tags(acc_id):
    account = Account.query.get_or_404(acc_id)
    data = request.json or {}
    if 'tags' in data:
        account.tags = data['tags']
    if 'source' in data:
        account.source = data['source']
    if 'channel' in data:
        account.channel = data['channel']
    db.session.commit()
    return jsonify(account.to_dict())


@app.route('/api/contacts/<int:contact_id>/tags', methods=['PATCH'])
@limiter.limit("20 per minute")
def update_contact_tags(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    data = request.json or {}
    if 'tags' in data:
        contact.tags = data['tags']
    db.session.commit()
    return jsonify(contact.to_dict())

@app.route('/api/wizard/query', methods=['POST'])
@limiter.limit("20 per hour")        # protect Anthropic API key from exhaustion
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
        log.exception(f"Wizard error: {str(e)}")
        def err_stream():
            yield f"data: {{\"text\": \"Error contacting Wizard: {str(e)}\"}}\n\n"
            yield "data: {\"done\": true}\n\n"
        return Response(err_stream(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
