import os
import sqlite3
import datetime
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from config import DB_PATH, DEFAULT_PROJECTS, ADMIN_IDS, DATABASE_URL

logger = logging.getLogger(__name__)

USE_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        logger.info("🐘 Using Cloud PostgreSQL Database for persistent storage.")
    except ImportError:
        logger.warning("psycopg2 not installed; falling back to SQLite.")
        USE_POSTGRES = False

def get_db_connection():
    if USE_POSTGRES:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

def _format_sql(sql: str) -> str:
    """If Postgres, converts '?' placeholders to '%s'."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql

def db_execute(sql: str, params: tuple = (), returning_id: bool = False):
    conn = get_db_connection()
    formatted_sql = _format_sql(sql)
    
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if returning_id:
            if not formatted_sql.strip().upper().endswith("RETURNING ID") and "INSERT INTO" in formatted_sql.upper():
                formatted_sql = formatted_sql.rstrip(" ;") + " RETURNING id;"
            cursor.execute(formatted_sql, params)
            row = cursor.fetchone()
            last_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            cursor.execute(formatted_sql, params)
            last_id = None
        rowcount = cursor.rowcount
    else:
        cursor = conn.cursor()
        cursor.execute(formatted_sql, params)
        last_id = cursor.lastrowid
        rowcount = cursor.rowcount

    conn.commit()
    conn.close()
    return last_id if returning_id else rowcount

def db_fetchone(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    cursor.execute(_format_sql(sql), params)
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

def db_fetchall(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    cursor.execute(_format_sql(sql), params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def init_db():
    """Initializes database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            phone TEXT,
            is_approved INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            assigned_project TEXT DEFAULT 'ALL',
            registered_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            shift_type TEXT DEFAULT 'DAY',
            project_name TEXT NOT NULL,
            worker_user_id BIGINT NOT NULL,
            worker_name TEXT NOT NULL,
            worker_role TEXT NOT NULL,
            work_completed TEXT NOT NULL,
            plan_tomorrow TEXT NOT NULL,
            blockers TEXT,
            photo_file_ids TEXT,
            message_id BIGINT
        );

        CREATE TABLE IF NOT EXISTS material_requests (
            id SERIAL PRIMARY KEY,
            mr_code TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            project_name TEXT NOT NULL,
            worker_user_id BIGINT NOT NULL,
            worker_name TEXT NOT NULL,
            worker_role TEXT NOT NULL,
            items_description TEXT NOT NULL,
            urgency TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            approved_by_name TEXT,
            approved_by_id BIGINT,
            updated_at TEXT,
            notes TEXT,
            message_id BIGINT,
            topic_id BIGINT
        );

        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            project_name TEXT NOT NULL,
            worker_user_id BIGINT NOT NULL,
            worker_name TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'NORMAL',
            status TEXT DEFAULT 'OPEN',
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            topic_id BIGINT DEFAULT 0,
            deadline TEXT,
            progress_percent INTEGER DEFAULT 0,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
    else:
        # SQLite schema
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS workers (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            phone TEXT,
            is_approved INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            assigned_project TEXT DEFAULT 'ALL',
            registered_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            shift_type TEXT DEFAULT 'DAY',
            project_name TEXT NOT NULL,
            worker_user_id INTEGER NOT NULL,
            worker_name TEXT NOT NULL,
            worker_role TEXT NOT NULL,
            work_completed TEXT NOT NULL,
            plan_tomorrow TEXT NOT NULL,
            blockers TEXT,
            photo_file_ids TEXT,
            message_id INTEGER,
            FOREIGN KEY (worker_user_id) REFERENCES workers(user_id)
        );

        CREATE TABLE IF NOT EXISTS material_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mr_code TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            project_name TEXT NOT NULL,
            worker_user_id INTEGER NOT NULL,
            worker_name TEXT NOT NULL,
            worker_role TEXT NOT NULL,
            items_description TEXT NOT NULL,
            urgency TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            approved_by_name TEXT,
            approved_by_id INTEGER,
            updated_at TEXT,
            notes TEXT,
            message_id INTEGER,
            topic_id INTEGER,
            FOREIGN KEY (worker_user_id) REFERENCES workers(user_id)
        );

        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date_str TEXT NOT NULL,
            project_name TEXT NOT NULL,
            worker_user_id INTEGER NOT NULL,
            worker_name TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'NORMAL',
            status TEXT DEFAULT 'OPEN',
            resolved_at TEXT,
            FOREIGN KEY (worker_user_id) REFERENCES workers(user_id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            topic_id INTEGER DEFAULT 0,
            deadline TEXT,
            progress_percent INTEGER DEFAULT 0,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # Auto-migration for existing SQLite files
        cursor.execute("PRAGMA table_info(reports)")
        columns = [row[1] for row in cursor.fetchall()]
        if "shift_type" not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN shift_type TEXT DEFAULT 'DAY'")
        if "photo_file_ids" not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN photo_file_ids TEXT")

        cursor.execute("PRAGMA table_info(projects)")
        proj_cols = [row[1] for row in cursor.fetchall()]
        if "deadline" not in proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN deadline TEXT")
        if "progress_percent" not in proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN progress_percent INTEGER DEFAULT 0")
        if "created_at" not in proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN created_at TEXT")

    conn.commit()
    conn.close()

    # Pre-seed default projects if table is empty
    active_projs = list_active_projects()
    if not active_projs and DEFAULT_PROJECTS:
        for p_name, t_id in DEFAULT_PROJECTS.items():
            add_or_update_project(p_name, topic_id=t_id, progress_percent=0)
        logger.info("Initialized default projects roster.")

# --- Settings Operations ---

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = db_fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default

def set_setting(key: str, value: str) -> None:
    db_execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))

