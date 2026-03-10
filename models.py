from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON

db = SQLAlchemy()


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
