from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON, func
from datetime import datetime

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# CRM Models
# ---------------------------------------------------------------------------

class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, nullable=False)
    industry = db.Column(db.Text)
    regulatory_tier = db.Column(db.Text)
    territory = db.Column(db.Text)
    pipeline_stage = db.Column(db.Text)
    health_score = db.Column(db.Integer)
    ytd_revenue = db.Column(db.Float, default=0.0)
    last_contact_date = db.Column(db.Text)
    source = db.Column(db.Text)          # e.g. "Referral", "Cold Outreach", "RFP"
    channel = db.Column(db.Text)         # e.g. "Email", "Trade Show", "Web"
    tags = db.Column(JSON, default=list) # e.g. ["PFAS", "Municipal", "At-Risk"]
    notes = db.Column(db.Text)
    created_at = db.Column(db.Text, default=lambda: datetime.utcnow().isoformat())

    # Relationships
    contacts = db.relationship("Contact", backref="account", lazy=True, cascade="all, delete-orphan")
    quotes = db.relationship("Quote", backref="account", lazy=True, cascade="all, delete-orphan")
    activities = db.relationship("Activity", backref="account", lazy=True, cascade="all, delete-orphan")
    edd_submissions = db.relationship("EddSubmission", backref="account", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "regulatory_tier": self.regulatory_tier,
            "territory": self.territory,
            "pipeline_stage": self.pipeline_stage,
            "health_score": self.health_score,
            "ytd_revenue": self.ytd_revenue or 0.0,
            "last_contact_date": self.last_contact_date,
            "source": self.source,
            "channel": self.channel,
            "tags": self.tags or [],
            "notes": self.notes,
            "created_at": self.created_at,
        }


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text)
    email = db.Column(db.Text)
    phone = db.Column(db.Text)
    last_contact_date = db.Column(db.Text)
    tags = db.Column(JSON, default=list)  # e.g. ["Decision Maker", "Technical"]
    notes = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "phone": self.phone,
            "last_contact_date": self.last_contact_date,
            "tags": self.tags or [],
            "notes": self.notes,
        }


class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    quote_number = db.Column(db.Text)
    services = db.Column(JSON, default=list)   # stored as JSON array natively
    amount = db.Column(db.Float)
    status = db.Column(db.Text, default="Draft")
    sent_date = db.Column(db.Text)
    expiry_date = db.Column(db.Text)
    notes = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "quote_number": self.quote_number,
            "services": self.services or [],
            "amount": self.amount,
            "status": self.status,
            "sent_date": self.sent_date,
            "expiry_date": self.expiry_date,
            "notes": self.notes,
        }


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    activity_type = db.Column(db.Text)
    summary = db.Column(db.Text)
    outcome = db.Column(db.Text)
    activity_date = db.Column(db.Text)
    created_by = db.Column(db.Text, default="Andrew Harris")

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "activity_type": self.activity_type,
            "summary": self.summary,
            "outcome": self.outcome,
            "activity_date": self.activity_date,
            "created_by": self.created_by,
        }


class EddSubmission(db.Model):
    __tablename__ = "edd_submissions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    project_name = db.Column(db.Text)
    submission_date = db.Column(db.Text)
    format_type = db.Column(db.Text)
    status = db.Column(db.Text)
    field_flags = db.Column(JSON, default=list)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "project_name": self.project_name,
            "submission_date": self.submission_date,
            "format_type": self.format_type,
            "status": self.status,
            "field_flags": self.field_flags or [],
        }


# ---------------------------------------------------------------------------
# Task Model
# ---------------------------------------------------------------------------

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Text)
    status = db.Column(db.Text, default="Open")       # Open, In Progress, Done
    priority = db.Column(db.Text, default="Medium")    # Low, Medium, High, Urgent
    assigned_to = db.Column(db.Text, default="Andrew Harris")
    created_at = db.Column(db.Text, default=lambda: datetime.utcnow().isoformat())

    account = db.relationship("Account", backref=db.backref("tasks", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date,
            "status": self.status,
            "priority": self.priority,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# User / Auth Model
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    current_title = db.Column(db.String(200))
    title_history = db.Column(JSON, default=list)
    role = db.Column(db.String(120), nullable=False)
    permissions = db.Column(JSON, nullable=False, default=list)
    primary_email = db.Column(db.String(200))
    alternate_emails = db.Column(JSON, default=list)
    primary_phone = db.Column(db.String(40))
    alternate_phones = db.Column(JSON, default=list)
    city = db.Column(db.String(120))
    state = db.Column(db.String(10))
    territory = db.Column(db.String(200))
    department = db.Column(db.String(120))
    manager = db.Column(db.String(120))
    reports_to = db.Column(db.String(120))
    relationship_to_andrew = db.Column(db.Text)
    contact_role = db.Column(db.String(200))
    tags = db.Column(JSON, default=list)
    notes = db.Column(db.Text)
    confidence = db.Column(db.String(20), default="High")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "current_title": self.current_title,
            "title_history": self.title_history or [],
            "role": self.role,
            "permissions": self.permissions or [],
            "primary_email": self.primary_email,
            "alternate_emails": self.alternate_emails or [],
            "primary_phone": self.primary_phone,
            "alternate_phones": self.alternate_phones or [],
            "city": self.city,
            "state": self.state,
            "territory": self.territory,
            "department": self.department,
            "manager": self.manager,
            "reports_to": self.reports_to,
            "relationship_to_andrew": self.relationship_to_andrew,
            "contact_role": self.contact_role,
            "tags": self.tags or [],
            "notes": self.notes,
            "confidence": self.confidence,
        }
