"""Seed the users table with Andrew and Ashley profiles."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User


def seed():
    with app.app_context():
        db.create_all()

        users_data = [
            {
                "username": "Andrew",
                "first_name": "Andrew",
                "last_name": "Harris",
                "current_title": "Regional Account Manager",
                "title_history": [],
                "role": "Account Manager",
                "permissions": ["admin", "sales", "bd", "architect", "developer"],
                "primary_email": "aharris@waypointanalytical.com",
                "alternate_emails": ["alh27526@gmail.com"],
                "primary_phone": "984-332-2588",
                "alternate_phones": [],
                "city": None,
                "state": "NC",
                "territory": "GNC; CNC; GNC-RDU",
                "department": "Sales",
                "manager": "Ashley Morris",
                "reports_to": None,
                "relationship_to_andrew": "Operator; account owner; internal builder",
                "contact_role": "Commercial lead",
                "tags": [
                    "Regional Account Manager",
                    "Eastern Carolinas",
                    "OpenClaw",
                    "Orbit",
                    "CRM owner",
                    "Environmental testing",
                ],
                "notes": "Owns customer-facing commercial activity in Eastern Carolinas. Internal builder/architect of OpenClaw and primary operator for Orbit concept.",
                "confidence": "High",
            },
            {
                "username": "Ashley",
                "first_name": "Ashley",
                "last_name": "Morris",
                "current_title": "VP of Sales",
                "title_history": ["National Director-Sales"],
                "role": "Sales Leadership",
                "permissions": ["admin", "sales", "bd"],
                "primary_email": "amorris@waypointanalytical.com",
                "alternate_emails": ["amorris@wpacorp.com"],
                "primary_phone": "901-484-3293",
                "alternate_phones": ["615-330-7988"],
                "city": "Gallatin",
                "state": "TN",
                "territory": None,
                "department": "Sales",
                "manager": None,
                "reports_to": "Andrew Harris",
                "relationship_to_andrew": "Andrew's direct manager; phase-1 co-development partner; executive sponsor",
                "contact_role": "Sales leadership",
                "tags": [
                    "VP Sales",
                    "Executive sponsor",
                    "Manager",
                    "Co-development partner",
                    "Quote database idea",
                    "Sales ops",
                    "Specialty testing",
                ],
                "notes": "Current role is best normalized as VP of Sales. Involved in process improvement, quote/searchability ideas, and specialty-testing escalation/routing.",
                "confidence": "High",
            },
        ]

        for data in users_data:
            existing = User.query.filter_by(username=data["username"]).first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                print(f"  Updated: {data['username']}")
            else:
                user = User(**data)
                db.session.add(user)
                print(f"  Created: {data['username']}")

        db.session.commit()
        print("\n✅ Users seeded successfully!")
        for u in User.query.all():
            print(f"   {u.username} | {u.current_title} | {u.role} | perms={u.permissions}")


if __name__ == "__main__":
    seed()
