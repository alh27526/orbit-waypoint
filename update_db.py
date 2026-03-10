import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orbit.db')

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(accounts)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'avg_tat_days' not in columns:
        print("Adding avg_tat_days column...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN avg_tat_days REAL DEFAULT 0.0")
        
    if 'incumbent_lab' not in columns:
        print("Adding incumbent_lab column...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN incumbent_lab TEXT")
        
    if 'contract_renewal_date' not in columns:
        print("Adding contract_renewal_date column...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN contract_renewal_date TEXT")

    # Update some existing accounts with mock data for the new fields so it looks good in the demo
    updates = [
        ("Eurofins", "2026-12-31", 6.2, "City of Durham"),
        ("PACE", "2026-06-30", 8.5, "Harnett Regional Water"),
        ("SGS", "2027-01-15", 5.1, "BRENNTAG Mid-South LLC"),
        ("Eurofins", "2026-07-01", 4.8, "NC State University Facilities")
    ]
    
    for inc, ren, tat, name in updates:
        cursor.execute(
            "UPDATE accounts SET incumbent_lab = ?, contract_renewal_date = ?, avg_tat_days = ? WHERE name = ?",
            (inc, ren, tat, name)
        )
        
    conn.commit()
    conn.close()
    print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
