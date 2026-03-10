"""
seed_quick_wins.py — Seed demo data for Sprint 3 quick wins.
Adds tags, source/channel, and tasks to existing accounts.
Idempotent: checks before inserting.
"""
import os
import sqlite3
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orbit.db')


def enrich():
    conn = sqlite3.connect(DB_PATH)

    # Build account name → id map
    accs = conn.execute("SELECT id, name FROM accounts").fetchall()
    acc_map = {row[1]: row[0] for row in accs}

    if not acc_map:
        print("❌ No accounts found. Run seed_data.py first.")
        conn.close()
        return

    # --- Create tasks table if not exists ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER REFERENCES accounts(id),
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Open',
            priority TEXT DEFAULT 'Medium',
            assigned_to TEXT DEFAULT 'Andrew Harris',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Add missing columns (safe even if they already exist) ---
    for col, coltype in [("source", "TEXT"), ("channel", "TEXT"), ("tags", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {coltype}")
        except Exception:
            pass  # column already exists

    for col, coltype in [("tags", "TEXT"),]:
        try:
            conn.execute(f"ALTER TABLE contacts ADD COLUMN {col} {coltype}")
        except Exception:
            pass

    conn.commit()

    # --- Account tags + source/channel ---
    ACCOUNT_META = {
        "City of Durham": {
            "tags": ["Municipal", "NPDES", "Biosolids", "Long-Term Client"],
            "source": "Existing Client",
            "channel": "Direct Relationship"
        },
        "BRENNTAG Mid-South LLC": {
            "tags": ["RCRA", "Haz Waste", "High Value", "LQG"],
            "source": "Existing Client",
            "channel": "Direct Relationship"
        },
        "City of Lumberton": {
            "tags": ["Municipal", "PFAS", "Post-Hurricane"],
            "source": "Existing Client",
            "channel": "Direct Relationship"
        },
        "Harnett Regional Water": {
            "tags": ["Prospect", "DW Compliance", "Competitor-PACE"],
            "source": "Cold Outreach",
            "channel": "Email"
        },
        "Rose Acre Farms": {
            "tags": ["Industrial WW", "Nutrient Monitoring", "Agriculture"],
            "source": "Referral",
            "channel": "Industry Contact"
        },
        "Town of Smithfield": {
            "tags": ["Municipal", "WW Monitoring", "At-Risk"],
            "source": "Existing Client",
            "channel": "Direct Relationship"
        },
        "Wake County Solid Waste": {
            "tags": ["Prospect", "Landfill", "GW Monitoring"],
            "source": "Trade Show",
            "channel": "NC DEQ Conference 2025"
        },
        "NC State University Facilities": {
            "tags": ["Institutional", "DW Compliance", "Stormwater", "Competitor-Eurofins"],
            "source": "RFP",
            "channel": "Public Bid"
        },
    }

    for name, meta in ACCOUNT_META.items():
        acc_id = acc_map.get(name)
        if acc_id:
            conn.execute(
                "UPDATE accounts SET tags = ?, source = ?, channel = ? WHERE id = ?",
                (json.dumps(meta["tags"]), meta["source"], meta["channel"], acc_id)
            )

    # --- Contact tags ---
    CONTACT_TAGS = {
        "Sarah Mitchell": ["Decision Maker", "Primary Contact"],
        "James Worthington": ["Technical", "Lab"],
        "David Chen": ["Decision Maker", "EHS"],
        "Patricia Williams": ["Facility Ops"],
        "Marcus Johnson": ["Decision Maker", "Public Works"],
        "Teresa Locklear": ["Environmental Compliance"],
        "Robert Glenn": ["Technical", "Water Treatment"],
        "Jennifer Hayes": ["Decision Maker", "Environmental"],
        "Carl Frazier": ["Decision Maker", "Unresponsive"],
        "Denise Armstrong": ["Prospect Contact", "Environmental Programs"],
        "Brian Cho": ["Technical", "EHS", "Procurement"],
    }

    for name, tags in CONTACT_TAGS.items():
        conn.execute("UPDATE contacts SET tags = ? WHERE name = ?", (json.dumps(tags), name))

    # --- Tasks ---
    TASKS = [
        {"account_name": "City of Durham", "title": "Review March NPDES EDD flags with James", "description": "6 field flags on stormwater EDD need resolution before NCDEQ submission deadline.", "due_date": "2026-03-15", "priority": "High"},
        {"account_name": "City of Durham", "title": "Send biosolids characterization follow-up", "description": "Follow up on WAY-0412 quote sent 3/6.", "due_date": "2026-03-12", "priority": "Medium"},
        {"account_name": "BRENNTAG Mid-South LLC", "title": "Confirm Q2 GW sampling dates", "description": "David Chen confirmed April 15-16. Send crew schedule.", "due_date": "2026-03-20", "priority": "Medium"},
        {"account_name": "Harnett Regional Water", "title": "Follow up on DW compliance quote", "description": "WAY-0385 expires 3/15. Robert indicated interest in trial quarter.", "due_date": "2026-03-11", "priority": "Urgent"},
        {"account_name": "Town of Smithfield", "title": "Schedule quarterly review with Carl Frazier", "description": "3 unanswered contact attempts. Consider on-site visit.", "due_date": "2026-03-14", "priority": "High"},
        {"account_name": "Rose Acre Farms", "title": "Prepare ammonia exceedance corrective action report", "description": "February discharge exceeded permit limit. NCDEQ may require formal response.", "due_date": "2026-03-18", "priority": "Urgent"},
        {"account_name": "NC State University Facilities", "title": "Await procurement decision on annual contract", "description": "Brian Cho presenting to procurement. Competing with Eurofins at 8% lower.", "due_date": "2026-03-15", "priority": "Medium"},
        {"account_name": "Wake County Solid Waste", "title": "Check with Denise on budget review result", "description": "Proposal sent Jan 15. County budget review was scheduled for March.", "due_date": "2026-03-20", "priority": "Low"},
    ]

    task_added = 0
    for t in TASKS:
        acc_id = acc_map.get(t["account_name"])
        if not acc_id:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE account_id = ? AND title = ?",
            (acc_id, t["title"])
        ).fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO tasks (account_id, title, description, due_date, priority) VALUES (?, ?, ?, ?, ?)",
                (acc_id, t["title"], t["description"], t["due_date"], t["priority"])
            )
            task_added += 1

    conn.commit()
    conn.close()
    print(f"✅ Quick wins seeded: account tags/source/channel, contact tags, {task_added} tasks.")


if __name__ == "__main__":
    enrich()
