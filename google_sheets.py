import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from config import BASE_DIR
from database import get_db_connection

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Configurable paths / credentials
SERVICE_ACCOUNT_FILE = BASE_DIR / "credentials.json"
SETTINGS_FILE = BASE_DIR / ".env"

def get_google_sheet_config() -> Dict[str, str]:
    """Reads Google Sheets configuration from environment."""
    load_dotenv(SETTINGS_FILE, override=True)
    return {
        "sheet_id": os.getenv("GOOGLE_SHEET_ID", "").strip(),
        "sheet_name": os.getenv("GOOGLE_SHEET_NAME", "Tilahun Engineering Site Ops").strip(),
        "webhook_url": os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip(),
        "credentials_path": os.getenv("GOOGLE_CREDENTIALS_FILE", str(SERVICE_ACCOUNT_FILE)).strip(),
    }

def get_gspread_client():
    """Returns an authenticated gspread client if credentials.json is present."""
    cfg = get_google_sheet_config()
    cred_path = Path(cfg["credentials_path"])
    
    if not cred_path.exists():
        # Check alternative filenames
        alt_path = BASE_DIR / "service_account.json"
        if alt_path.exists():
            cred_path = alt_path
        else:
            return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(str(cred_path), scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Failed to authenticate with Google Sheets API: {e}")
        return None

def open_or_create_spreadsheet(client):
    """Opens the spreadsheet by ID or Name, creating tabs if needed."""
    cfg = get_google_sheet_config()
    sh = None
    if cfg["sheet_id"]:
        try:
            sh = client.open_by_key(cfg["sheet_id"])
        except Exception:
            pass

    if not sh:
        try:
            sh = client.open(cfg["sheet_name"])
        except Exception:
            pass

    if not sh:
        # Create a new spreadsheet
        sh = client.create(cfg["sheet_name"])
        logger.info(f"Created new Google Spreadsheet: {sh.title} (ID: {sh.id})")

    _ensure_worksheets_exist(sh)
    return sh

def _ensure_worksheets_exist(sh):
    """Ensures standard tabs and headers exist in the Google Sheet."""
    existing_titles = [w.title for w in sh.worksheets()]

    headers_map = {
        "Projects": ["Project Name", "Progress (%)", "Target Deadline", "Topic ID", "Status", "Last Updated"],
        "Reports": ["ID", "Timestamp", "Shift", "Project", "Worker Name", "Role", "Work Completed", "Plan / Handover", "Blockers"],
        "MaterialRequests": ["MR Code", "Timestamp", "Project", "Worker Name", "Role", "Items Description", "Urgency", "Status", "Approved By", "Last Updated"],
        "Issues": ["ID", "Timestamp", "Project", "Reported By", "Description", "Severity", "Status", "Resolved At"],
        "Workers": ["Telegram User ID", "Full Name", "Role", "Approved", "Admin", "Registration Date"]
    }

    for title, headers in headers_map.items():
        if title not in existing_titles:
            ws = sh.add_worksheet(title=title, rows=100, cols=len(headers) + 2)
            ws.append_row(headers)
            # Format header row with bold
            try:
                ws.format("A1:Z1", {"textFormat": {"bold": True}})
            except Exception:
                pass
        else:
            ws = sh.worksheet(title)
            # Check if header is present
            first_row = ws.row_values(1)
            if not first_row:
                ws.append_row(headers)

def sync_all_database_to_sheets() -> Dict[str, Any]:
    """
    Performs a full two-way/one-way export from local SQLite DB to Google Sheets.
    Supports both Direct Service Account API (gspread) and Webhook fallback.
    """
    cfg = get_google_sheet_config()
    client = get_gspread_client()

    if client:
        try:
            sh = open_or_create_spreadsheet(client)
            conn = get_db_connection()

            # 1. Projects
            rows_proj = conn.execute("SELECT name, progress_percent, deadline, topic_id, CASE WHEN is_active=1 THEN 'Active' ELSE 'Inactive' END, created_at FROM projects ORDER BY name ASC").fetchall()
            ws_p = sh.worksheet("Projects")
            ws_p.clear()
            ws_p.append_row(["Project Name", "Progress (%)", "Target Deadline", "Topic ID", "Status", "Last Updated"])
            for r in rows_proj:
                ws_p.append_row(list(r))

            # 2. Reports
            rows_rep = conn.execute("SELECT id, timestamp, shift_type, project_name, worker_name, worker_role, work_completed, plan_tomorrow, blockers FROM reports ORDER BY id ASC").fetchall()
            ws_r = sh.worksheet("Reports")
            ws_r.clear()
            ws_r.append_row(["ID", "Timestamp", "Shift", "Project", "Worker Name", "Role", "Work Completed", "Plan / Handover", "Blockers"])
            for r in rows_rep:
                ws_r.append_row(list(r))

            # 3. Material Requests
            rows_mr = conn.execute("SELECT mr_code, timestamp, project_name, worker_name, worker_role, items_description, urgency, status, approved_by_name, updated_at FROM material_requests ORDER BY id ASC").fetchall()
            ws_m = sh.worksheet("MaterialRequests")
            ws_m.clear()
            ws_m.append_row(["MR Code", "Timestamp", "Project", "Worker Name", "Role", "Items Description", "Urgency", "Status", "Approved By", "Last Updated"])
            for r in rows_mr:
                ws_m.append_row(list(r))

            # 4. Issues
            rows_iss = conn.execute("SELECT id, timestamp, project_name, worker_name, description, severity, status, resolved_at FROM issues ORDER BY id ASC").fetchall()
            ws_i = sh.worksheet("Issues")
            ws_i.clear()
            ws_i.append_row(["ID", "Timestamp", "Project", "Reported By", "Description", "Severity", "Status", "Resolved At"])
            for r in rows_iss:
                ws_i.append_row(list(r))

            # 5. Workers
            rows_wor = conn.execute("SELECT user_id, full_name, role, is_approved, is_admin, registered_at FROM workers ORDER BY registered_at ASC").fetchall()
            ws_w = sh.worksheet("Workers")
            ws_w.clear()
            ws_w.append_row(["Telegram User ID", "Full Name", "Role", "Approved", "Admin", "Registration Date"])
            for r in rows_wor:
                ws_w.append_row(list(r))

            conn.close()
            return {"success": True, "method": "Google Sheets API", "url": sh.url}
        except Exception as e:
            logger.error(f"Failed full sync via gspread: {e}")

    # Fallback to Webhook URL if configured
    if cfg["webhook_url"]:
        try:
            conn = get_db_connection()
            payload = {
                "action": "FULL_SYNC",
                "timestamp": datetime.datetime.now().isoformat(),
                "projects": [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()],
                "reports": [dict(r) for r in conn.execute("SELECT * FROM reports").fetchall()],
                "materials": [dict(r) for r in conn.execute("SELECT * FROM material_requests").fetchall()],
                "issues": [dict(r) for r in conn.execute("SELECT * FROM issues").fetchall()],
                "workers": [dict(r) for r in conn.execute("SELECT * FROM workers").fetchall()],
            }
            conn.close()
            resp = requests.post(cfg["webhook_url"], json=payload, timeout=60)
            if resp.status_code == 200:
                return {"success": True, "method": "Google Apps Script Webhook", "url": cfg["webhook_url"]}
        except Exception as e:
            logger.error(f"Failed sync via Webhook: {e}")

    return {
        "success": False,
        "error": "Google Sheets credentials not configured. Please place `credentials.json` in project directory or configure `GOOGLE_SHEET_WEBHOOK_URL` in `.env`."
    }

def append_report_live(report_id: int, timestamp: str, shift: str, project: str, worker_name: str, role: str, completed: str, plan: str, blockers: str):
    """Appends a new report row to Google Sheets in real-time."""
    client = get_gspread_client()
    if client:
        try:
            sh = open_or_create_spreadsheet(client)
            ws = sh.worksheet("Reports")
            ws.append_row([report_id, timestamp, shift, project, worker_name, role, completed, plan, blockers])
            return True
        except Exception as e:
            logger.warning(f"Could not live append report to Google Sheets: {e}")

    cfg = get_google_sheet_config()
    if cfg["webhook_url"]:
        try:
            requests.post(cfg["webhook_url"], json={
                "action": "ADD_REPORT",
                "data": {
                    "id": report_id, "timestamp": timestamp, "shift": shift,
                    "project": project, "worker_name": worker_name, "role": role,
                    "completed": completed, "plan": plan, "blockers": blockers
                }
            }, timeout=8)
            return True
        except Exception:
            pass
    return False

def append_material_live(mr_code: str, timestamp: str, project: str, worker_name: str, role: str, items: str, urgency: str, status: str):
    """Appends a new material request row to Google Sheets in real-time."""
    client = get_gspread_client()
    if client:
        try:
            sh = open_or_create_spreadsheet(client)
            ws = sh.worksheet("MaterialRequests")
            ws.append_row([mr_code, timestamp, project, worker_name, role, items, urgency, status, "", timestamp])
            return True
        except Exception as e:
            logger.warning(f"Could not live append material request to Google Sheets: {e}")

    cfg = get_google_sheet_config()
    if cfg["webhook_url"]:
        try:
            requests.post(cfg["webhook_url"], json={
                "action": "ADD_MATERIAL",
                "data": {
                    "mr_code": mr_code, "timestamp": timestamp, "project": project,
                    "worker_name": worker_name, "role": role, "items": items,
                    "urgency": urgency, "status": status
                }
            }, timeout=8)
            return True
        except Exception:
            pass
    return False

def update_material_status_live(mr_code: str, status: str, approved_by: str):
    """Updates a material request status in Google Sheets in real-time."""
    client = get_gspread_client()
    if client:
        try:
            sh = open_or_create_spreadsheet(client)
            ws = sh.worksheet("MaterialRequests")
            cell = ws.find(mr_code)
            if cell:
                # Column 8: Status, Column 9: Approved By, Column 10: Last Updated
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ws.update_cell(cell.row, 8, status)
                ws.update_cell(cell.row, 9, approved_by)
                ws.update_cell(cell.row, 10, now_str)
                return True
        except Exception as e:
            logger.warning(f"Could not live update material request in Google Sheets: {e}")

    cfg = get_google_sheet_config()
    if cfg["webhook_url"]:
        try:
            requests.post(cfg["webhook_url"], json={
                "action": "UPDATE_MATERIAL",
                "mr_code": mr_code, "status": status, "approved_by": approved_by
            }, timeout=8)
            return True
        except Exception:
            pass
    return False

def update_project_live(project_name: str, progress_percent: int, deadline: Optional[str] = None, topic_id: int = 0):
    """Updates project progress/deadline in Google Sheets in real-time."""
    client = get_gspread_client()
    if client:
        try:
            sh = open_or_create_spreadsheet(client)
            ws = sh.worksheet("Projects")
            cell = ws.find(project_name)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if cell:
                ws.update_cell(cell.row, 2, progress_percent)
                if deadline:
                    ws.update_cell(cell.row, 3, deadline)
                if topic_id:
                    ws.update_cell(cell.row, 4, topic_id)
                ws.update_cell(cell.row, 6, now_str)
            else:
                ws.append_row([project_name, progress_percent, deadline or "", topic_id or "", "Active", now_str])
            return True
        except Exception as e:
            logger.warning(f"Could not live update project in Google Sheets: {e}")
    return False
