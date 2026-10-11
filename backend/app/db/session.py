import sqlite3
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.security import hash_password

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Initializes tables for users, projects, estimates, and what-if history with migrations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 2. Projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        project_type TEXT NOT NULL,
        overall_complexity TEXT NOT NULL,
        platform TEXT NOT NULL,
        team_size INTEGER NOT NULL,
        requested_deadline_days INTEGER,
        rate_profile TEXT NOT NULL,
        contingency_pct REAL NOT NULL,
        raw_features_json TEXT NOT NULL,
        user_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Migration: Ensure columns exist on projects
    cursor.execute("PRAGMA table_info(projects);")
    columns = [col["name"] for col in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN user_id TEXT;")
        logger.info("Migrated projects table: added user_id column.")
    if "currency_code" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN currency_code TEXT DEFAULT 'INR';")
    if "working_hours_per_day" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN working_hours_per_day REAL DEFAULT 8.0;")
    if "working_days_per_week" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN working_days_per_week INTEGER DEFAULT 5;")

    # 3. Estimates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estimates (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        engine_version TEXT NOT NULL,
        total_effort_hours REAL NOT NULL,
        optimistic_effort_hours REAL NOT NULL,
        pessimistic_effort_hours REAL NOT NULL,
        final_budget_inr REAL NOT NULL,
        labour_cost_inr REAL NOT NULL,
        additional_costs_inr REAL NOT NULL,
        contingency_amount_inr REAL NOT NULL,
        budget_range_low_inr REAL NOT NULL,
        budget_range_high_inr REAL NOT NULL,
        critical_path_hours REAL NOT NULL,
        min_feasible_days INTEGER NOT NULL,
        likely_calendar_days INTEGER NOT NULL,
        is_timeline_feasible INTEGER NOT NULL,
        risk_score REAL NOT NULL,
        risk_level TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        confidence_level TEXT NOT NULL,
        full_estimate_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Migration: Ensure columns exist on estimates
    cursor.execute("PRAGMA table_info(estimates);")
    est_columns = [col["name"] for col in cursor.fetchall()]
    if "currency_code" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN currency_code TEXT DEFAULT 'INR';")
    if "exchange_rate" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN exchange_rate REAL DEFAULT 1.0;")
    if "final_budget_converted" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN final_budget_converted REAL;")
    if "working_hours_per_day" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN working_hours_per_day REAL DEFAULT 8.0;")
    if "working_days_per_week" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN working_days_per_week INTEGER DEFAULT 5;")
    if "canonical_currency" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN canonical_currency TEXT DEFAULT 'INR';")
    if "canonical_amount_inr" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN canonical_amount_inr REAL;")
    if "exchange_rate_source" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN exchange_rate_source TEXT DEFAULT 'CostPilot Treasury Configured Benchmark';")
    if "exchange_rate_timestamp" not in est_columns:
        cursor.execute("ALTER TABLE estimates ADD COLUMN exchange_rate_timestamp TEXT DEFAULT '2026-10-10T12:00:00Z';")

    # 4. What-if scenarios table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS whatif_scenarios (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        scenario_name TEXT NOT NULL,
        override_params_json TEXT NOT NULL,
        delta_budget_inr REAL NOT NULL,
        delta_effort_hours REAL NOT NULL,
        delta_days INTEGER NOT NULL,
        scenario_estimate_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # 5. Project reconciliations table (Actual vs Estimated Outcomes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_reconciliations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL UNIQUE,
        user_id TEXT,
        actual_effort_hours REAL NOT NULL,
        actual_duration_days REAL NOT NULL,
        actual_cost REAL NOT NULL,
        currency_code TEXT DEFAULT 'INR',
        project_status TEXT DEFAULT 'Completed',
        notes TEXT,
        reconciliation_date TEXT NOT NULL,
        data_provenance TEXT DEFAULT 'User-recorded verified outcome',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Seed Default Demo User if users table is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM users;")
    row = cursor.fetchone()
    if row and row["cnt"] == 0:
        demo_id = "usr_demo_001"
        now = datetime.now(timezone.utc).isoformat()
        pwd_hash, salt = hash_password("Password@123")
        cursor.execute("""
        INSERT INTO users (id, full_name, email, phone, password_hash, salt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (demo_id, "Alex Mercer", "demo@costpilot.ai", "+1 (555) 019-2834", pwd_hash, salt, now, now))
        
        # Associate existing unassigned projects with demo user
        cursor.execute("UPDATE projects SET user_id = ? WHERE user_id IS NULL;", (demo_id,))
        logger.info("Seeded initial demo user (demo@costpilot.ai / Password@123).")

    conn.commit()
    conn.close()
    logger.info(f"Initialized SQLite database at {DB_PATH}")


# Auto-initialize database on import
init_db()