# --- Worker CRUD ---

def get_worker(user_id: int) -> Optional[Dict[str, Any]]:
    return db_fetchone("SELECT * FROM workers WHERE user_id = ?", (user_id,))

def register_worker(user_id: int, full_name: str, role: str, is_approved: bool = False, is_admin: bool = False) -> None:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("""
    INSERT INTO workers (user_id, full_name, role, is_approved, is_admin, registered_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        full_name = excluded.full_name,
        role = excluded.role,
        is_approved = excluded.is_approved,
        is_admin = excluded.is_admin
    """, (user_id, full_name, role, 1 if is_approved else 0, 1 if is_admin else 0, now_str))

def set_worker_approval(user_id: int, approved: bool) -> bool:
    count = db_execute("UPDATE workers SET is_approved = ? WHERE user_id = ?", (1 if approved else 0, user_id))
    return count > 0

def list_all_workers() -> List[Dict[str, Any]]:
    return db_fetchall("SELECT * FROM workers ORDER BY registered_at DESC")

# --- Projects ---

def list_active_projects() -> List[Dict[str, Any]]:
    return db_fetchall("SELECT * FROM projects WHERE is_active = 1 ORDER BY name ASC")

def get_project(name: str) -> Optional[Dict[str, Any]]:
    return db_fetchone("SELECT * FROM projects WHERE name = ?", (name,))

def get_project_by_topic_id(topic_id: int) -> Optional[Dict[str, Any]]:
    """Finds an active project associated with a Telegram Topic message_thread_id."""
    if not topic_id:
        return None
    return db_fetchone("SELECT * FROM projects WHERE topic_id = ? AND is_active = 1", (topic_id,))

def add_or_update_project(name: str, topic_id: int = 0, deadline: Optional[str] = None, progress_percent: int = 0) -> None:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("""
    INSERT INTO projects (name, topic_id, deadline, progress_percent, created_at, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
    ON CONFLICT(name) DO UPDATE SET
        topic_id = CASE WHEN excluded.topic_id != 0 THEN excluded.topic_id ELSE projects.topic_id END,
        deadline = COALESCE(excluded.deadline, projects.deadline),
        progress_percent = COALESCE(excluded.progress_percent, projects.progress_percent),
        is_active = 1
    """, (name, topic_id, deadline, progress_percent, now_str))

def update_project_progress(name: str, progress_percent: int) -> bool:
    progress_percent = max(0, min(100, progress_percent))
    count = db_execute("UPDATE projects SET progress_percent = ? WHERE name = ?", (progress_percent, name))
    return count > 0

def update_project_deadline(name: str, deadline: str) -> bool:
    count = db_execute("UPDATE projects SET deadline = ? WHERE name = ?", (deadline, name))
    return count > 0

def remove_project(name: str) -> bool:
    count = db_execute("UPDATE projects SET is_active = 0 WHERE name = ?", (name,))
    return count > 0

def render_progress_bar(percent: int, length: int = 10) -> str:
    """Renders a visual progress bar e.g. [██████░░░░] 60%"""
    percent = max(0, min(100, int(percent or 0)))
    filled = int(round((percent / 100) * length))
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percent}%"

def get_deadline_info(deadline_str: Optional[str]) -> str:
    """Calculates remaining days or overdue status for a project deadline."""
    if not deadline_str:
        return "No deadline set"
    try:
        clean_d = deadline_str.strip()
        if "-" in clean_d:
            parts = clean_d.split("-")
            if len(parts) == 3:
                target_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            else:
                return deadline_str
        elif "/" in clean_d:
            parts = clean_d.split("/")
            if len(parts) == 3:
                target_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
            else:
                return deadline_str
        else:
            return deadline_str

        today = datetime.date.today()
        days_left = (target_date - today).days

        if days_left > 0:
            return f"{deadline_str} ({days_left} days remaining ⏳)"
        elif days_left == 0:
            return f"{deadline_str} (Due Today ⚠️)"
        else:
            return f"{deadline_str} ({abs(days_left)} days OVERDUE 🚨)"
    except Exception:
        return deadline_str

# --- Daily Reports ---

