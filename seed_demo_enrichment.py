"""
seed_demo_enrichment.py — Enrich the Orbit database with additional demo data.
Adds more EDD submissions (with field flags) and activities across accounts
to ensure the Nathan Parra demo has rich, realistic data at every touchpoint.

Idempotent: checks for existing data before inserting.
"""
import os
import sys
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

    # --- Additional EDD Submissions ---
    NEW_EDDS = [
        # Durham — add a third EDD with more specific NCDEQ flags
        {
            "account_name": "City of Durham",
            "project_name": "NPDES Stormwater Discharge - March 2026",
            "submission_date": "2026-03-08",
            "format_type": "NCDEQ",
            "status": "Pending",
            "field_flags": json.dumps([
                "NCDEQ field 'Monitoring Location ID' (ML_ID) blank for SW-003 outfall",
                "Method Detection Limit (MDL) not reported for TSS analysis — required per 15A NCAC 02B",
                "Sample collection method listed as 'Grab' but permit NC0023841 requires 24-hr composite for BOD",
                "Lab certification number missing — NCDEQ requires NC DENR-certified lab ID on all EDD rows",
                "Flow measurement units inconsistent: MGD in header vs GPM in data rows",
                "Hardness-dependent metals criteria not calculated — required for copper limit derivation"
            ])
        },
        # Lumberton — PFAS-related EDD with flags
        {
            "account_name": "City of Lumberton",
            "project_name": "PFAS Occurrence Monitoring - Q1 2026",
            "submission_date": "2026-03-01",
            "format_type": "EPA",
            "status": "Pending",
            "field_flags": json.dumps([
                "EPA Method 537.1 requires field blank — none submitted",
                "PFOS result below MRL but reported as 'ND' instead of '<MRL' value",
                "Sample preservation temperature out of range (6.2°C recorded, must be ≤4°C per method)"
            ])
        },
        {
            "account_name": "City of Lumberton",
            "project_name": "NPDES Monthly Discharge - January 2026",
            "submission_date": "2026-01-31",
            "format_type": "NCDEQ",
            "status": "Submitted",
            "field_flags": json.dumps([])
        },
        # Rose Acre Farms — industrial WW EDD
        {
            "account_name": "Rose Acre Farms",
            "project_name": "Industrial WW Discharge - February 2026",
            "submission_date": "2026-02-28",
            "format_type": "NCDEQ",
            "status": "Pending",
            "field_flags": json.dumps([
                "Ammonia-N result exceeds permit limit (4.2 mg/L vs 2.0 mg/L limit) — flag as exceedance",
                "TKN analysis holding time exceeded: collected 02/15, analyzed 02/22 (7d max for EPA 351.2)"
            ])
        },
        # Town of Smithfield — municipal WW
        {
            "account_name": "Town of Smithfield",
            "project_name": "NPDES Monthly Discharge - December 2025",
            "submission_date": "2025-12-31",
            "format_type": "NCDEQ",
            "status": "Accepted",
            "field_flags": json.dumps([])
        },
    ]

    # --- Additional Activities (to fill timelines) ---
    NEW_ACTIVITIES = [
        # Durham — richer timeline
        {"account_name": "City of Durham", "activity_type": "email", "summary": "Sent NPDES EDD to James Worthington for review before NCDEQ submission. Flagged 4 missing fields.", "outcome": "James will pull missing data from SCADA system by Friday.", "activity_date": "2026-03-08"},
        {"account_name": "City of Durham", "activity_type": "call", "summary": "Called Sarah Mitchell to discuss biosolids RFP timeline and new stormwater permit requirements.", "outcome": "RFP drafting in progress. Sarah wants Waypoint to bid on both characterization and monitoring.", "activity_date": "2026-02-20"},
        {"account_name": "City of Durham", "activity_type": "note", "summary": "NCDEQ issued Notice of Violation to Durham for late February NPDES submission. Need to prioritize March EDD accuracy.", "outcome": None, "activity_date": "2026-03-05"},

        # Lumberton
        {"account_name": "City of Lumberton", "activity_type": "call", "summary": "Discussed PFAS monitoring requirements with Marcus Johnson. EPA Method 537.1 scope.", "outcome": "Marcus concerned about cost. Sent comparison sheet vs competitor pricing.", "activity_date": "2026-02-15"},
        {"account_name": "City of Lumberton", "activity_type": "email", "summary": "Sent PFAS EDD to Teresa Locklear — flagged 3 issues requiring correction before EPA submission.", "outcome": "Teresa acknowledged, working on field blank documentation.", "activity_date": "2026-03-02"},

        # Rose Acre
        {"account_name": "Rose Acre Farms", "activity_type": "site_visit", "summary": "Conducted sampling at discharge points for monthly industrial WW monitoring.", "outcome": "Collected 6 composite samples. Lab results expected by March 10.", "activity_date": "2026-02-25"},
        {"account_name": "Rose Acre Farms", "activity_type": "call", "summary": "Jennifer Hayes flagged ammonia exceedance on February discharge results.", "outcome": "Recommending resample + treatment review. May need corrective action report to NCDEQ.", "activity_date": "2026-03-04"},

        # Smithfield
        {"account_name": "Town of Smithfield", "activity_type": "email", "summary": "Sent quarterly review reminder to Carl Frazier. Offered to schedule on-site meeting.", "outcome": "No response yet. Third attempt this month.", "activity_date": "2026-02-10"},

        # Wake County
        {"account_name": "Wake County Solid Waste", "activity_type": "email", "summary": "Sent proposal for landfill groundwater monitoring (semi-annual) to Denise Armstrong.", "outcome": "Denise forwarded to county procurement. Budget review in March.", "activity_date": "2026-01-15"},

        # NC State
        {"account_name": "NC State University Facilities", "activity_type": "call", "summary": "Called Brian Cho for update on annual contract decision. Eurofins undercut by 8%.", "outcome": "Brian says procurement weighing turnaround time vs price. Decision expected by March 15.", "activity_date": "2026-03-03"},
    ]

    # --- Insert EDDs (skip if project_name already exists for that account) ---
    edd_added = 0
    for e in NEW_EDDS:
        acc_id = acc_map.get(e["account_name"])
        if not acc_id:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM edd_submissions WHERE account_id = ? AND project_name = ?",
            (acc_id, e["project_name"])
        ).fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO edd_submissions (account_id, project_name, submission_date, format_type, status, field_flags) VALUES (?, ?, ?, ?, ?, ?)",
                (acc_id, e["project_name"], e["submission_date"], e["format_type"], e["status"], e["field_flags"])
            )
            edd_added += 1

    # --- Insert Activities (skip if summary + date combo exists) ---
    act_added = 0
    for a in NEW_ACTIVITIES:
        acc_id = acc_map.get(a["account_name"])
        if not acc_id:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM activities WHERE account_id = ? AND summary = ? AND activity_date = ?",
            (acc_id, a["summary"], a["activity_date"])
        ).fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO activities (account_id, activity_type, summary, outcome, activity_date) VALUES (?, ?, ?, ?, ?)",
                (acc_id, a["activity_type"], a["summary"], a.get("outcome", ""), a["activity_date"])
            )
            act_added += 1

    conn.commit()
    conn.close()

    print(f"✅ Demo enrichment complete: {edd_added} new EDD submissions, {act_added} new activities added.")


if __name__ == "__main__":
    enrich()
