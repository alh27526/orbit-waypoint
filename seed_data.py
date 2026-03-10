"""
seed_data.py — Seed the Orbit database with demo Waypoint accounts.
Idempotent: running twice does not create duplicates.
"""
import os
import sys
import sqlite3
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orbit.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT,
    regulatory_tier TEXT,
    territory TEXT,
    pipeline_stage TEXT,
    health_score INTEGER,
    ytd_revenue REAL,
    last_contact_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    name TEXT NOT NULL,
    title TEXT,
    email TEXT,
    phone TEXT,
    last_contact_date TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    quote_number TEXT,
    services TEXT,
    amount REAL,
    status TEXT,
    sent_date TEXT,
    expiry_date TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    activity_type TEXT,
    summary TEXT,
    outcome TEXT,
    activity_date TEXT,
    created_by TEXT DEFAULT 'Andrew Harris'
);

CREATE TABLE IF NOT EXISTS edd_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    project_name TEXT,
    submission_date TEXT,
    format_type TEXT,
    status TEXT,
    field_flags TEXT
);
"""

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
        "notes": "Long-standing municipal client. Quarterly DW compliance + NPDES monitoring. Biosolids RFP opportunity Q3."
    },
    {
        "name": "City of Lumberton",
        "industry": "Municipal Water / Wastewater",
        "regulatory_tier": "Municipal",
        "territory": "CNC",
        "pipeline_stage": "Active",
        "health_score": 71,
        "ytd_revenue": 8400.00,
        "last_contact_date": "2026-02-15",
        "notes": "Monthly NPDES discharge monitoring. PFAS testing opportunity. Post-hurricane infrastructure rebuild."
    },
    {
        "name": "BRENNTAG Mid-South LLC",
        "industry": "Industrial / Chemical Distribution",
        "regulatory_tier": "RCRA",
        "territory": "GNC",
        "pipeline_stage": "Active",
        "health_score": 91,
        "ytd_revenue": 22500.00,
        "last_contact_date": "2026-03-05",
        "notes": "RCRA LQG. Quarterly haz waste profiling + annual GW monitoring. High-value retained account."
    },
    {
        "name": "Harnett Regional Water",
        "industry": "Municipal Water",
        "regulatory_tier": "Municipal",
        "territory": "CNC",
        "pipeline_stage": "Quoted",
        "health_score": 55,
        "ytd_revenue": 0.00,
        "last_contact_date": "2026-01-20",
        "notes": "Prospect — currently uses PACE. Quote sent Dec 2025 for DW compliance package. Follow up needed."
    },
    {
        "name": "Rose Acre Farms",
        "industry": "Agricultural / Industrial",
        "regulatory_tier": "Industrial Wastewater",
        "territory": "GNC-RDU",
        "pipeline_stage": "Active",
        "health_score": 76,
        "ytd_revenue": 12000.00,
        "last_contact_date": "2026-02-28",
        "notes": "Industrial WW client. Monthly discharge monitoring + semi-annual GW. Nutrient regulation changes may increase scope."
    },
    {
        "name": "Town of Smithfield",
        "industry": "Municipal Water / Wastewater",
        "regulatory_tier": "Municipal",
        "territory": "GNC",
        "pipeline_stage": "Active",
        "health_score": 68,
        "ytd_revenue": 6800.00,
        "last_contact_date": "2026-01-28",
        "notes": "Municipal WW monitoring. At-risk — no contact in 40+ days. Needs quarterly review scheduling."
    },
    {
        "name": "Wake County Solid Waste",
        "industry": "Solid Waste Management",
        "regulatory_tier": "Industrial",
        "territory": "GNC-RDU",
        "pipeline_stage": "Prospect",
        "health_score": 42,
        "ytd_revenue": 0.00,
        "last_contact_date": "2025-12-10",
        "notes": "New prospect. Landfill GW monitoring opportunity. Initial meeting held Dec 2025. No follow-up yet."
    },
    {
        "name": "NC State University Facilities",
        "industry": "Institutional",
        "regulatory_tier": "Municipal",
        "territory": "GNC-RDU",
        "pipeline_stage": "Negotiating",
        "health_score": 65,
        "ytd_revenue": 3200.00,
        "last_contact_date": "2026-02-20",
        "notes": "Campus DW compliance + stormwater. Negotiating annual contract. Competing with Eurofins on price."
    },
]

CONTACTS = [
    # City of Durham
    {"account_name": "City of Durham", "name": "Sarah Mitchell", "title": "Utilities Director", "email": "smitchell@durhamnc.gov", "phone": "919-560-4326", "last_contact_date": "2026-03-01"},
    {"account_name": "City of Durham", "name": "James Worthington", "title": "Lab Coordinator", "email": "jworthington@durhamnc.gov", "phone": "919-560-4330", "last_contact_date": "2026-02-15"},
    # City of Lumberton
    {"account_name": "City of Lumberton", "name": "Marcus Johnson", "title": "Public Works Director", "email": "mjohnson@ci.lumberton.nc.us", "phone": "910-671-3869", "last_contact_date": "2026-02-15"},
    {"account_name": "City of Lumberton", "name": "Teresa Locklear", "title": "Environmental Compliance", "email": "tlocklear@ci.lumberton.nc.us", "phone": "910-671-3870", "last_contact_date": "2026-02-10"},
    # BRENNTAG
    {"account_name": "BRENNTAG Mid-South LLC", "name": "David Chen", "title": "EHS Manager", "email": "david.chen@brenntag.com", "phone": "919-688-4400", "last_contact_date": "2026-03-05"},
    {"account_name": "BRENNTAG Mid-South LLC", "name": "Patricia Williams", "title": "Facility Manager", "email": "patricia.williams@brenntag.com", "phone": "919-688-4401", "last_contact_date": "2026-02-20"},
    # Harnett Regional Water
    {"account_name": "Harnett Regional Water", "name": "Robert Glenn", "title": "Water Treatment Superintendent", "email": "rglenn@harnett.org", "phone": "910-893-7575", "last_contact_date": "2026-01-20"},
    {"account_name": "Harnett Regional Water", "name": "Amy Simmons", "title": "Quality Assurance", "email": "asimmons@harnett.org", "phone": "910-893-7576", "last_contact_date": "2026-01-15"},
    # Rose Acre Farms
    {"account_name": "Rose Acre Farms", "name": "Jennifer Hayes", "title": "Environmental Manager", "email": "jhayes@roseacre.com", "phone": "919-555-0142", "last_contact_date": "2026-02-28"},
    # Town of Smithfield
    {"account_name": "Town of Smithfield", "name": "Carl Frazier", "title": "Utilities Superintendent", "email": "cfrazier@townofsmithfield.com", "phone": "919-934-2116", "last_contact_date": "2026-01-28"},
    # Wake County
    {"account_name": "Wake County Solid Waste", "name": "Denise Armstrong", "title": "Environmental Programs Manager", "email": "darmstrong@wakegov.com", "phone": "919-856-6187", "last_contact_date": "2025-12-10"},
    # NC State
    {"account_name": "NC State University Facilities", "name": "Brian Cho", "title": "Environmental Health & Safety", "email": "bcho@ncsu.edu", "phone": "919-515-7915", "last_contact_date": "2026-02-20"},
]

QUOTES = [
    {"account_name": "City of Durham", "quote_number": "WAY-0412", "services": json.dumps(["TCLP Metals Suite", "Full VOC/SVOC Scan"]), "amount": 3200.00, "status": "Sent", "sent_date": "2026-03-06", "expiry_date": "2026-04-06", "notes": "Biosolids characterization testing for new management program"},
    {"account_name": "City of Durham", "quote_number": "WAY-0398", "services": json.dumps(["Drinking Water Compliance Package", "Lead & Copper Rule"]), "amount": 1850.00, "status": "Pending", "sent_date": "2026-02-20", "expiry_date": "2026-03-20", "notes": "Annual DW compliance renewal"},
    {"account_name": "Harnett Regional Water", "quote_number": "WAY-0385", "services": json.dumps(["EPA 200.8 Metals", "EPA 524.2 VOCs", "EPA 300.0 Inorganics", "EPA 533 PFAS"]), "amount": 18500.00, "status": "Sent", "sent_date": "2025-12-15", "expiry_date": "2026-03-15", "notes": "Full DW compliance package — competing with PACE on price"},
    {"account_name": "NC State University Facilities", "quote_number": "WAY-0410", "services": json.dumps(["Campus DW Compliance", "Stormwater Monitoring"]), "amount": 8200.00, "status": "Negotiating", "sent_date": "2026-02-25", "expiry_date": "2026-03-25", "notes": "Annual contract — Eurofins competing at 8% lower"},
]

ACTIVITIES = [
    {"account_name": "City of Durham", "activity_type": "site_visit", "summary": "Quarterly review with Sarah Mitchell. Discussed biosolids testing RFP.", "outcome": "RFP expected Q3 2026. Will send quote for characterization testing.", "activity_date": "2026-03-01"},
    {"account_name": "City of Durham", "activity_type": "quote", "summary": "Sent WAY-0412 for biosolids characterization testing.", "outcome": "Awaiting response.", "activity_date": "2026-03-06"},
    {"account_name": "BRENNTAG Mid-South LLC", "activity_type": "call", "summary": "Confirmed Q2 groundwater monitoring schedule with David Chen.", "outcome": "Sampling scheduled for April 15-16.", "activity_date": "2026-03-05"},
    {"account_name": "BRENNTAG Mid-South LLC", "activity_type": "email", "summary": "Sent annual contract renewal pricing for FY2027.", "outcome": "David reviewing internally. Expects approval by March 20.", "activity_date": "2026-03-03"},
    {"account_name": "Harnett Regional Water", "activity_type": "call", "summary": "Follow-up call to Robert Glenn on outstanding quote WAY-0385.", "outcome": "Robert says PACE turnaround issues continue. Interested in trial quarter.", "activity_date": "2026-01-20"},
    {"account_name": "Rose Acre Farms", "activity_type": "email", "summary": "Sent updated nutrient monitoring proposal per new NC regulations.", "outcome": "Jennifer reviewing.", "activity_date": "2026-02-28"},
    {"account_name": "Town of Smithfield", "activity_type": "call", "summary": "Called Carl Frazier for quarterly check-in. No answer.", "outcome": "Left voicemail. Need to follow up.", "activity_date": "2026-01-28"},
    {"account_name": "NC State University Facilities", "activity_type": "email", "summary": "Sent revised pricing after Eurofins counteroffer.", "outcome": "Brian Cho said he would present to procurement this week.", "activity_date": "2026-02-20"},
]

EDD_SUBMISSIONS = [
    {
        "account_name": "City of Durham",
        "project_name": "NPDES Monthly Discharge - February 2026",
        "submission_date": "2026-02-28",
        "format_type": "NCDEQ",
        "status": "Pending",
        "field_flags": json.dumps([
            "Missing monitoring location identifier for Outfall 002",
            "Sample time not recorded for 02/15 grab samples",
            "Fecal coliform result qualifier flag missing",
            "pH daily monitoring gap on 02/22 — no value recorded"
        ])
    },
    {
        "account_name": "City of Durham",
        "project_name": "Drinking Water Compliance - Q4 2025",
        "submission_date": "2025-12-31",
        "format_type": "EPA",
        "status": "Submitted",
        "field_flags": json.dumps([])
    },
    {
        "account_name": "BRENNTAG Mid-South LLC",
        "project_name": "RCRA GW Monitoring - Q4 2025",
        "submission_date": "2025-12-20",
        "format_type": "NCDEQ",
        "status": "Accepted",
        "field_flags": json.dumps([])
    },
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Create schema
    conn.executescript(SCHEMA)

    # Check if already seeded
    existing = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if existing > 0:
        print(f"ℹ️  Database already has {existing} accounts. Skipping seed (idempotent).")
        conn.close()
        return

    # Insert accounts
    for acc in ACCOUNTS:
        conn.execute(
            "INSERT INTO accounts (name, industry, regulatory_tier, territory, pipeline_stage, health_score, ytd_revenue, last_contact_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (acc["name"], acc["industry"], acc["regulatory_tier"], acc["territory"], acc["pipeline_stage"], acc["health_score"], acc["ytd_revenue"], acc["last_contact_date"], acc["notes"])
        )
    conn.commit()

    # Build account name → id map
    accs = conn.execute("SELECT id, name FROM accounts").fetchall()
    acc_map = {row[1]: row[0] for row in accs}

    # Insert contacts
    for c in CONTACTS:
        acc_id = acc_map.get(c["account_name"])
        if acc_id:
            conn.execute(
                "INSERT INTO contacts (account_id, name, title, email, phone, last_contact_date) VALUES (?, ?, ?, ?, ?, ?)",
                (acc_id, c["name"], c["title"], c["email"], c["phone"], c["last_contact_date"])
            )

    # Insert quotes
    for q in QUOTES:
        acc_id = acc_map.get(q["account_name"])
        if acc_id:
            conn.execute(
                "INSERT INTO quotes (account_id, quote_number, services, amount, status, sent_date, expiry_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (acc_id, q["quote_number"], q["services"], q["amount"], q["status"], q["sent_date"], q["expiry_date"], q["notes"])
            )

    # Insert activities
    for a in ACTIVITIES:
        acc_id = acc_map.get(a["account_name"])
        if acc_id:
            conn.execute(
                "INSERT INTO activities (account_id, activity_type, summary, outcome, activity_date) VALUES (?, ?, ?, ?, ?)",
                (acc_id, a["activity_type"], a["summary"], a["outcome"], a["activity_date"])
            )

    # Insert EDD submissions
    for e in EDD_SUBMISSIONS:
        acc_id = acc_map.get(e["account_name"])
        if acc_id:
            conn.execute(
                "INSERT INTO edd_submissions (account_id, project_name, submission_date, format_type, status, field_flags) VALUES (?, ?, ?, ?, ?, ?)",
                (acc_id, e["project_name"], e["submission_date"], e["format_type"], e["status"], e["field_flags"])
            )

    conn.commit()
    conn.close()

    print(f"✅ Database seeded with {len(ACCOUNTS)} accounts, {len(CONTACTS)} contacts, {len(QUOTES)} quotes, {len(ACTIVITIES)} activities, {len(EDD_SUBMISSIONS)} EDD submissions.")


if __name__ == "__main__":
    seed()