def save_daily_report(
    project_name: str,
    worker_user_id: int,
    worker_name: str,
    worker_role: str,
    work_completed: str,
    plan_tomorrow: str,
    shift_type: str = "DAY",
    blockers: Optional[str] = None,
    photo_file_ids: Optional[str] = None,
    message_id: Optional[int] = None
) -> int:
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    report_id = db_execute("""
    INSERT INTO reports (timestamp, date_str, shift_type, project_name, worker_user_id, worker_name, worker_role, work_completed, plan_tomorrow, blockers, photo_file_ids, message_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now_str, date_str, shift_type.upper(), project_name, worker_user_id, worker_name, worker_role, work_completed, plan_tomorrow, blockers, photo_file_ids, message_id), returning_id=True)

    # If blockers entered (and not 'none'), auto-create an open issue
    if blockers and blockers.strip().lower() not in ("none", "no", "n/a", "nil", "-"):
        db_execute("""
        INSERT INTO issues (timestamp, date_str, project_name, worker_user_id, worker_name, description, severity, status)
        VALUES (?, ?, ?, ?, ?, ?, 'NORMAL', 'OPEN')
        """, (now_str, date_str, project_name, worker_user_id, worker_name, blockers.strip()))

    return report_id

def get_latest_report(project_name: str, shift_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if shift_type:
        return db_fetchone("""
        SELECT * FROM reports WHERE project_name = ? AND shift_type = ? ORDER BY timestamp DESC LIMIT 1
        """, (project_name, shift_type.upper()))
    else:
        return db_fetchone("""
        SELECT * FROM reports WHERE project_name = ? ORDER BY timestamp DESC LIMIT 1
        """, (project_name,))

def get_today_report_for_project(project_name: str, date_str: Optional[str] = None, shift_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if shift_type:
        return db_fetchone("""
        SELECT * FROM reports WHERE project_name = ? AND date_str = ? AND shift_type = ? LIMIT 1
        """, (project_name, date_str, shift_type.upper()))
    else:
        return db_fetchone("""
        SELECT * FROM reports WHERE project_name = ? AND date_str = ? LIMIT 1
        """, (project_name, date_str))

# --- Material Requests (Numbered #MR-001) ---

def generate_next_mr_code() -> str:
    """Generates next sequential Material Request code e.g. MR-001, MR-014."""
    row = db_fetchone("SELECT MAX(id) as max_id FROM material_requests")
    max_id = (row["max_id"] or 0) if row and row.get("max_id") is not None else 0
    next_num = max_id + 1
    return f"MR-{next_num:03d}"

def create_material_request(
    project_name: str,
    worker_user_id: int,
    worker_name: str,
    worker_role: str,
    items_description: str,
    urgency: str
) -> Dict[str, Any]:
    mr_code = generate_next_mr_code()
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    req_id = db_execute("""
    INSERT INTO material_requests (mr_code, timestamp, date_str, project_name, worker_user_id, worker_name, worker_role, items_description, urgency, status, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
    """, (mr_code, now_str, date_str, project_name, worker_user_id, worker_name, worker_role, items_description, urgency, now_str), returning_id=True)

    return {
        "id": req_id,
        "mr_code": mr_code,
        "timestamp": now_str,
        "project_name": project_name,
        "worker_name": worker_name,
        "worker_role": worker_role,
        "items_description": items_description,
        "urgency": urgency,
        "status": "PENDING"
    }

def get_material_request_by_code(mr_code: str) -> Optional[Dict[str, Any]]:
    clean_code = mr_code.upper().replace("#", "").strip()
    if clean_code.startswith("MR-") and clean_code[3:].isdigit():
        num = int(clean_code[3:])
        clean_code = f"MR-{num:03d}"

    return db_fetchone("SELECT * FROM material_requests WHERE mr_code = ?", (clean_code,))

def update_material_request_status(
    mr_code: str,
    new_status: str,
    approved_by_name: str,
    approved_by_id: int,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    clean_code = mr_code.upper().replace("#", "").strip()
    if clean_code.startswith("MR-") and clean_code[3:].isdigit():
        num = int(clean_code[3:])
        clean_code = f"MR-{num:03d}"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("""
    UPDATE material_requests
    SET status = ?, approved_by_name = ?, approved_by_id = ?, updated_at = ?, notes = COALESCE(?, notes)
    WHERE mr_code = ?
    """, (new_status, approved_by_name, approved_by_id, now_str, notes, clean_code))
    
    return db_fetchone("SELECT * FROM material_requests WHERE mr_code = ?", (clean_code,))

def get_open_material_requests(project_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if project_name:
        return db_fetchall("""
        SELECT * FROM material_requests 
        WHERE project_name = ? AND status IN ('PENDING', 'IN_TRANSIT')
        ORDER BY id DESC
        """, (project_name,))
    else:
        return db_fetchall("""
        SELECT * FROM material_requests 
        WHERE status IN ('PENDING', 'IN_TRANSIT')
        ORDER BY id DESC
        """)

# --- Issues & Blockers ---

def get_open_issues(project_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if project_name:
        return db_fetchall("""
        SELECT * FROM issues WHERE project_name = ? AND status = 'OPEN' ORDER BY timestamp DESC
        """, (project_name,))
    else:
        return db_fetchall("SELECT * FROM issues WHERE status = 'OPEN' ORDER BY timestamp DESC")

# Initialize tables on import
init_db()
