"""
import_real_data.py — Import real Nutshell CRM data into Orbit.

Sources:
- ALH_Nutshell_Companies_MASTER_IMPORT.csv (302 companies)
- ALH_Nutshell_People_Import_Cleaned.csv (716 contacts)
- ACCOUNTS_INDEX.md (revenue tiers, Territory data)

This replaces seed_data.py with REAL production data.
"""
import os
import csv
import re
import sqlite3

# Resolve the curly-quote directory name
BASE = None
for d in os.listdir("/Users/alh/Documents"):
    if d.startswith("Documents - Andrew"):
        BASE = os.path.join("/Users/alh/Documents", d)
        break

CRM_DIR = os.path.join(BASE, "brain", "work", "crm") if BASE else None
ORBIT_DIR = os.path.join(BASE, "orbit") if BASE else None
DB_PATH = os.path.join(ORBIT_DIR, "orbit.db") if ORBIT_DIR else None

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_number TEXT,
    industry TEXT,
    regulatory_tier TEXT,
    territory TEXT,
    pipeline_stage TEXT,
    health_score INTEGER,
    ytd_revenue REAL DEFAULT 0,
    last_contact_date TEXT,
    tags TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    first_name TEXT,
    last_name TEXT,
    name TEXT NOT NULL,
    title TEXT,
    email TEXT,
    phone TEXT,
    mobile TEXT,
    last_contact_date TEXT,
    tags TEXT,
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


def parse_accounts_index(index_path):
    """Parse ACCOUNTS_INDEX.md to extract revenue tier and account number data."""
    revenue_map = {}
    if not os.path.exists(index_path):
        return revenue_map

    with open(index_path, "r") as f:
        content = f.read()

    # Parse the table rows
    for line in content.split("\n"):
        if "|" in line and "017-" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 8:
                company = parts[1].strip()
                # Clean wiki links
                company = re.sub(r'\[\[[^\|]*\|([^\]]*)\]\]', r'\1', company)
                company = re.sub(r'\[\[([^\]]*)\]\]', r'\1', company)
                acct_num = parts[2].strip()
                territory = parts[3].strip()
                client_type = parts[4].strip()
                revenue_str = parts[5].strip().replace("$", "").replace(",", "")
                tier = parts[6].strip()

                try:
                    revenue = float(revenue_str)
                except ValueError:
                    revenue = 0.0

                # Normalize company name for matching
                key = company.upper().strip()
                revenue_map[key] = {
                    "account_number": acct_num,
                    "revenue": revenue,
                    "tier": tier,
                    "territory": territory,
                    "client_type": client_type,
                }

    return revenue_map


def determine_industry(tags_str, client_type=""):
    """Map tags and client type to an industry category."""
    tags = tags_str.lower() if tags_str else ""
    ct = client_type.lower()

    if "municipal-dw" in ct or "municipal-dw" in tags:
        return "Municipal Water"
    if "municipal-ww" in ct or "municipal-ww" in tags:
        return "Municipal Wastewater"
    if "municipal" in ct or "municipal" in tags:
        return "Municipal"
    if "industrial" in ct or "industrial" in tags:
        return "Industrial"
    if "consultant" in ct or "consultant" in tags:
        return "Consultant"
    if "agriculture" in ct or "agriculture" in tags:
        return "Agricultural"
    if "utility-operator" in ct or "utility" in tags:
        return "Utility Operator"
    if "education" in ct or "education" in tags:
        return "Education"
    if "solid-waste" in ct or "solid-waste" in tags:
        return "Solid Waste"
    if "environmental" in ct or "environmental-org" in tags:
        return "Environmental Organization"
    if "rcra" in tags:
        return "RCRA Industrial"
    if "development" in ct:
        return "Development"
    if "laboratory" in ct:
        return "Laboratory"
    if "government" in ct:
        return "Government"
    return "Other"


def determine_pipeline_stage(revenue, tier=""):
    """Infer pipeline stage from revenue and tier."""
    if revenue > 50000:
        return "Retained"
    elif revenue > 10000:
        return "Active"
    elif revenue > 0:
        return "Active"
    else:
        return "Prospect"


def compute_health_score(revenue, tier=""):
    """Compute a health score based on revenue tier."""
    tier = tier.lower() if tier else ""
    if "tier-1" in tier:
        return 90
    elif "tier-2" in tier:
        return 75
    elif "tier-3" in tier:
        return 60
    elif "tier-4" in tier:
        return 45
    else:
        return 30  # Unknown/prospect


