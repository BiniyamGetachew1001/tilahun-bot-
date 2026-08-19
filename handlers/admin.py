import logging
import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from excel_exporter import export_all_data_to_excel
from google_sheets import sync_all_database_to_sheets, update_project_live
from database import (
    list_all_workers,
    set_worker_approval,
    get_worker,
    add_or_update_project,
    remove_project,
    list_active_projects,
    get_project,
    update_project_progress,
    update_project_deadline,
    render_progress_bar,
    get_deadline_info,
    set_setting,
    get_setting,
    get_weekly_worker_summary,
)
from config import SUPERGROUP_CHAT_ID
from handlers.auth import is_admin, is_authorized

logger = logging.getLogger(__name__)

# Conversation states for creating project with deadline
NEW_PROJ_NAME, NEW_PROJ_DEADLINE = range(2)

# Conversation states for updating progress
PROG_SELECT_PROJ, PROG_INPUT_PERCENT = range(2)

def build_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Builds the interactive controller button menu for managers/admins."""
    keyboard = [
        [InlineKeyboardButton("➕ Create Project & Topic", callback_data="admin_create_proj")],
        [InlineKeyboardButton("📊 Project Progress Overview", callback_data="admin_progress_overview")],
        [InlineKeyboardButton("📈 Update Project Progress (%)", callback_data="admin_update_progress_btn")],
        [InlineKeyboardButton("📋 Weekly Worker Activity Digest", callback_data="admin_weekly_summary")],
        [InlineKeyboardButton("👥 Registered Workers", callback_data="admin_workers_roster")],
        [InlineKeyboardButton("🔄 Sync Google Sheets", callback_data="admin_sync_sheets")],
        [InlineKeyboardButton("📥 Download Excel Export", callback_data="admin_export_excel")],
        [InlineKeyboardButton("🔔 Check Missing Reports", callback_data="admin_check_reports_btn")],
    ]
    return InlineKeyboardMarkup(keyboard)

def format_weekly_worker_summary_text(summary_data: dict) -> list:
    """Formats the weekly worker activity digest into Telegram-friendly text chunks."""
    start_date = summary_data["start_date"]
    end_date = summary_data["end_date"]
    total_days = summary_data["total_days"]
    workers = summary_data["workers"]

    if not workers:
        return ["📊 *Weekly Worker Activity Summary*\n\n❌ No registered workers found in database."]

    messages = []
    header = (
        f"📊 *WEEKLY WORKER ACTIVITY DIGEST*\n"
        f"📅 Period: *{start_date}* to *{end_date}* ({total_days} days)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    current_chunk = header

    for w in workers:
        w_name = w["full_name"]
        w_role = w["role"]
        sub_count = w["submitted_count"]
        pct = w["percentage"]
        star = "⭐" if pct >= 90 else ("⚠️" if pct < 50 else "")

        worker_block = (
            f"👤 *{w_name}* _({w_role})_\n"
            f"📈 Consistency: *{sub_count}/{total_days} days ({pct}%)* {star}\n"
        )

        for entry in w["daily_entries"]:
            d_name = entry["day_name"]
            d_str = entry["date"]
            summary = entry["summary"]
            if entry["status"] == "SUBMITTED":
                worker_block += f" • *{d_name} ({d_str[-5:]}):* {summary}\n"
            else:
                worker_block += f" • *{d_name} ({d_str[-5:]}):* ❌ _Missed report_\n"

        worker_block += "────────────────────\n"

        if len(current_chunk) + len(worker_block) > 3800:
            messages.append(current_chunk)
            current_chunk = worker_block
        else:
            current_chunk += worker_block

    if current_chunk:
        current_chunk += "\n💡 _Tip: Run /export_sheets to download full master Excel spreadsheets._"
        messages.append(current_chunk)

    return messages

async def weekly_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /weekly_report — generates a 7-day worker submission & missed report breakdown."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can access the Weekly Worker Activity Report.")
        return

    msg = await update.message.reply_text("⏳ Compiling Weekly Worker Activity Report...")
    summary_data = get_weekly_worker_summary(days=7)
    chunks = format_weekly_worker_summary_text(summary_data)
    
    await msg.delete()
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode="Markdown")

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /admin or /control — displays the Manager Controller Board."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can access the Control Dashboard.")
        return

    await update.message.reply_text(
        "🎛️ *SITE MANAGEMENT CONTROLLER PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Use the buttons below to create project topics with deadlines, monitor real-time progress bars, and manage site operations:",
        reply_markup=build_admin_panel_keyboard(),
        parse_mode="Markdown"
    )

async def admin_panel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks on the Admin Controller Board and Main Menu."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    # Handle public/worker menu callbacks first
    if data == "menu_projects":
        return await list_projects_command(update, context)
    elif data == "menu_profile":
        from handlers.auth import profile_command
        return await profile_command(update, context)

    # All actions below require Admin permissions
    if not is_admin(user.id):
        await query.answer("⛔ Only managers/admins can access this function.", show_alert=True)
        return

    if data in ("admin_dashboard", "menu_admin"):
        await query.edit_message_text(
            "🎛️ *SITE MANAGEMENT CONTROLLER PANEL*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Use the buttons below to create project topics with deadlines, monitor real-time progress bars, and manage site operations:",
            reply_markup=build_admin_panel_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "admin_progress_overview":
        projects = list_active_projects()
        if not projects:
            text = "No active projects registered."
        else:
            lines = ["📊 *PROJECTS REAL-TIME PROGRESS OVERVIEW:*", "━━━━━━━━━━━━━━━━━━━━\n"]
            for p in projects:
                p_name = p["name"]
                percent = p.get("progress_percent", 0) or 0
                deadline_str = get_deadline_info(p.get("deadline"))
                bar = render_progress_bar(percent, length=10)
                topic_id = p.get("topic_id", 0)
                topic_str = f"Topic #{topic_id}" if topic_id else "General"

                lines.append(
                    f"🏗️ *{p_name}* ({topic_str})\n"
                    f"   {bar}\n"
                    f"   ⏳ *Target:* {deadline_str}\n"
                )
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)

        keyboard = [
            [InlineKeyboardButton("📈 Update a Project Progress", callback_data="admin_update_progress_btn")],
            [InlineKeyboardButton("⬅️ Back to Controller", callback_data="admin_dashboard")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data in ("admin_workers_roster", "menu_workers"):
        workers = list_all_workers()
        lines = ["👥 *Registered Workers Roster:*", "━━━━━━━━━━━━━━━━━━━━"]
        for w in workers:
            status_icon = "✅ Approved" if w.get("is_approved") else "⏳ Pending"
            admin_badge = " ⭐ [ADMIN]" if w.get("is_admin") else ""
            lines.append(f"• *{w['full_name']}* — _{w['role']}_{admin_badge}\n  ID: `{w['user_id']}` | {status_icon}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("Approve pending worker: `/approve_worker <user_id>`")

        keyboard = [[InlineKeyboardButton("⬅️ Back to Controller", callback_data="admin_dashboard")]]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_weekly_summary":
        await query.edit_message_text("⏳ Generating Weekly Worker Activity Digest...")
        summary_data = get_weekly_worker_summary(days=7)
        chunks = format_weekly_worker_summary_text(summary_data)
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Controller", callback_data="admin_dashboard")]])
        for i, chunk in enumerate(chunks):
            reply_markup = back_kb if i == len(chunks) - 1 else None
            if i == 0:
                await query.edit_message_text(chunk, reply_markup=reply_markup, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=query.message.chat_id, text=chunk, reply_markup=reply_markup, parse_mode="Markdown")

    elif data in ("admin_export_excel", "menu_export"):
        await query.edit_message_text("⏳ Generating Excel export (Reports, MaterialRequests, Issues, Workers)...")
        try:
            excel_path = export_all_data_to_excel()
            with open(excel_path, "rb") as doc_file:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=doc_file,
                    filename=excel_path.name,
                    caption="📊 *Site Management Master Data Export*\nIncludes 4 Tabs: `Reports`, `MaterialRequests`, `Issues`, `Workers`.",
                    parse_mode="Markdown"
                )
            await query.message.reply_text("✅ Export complete!", reply_markup=build_admin_panel_keyboard())
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            await query.message.reply_text(f"❌ Export failed: {e}", reply_markup=build_admin_panel_keyboard())

    elif data == "admin_check_reports_btn":
        await query.edit_message_text("🔍 Checking Day and Night report submissions across all active projects...")
        from scheduler import check_missing_day_reports, check_missing_night_reports
        await check_missing_day_reports(context)
        await check_missing_night_reports(context)
        await query.message.reply_text("✅ Cutoff check completed.", reply_markup=build_admin_panel_keyboard())

    elif data in ("admin_sync_sheets", "menu_sync"):
        await query.edit_message_text("⏳ Syncing database with Google Sheets...")
        res = sync_all_database_to_sheets()
        if res.get("success"):
            url_msg = f"\n🔗 [Open Google Sheet]({res['url']})" if "url" in res else ""
            await query.message.reply_text(
                f"✅ *Google Sheets Live Sync Successful!*\n"
                f"Synchronized via: *{res.get('method', 'Google Sheets API')}*{url_msg}",
                reply_markup=build_admin_panel_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                f"⚠️ *Google Sheets Notice:*\n{res.get('error')}\n\n"
                f"Place your `credentials.json` (Service Account) in the bot folder or configure `GOOGLE_SHEET_WEBHOOK_URL` in `.env`.",
                reply_markup=build_admin_panel_keyboard(),
                parse_mode="Markdown"
            )

async def sync_sheets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /sync_sheets — triggers full sync of local database into Google Sheets."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can sync with Google Sheets.")
        return

    msg = await update.message.reply_text("⏳ Synchronizing all project data with Google Sheets...")
    res = sync_all_database_to_sheets()
    if res.get("success"):
        url_msg = f"\n🔗 [Open Google Sheet]({res['url']})" if "url" in res else ""
        await msg.edit_text(
            f"✅ *Google Sheets Live Sync Successful!*\n"
            f"Synchronized via: *{res.get('method', 'Google Sheets API')}*{url_msg}",
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(
            f"⚠️ *Google Sheets Sync Notice:*\n{res.get('error')}\n\n"
            f"To enable Google Sheets:\n"
            f"1. Put `credentials.json` in project directory, OR\n"
            f"2. Add `GOOGLE_SHEET_WEBHOOK_URL` to `.env`.",
            parse_mode="Markdown"
        )

# --- Create Project with Deadline Wizard ---

async def start_create_project_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /create_project or clicking 'Create Project & Topic' button."""
    user = update.effective_user
    if not is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Only managers/admins can create projects.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Only managers/admins can create projects.")
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "➕ *Create New Project & Forum Topic*\n\n"
            "Step 1/2: What is the *Project Name*?\n"
            "(e.g., `Site 204 - Commercial Center` or `Tower B Renovation`):",
            parse_mode="Markdown"
        )
    else:
        # Check if project name was provided directly e.g. /create_project Site 204
        if context.args:
            context.user_data["new_proj_name"] = " ".join(context.args).strip()
            keyboard = [
                [InlineKeyboardButton("⚡ Skip Deadline", callback_data="skip_deadline")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_create_proj")]
            ]
            await update.message.reply_text(
                f"🏗️ Project Name: *{context.user_data['new_proj_name']}*\n\n"
                f"Step 2/2: What is the *Target Deadline* for this project?\n"
                f"(Format: `YYYY-MM-DD`, e.g., `2026-11-30`, or click *Skip Deadline*):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return NEW_PROJ_DEADLINE

        await update.message.reply_text(
            "➕ *Create New Project & Forum Topic*\n\n"
            "Step 1/2: What is the *Project Name*?\n"
            "(e.g., `Site 204 - Commercial Center` or `Tower B Renovation`):",
            parse_mode="Markdown"
        )
    return NEW_PROJ_NAME

async def receive_new_proj_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Please enter a valid project name:")
        return NEW_PROJ_NAME

    context.user_data["new_proj_name"] = name
    keyboard = [
        [InlineKeyboardButton("⚡ Skip Deadline", callback_data="skip_deadline")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_create_proj")]
    ]
    await update.message.reply_text(
        f"🏗️ Project Name: *{name}*\n\n"
        f"Step 2/2: What is the *Target Deadline* for this project?\n"
        f"(Format: `YYYY-MM-DD`, e.g., `2026-11-30`, or click *Skip Deadline*):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return NEW_PROJ_DEADLINE

async def receive_new_proj_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    deadline_text = update.message.text.strip() if update.message else None
    return await _finish_project_creation(update, context, deadline_text)

async def deadline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "cancel_create_proj":
        await query.edit_message_text("❌ Project creation cancelled.")
        return ConversationHandler.END
    # skip deadline
    return await _finish_project_creation(update, context, None)

async def _finish_project_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, deadline: str = None) -> int:
    proj_name = context.user_data.get("new_proj_name", "New Project")
    user = update.effective_user

    status_text = f"⏳ Creating Forum Topic for *{proj_name}* in Telegram..."
    if update.callback_query:
        msg = await update.callback_query.edit_message_text(status_text, parse_mode="Markdown")
    else:
        msg = await update.message.reply_text(status_text, parse_mode="Markdown")

    topic_id = 0
    if SUPERGROUP_CHAT_ID != 0:
        try:
            topic = await context.bot.create_forum_topic(
                chat_id=SUPERGROUP_CHAT_ID,
                name=f"🏗️ {proj_name}",
                icon_color=0x8EEE98
            )
            topic_id = topic.message_thread_id
            
            # Post welcome & progress card into the new topic
            deadline_info = get_deadline_info(deadline)
            bar = render_progress_bar(0)
            topic_welcome = (
                f"🏗️ *TOPIC CREATED: {proj_name.upper()}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Initial Progress:* {bar}\n"
                f"⏳ *Target Deadline:* {deadline_info}\n"
                f"👤 *Created By:* {user.full_name}\n\n"
                f"Daily and Night progress reports for this site will be logged here.\n"
                f"Foremen can submit updates via `/report` or `/night_report`."
            )
            await context.bot.send_message(
                chat_id=SUPERGROUP_CHAT_ID,
                message_thread_id=topic_id,
                text=topic_welcome,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to create forum topic in Telegram: {e}")

    # Save to SQLite Database with deadline and 0% initial progress
    add_or_update_project(proj_name, topic_id=topic_id, deadline=deadline, progress_percent=0)

    deadline_display = get_deadline_info(deadline)
    bar_display = render_progress_bar(0)
    topic_display = f"`Topic #{topic_id}`" if topic_id else "(General Group)"

    final_text = (
        f"🎉 *Project Created & Initialized!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏗️ *Project:* {proj_name}\n"
        f"📌 *Telegram Topic:* {topic_display}\n"
        f"⏳ *Deadline:* {deadline_display}\n"
        f"📊 *Progress Bar:* {bar_display}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(final_text, parse_mode="Markdown")
    else:
        await msg.edit_text(final_text, parse_mode="Markdown")

    context.user_data.pop("new_proj_name", None)
    return ConversationHandler.END

async def cancel_create_proj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Project creation cancelled.")
    return ConversationHandler.END

def get_create_project_wizard_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("create_project", start_create_project_wizard),
            CallbackQueryHandler(start_create_project_wizard, pattern=r"^admin_create_proj$"),
        ],
        states={
            NEW_PROJ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_proj_name)],
            NEW_PROJ_DEADLINE: [
                CallbackQueryHandler(deadline_callback, pattern=r"^(skip_deadline|cancel_create_proj)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_proj_deadline)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_create_proj)],
        allow_reentry=True,
    )

# --- Update Project Progress Wizard (/progress) ---

async def progress_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /progress or 'Update Project Progress' button."""
    user = update.effective_user
    if not is_authorized(user.id):
        await update.message.reply_text("⚠️ You must be an approved worker/manager to update progress.")
        return ConversationHandler.END

    projects = list_active_projects()
    if not projects:
        await update.message.reply_text("❌ No active projects found.")
        return ConversationHandler.END

    keyboard = []
    for proj in projects:
        curr_pct = proj.get("progress_percent", 0) or 0
        keyboard.append([InlineKeyboardButton(f"🏗️ {proj['name']} ({curr_pct}%)", callback_data=f"prog_pick_{proj['name']}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="prog_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "📈 *Update Project Progress*\n\nSelect the project to update its completion percentage:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return PROG_SELECT_PROJ

async def progress_project_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "prog_cancel":
        await query.edit_message_text("❌ Progress update cancelled.")
        return ConversationHandler.END

    proj_name = data.replace("prog_pick_", "")
    context.user_data["prog_target_proj"] = proj_name
    proj = get_project(proj_name)
    curr_pct = proj.get("progress_percent", 0) if proj else 0
    curr_bar = render_progress_bar(curr_pct)

    keyboard = [
        [
            InlineKeyboardButton("25%", callback_data="prog_set_25"),
            InlineKeyboardButton("50%", callback_data="prog_set_50"),
            InlineKeyboardButton("75%", callback_data="prog_set_75"),
        ],
        [
            InlineKeyboardButton("90%", callback_data="prog_set_90"),
            InlineKeyboardButton("100% (Completed 🎉)", callback_data="prog_set_100"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="prog_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🏗️ *Project:* {proj_name}\n"
        f"📊 *Current Progress:* {curr_bar}\n\n"
        f"Select new percentage from buttons below, or *type any number (0-100)*:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return PROG_INPUT_PERCENT

async def progress_percent_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    proj_name = context.user_data.get("prog_target_proj", "Project")
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "prog_cancel":
            await query.edit_message_text("❌ Progress update cancelled.")
            return ConversationHandler.END
        pct_str = query.data.replace("prog_set_", "")
        new_pct = int(pct_str)
    else:
        text = update.message.text.strip().replace("%", "")
        if not text.isdigit():
            await update.message.reply_text("Please enter a valid number between 0 and 100 (or tap a button):")
            return PROG_INPUT_PERCENT
        new_pct = int(text)

    new_pct = max(0, min(100, new_pct))
    update_project_progress(proj_name, new_pct)
    proj = get_project(proj_name)
    bar = render_progress_bar(new_pct)
    deadline_info = get_deadline_info(proj.get("deadline") if proj else None)

    card = (
        f"✅ *PROJECT PROGRESS UPDATED!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏗️ *Project:* {proj_name}\n"
        f"📊 *New Progress:* {bar}\n"
        f"⏳ *Target Deadline:* {deadline_info}\n"
        f"👤 *Updated By:* {update.effective_user.full_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    # Post update into the project's Telegram forum topic if configured
    if SUPERGROUP_CHAT_ID != 0 and proj and proj.get("topic_id"):
        try:
            await context.bot.send_message(
                chat_id=SUPERGROUP_CHAT_ID,
                message_thread_id=proj["topic_id"],
                text=card,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to post progress card into topic: {e}")

    if update.callback_query:
        await update.callback_query.edit_message_text(card, parse_mode="Markdown")
    else:
        await update.message.reply_text(card, parse_mode="Markdown")

    context.user_data.pop("prog_target_proj", None)
    return ConversationHandler.END

def get_progress_update_wizard_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("progress", progress_command_start),
            CallbackQueryHandler(progress_command_start, pattern=r"^(admin_update_progress_btn|menu_progress)$"),
            CallbackQueryHandler(progress_project_selected, pattern=r"^prog_pick_"),
        ],
        states={
            PROG_SELECT_PROJ: [CallbackQueryHandler(progress_project_selected, pattern=r"^(prog_pick_|prog_cancel)")],
            PROG_INPUT_PERCENT: [
                CallbackQueryHandler(progress_percent_received, pattern=r"^(prog_set_|prog_cancel)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, progress_percent_received)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_create_proj)],
        allow_reentry=True,
    )

# --- Remaining Admin Helper Commands ---

async def export_sheets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can export data sheets.")
        return

    status_msg = await update.message.reply_text("⏳ Generating Excel export (Reports, MaterialRequests, Issues, Workers)...")
    try:
        excel_path = export_all_data_to_excel()
        with open(excel_path, "rb") as doc_file:
            await update.message.reply_document(
                document=doc_file,
                filename=excel_path.name,
                caption="📊 *Site Management Master Data Export*\nIncludes 4 Tabs: `Reports`, `MaterialRequests`, `Issues`, `Workers`.",
                parse_mode="Markdown"
            )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        await status_msg.edit_text(f"❌ Export failed: {e}")

async def list_workers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can view worker rosters.")
        return

    workers = list_all_workers()
    if not workers:
        await update.message.reply_text("No workers registered yet.")
        return

    lines = ["👥 *Registered Workers Roster:*", "━━━━━━━━━━━━━━━━━━━━"]
    for w in workers:
        status_icon = "✅" if w.get("is_approved") else "⏳ Pending"
        admin_badge = " [ADMIN]" if w.get("is_admin") else ""
        lines.append(f"• *{w['full_name']}* — _{w['role']}_{admin_badge}\n  ID: `{w['user_id']}` | Status: {status_icon}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("To approve a pending worker: `/approve_worker <user_id>`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def approve_worker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can approve workers.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/approve_worker <user_id>`", parse_mode="Markdown")
        return

    try:
        target_uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid User ID. Must be numeric.")
        return

    worker = get_worker(target_uid)
    if not worker:
        await update.message.reply_text(f"No worker found with ID `{target_uid}`.", parse_mode="Markdown")
        return

    set_worker_approval(target_uid, True)
    await update.message.reply_text(f"✅ Approved worker *{worker['full_name']}* (`{target_uid}`).", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text="🎉 *Your account has been approved by management!* You can now submit `/report` and `/request_material`.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not message worker {target_uid}: {e}")

async def list_projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    projects = list_active_projects()
    is_cb = bool(update.callback_query)

    if is_cb:
        await update.callback_query.answer()

    if not projects:
        msg_txt = "❌ No active projects found."
        if is_cb:
            await update.callback_query.edit_message_text(msg_txt)
        else:
            await update.message.reply_text(msg_txt)
        return

    lines = ["🏗️ *Active Projects & Progress:*", "━━━━━━━━━━━━━━━━━━━━\n"]
    keyboard = []

    for p in projects:
        p_name = p["name"]
        pct = p.get("progress_percent", 0) or 0
        bar = render_progress_bar(pct)
        deadline = get_deadline_info(p.get("deadline"))
        topic_info = f"Topic #{p['topic_id']}" if p.get("topic_id") else "General Group"
        lines.append(f"• *{p_name}* ({topic_info})\n  {bar}\n  ⏳ Target: {deadline}\n")
        keyboard.append([InlineKeyboardButton(f"📊 {p_name} ({pct}%)", callback_data=f"status_proj_{p_name}")])

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("Tap any project button below to view details and open requests:")

    user_id = update.effective_user.id
    if is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("➕ Create Project", callback_data="admin_create_proj"),
            InlineKeyboardButton("📈 Update Progress", callback_data="admin_update_progress_btn"),
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    full_text = "\n".join(lines)

    if is_cb:
        await update.callback_query.edit_message_text(full_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(full_text, reply_markup=reply_markup, parse_mode="Markdown")

async def remove_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can remove projects.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/remove_project <Project Name>`", parse_mode="Markdown")
        return

    proj_name = " ".join(context.args).strip()
    success = remove_project(proj_name)
    if success:
        await update.message.reply_text(f"✅ Project *{proj_name}* deactivated.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Project *{proj_name}* not found.", parse_mode="Markdown")

async def add_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can add projects.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/add_project <Project Name> [TopicThreadID]`\nExample: `/add_project Site 105 28`", parse_mode="Markdown")
        return

    topic_id = 0
    if len(context.args) > 1 and context.args[-1].isdigit():
        topic_id = int(context.args[-1])
        proj_name = " ".join(context.args[:-1]).strip()
    else:
        proj_name = " ".join(context.args).strip()

    add_or_update_project(proj_name, topic_id)
    topic_str = f"with Topic ID `{topic_id}`" if topic_id else "(General Topic)"
    await update.message.reply_text(f"✅ Project *{proj_name}* registered successfully {topic_str}.", parse_mode="Markdown")

async def setup_topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /setup_topics — initialize default forum topics."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can setup topics.")
        return

    status_msg = await update.message.reply_text("⏳ Initializing standard Forum Topics in Telegram Supergroup...")
    from setup_topics import DEFAULT_TOPICS, update_env_file
    bot = context.bot
    created_ids = {}
    success_count = 0

    for t in DEFAULT_TOPICS:
        try:
            topic = await bot.create_forum_topic(
                chat_id=SUPERGROUP_CHAT_ID,
                name=t["name"],
                icon_color=t.get("color")
            )
            thread_id = topic.message_thread_id
            success_count += 1

            if t["type"] == "project":
                add_or_update_project(t["proj_name"], thread_id)
                created_ids[t["proj_name"]] = thread_id
            elif t["type"] == "materials":
                set_setting("materials_topic_id", str(thread_id))
                created_ids["TOPIC_MATERIALS"] = thread_id
            elif t["type"] == "issues":
                set_setting("issues_topic_id", str(thread_id))
                created_ids["TOPIC_ISSUES"] = thread_id
            elif t["type"] == "announcements":
                set_setting("announcements_topic_id", str(thread_id))
                created_ids["TOPIC_ANNOUNCEMENTS"] = thread_id

            await bot.send_message(
                chat_id=SUPERGROUP_CHAT_ID,
                message_thread_id=thread_id,
                text=f"👋 *Welcome to {t['name']}!*\nManaged by @TilahunSiteBot.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to create topic {t['name']}: {e}")

    update_env_file(created_ids)
    await status_msg.edit_text(
        f"🎉 *Topic Setup Complete!*\n\n"
        f"Successfully created *{success_count}* topics in Supergroup.\n"
        f"Type `/projects` to view all active project topics.",
        parse_mode="Markdown"
    )
