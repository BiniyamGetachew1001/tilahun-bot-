#!/usr/bin/env python3
"""
====================================================================
🏗️ TILAHUN ENGINEERING — GOOGLE SHEETS TERMINAL CONTROLLER CLI
====================================================================
Allows complete setup, testing, synchronization, and live control of
Google Sheets directly from your PowerShell / Command Prompt terminal.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load local environment
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

import google_sheets
from database import get_db_connection


def print_banner():
    print("=" * 65)
    print("  🏗️  TILAHUN ENGINEERING — GOOGLE SHEETS CONTROLLER CLI")
    print("=" * 65)


def get_current_status():
    """Returns current configured connection methods."""
    cfg = google_sheets.get_google_sheet_config()
    cred_file = BASE_DIR / "credentials.json"
    alt_cred_file = BASE_DIR / "service_account.json"
    
    sa_available = cred_file.exists() or alt_cred_file.exists()
    wh_available = bool(cfg["webhook_url"])
    
    return {
        "sa_available": sa_available,
        "sa_path": str(cred_file if cred_file.exists() else alt_cred_file),
        "webhook_url": cfg["webhook_url"],
        "sheet_name": cfg["sheet_name"],
        "sheet_id": cfg["sheet_id"]
    }


def test_connection():
    """Tests Google Sheets connectivity via Service Account or Webhook."""
    print("\n🔍 Testing Google Sheets Connection...")
    status = get_current_status()

    # 1. Test Service Account (gspread)
    if status["sa_available"]:
        print(f"🔑 Found Service Account credentials at: {status['sa_path']}")
        client = google_sheets.get_gspread_client()
        if client:
            try:
                sh = google_sheets.open_or_create_spreadsheet(client)
                print(f"✅ [SUCCESS] Connected via Google Sheets API (gspread)!")
                print(f"   📑 Spreadsheet Title: {sh.title}")
                print(f"   🔗 Spreadsheet URL:   {sh.url}")
                print(f"   📂 Available Tabs:    {', '.join([w.title for w in sh.worksheets()])}")
                return True
            except Exception as e:
                print(f"❌ [ERROR] Could not open spreadsheet: {e}")
        else:
            print("❌ [ERROR] Failed to authorize Service Account credentials.")

    # 2. Test Webhook
    if status["webhook_url"]:
        print(f"🌐 Testing Google Apps Script Webhook URL: {status['webhook_url'][:45]}...")
        import requests
        try:
            resp = requests.get(status["webhook_url"], timeout=10)
            if resp.status_code == 200:
                print("✅ [SUCCESS] Webhook is ONLINE and reachable!")
                print(f"   📩 Response: {resp.text}")
                return True
            else:
                print(f"⚠️ Webhook returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ [ERROR] Connection to Webhook failed: {e}")
            return False

    if not status["sa_available"] and not status["webhook_url"]:
        print("⚠️ No Google Sheets credentials configured yet.")
        print("   Options to connect:")
        print("   1. Paste Google Apps Script Webhook URL")
        print("   2. Place 'credentials.json' (Service Account key) in this directory.")
        return False

    return False


def set_webhook_url(url: str):
    """Saves the Google Sheet Webhook URL to .env."""
    url = url.strip().strip("'").strip('"')
    if not url.startswith("http"):
        print("❌ Invalid URL. It should start with https://script.google.com/...")
        return False

    env_path = BASE_DIR / ".env"
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("GOOGLE_SHEET_WEBHOOK_URL="):
            new_lines.append(f"GOOGLE_SHEET_WEBHOOK_URL={url}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"\nGOOGLE_SHEET_WEBHOOK_URL={url}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    os.environ["GOOGLE_SHEET_WEBHOOK_URL"] = url
    print(f"✅ Webhook URL successfully saved to .env!")
    return True


def trigger_sync():
    """Performs full sync from SQLite database to Google Sheets."""
    print("\n🔄 Starting Full Synchronization (SQLite ➔ Google Sheets)...")
    res = google_sheets.sync_all_database_to_sheets()
    if res.get("success"):
        print("✅ [SYNC COMPLETE] All records uploaded successfully!")
        print(f"   📡 Method: {res.get('method')}")
        if res.get("url"):
            print(f"   🔗 URL: {res.get('url')}")
        return True
    else:
        print(f"❌ [SYNC FAILED] {res.get('error')}")
        return False


def view_local_db_summary():
    """Displays local SQLite database stats."""
    conn = get_db_connection()
    projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    materials = conn.execute("SELECT COUNT(*) FROM material_requests").fetchone()[0]
    issues = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    workers = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    conn.close()

    print("\n📊 Local Database Snapshot (site_manager.db):")
    print(f"  • 🏗️ Active Projects:     {projects}")
    print(f"  • 📋 Submitted Reports:   {reports}")
    print(f"  • 📦 Material Requests:   {materials}")
    print(f"  • ⚠️ Logged Issues:       {issues}")
    print(f"  • 👥 Registered Workers:  {workers}")


def interactive_menu():
    """Terminal interactive menu."""
    while True:
        print_banner()
        status = get_current_status()
        print(f"⚙️ Status:")
        print(f"  • Direct API (credentials.json): {'🟢 Connected' if status['sa_available'] else '⚪ Not configured'}")
        print(f"  • Webhook URL:                   {'🟢 Configured' if status['webhook_url'] else '⚪ Not configured'}")
        print("-" * 65)
        print("1. 🔍 Test Connection")
        print("2. 🔄 Run Full Sync (Database ➔ Google Sheets)")
        print("3. 🔗 Set / Update Google Apps Script Webhook URL")
        print("4. 📊 View Local Database Summary")
        print("5. 📖 Show Setup Guide for Direct Google API (credentials.json)")
        print("0. 🚪 Exit")
        print("-" * 65)

        choice = input("Enter choice [0-5]: ").strip()

        if choice == "1":
            test_connection()
        elif choice == "2":
            trigger_sync()
        elif choice == "3":
            url = input("\nPaste your Web App URL (https://script.google.com/...): ").strip()
            if url:
                if set_webhook_url(url):
                    test_connection()
        elif choice == "4":
            view_local_db_summary()
        elif choice == "5":
            show_service_account_guide()
        elif choice == "0":
            print("Goodbye! 👋")
            break
        else:
            print("Invalid selection. Please try again.")

        input("\nPress Enter to return to menu...")


def show_service_account_guide():
    print("""
