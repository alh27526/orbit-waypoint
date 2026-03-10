"""
seed_production.py — One-time production seed script.
Run ONCE after deploying to Render to populate the DB with initial data.

Usage (from Render Shell tab or locally against DATABASE_URL):
    DATABASE_URL=postgresql://... python seed_production.py
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# Validate we have a DB URL before importing Flask
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("❌ DATABASE_URL is not set. Exiting.")
    sys.exit(1)

# Normalize Render's postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    os.environ["DATABASE_URL"] = DATABASE_URL.replace("postgres://", "postgresql://", 1)

from app import app
from models import db, Account, Contact, Quote, Activity, EddSubmission

ACCOUNTS = [
    {
        "name": "City of Durham",
        "industry": "Municipal Water / Wastewater",
        "regulatory_tier": "Municipal",
        "territory": "GNC",
        "pipeline_stage": "Active",
        "health_score": 82,
        "ytd_revenue": 14200.00,
        "last_contact_date": "2026-03-01",
        "notes": "Key NPDES permit renewal in Q3. EDD submission pending.",
    },
    {
        "name": "Harnett Regional Water",
        "industry": "Municipal Water",
        "regulatory_tier": "Municipal",
        "territory": "GNC",
        "pipeline_stage": "Active",
        "health_score": 91,
        "ytd_revenue": 9800.00,
        "last_contact_date": "2026-02-15",
        "notes": "Long-term contract. Quarterly organics and metals.",
    },
    {
        "name": "City of Lumberton",
        "industry": "Municipal Water / Wastewater",
        "regulatory_tier": "Municipal",
        "territory": "SE",
        "pipeline_stage": "At Risk",
        "health_score": 44,
        "ytd_revenue": 3100.00,
        "last_contact_date": "2025-11-20",
        "notes": "Budget constraints. Competing bid from TestAmerica. Needs follow-up.",
    },
    {
        "name": "Rose Acre Farms",
        "industry": "Agriculture / Food Processing",
        "regulatory_tier": "Industrial",
        "territory": "SE",
        "pipeline_stage": "Active",
        "health_score": 76,
        "ytd_revenue": 22500.00,
        "last_contact_date": "2026-02-28",
        "notes": "High volume. Ammonia, BOD, TSS per state NPDES permit.",
    },
    {
        "name": "Brenntag Mid-South",
        "industry": "Chemical Distribution",
        "regulatory_tier": "RCRA / Industrial",
        "territory": "SE",
        "pipeline_stage": "Prospecting",
        "health_score": 60,
        "ytd_revenue": 0.00,
        "last_contact_date": "2026-01-10",
        "notes": "Intro meeting completed. Awaiting waste characterization quote.",
    },
]

CONTACTS = [
    {"account_name": "City of Durham", "name": "Sarah Mitchell", "title": "Environmental Compliance Manager", "email": "s.mitchell@durhamnc.gov", "phone": "919-555-0142"},
    {"account_name": "City of Durham", "name": "James Okafor", "title": "Lab Coordinator", "email": "j.okafor@durhamnc.gov", "phone": "919-555-0143"},
    {"account_name": "Harnett Regional Water", "name": "Teresa Banks", "title": "Water Quality Director", "email": "tbanks@harnettwater.org", "phone": "910-555-0201"},
    {"account_name": "City of Lumberton", "name": "Marcus Reeves", "title": "Utilities Director", "email": "mreeves@lumbertonNC.gov", "phone": "910-555-0312"},
    {"account_name": "Rose Acre Farms", "name": "Dan Whitfield", "title": "Environmental Manager", "email": "dwhitfield@roseacre.com", "phone": "252-555-0455"},
    {"account_name": "Brenntag Mid-South", "name": "Kelly Nguyen", "title": "HSE Manager", "email": "kelly.nguyen@brenntag.com", "phone": "901-555-0521"},
]


def seed():
    with app.app_context():
        db.create_all()

        seeded = 0
        for acc_data in ACCOUNTS:
            exists = Account.query.filter_by(name=acc_data["name"]).first()
            if not exists:
                acc = Account(**acc_data)
                db.session.add(acc)
                db.session.flush()  # get the ID

                # Seed matching contacts
                for c in CONTACTS:
                    if c["account_name"] == acc_data["name"]:
                        contact = Contact(
                            account_id=acc.id,
                            name=c["name"],
                            title=c["title"],
                            email=c["email"],
                            phone=c["phone"],
                        )
                        db.session.add(contact)
                seeded += 1

        db.session.commit()
        print(f"✅ Production seed complete: {seeded} accounts inserted.")
        print("   Run 'python seed_users.py' next to seed the users table.")


if __name__ == "__main__":
    seed()
