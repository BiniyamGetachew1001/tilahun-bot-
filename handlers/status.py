import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    list_active_projects,
    get_project,
    get_project_by_topic_id,
    get_latest_report,
    get_open_material_requests,
    get_open_issues,
    render_progress_bar,
    get_deadline_info,
)
from handlers.auth import is_authorized, is_admin

from locales import t, get_user_lang

logger = logging.getLogger(__name__)

def build_status_message(project_name: str, lang: str = "en") -> str:
    """Builds a comprehensive mid-day status report for a given project in the target language."""
    proj = get_project(project_name)
    latest_report = get_latest_report(project_name)
    open_mrs = get_open_material_requests(project_name)
    open_issues = get_open_issues(project_name)

    # 0. Progress and Deadline section
    pct = proj.get("progress_percent", 0) if proj else 0
    bar = render_progress_bar(pct, length=10)
    deadline_str = get_deadline_info(proj.get("deadline") if proj else None)
    prog_section = t("status_progress_lbl", lang, bar=bar, deadline=deadline_str)

    # 1. Report summary
    if latest_report:
        rep_date = latest_report["timestamp"]
        rep_shift = "🌙 Night Shift" if latest_report.get("shift_type") == "NIGHT" else "☀️ Day Shift"
        rep_author = f"{latest_report['worker_name']} ({latest_report.get('worker_role', 'Worker')})"
        work_done = latest_report["work_completed"]
        if len(work_done) > 120:
            work_done = work_done[:117] + "..."
        rep_section = t("status_last_report", lang, shift=rep_shift, date=rep_date, author=rep_author, work=work_done)
    else:
        rep_section = t("status_no_reports", lang)

    # 2. Material requests summary
    if open_mrs:
        mr_lines = []
        for mr in open_mrs[:5]:
            urg_icon = "🔴" if mr["urgency"] == "URGENT" else ("🟡" if mr["urgency"] == "PRIORITY" else "🟢")
            status_icon = "🚚" if mr["status"] == "IN_TRANSIT" else "⏳"
            item_summary = mr["items_description"]
            if len(item_summary) > 40:
                item_summary = item_summary[:37] + "..."
            mr_lines.append(f"• `{mr['mr_code']}` {urg_icon} {status_icon} _{item_summary}_")
        
        extra_count = len(open_mrs) - 5
        extra_str = f"\n_...and {extra_count} more open requests_" if extra_count > 0 else ""
        mr_section = t("status_open_mrs", lang, count=len(open_mrs)) + "\n" + "\n".join(mr_lines) + extra_str
    else:
        mr_section = t("status_no_mrs", lang)

    # 3. Unresolved issues / blockers
    if open_issues:
        issue_lines = []
        for issue in open_issues[:4]:
            desc = issue["description"]
            if len(desc) > 50:
                desc = desc[:47] + "..."
            issue_lines.append(f"• ⚠️ _{desc}_ (by {issue['worker_name']})")
        issue_section = t("status_open_issues", lang, count=len(open_issues)) + "\n" + "\n".join(issue_lines)
    else:
        issue_section = t("status_no_issues", lang)

    title = t("status_project_title", lang, project=project_name)
    return (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{prog_section}\n\n"
        f"{rep_section}\n\n"
        f"{mr_section}\n\n"
        f"{issue_section}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def build_status_card_keyboard(project_name: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Builds interactive action buttons on a status card."""
    keyboard = [
        [
            InlineKeyboardButton(t("btn_refresh", lang), callback_data=f"status_proj_{project_name}"),
            InlineKeyboardButton(t("btn_submit_report", lang), callback_data=f"rep_proj_{project_name}"),
        ],
        [
            InlineKeyboardButton(t("btn_request_material", lang), callback_data=f"mr_proj_{project_name}"),
            InlineKeyboardButton("📈 Update Progress", callback_data=f"prog_pick_{project_name}"),
        ],
        [
            InlineKeyboardButton(t("btn_back_to_projects", lang), callback_data="status_back"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /status [ProjectName] or '📊 Project Status' button."""
    user = update.effective_user
    lang = get_user_lang(user.id)
    if not is_authorized(user.id):
        await update.message.reply_text("⚠️ Please register with `/start` first.", parse_mode="Markdown")
        return

    projects = list_active_projects()
    if not projects:
        await update.message.reply_text("❌ No active projects found.")
        return

    # Auto-detect if executed inside a Project Forum Topic
    thread_id = getattr(update.message, "message_thread_id", None) if update.message else None
    if thread_id:
        topic_proj = get_project_by_topic_id(thread_id)
        if topic_proj:
            status_text = build_status_message(topic_proj["name"], lang=lang)
            await update.message.reply_text(
                status_text,
                reply_markup=build_status_card_keyboard(topic_proj["name"], lang=lang),
                parse_mode="Markdown"
            )
            return

    # Check if project name was provided as an argument e.g. /status Project Alpha
    if context.args:
        arg_project = " ".join(context.args).strip()
        matched = next((p for p in projects if p["name"].lower() == arg_project.lower()), None)
        if matched:
            status_text = build_status_message(matched["name"], lang=lang)
            await update.message.reply_text(
                status_text,
                reply_markup=build_status_card_keyboard(matched["name"], lang=lang),
                parse_mode="Markdown"
            )
            return
        else:
            await update.message.reply_text(f"❌ Project '{arg_project}' not found. Please choose below:")

    # Otherwise display project selection buttons
    keyboard = []
    for proj in projects:
        pct = proj.get("progress_percent", 0) or 0
        keyboard.append([InlineKeyboardButton(f"📊 {proj['name']} ({pct}%)", callback_data=f"status_proj_{proj['name']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    dashboard_prompt = "📊 *የፕሮጀክት ሁኔታ መመልከቻ*\n\nየእያንዳንዱን ፕሮጀክት ሁኔታ ለማየት ከታች ይምረጡ:" if lang == "am" else (
        "📊 *Haala Piroojektii*\n\nHaala piroojektii arguuf armaan gadii filadhaa:" if lang == "om" else
        "📊 *Project Status Dashboard*\n\nSelect a project to view its real-time status summary:"
    )
    await update.message.reply_text(
        dashboard_prompt,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles project selection and refresh from /status inline buttons."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    data = query.data

    if data.startswith("status_proj_"):
        project_name = data.replace("status_proj_", "")
        status_text = build_status_message(project_name, lang=lang)

        try:
            await query.edit_message_text(
                status_text,
                reply_markup=build_status_card_keyboard(project_name, lang=lang),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.debug(f"Message not changed: {e}")

    elif data == "status_back":
        projects = list_active_projects()
        keyboard = []
        for proj in projects:
            pct = proj.get("progress_percent", 0) or 0
            keyboard.append([InlineKeyboardButton(f"📊 {proj['name']} ({pct}%)", callback_data=f"status_proj_{proj['name']}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        dashboard_prompt = "📊 *የፕሮጀክት ሁኔታ መመልከቻ*\n\nየእያንዳንዱን ፕሮጀክት ሁኔታ ለማየት ከታች ይምረጡ:" if lang == "am" else (
            "📊 *Haala Piroojektii*\n\nHaala piroojektii arguuf armaan gadii filadhaa:" if lang == "om" else
            "📊 *Project Status Dashboard*\n\nSelect a project to view its real-time status summary:"
        )
        await query.edit_message_text(
            dashboard_prompt,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
