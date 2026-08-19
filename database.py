import sqlite3
import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from config import DB_PATH, DEFAULT_PROJECTS, ADMIN_IDS

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """Initializes SQLite database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Workers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        phone TEXT,
        is_approved INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        assigned_project TEXT DEFAULT 'ALL',
        registered_at TEXT
    )
    """)

    # 2. Reports table
    cursor.execute("""
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
    )
    """)

    # Auto-migration: Ensure shift_type column exists if table was created previously
    cursor.execute("PRAGMA table_info(reports)")
    columns = [row[1] for row in cursor.fetchall()]
    if "shift_type" not in columns:
        cursor.execute("ALTER TABLE reports ADD COLUMN shift_type TEXT DEFAULT 'DAY'")

    # 3. Material Requests table
    cursor.execute("""
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
    )
    """)

    # 4. Issues table
    cursor.execute("""
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
    )
    """)

    # 5. Projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        name TEXT PRIMARY KEY,
        topic_id INTEGER DEFAULT 0,
        deadline TEXT,
        progress_percent INTEGER DEFAULT 0,
        created_at TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # Auto-migration for projects table columns
    cursor.execute("PRAGMA table_info(projects)")
    proj_cols = [row[1] for row in cursor.fetchall()]
    if "deadline" not in proj_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN deadline TEXT")
    if "progress_percent" not in proj_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN progress_percent INTEGER DEFAULT 0")
    if "created_at" not in proj_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN created_at TEXT")

    # 6. Settings table (for dynamic configuration like topic IDs)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

# --- Settings Operations ---

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

# --- Worker CRUD ---

def get_worker(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def register_worker(user_id: int, full_name: str, role: str, is_approved: bool = False, is_admin: bool = False) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO workers (user_id, full_name, role, is_approved, is_admin, registered_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        full_name = excluded.full_name,
        role = excluded.role,
        is_approved = excluded.is_approved,
        is_admin = excluded.is_admin
    """, (user_id, full_name, role, 1 if is_approved else 0, 1 if is_admin else 0, now_str))
    conn.commit()
    conn.close()

def set_worker_approval(user_id: int, approved: bool) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE workers SET is_approved = ? WHERE user_id = ?", (1 if approved else 0, user_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def list_all_workers() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers ORDER BY registered_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Projects ---

def list_active_projects() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE is_active = 1 ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_project(name: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_project_by_topic_id(topic_id: int) -> Optional[Dict[str, Any]]:
    """Finds an active project associated with a Telegram Topic message_thread_id."""
    if not topic_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE topic_id = ? AND is_active = 1", (topic_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_or_update_project(name: str, topic_id: int = 0, deadline: Optional[str] = None, progress_percent: int = 0) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO projects (name, topic_id, deadline, progress_percent, created_at, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
    ON CONFLICT(name) DO UPDATE SET
        topic_id = CASE WHEN excluded.topic_id != 0 THEN excluded.topic_id ELSE projects.topic_id END,
        deadline = COALESCE(excluded.deadline, projects.deadline),
        progress_percent = COALESCE(excluded.progress_percent, projects.progress_percent),
        is_active = 1
    """, (name, topic_id, deadline, progress_percent, now_str))
    conn.commit()
    conn.close()

def update_project_progress(name: str, progress_percent: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    progress_percent = max(0, min(100, progress_percent))
    cursor.execute("UPDATE projects SET progress_percent = ? WHERE name = ?", (progress_percent, name))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def update_project_deadline(name: str, deadline: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET deadline = ? WHERE name = ?", (deadline, name))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def remove_project(name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET is_active = 0 WHERE name = ?", (name,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

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
        # Support formats like YYYY-MM-DD or DD/MM/YYYY
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
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO reports (timestamp, date_str, shift_type, project_name, worker_user_id, worker_name, worker_role, work_completed, plan_tomorrow, blockers, photo_file_ids, message_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now_str, date_str, shift_type.upper(), project_name, worker_user_id, worker_name, worker_role, work_completed, plan_tomorrow, blockers, photo_file_ids, message_id))
    report_id = cursor.lastrowid

    # If blockers entered (and not 'none'), auto-create an open issue
    if blockers and blockers.strip().lower() not in ("none", "no", "n/a", "nil", "-"):
        cursor.execute("""
        INSERT INTO issues (timestamp, date_str, project_name, worker_user_id, worker_name, description, severity, status)
        VALUES (?, ?, ?, ?, ?, ?, 'NORMAL', 'OPEN')
        """, (now_str, date_str, project_name, worker_user_id, worker_name, blockers.strip()))

    conn.commit()
    conn.close()
    return report_id

def get_latest_report(project_name: str, shift_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if shift_type:
        cursor.execute("""
        SELECT * FROM reports WHERE project_name = ? AND shift_type = ? ORDER BY timestamp DESC LIMIT 1
        """, (project_name, shift_type.upper()))
    else:
        cursor.execute("""
        SELECT * FROM reports WHERE project_name = ? ORDER BY timestamp DESC LIMIT 1
        """, (project_name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_today_report_for_project(project_name: str, date_str: Optional[str] = None, shift_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    if shift_type:
        cursor.execute("""
        SELECT * FROM reports WHERE project_name = ? AND date_str = ? AND shift_type = ? LIMIT 1
        """, (project_name, date_str, shift_type.upper()))
    else:
        cursor.execute("""
        SELECT * FROM reports WHERE project_name = ? AND date_str = ? LIMIT 1
        """, (project_name, date_str))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Material Requests (Numbered #MR-001) ---

def generate_next_mr_code() -> str:
    """Generates next sequential Material Request code e.g. MR-001, MR-014."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM material_requests")
    max_id = cursor.fetchone()[0] or 0
    conn.close()
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

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO material_requests (mr_code, timestamp, date_str, project_name, worker_user_id, worker_name, worker_role, items_description, urgency, status, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
    """, (mr_code, now_str, date_str, project_name, worker_user_id, worker_name, worker_role, items_description, urgency, now_str))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()

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
    # Normalize: allow user to type "mr-14", "#MR-014", "MR-014"
    clean_code = mr_code.upper().replace("#", "").strip()
    if clean_code.startswith("MR-") and clean_code[3:].isdigit():
        num = int(clean_code[3:])
        clean_code = f"MR-{num:03d}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM material_requests WHERE mr_code = ?", (clean_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE material_requests
    SET status = ?, approved_by_name = ?, approved_by_id = ?, updated_at = ?, notes = COALESCE(?, notes)
    WHERE mr_code = ?
    """, (new_status, approved_by_name, approved_by_id, now_str, notes, clean_code))
    conn.commit()
    
    cursor.execute("SELECT * FROM material_requests WHERE mr_code = ?", (clean_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_open_material_requests(project_name: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if project_name:
        cursor.execute("""
        SELECT * FROM material_requests 
        WHERE project_name = ? AND status IN ('PENDING', 'IN_TRANSIT')
        ORDER BY id DESC
        """, (project_name,))
    else:
        cursor.execute("""
        SELECT * FROM material_requests 
        WHERE status IN ('PENDING', 'IN_TRANSIT')
        ORDER BY id DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Issues & Blockers ---

def get_open_issues(project_name: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if project_name:
        cursor.execute("""
        SELECT * FROM issues WHERE project_name = ? AND status = 'OPEN' ORDER BY timestamp DESC
        """, (project_name,))
    else:
        cursor.execute("SELECT * FROM issues WHERE status = 'OPEN' ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize tables on import
init_db()
