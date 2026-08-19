import pandas as pd
import datetime
from pathlib import Path
from config import EXPORTS_DIR, DB_PATH
from database import get_db_connection

def export_all_data_to_excel() -> Path:
    """
    Exports all database tables into a single formatted Excel (.xlsx) file with tabs:
    - Reports
    - MaterialRequests
    - Issues
    - Workers
    """
    conn = get_db_connection()

    # Load dataframes
    df_reports = pd.read_sql_query("SELECT id, timestamp, shift_type AS [Shift], project_name AS [Project], worker_name AS [Worker Name], worker_role AS [Role], work_completed AS [Work Completed], plan_tomorrow AS [Plan/Handover], blockers AS [Blockers] FROM reports ORDER BY id DESC", conn)
    df_materials = pd.read_sql_query("SELECT mr_code AS [MR ID], timestamp, project_name, worker_name, worker_role, items_description, urgency, status, approved_by_name AS [Approved By], updated_at FROM material_requests ORDER BY id DESC", conn)
    df_issues = pd.read_sql_query("SELECT id, timestamp, project_name, worker_name, description, severity, status, resolved_at FROM issues ORDER BY id DESC", conn)
    df_workers = pd.read_sql_query("SELECT user_id AS [Telegram User ID], full_name AS [Full Name], role AS [Role], is_approved AS [Approved], is_admin AS [Admin], registered_at AS [Registered Date] FROM workers ORDER BY registered_at DESC", conn)
    df_projects = pd.read_sql_query("SELECT name AS [Project Name], progress_percent AS [Progress %], deadline AS [Target Deadline], topic_id AS [Telegram Topic ID], CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END AS [Status] FROM projects ORDER BY name ASC", conn)

    conn.close()

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = EXPORTS_DIR / f"SiteManagement_Export_{timestamp_str}.xlsx"

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df_projects.to_excel(writer, sheet_name="Projects", index=False)
        df_reports.to_excel(writer, sheet_name="Reports", index=False)
        df_materials.to_excel(writer, sheet_name="MaterialRequests", index=False)
        df_issues.to_excel(writer, sheet_name="Issues", index=False)
        df_workers.to_excel(writer, sheet_name="Workers", index=False)

        # Style column widths nicely
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val_str = str(cell.value or "")
                    max_len = max(max_len, len(val_str))
                worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

    return file_path