====================================================================
🔑 Direct Google Sheets API Setup (Zero Webhook, Direct Terminal Control)
====================================================================
1. Go to Google Cloud Console (https://console.cloud.google.com)
2. Create a project (or select existing).
3. Enable 'Google Sheets API' & 'Google Drive API'.
4. Go to 'Credentials' → 'Create Credentials' → 'Service Account'.
5. Create a key in JSON format and download it.
6. Rename downloaded file to 'credentials.json' and place it in:
   C:\\Users\\biniy\\Documents\\projects\\telegram_site_bot\\credentials.json
7. Open your Google Sheet and click 'Share' (top right).
8. Add the client_email found inside credentials.json as 'Editor'.
====================================================================
""")


def main():
    parser = argparse.ArgumentParser(description="Tilahun Engineering Google Sheets Terminal CLI")
    parser.add_argument("--test", action="store_true", help="Test connection to Google Sheets")
    parser.add_argument("--sync", action="store_true", help="Trigger full sync from database to Google Sheets")
    parser.add_argument("--set-url", type=str, help="Configure Webhook URL")
    parser.add_argument("--summary", action="store_true", help="Show local database summary")

    args = parser.parse_args()

    if args.set_url:
        set_webhook_url(args.set_url)
        test_connection()
    elif args.test:
        test_connection()
    elif args.sync:
        trigger_sync()
    elif args.summary:
        view_local_db_summary()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