def import_data():
    if not CRM_DIR or not DB_PATH:
        print("ERROR: Could not find project directories")
        return

    companies_csv = os.path.join(CRM_DIR, "ALH_Nutshell_Companies_MASTER_IMPORT.csv")
    people_csv = os.path.join(CRM_DIR, "ALH_Nutshell_People_Import_Cleaned.csv")
    index_md = os.path.join(CRM_DIR, "ACCOUNTS_INDEX.md")

    if not os.path.exists(companies_csv):
        print(f"ERROR: Companies CSV not found: {companies_csv}")
        return

    # Parse revenue/tier data from accounts index
    revenue_map = parse_accounts_index(index_md)
    print(f"📊 Loaded revenue data for {len(revenue_map)} accounts from ACCOUNTS_INDEX.md")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Create schema (preserves existing tables)
    # Actually, we want to drop tables first to recreate the schema cleanly
    conn.executescript("""
        DROP TABLE IF EXISTS edd_submissions;
        DROP TABLE IF EXISTS activities;
        DROP TABLE IF EXISTS quotes;
        DROP TABLE IF EXISTS contacts;
        DROP TABLE IF EXISTS accounts;
    """)
    conn.executescript(SCHEMA)

    # Check for existing data
    existing = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if existing > 0:
        print(f"⚠️  Database already has {existing} accounts. Clearing for fresh import...")
        conn.execute("DELETE FROM accounts")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM quotes")
        conn.execute("DELETE FROM activities")
        conn.execute("DELETE FROM edd_submissions")
        conn.commit()

    # ── Import Companies ──
    account_count = 0
    with open(companies_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = row.get("Company", "").strip()
            if not company:
                continue

            territory = row.get("Territory", "").strip()
            tags = row.get("Tags", "").strip()
            phone = row.get("Phone", "").strip()
            address = row.get("Address", "").strip()
            city = row.get("City", "").strip()
            state = row.get("State", "").strip()

            # Match to revenue index
            key = company.upper()
            rev_data = revenue_map.get(key, {})
            revenue = rev_data.get("revenue", 0.0)
            tier = rev_data.get("tier", "")
            client_type = rev_data.get("client_type", "")
            acct_num = rev_data.get("account_number", "")

            # If territory from index is more specific, use it
            if rev_data.get("territory"):
                territory = rev_data["territory"]

            industry = determine_industry(tags, client_type)
            pipeline_stage = determine_pipeline_stage(revenue, tier)
            health_score = compute_health_score(revenue, tier)

            conn.execute(
                """INSERT INTO accounts 
                   (name, account_number, industry, regulatory_tier, territory, pipeline_stage, 
                    health_score, ytd_revenue, tags, phone, address, city, state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company, acct_num, industry, tier or "Unknown", territory, pipeline_stage,
                 health_score, revenue, tags, phone, address, city, state)
            )
            account_count += 1

    conn.commit()
    print(f"✅ Imported {account_count} accounts")

    # Build company name → account_id map
    accs = conn.execute("SELECT id, name FROM accounts").fetchall()
    acc_map = {}
    for row in accs:
        acc_map[row[1].upper()] = row[0]

    # ── Import Contacts ──
    contact_count = 0
    if os.path.exists(people_csv):
        with open(people_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get("Company", "").strip()
                first = row.get("First Name", "").strip()
                last = row.get("Last Name", "").strip()
                title = row.get("Title", "").strip()
                email = row.get("Email", "").strip()
                work_phone = row.get("Work Phone", "").strip()
                mobile = row.get("Mobile", "").strip()
                tags = row.get("Tags", "").strip()

                if not company or not (first or last):
                    continue

                full_name = f"{first} {last}".strip()
                acc_id = acc_map.get(company.upper())

                if acc_id:
                    conn.execute(
                        """INSERT INTO contacts 
                           (account_id, first_name, last_name, name, title, email, phone, mobile, tags)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (acc_id, first, last, full_name, title, email, work_phone, mobile, tags)
                    )
                    contact_count += 1

        conn.commit()
        print(f"✅ Imported {contact_count} contacts (matched to accounts)")
    else:
        print("⚠️  People CSV not found, skipping contacts")

    # Print summary
    tier_summary = conn.execute(
        "SELECT regulatory_tier, COUNT(*), COALESCE(SUM(ytd_revenue), 0) FROM accounts GROUP BY regulatory_tier ORDER BY SUM(ytd_revenue) DESC"
    ).fetchall()

    print("\n📊 Import Summary:")
    print(f"   Total Accounts: {account_count}")
    print(f"   Total Contacts: {contact_count}")
    print(f"   Total Revenue:  ${conn.execute('SELECT COALESCE(SUM(ytd_revenue), 0) FROM accounts').fetchone()[0]:,.0f}")
    print("\n   By Tier:")
    for tier_row in tier_summary:
        print(f"     {tier_row[0] or 'Unknown':>10}: {tier_row[1]:>4} accounts | ${tier_row[2]:>12,.0f}")

    territory_summary = conn.execute(
        "SELECT territory, COUNT(*), COALESCE(SUM(ytd_revenue), 0) FROM accounts GROUP BY territory ORDER BY COUNT(*) DESC"
    ).fetchall()
    print("\n   By Territory:")
    for t in territory_summary:
        print(f"     {t[0] or 'Unknown':>10}: {t[1]:>4} accounts | ${t[2]:>12,.0f}")

    conn.close()
    print("\n🚀 Real data import complete. Orbit is now running on production CRM data.")


if __name__ == "__main__":
    import_data()
