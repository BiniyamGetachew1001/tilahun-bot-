import logging
import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllChatAdministrators,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import BOT_TOKEN, SUPERGROUP_CHAT_ID, ADMIN_IDS
from database import init_db
from handlers.auth import (
    get_onboarding_handler,
    handle_worker_approval_callback,
    menu_command,
    profile_command,
)
from handlers.report import (
    get_report_handler,
)
from handlers.materials import (
    get_material_request_handler,
    handle_mr_action_callback,
    approve_command,
    reject_command,
)
from handlers.status import (
    status_command,
    status_callback,
)
from handlers.admin import (
    admin_panel_command,
    admin_panel_callback_handler,
    get_create_project_wizard_handler,
    get_progress_update_wizard_handler,
    sync_sheets_command,
    export_sheets_command,
    list_workers_command,
    approve_worker_command,
    add_project_command,
    setup_topics_command,
    list_projects_command,
    remove_project_command,
)
from scheduler import (
    setup_cutoff_scheduler,
    check_missing_day_reports,
    check_missing_night_reports
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles exceptions gracefully and retries on transient network disconnects."""
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        logger.warning(f"Transient network issue: {err}. Retrying automatically...")
    else:
        logger.error("Exception occurred while handling an update:", exc_info=err)

async def manual_check_reports_command(update, context):
    """Admin command to run the missing reports cutoff check immediately."""
    from handlers.auth import is_admin
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Only managers/admins can trigger manual cutoff checks.")
        return
    await update.message.reply_text("🔍 Checking Day and Night report submissions across all active projects...")
    await check_missing_day_reports(context)
    await check_missing_night_reports(context)
    await update.message.reply_text("✅ Check complete.")

async def setup_bot_commands(application: Application) -> None:
    """
    Registers standard Telegram Slash Command popup menus for Groups, Private DMs, and Admins.
    When users in the group type '/', this populates the inline command list.
    """
    from telegram import BotCommandScopeDefault

    group_commands = [
        BotCommand("menu", "📱 Interactive Actions Dashboard & Buttons"),
        BotCommand("report", "☀️ Submit Day Shift Progress Report"),
        BotCommand("night_report", "🌙 Submit Night Shift Progress Report"),
        BotCommand("request_material", "📦 Request Materials / Tools (#MR-XXX)"),
        BotCommand("status", "📊 View Project Snapshot & Progress Bar"),
        BotCommand("progress", "📈 Update/View Project Completion (%)"),
        BotCommand("projects", "🏗️ List Active Projects & Deadlines"),
        BotCommand("admin", "🎛️ Manager Controller Board"),
    ]

    private_commands = [
        BotCommand("start", "👋 Register / Open Buttons Menu"),
        BotCommand("menu", "📱 Interactive Actions Dashboard & Buttons"),
        BotCommand("report", "☀️ Submit Day Shift Progress Report"),
        BotCommand("night_report", "🌙 Submit Night Shift Progress Report"),
        BotCommand("request_material", "📦 Request Materials / Tools (#MR-XXX)"),
        BotCommand("status", "📊 View Project Status"),
        BotCommand("progress", "📈 Update Project Progress"),
        BotCommand("projects", "🏗️ Active Projects & Deadlines"),
        BotCommand("profile", "👤 View My Worker Profile & Status"),
        BotCommand("admin", "🎛️ Manager Control Dashboard"),
        BotCommand("sync_sheets", "🔄 Sync Live with Google Sheets"),
        BotCommand("export_sheets", "📥 Download Excel Export"),
    ]

    admin_commands = [
        BotCommand("start", "👋 Main Menu & Persistent Buttons"),
        BotCommand("menu", "📱 Interactive Actions Dashboard"),
        BotCommand("admin", "🎛️ Manager Controller Board"),
        BotCommand("report", "☀️ Submit Day Shift Progress Report"),
        BotCommand("night_report", "🌙 Submit Night Shift Progress Report"),
        BotCommand("request_material", "📦 Request Materials / Tools (#MR-XXX)"),
        BotCommand("status", "📊 Project Snapshot Dashboard"),
        BotCommand("progress", "📈 Update/View Completion (%)"),
        BotCommand("projects", "🏗️ List Active Projects & Deadlines"),
        BotCommand("create_project", "➕ Create New Project & Forum Topic"),
        BotCommand("sync_sheets", "🔄 Sync Live with Google Sheets"),
        BotCommand("export_sheets", "📥 Download Master Excel Spreadsheet"),
        BotCommand("workers", "👥 Registered Workers Roster"),
    ]

    try:
        await application.bot.set_my_commands(group_commands, scope=BotCommandScopeDefault())
        await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        await application.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
        logger.info("✅ Telegram Slash Command menus registered successfully across all scopes.")
    except Exception as e:
        logger.warning(f"Could not register Telegram slash commands: {e}")

import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Responds with 200 OK to cloud pingers/health checks to prevent sleep."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Telegram Bot is active and running 24/7.")

    def log_message(self, format, *args):
        pass  # Suppress excessive HTTP access logs

def start_health_server():
    """Starts background HTTP server on the cloud assigned PORT (default 10000)."""
    port = int(os.getenv("PORT", "10000"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"🌐 Cloud Health Check server listening on port {port}")
    except Exception as e:
        logger.warning(f"Could not start health check server on port {port}: {e}")

def main():
    # Start health check server for Render/Koyeb 24/7 uptime
    start_health_server()

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n" + "="*60)
        print("⚠️  ERROR: BOT_TOKEN is not configured!")
        print("Please edit .env or set BOT_TOKEN in config.py with your token from @BotFather.")
        print("="*60 + "\n")
        sys.exit(1)

    # Initialize database
    init_db()
    print("✅ Database initialized successfully.")

    # Build Telegram application with resilient HTTP timeouts
    t_request = HTTPXRequest(
        connection_pool_size=16,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
    )
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(t_request)
        .get_updates_request(t_request)
        .post_init(setup_bot_commands)
        .build()
    )

    # 1. Onboarding & Registration (/start)
    application.add_handler(get_onboarding_handler())
    application.add_handler(CallbackQueryHandler(handle_worker_approval_callback, pattern=r"^(approve|reject)_worker_"))

    # 2. Daily & Night Report Wizard (/report, /night_report, /day_report, and reply buttons)
    application.add_handler(get_report_handler())

    # 3. Material Requisition Wizard (/request_material, /approve, /reject, and reply buttons)
    application.add_handler(get_material_request_handler())
    application.add_handler(CallbackQueryHandler(handle_mr_action_callback, pattern=r"^mraction_"))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))

    # 4. Status Command (/status and reply buttons)
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.Regex(r"^📊 Project Status$"), status_command))
    application.add_handler(CallbackQueryHandler(status_callback, pattern=r"^status_"))

    # 5. Project Creation Wizard with Deadline & Progress Wizard
    application.add_handler(get_create_project_wizard_handler())
    application.add_handler(get_progress_update_wizard_handler())

    # 6. Navigation, Profile, & Menu Commands (/menu, /profile, /help)
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(MessageHandler(filters.Regex(r"^📱 Main Menu$"), menu_command))

    # 7. Admin Controller Board & Management Commands
    application.add_handler(CommandHandler("admin", admin_panel_command))
    application.add_handler(CommandHandler("control", admin_panel_command))
    application.add_handler(MessageHandler(filters.Regex(r"^🎛️ Manager Panel$"), admin_panel_command))
    application.add_handler(CallbackQueryHandler(admin_panel_callback_handler, pattern=r"^(admin_|menu_)"))

    application.add_handler(CommandHandler("sync_sheets", sync_sheets_command))
    application.add_handler(MessageHandler(filters.Regex(r"^🔄 Sync Sheets$"), sync_sheets_command))

    application.add_handler(CommandHandler("export_sheets", export_sheets_command))
    application.add_handler(MessageHandler(filters.Regex(r"^📥 Export Excel$"), export_sheets_command))

    application.add_handler(CommandHandler("projects", list_projects_command))
    application.add_handler(MessageHandler(filters.Regex(r"^🏗️ (Projects|All Projects)$"), list_projects_command))

    application.add_handler(CommandHandler("workers", list_workers_command))
    application.add_handler(CommandHandler("approve_worker", approve_worker_command))
    application.add_handler(CommandHandler("setup_topics", setup_topics_command))
    application.add_handler(CommandHandler("remove_project", remove_project_command))
    application.add_handler(CommandHandler("add_project", add_project_command))
    application.add_handler(CommandHandler("check_reports", manual_check_reports_command))

    # 8. Scheduled Cutoff Reminders (Day: 19:00, Night: 07:00)
    setup_cutoff_scheduler(application)

    # 9. Register Global Error Handler for Automatic Reconnects
    application.add_error_handler(error_handler)

    print("🚀 Site Management Bot is starting up...")
    print(f"📌 Admin IDs: {ADMIN_IDS}")
    print("Press Ctrl+C to stop.\n")

    application.run_polling()

if __name__ == "__main__":
    main()
