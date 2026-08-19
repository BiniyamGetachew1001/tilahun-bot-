import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import SUPERGROUP_CHAT_ID
from database import (
    get_worker,
    list_active_projects,
    get_project,
    get_project_by_topic_id,
    save_daily_report,
    update_project_progress,
    render_progress_bar,
    get_deadline_info,
)
from google_sheets import append_report_live, update_project_live
from handlers.auth import is_authorized

logger = logging.getLogger(__name__)

# Conversation states
SELECT_PROJECT, SELECT_SHIFT, INPUT_COMPLETED, INPUT_TOMORROW, INPUT_BLOCKERS, INPUT_PHOTO, INPUT_PROGRESS = range(7)

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /report, /day_report, '☀️ Day Report' button, and 'menu_day_report'."""
    context.user_data["default_shift"] = "DAY"
    return await _init_report_flow(update, context)

async def night_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /night_report, '🌙 Night Report' button, and 'menu_night_report'."""
    context.user_data["default_shift"] = "NIGHT"
    return await _init_report_flow(update, context)

async def _init_report_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    is_cb = bool(update.callback_query)
    
    if is_cb:
        await update.callback_query.answer()

    if not is_authorized(user.id):
        worker = get_worker(user.id)
        msg_txt = "⚠️ You must first register with `/start` before submitting reports." if not worker else "⏳ Your account is pending manager approval. Please wait until approved."
        if is_cb:
            await update.callback_query.edit_message_text(msg_txt, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg_txt, parse_mode="Markdown")
        return ConversationHandler.END

    projects = list_active_projects()
    if not projects:
        msg_txt = "❌ No active projects found. Please contact an admin."
        if is_cb:
            await update.callback_query.edit_message_text(msg_txt)
        else:
            await update.message.reply_text(msg_txt)
        return ConversationHandler.END

    # Auto-detect if command was executed directly inside a Project Forum Topic
    thread_id = getattr(update.message, "message_thread_id", None) if update.message else None
    if thread_id:
        topic_proj = get_project_by_topic_id(thread_id)
        if topic_proj:
            context.user_data["report_project"] = topic_proj["name"]
            context.user_data["report_topic_id"] = topic_proj.get("topic_id", thread_id)
            if context.user_data.get("default_shift"):
                context.user_data["report_shift"] = context.user_data["default_shift"]
                shift_label = "🌙 Night Shift" if context.user_data["report_shift"] == "NIGHT" else "☀️ Day Shift"
                await update.message.reply_text(
                    f"📋 *{shift_label} Report — {topic_proj['name']}*\n\n"
                    f"Step 1/5: *What work was completed during this shift?*\n"
                    f"(Type a text summary or record a 🎙️ Voice Message):",
                    parse_mode="Markdown"
                )
                return INPUT_COMPLETED
            else:
                return await prompt_shift_selection(update, context)

    # Check if project name was provided in command arguments e.g. /report Project Alpha
    if context.args:
        arg_project = " ".join(context.args).strip()
        matched = next((p for p in projects if p["name"].lower() == arg_project.lower()), None)
        if matched:
            context.user_data["report_project"] = matched["name"]
            context.user_data["report_topic_id"] = matched.get("topic_id", 0)
            
            if context.user_data.get("default_shift"):
                context.user_data["report_shift"] = context.user_data["default_shift"]
                shift_label = "🌙 Night Shift" if context.user_data["report_shift"] == "NIGHT" else "☀️ Day Shift"
                await update.message.reply_text(
                    f"📋 *{shift_label} Report — {matched['name']}*\n\n"
                    f"Step 1/5: *What work was completed during this shift?*\n"
                    f"(Type a text summary or record a 🎙️ Voice Message):",
                    parse_mode="Markdown"
                )
                return INPUT_COMPLETED
            else:
                return await prompt_shift_selection(update, context)

    # Display project selection buttons
    keyboard = []
    for proj in projects:
        pct = proj.get("progress_percent", 0) or 0
        keyboard.append([InlineKeyboardButton(f"🏗️ {proj['name']} ({pct}%)", callback_data=f"rep_proj_{proj['name']}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="rep_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    header = "🌙 *Night Shift Progress Report*" if context.user_data.get("default_shift") == "NIGHT" else "📋 *Day Shift Progress Report*"
    prompt_txt = f"{header}\n\nSelect the *Project* you are reporting for:"

    if is_cb:
        await update.callback_query.edit_message_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_PROJECT

async def project_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "rep_cancel":
        await query.edit_message_text("❌ Report submission cancelled.")
        return ConversationHandler.END

    project_name = data.replace("rep_proj_", "")
    proj = get_project(project_name)
    context.user_data["report_project"] = project_name
    context.user_data["report_topic_id"] = proj.get("topic_id", 0) if proj else 0

    if context.user_data.get("default_shift"):
        context.user_data["report_shift"] = context.user_data["default_shift"]
        shift_label = "🌙 Night Shift" if context.user_data["report_shift"] == "NIGHT" else "☀️ Day Shift"
        await query.edit_message_text(
            f"📋 *{shift_label} Report — {project_name}*\n\n"
            f"Step 1/5: *What work was completed during this shift?*\n"
            f"(Type a text summary or record a 🎙️ Voice Message):",
            parse_mode="Markdown"
        )
        return INPUT_COMPLETED

    return await prompt_shift_selection(query, context, is_query=True)

async def prompt_shift_selection(target, context: ContextTypes.DEFAULT_TYPE, is_query: bool = False) -> int:
    project_name = context.user_data.get("report_project", "Project")
    keyboard = [
        [
            InlineKeyboardButton("☀️ Day Shift", callback_data="rep_shift_DAY"),
            InlineKeyboardButton("🌙 Night Shift", callback_data="rep_shift_NIGHT")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"🏗️ *Project:* {project_name}\n\nSelect the *Working Shift*:"

    if is_query:
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_SHIFT

async def shift_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "rep_cancel":
        await query.edit_message_text("❌ Report submission cancelled.")
        return ConversationHandler.END

    shift = data.replace("rep_shift_", "")
    context.user_data["report_shift"] = shift
    project_name = context.user_data.get("report_project", "Project")
    shift_label = "🌙 Night Shift" if shift == "NIGHT" else "☀️ Day Shift"

    work_prompt = "during tonight's shift" if shift == "NIGHT" else "today"
    await query.edit_message_text(
        f"📋 *{shift_label} Report — {project_name}*\n\n"
        f"Step 1/5: *What work was completed {work_prompt}?*\n"
        f"(Type a text summary or send a 🎙️ Voice Memo):",
        parse_mode="Markdown"
    )
    return INPUT_COMPLETED

async def receive_completed_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_completed"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        text = msg.text.strip()
        if len(text) < 2:
            await msg.reply_text("Please enter a brief description of the work completed:")
            return INPUT_COMPLETED
        context.user_data["report_completed"] = text

    shift = context.user_data.get("report_shift", "DAY")
    plan_prompt = "for the next shift / morning handover" if shift == "NIGHT" else "for tomorrow"

    await update.message.reply_text(
        f"Step 2/5: *What is the plan {plan_prompt}?*\n"
        f"(List scheduled tasks or send a 🎙️ Voice Memo):",
        parse_mode="Markdown"
    )
    return INPUT_TOMORROW

async def receive_tomorrow_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_tomorrow"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        text = msg.text.strip()
        if len(text) < 2:
            await msg.reply_text("Please enter the plan / handover:")
            return INPUT_TOMORROW
        context.user_data["report_tomorrow"] = text

    shift = context.user_data.get("report_shift", "DAY")
    blocker_prompt = "delays, night hazards, or blockers" if shift == "NIGHT" else "delays, issues, or blockers"

    await update.message.reply_text(
        f"Step 3/5: *Any {blocker_prompt}?*\n"
        f"(Type *None* if no issues, or describe the problem):",
        parse_mode="Markdown"
    )
    return INPUT_BLOCKERS

async def receive_blockers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_blockers"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        context.user_data["report_blockers"] = msg.text.strip()

    # Prompt for photo upload (Step 4/5)
    keyboard = [
        [InlineKeyboardButton("⏩ Skip Photo", callback_data="rep_skip_photo")],
        [InlineKeyboardButton("❌ Cancel", callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Step 4/5: 📸 *Site Progress Photos*\n\n"
        "Send a photo showing the work done or site progress, or click *Skip Photo* below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return INPUT_PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        context.user_data["report_photo_id"] = photo_file_id
        await msg.reply_text("📸 *Photo attached successfully!*", parse_mode="Markdown")
    elif msg.text and msg.text.strip().lower() in ("skip", "no", "none", "pass", "-", "skip photo"):
        context.user_data["report_photo_id"] = None
    else:
        await msg.reply_text("Please upload a photo, or send 'skip' to continue without photos.")
        return INPUT_PHOTO

    return await prompt_progress_step(update, context)

async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "rep_cancel":
        await query.edit_message_text("❌ Report submission cancelled.")
        return ConversationHandler.END

    context.user_data["report_photo_id"] = None
    return await prompt_progress_step(query, context, is_query=True)

async def prompt_progress_step(target, context: ContextTypes.DEFAULT_TYPE, is_query: bool = False) -> int:
    proj_name = context.user_data.get("report_project", "Project")
    proj = get_project(proj_name)
    curr_pct = proj.get("progress_percent", 0) if proj else 0
    curr_bar = render_progress_bar(curr_pct)

    keyboard = [
        [
            InlineKeyboardButton("25%", callback_data="rep_pct_25"),
            InlineKeyboardButton("50%", callback_data="rep_pct_50"),
            InlineKeyboardButton("75%", callback_data="rep_pct_75"),
        ],
        [
            InlineKeyboardButton("90%", callback_data="rep_pct_90"),
            InlineKeyboardButton("100% 🎉", callback_data="rep_pct_100"),
            InlineKeyboardButton(f"Keep {curr_pct}%", callback_data=f"rep_pct_{curr_pct}"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"Step 5/5: *Overall Project Completion Percentage:*\n\n"
        f"Current Progress: {curr_bar}\n"
        f"Select updated percentage below or *type any number (0-100)*:"
    )

    if is_query:
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return INPUT_PROGRESS

async def receive_progress_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    proj_name = context.user_data.get("report_project", "General")
    proj_db = get_project(proj_name)
    curr_pct = proj_db.get("progress_percent", 0) if proj_db else 0

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "rep_cancel":
            await query.edit_message_text("❌ Report submission cancelled.")
            return ConversationHandler.END
        pct_val = int(data.replace("rep_pct_", ""))
    else:
        raw_text = update.message.text.strip().replace("%", "")
        if raw_text.isdigit():
            pct_val = int(raw_text)
        else:
            pct_val = curr_pct

    pct_val = max(0, min(100, pct_val))
    update_project_progress(proj_name, pct_val)

    # Gather full report data
    user = update.effective_user
    worker = get_worker(user.id)
    worker_name = worker["full_name"] if worker else user.full_name
    worker_role = worker["role"] if worker else "Worker"

    topic_id = (proj_db.get("topic_id") if proj_db else None) or context.user_data.get("report_topic_id", 0)
    shift = context.user_data.get("report_shift", "DAY").upper()
    work_completed = context.user_data.get("report_completed", "N/A")
    plan_tomorrow = context.user_data.get("report_tomorrow", "N/A")
    blockers_text = context.user_data.get("report_blockers", "None")
    photo_id = context.user_data.get("report_photo_id")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    shift_title = "🌙 NIGHT SHIFT PROGRESS REPORT" if shift == "NIGHT" else "☀️ DAY SHIFT PROGRESS REPORT"
    shift_badge = "🌙 Night Shift" if shift == "NIGHT" else "☀️ Day Shift"
    plan_label = "🎯 Handover / Next Shift Plan:" if shift == "NIGHT" else "🎯 Plan for Tomorrow:"

    bar_display = render_progress_bar(pct_val)
    deadline_display = get_deadline_info(proj_db.get("deadline") if proj_db else None)

    blockers_display = blockers_text if blockers_text.lower() not in ("none", "no", "n/a", "nil", "-") else "None (On Schedule ✅)"

    card_text = (
        f"📋 *{shift_title}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏗️ *Project:* {proj_name}\n"
        f"👤 *Reported By:* {worker_name} _({worker_role})_\n"
        f"🕒 *Shift:* {shift_badge}\n"
        f"📊 *Project Progress:* {bar_display}\n"
        f"⏳ *Target Deadline:* {deadline_display}\n"
        f"📅 *Date & Time:* {now_str}\n\n"
        f"✅ *Work Completed:*\n{work_completed}\n\n"
        f"{plan_label}\n{plan_tomorrow}\n\n"
        f"⚠️ *Delays / Blockers:*\n{blockers_display}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    sent_msg_id = None
    if SUPERGROUP_CHAT_ID != 0:
        try:
            if photo_id:
                if len(card_text) <= 1024:
                    sent_msg = await context.bot.send_photo(
                        chat_id=SUPERGROUP_CHAT_ID,
                        photo=photo_id,
                        caption=card_text,
                        parse_mode="Markdown",
                        message_thread_id=topic_id if topic_id != 0 else None
                    )
                    sent_msg_id = sent_msg.message_id
                else:
                    sent_msg = await context.bot.send_message(
                        chat_id=SUPERGROUP_CHAT_ID,
                        text=card_text,
                        parse_mode="Markdown",
                        message_thread_id=topic_id if topic_id != 0 else None
                    )
                    sent_msg_id = sent_msg.message_id
                    await context.bot.send_photo(
                        chat_id=SUPERGROUP_CHAT_ID,
                        photo=photo_id,
                        caption=f"📸 *Site Progress Photo — {proj_name}*",
                        parse_mode="Markdown",
                        message_thread_id=topic_id if topic_id != 0 else None
                    )
            else:
                kwargs = {"chat_id": SUPERGROUP_CHAT_ID, "text": card_text, "parse_mode": "Markdown"}
                if topic_id and topic_id != 0:
                    kwargs["message_thread_id"] = topic_id
                sent_msg = await context.bot.send_message(**kwargs)
                sent_msg_id = sent_msg.message_id
        except Exception as e:
            logger.error(f"Failed to post report to Supergroup topic ({topic_id}): {e}")

    report_id = save_daily_report(
        project_name=proj_name,
        worker_user_id=user.id,
        worker_name=worker_name,
        worker_role=worker_role,
        work_completed=work_completed,
        plan_tomorrow=plan_tomorrow,
        shift_type=shift,
        blockers=blockers_text,
        photo_file_ids=photo_id,
        message_id=sent_msg_id
    )

    # Real-time sync to Google Sheets
    try:
        append_report_live(report_id, now_str, shift, proj_name, worker_name, worker_role, work_completed, plan_tomorrow, blockers_text)
        update_project_live(proj_name, pct_val, proj_db.get("deadline") if proj_db else None, topic_id)
    except Exception as e:
        logger.warning(f"Google Sheets background sync notice: {e}")

    photo_note = " 📸 *(1 Photo Attached)*" if photo_id else ""
    confirm_msg = (
        f"🎉 *{shift_badge} Report Logged!* (Report #{report_id}){photo_note}\n\n"
        f"{card_text}"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(confirm_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(confirm_msg, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Report submission cancelled.")
    else:
        await update.message.reply_text("❌ Report submission cancelled.", parse_mode="Markdown")
    return ConversationHandler.END

def get_report_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("report", report_start),
            CommandHandler("day_report", report_start),
            CommandHandler("night_report", night_report_start),
            MessageHandler(filters.Regex(r"^☀️ Day Report$"), report_start),
            MessageHandler(filters.Regex(r"^🌙 Night Report$"), night_report_start),
            CallbackQueryHandler(report_start, pattern=r"^menu_day_report$"),
            CallbackQueryHandler(night_report_start, pattern=r"^menu_night_report$"),
            CallbackQueryHandler(project_selected_callback, pattern=r"^rep_proj_"),
        ],
        states={
            SELECT_PROJECT: [
                CallbackQueryHandler(project_selected_callback, pattern=r"^rep_proj_"),
                CallbackQueryHandler(cancel_report, pattern=r"^rep_cancel$")
            ],
            SELECT_SHIFT: [
                CallbackQueryHandler(shift_selected_callback, pattern=r"^rep_shift_"),
                CallbackQueryHandler(cancel_report, pattern=r"^rep_cancel$")
            ],
            INPUT_COMPLETED: [MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, receive_completed_work)],
            INPUT_TOMORROW: [MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, receive_tomorrow_plan)],
            INPUT_BLOCKERS: [MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, receive_blockers)],
            INPUT_PHOTO: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_photo),
                CallbackQueryHandler(skip_photo_callback, pattern=r"^(rep_skip_photo|rep_cancel)$")
            ],
            INPUT_PROGRESS: [
                CallbackQueryHandler(receive_progress_and_finish, pattern=r"^(rep_pct_|rep_cancel)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_progress_and_finish)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_report)],
        allow_reentry=True,
    )

