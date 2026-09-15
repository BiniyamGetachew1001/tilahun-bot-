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
from config import SUPERGROUP_CHAT_ID, ADMIN_IDS
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
from locales import t, get_user_lang

logger = logging.getLogger(__name__)

# Conversation states
SELECT_PROJECT, SELECT_SHIFT, INPUT_COMPLETED, INPUT_TOMORROW, INPUT_BLOCKERS, INPUT_PHOTO, INPUT_PROGRESS = range(7)

def build_report_card(
    project_name: str,
    worker_name: str,
    worker_role: str,
    shift: str,
    pct_val: int,
    deadline_display: str,
    now_str: str,
    work_completed: str,
    plan_tomorrow: str,
    blockers_display: str,
    lang: str = "en"
) -> str:
    """Formats a structured report card in the target language (English, Amharic, or Afaan Oromoo)."""
    bar_display = render_progress_bar(pct_val)

    if lang == "am":
        shift_title = "🌙 የማታ ፈረቃ የስራ ሂደት ሪፖርት" if shift == "NIGHT" else "☀️ የቀን ፈረቃ የስራ ሂደት ሪፖርት"
        shift_badge = "🌙 የማታ ፈረቃ" if shift == "NIGHT" else "☀️ የቀን ፈረቃ"
        plan_label = "🎯 የጠዋት ርክክብ / ቀጣይ እቅድ:" if shift == "NIGHT" else "🎯 የነገ እቅድ:"
        blockers_clean = blockers_display if blockers_display.lower() not in ("none", "no", "n/a", "nil", "-", "የለም") else "ምንም የለም (በእቅዱ መሰረት ✅)"

        return (
            f"📋 *{shift_title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *ፕሮጀክት:* {project_name}\n"
            f"👤 *ሪፖርት ያደረገው:* {worker_name} _({worker_role})_\n"
            f"🕒 *ፈረቃ:* {shift_badge}\n"
            f"📊 *የፕሮጀክት እርምጃ:* {bar_display}\n"
            f"⏳ *የማጠናቀቂያ ጊዜ:* {deadline_display}\n"
            f"📅 *ቀንና ሰዓት:* {now_str}\n\n"
            f"✅ *የተሰራው ስራ:*\n{work_completed}\n\n"
            f"{plan_label}\n{plan_tomorrow}\n\n"
            f"⚠️ *ያጋጠሙ ችግሮች / እንቅፋቶች:*\n{blockers_clean}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    elif lang == "om":
        shift_title = "🌙 GABAASA RAAWWII GAREE HALKAN" if shift == "NIGHT" else "☀️ GABAASA RAAWWII GAREE GUYYAA"
        shift_badge = "🌙 Garee Halkan" if shift == "NIGHT" else "☀️ Garee Guyyaa"
        plan_label = "🎯 Dabarsoo / Karoora Garee Dhufuuf:" if shift == "NIGHT" else "🎯 Karoora Boriif:"
        blockers_clean = blockers_display if blockers_display.lower() not in ("none", "no", "n/a", "nil", "-", "hinjiru") else "Hin jiru (Akka karooratti ✅)"

        return (
            f"📋 *{shift_title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *Piroojektii:* {project_name}\n"
            f"👤 *Nama Gabaase:* {worker_name} _({worker_role})_\n"
            f"🕒 *Garee:* {shift_badge}\n"
            f"📊 *Adeemsa Piroojektii:* {bar_display}\n"
            f"⏳ *Yeroo Xumuraa:* {deadline_display}\n"
            f"📅 *Guyyaa fi Sa'aatii:* {now_str}\n\n"
            f"✅ *Hojii Raawwatame:*\n{work_completed}\n\n"
            f"{plan_label}\n{plan_tomorrow}\n\n"
            f"⚠️ *Gufuuwwan / Rakkoolee:*\n{blockers_clean}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        shift_title = "🌙 NIGHT SHIFT PROGRESS REPORT" if shift == "NIGHT" else "☀️ DAY SHIFT PROGRESS REPORT"
        shift_badge = "🌙 Night Shift" if shift == "NIGHT" else "☀️ Day Shift"
        plan_label = "🎯 Handover / Next Shift Plan:" if shift == "NIGHT" else "🎯 Plan for Tomorrow:"
        blockers_clean = blockers_display if blockers_display.lower() not in ("none", "no", "n/a", "nil", "-") else "None (On Schedule ✅)"

        return (
            f"📋 *{shift_title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *Project:* {project_name}\n"
            f"👤 *Reported By:* {worker_name} _({worker_role})_\n"
            f"🕒 *Shift:* {shift_badge}\n"
            f"📊 *Project Progress:* {bar_display}\n"
            f"⏳ *Target Deadline:* {deadline_display}\n"
            f"📅 *Date & Time:* {now_str}\n\n"
            f"✅ *Work Completed:*\n{work_completed}\n\n"
            f"{plan_label}\n{plan_tomorrow}\n\n"
            f"⚠️ *Delays / Blockers:*\n{blockers_clean}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

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
    lang = get_user_lang(user.id)
    is_cb = bool(update.callback_query)
    
    if is_cb:
        await update.callback_query.answer()

    if not is_authorized(user.id):
        worker = get_worker(user.id)
        msg_txt = t("unauthorized_msg", lang) if not worker else t("pending_msg", lang)
        if is_cb:
            await update.callback_query.edit_message_text(msg_txt, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg_txt, parse_mode="Markdown")
        return ConversationHandler.END

    projects = list_active_projects()
    if not projects:
        msg_txt = "❌ No active projects found." if lang == "en" else ("❌ ምንም ንቁ ፕሮጀክት አልተገኘም።" if lang == "am" else "❌ Piroojektiin hojiirra jiru hin argamne.")
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
                shift_label = t("rep_shift_night", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_shift_day", lang)
                time_scope = t("rep_time_tonight", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_time_today", lang)
                prompt_text = t("rep_step1_work", lang, shift_label=shift_label, project=topic_proj["name"], time_scope=time_scope)
                await update.message.reply_text(prompt_text, parse_mode="Markdown")
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
                shift_label = t("rep_shift_night", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_shift_day", lang)
                time_scope = t("rep_time_tonight", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_time_today", lang)
                prompt_text = t("rep_step1_work", lang, shift_label=shift_label, project=matched["name"], time_scope=time_scope)
                await update.message.reply_text(prompt_text, parse_mode="Markdown")
                return INPUT_COMPLETED
            else:
                return await prompt_shift_selection(update, context)

    # Display project selection buttons
    keyboard = []
    for proj in projects:
        pct = proj.get("progress_percent", 0) or 0
        keyboard.append([InlineKeyboardButton(f"🏗️ {proj['name']} ({pct}%)", callback_data=f"rep_proj_{proj['name']}")])
    keyboard.append([InlineKeyboardButton(t("btn_cancel", lang), callback_data="rep_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    header = t("rep_header_night", lang) if context.user_data.get("default_shift") == "NIGHT" else t("rep_header_day", lang)
    prompt_txt = t("rep_select_project", lang, header=header)

    if is_cb:
        await update.callback_query.edit_message_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_PROJECT

async def project_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    data = query.data
    if data == "rep_cancel":
        await query.edit_message_text(t("rep_cancelled", lang))
        return ConversationHandler.END

    project_name = data.replace("rep_proj_", "")
    proj = get_project(project_name)
    context.user_data["report_project"] = project_name
    context.user_data["report_topic_id"] = proj.get("topic_id", 0) if proj else 0

    if context.user_data.get("default_shift"):
        context.user_data["report_shift"] = context.user_data["default_shift"]
        shift_label = t("rep_shift_night", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_shift_day", lang)
        time_scope = t("rep_time_tonight", lang) if context.user_data["report_shift"] == "NIGHT" else t("rep_time_today", lang)
        prompt_text = t("rep_step1_work", lang, shift_label=shift_label, project=project_name, time_scope=time_scope)
        await query.edit_message_text(prompt_text, parse_mode="Markdown")
        return INPUT_COMPLETED

    return await prompt_shift_selection(query, context, is_query=True)

async def prompt_shift_selection(target, context: ContextTypes.DEFAULT_TYPE, is_query: bool = False) -> int:
    user_id = target.from_user.id if is_query else target.effective_user.id
    lang = get_user_lang(user_id)
    project_name = context.user_data.get("report_project", "Project")

    keyboard = [
        [
            InlineKeyboardButton(t("rep_shift_day", lang), callback_data="rep_shift_DAY"),
            InlineKeyboardButton(t("rep_shift_night", lang), callback_data="rep_shift_NIGHT")
        ],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = t("rep_select_shift", lang, project=project_name)

    if is_query:
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECT_SHIFT

async def shift_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    data = query.data
    if data == "rep_cancel":
        await query.edit_message_text(t("rep_cancelled", lang))
        return ConversationHandler.END

    shift = data.replace("rep_shift_", "")
    context.user_data["report_shift"] = shift
    project_name = context.user_data.get("report_project", "Project")
    shift_label = t("rep_shift_night", lang) if shift == "NIGHT" else t("rep_shift_day", lang)
    time_scope = t("rep_time_tonight", lang) if shift == "NIGHT" else t("rep_time_today", lang)
    prompt_text = t("rep_step1_work", lang, shift_label=shift_label, project=project_name, time_scope=time_scope)

    await query.edit_message_text(prompt_text, parse_mode="Markdown")
    return INPUT_COMPLETED

async def receive_completed_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    lang = get_user_lang(user.id)

    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_completed"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        text = msg.text.strip()
        if len(text) < 2:
            prompt_retry = "Please enter a brief description of the work completed:" if lang == "en" else (
                "እባክዎ የተጠናቀቀውን ስራ በአጭሩ ይግለጹ:" if lang == "am" else "Maaloo ibsa gabaabaa hojii xumuramee galchaa:"
            )
            await msg.reply_text(prompt_retry)
            return INPUT_COMPLETED
        context.user_data["report_completed"] = text

    shift = context.user_data.get("report_shift", "DAY")
    plan_prompt = t("rep_plan_handover", lang) if shift == "NIGHT" else t("rep_plan_tomorrow", lang)
    prompt_text = t("rep_step2_plan", lang, time_scope=plan_prompt)

    await update.message.reply_text(prompt_text, parse_mode="Markdown")
    return INPUT_TOMORROW

async def receive_tomorrow_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    lang = get_user_lang(user.id)

    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_tomorrow"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        text = msg.text.strip()
        if len(text) < 2:
            prompt_retry = "Please enter the plan / handover:" if lang == "en" else (
                "እባክዎ እቅድዎን ወይም የርክክብ መረጃውን ያስገቡ:" if lang == "am" else "Maaloo karoora ykn dabarsoo galchaa:"
            )
            await msg.reply_text(prompt_retry)
            return INPUT_TOMORROW
        context.user_data["report_tomorrow"] = text

    shift = context.user_data.get("report_shift", "DAY")
    blocker_prompt = t("rep_blockers_night", lang) if shift == "NIGHT" else t("rep_blockers_day", lang)
    prompt_text = t("rep_step3_blockers", lang, blocker_prompt=blocker_prompt)

    await update.message.reply_text(prompt_text, parse_mode="Markdown")
    return INPUT_BLOCKERS

async def receive_blockers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    lang = get_user_lang(user.id)

    if msg.voice:
        duration = msg.voice.duration
        caption = f" - {msg.caption}" if msg.caption else ""
        context.user_data["report_blockers"] = f"🎙️ [Voice Memo ({duration}s)]{caption}"
    else:
        context.user_data["report_blockers"] = msg.text.strip()

    # Prompt for photo upload (Step 4/5)
    keyboard = [
        [InlineKeyboardButton(t("btn_skip_photo", lang), callback_data="rep_skip_photo")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        t("rep_step4_photo", lang),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return INPUT_PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    lang = get_user_lang(user.id)

    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        context.user_data["report_photo_id"] = photo_file_id
        await msg.reply_text(t("rep_photo_attached", lang), parse_mode="Markdown")
    elif msg.text and msg.text.strip().lower() in ("skip", "no", "none", "pass", "-", "skip photo", "ዝለል", "darbi"):
        context.user_data["report_photo_id"] = None
    else:
        prompt_retry = "Please upload a photo, or send 'skip' to continue without photos." if lang == "en" else (
            "እባክዎ ፎቶ ይላኩ ወይም ያለ ፎቶ ለመቀጠል 'ዝለል' ይበሉ:" if lang == "am" else "Maaloo suuraa ergaa ykn suuraa malee itti fufuuf 'darbi' jedhaa:"
        )
        await msg.reply_text(prompt_retry)
        return INPUT_PHOTO

    return await prompt_progress_step(update, context)

async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    if query.data == "rep_cancel":
        await query.edit_message_text(t("rep_cancelled", lang))
        return ConversationHandler.END

    context.user_data["report_photo_id"] = None
    return await prompt_progress_step(query, context, is_query=True)

async def prompt_progress_step(target, context: ContextTypes.DEFAULT_TYPE, is_query: bool = False) -> int:
    user_id = target.from_user.id if is_query else target.effective_user.id
    lang = get_user_lang(user_id)
    proj_name = context.user_data.get("report_project", "Project")
    proj = get_project(proj_name)
    curr_pct = proj.get("progress_percent", 0) if proj else 0
    curr_bar = render_progress_bar(curr_pct)

    keep_text = f"Keep {curr_pct}%" if lang == "en" else (f"{curr_pct}% ይቆይ" if lang == "am" else f"{curr_pct}% Haa turu")
    keyboard = [
        [
            InlineKeyboardButton("25%", callback_data="rep_pct_25"),
            InlineKeyboardButton("50%", callback_data="rep_pct_50"),
            InlineKeyboardButton("75%", callback_data="rep_pct_75"),
        ],
        [
            InlineKeyboardButton("90%", callback_data="rep_pct_90"),
            InlineKeyboardButton("100% 🎉", callback_data="rep_pct_100"),
            InlineKeyboardButton(keep_text, callback_data=f"rep_pct_{curr_pct}"),
        ],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="rep_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = t("rep_step5_progress", lang, bar=curr_bar)

    if is_query:
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return INPUT_PROGRESS

async def receive_progress_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    proj_name = context.user_data.get("report_project", "General")
    proj_db = get_project(proj_name)
    curr_pct = proj_db.get("progress_percent", 0) if proj_db else 0

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "rep_cancel":
            await query.edit_message_text(t("rep_cancelled", lang))
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
    deadline_display = get_deadline_info(proj_db.get("deadline") if proj_db else None)

    # Build localized card for the worker
    worker_card = build_report_card(
        project_name=proj_name,
        worker_name=worker_name,
        worker_role=worker_role,
        shift=shift,
        pct_val=pct_val,
        deadline_display=deadline_display,
        now_str=now_str,
        work_completed=work_completed,
        plan_tomorrow=plan_tomorrow,
        blockers_display=blockers_text,
        lang=lang
    )

    sent_msg_id = None
    if SUPERGROUP_CHAT_ID != 0:
        default_card = build_report_card(
            project_name=proj_name,
            worker_name=worker_name,
            worker_role=worker_role,
            shift=shift,
            pct_val=pct_val,
            deadline_display=deadline_display,
            now_str=now_str,
            work_completed=work_completed,
            plan_tomorrow=plan_tomorrow,
            blockers_display=blockers_text,
            lang="en"
        )
        try:
            if photo_id:
                if len(default_card) <= 1024:
                    sent_msg = await context.bot.send_photo(
                        chat_id=SUPERGROUP_CHAT_ID,
                        photo=photo_id,
                        caption=default_card,
                        parse_mode="Markdown",
                        message_thread_id=topic_id if topic_id != 0 else None
                    )
                    sent_msg_id = sent_msg.message_id
                else:
                    sent_msg = await context.bot.send_message(
                        chat_id=SUPERGROUP_CHAT_ID,
                        text=default_card,
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
                kwargs = {"chat_id": SUPERGROUP_CHAT_ID, "text": default_card, "parse_mode": "Markdown"}
                if topic_id and topic_id != 0:
                    kwargs["message_thread_id"] = topic_id
                sent_msg = await context.bot.send_message(**kwargs)
        except Exception as e:
            logger.debug(f"Supergroup report notice: {e}")

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

    # Deliver report card directly to all Site Managers / Admins via DM in each admin's language
    for admin_id in ADMIN_IDS:
        if admin_id != user.id:
            try:
                admin_lang = get_user_lang(admin_id)
                admin_card = build_report_card(
                    project_name=proj_name,
                    worker_name=worker_name,
                    worker_role=worker_role,
                    shift=shift,
                    pct_val=pct_val,
                    deadline_display=deadline_display,
                    now_str=now_str,
                    work_completed=work_completed,
                    plan_tomorrow=plan_tomorrow,
                    blockers_display=blockers_text,
                    lang=admin_lang
                )
                if photo_id:
                    if len(admin_card) <= 1024:
                        await context.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=admin_card, parse_mode="Markdown")
                    else:
                        await context.bot.send_message(chat_id=admin_id, text=admin_card, parse_mode="Markdown")
                        await context.bot.send_photo(chat_id=admin_id, photo=photo_id)
                else:
                    await context.bot.send_message(chat_id=admin_id, text=admin_card, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Could not deliver report card to admin {admin_id}: {e}")

    # Real-time sync to Google Sheets
    try:
        append_report_live(report_id, now_str, shift, proj_name, worker_name, worker_role, work_completed, plan_tomorrow, blockers_text)
        update_project_live(proj_name, pct_val, proj_db.get("deadline") if proj_db else None, topic_id)
    except Exception as e:
        logger.warning(f"Google Sheets background sync notice: {e}")

    photo_note = " 📸 *(1 Photo)*" if photo_id else ""
    shift_badge_w = t("rep_shift_night", lang) if shift == "NIGHT" else t("rep_shift_day", lang)
    confirm_msg = t("rep_success_confirm", lang, shift_badge=shift_badge_w, report_id=report_id, photo_note=photo_note, card=worker_card)

    if update.callback_query:
        await update.callback_query.edit_message_text(confirm_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(confirm_msg, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    cancel_text = t("rep_cancelled", lang)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(cancel_text)
    else:
        await update.message.reply_text(cancel_text, parse_mode="Markdown")
    return ConversationHandler.END

def get_report_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("report", report_start),
            CommandHandler("day_report", report_start),
            CommandHandler("night_report", night_report_start),
            MessageHandler(filters.Regex(r"^(☀️ Day Report|☀️ የቀን ሪፖርት|☀️ Gabaasa Guyyaa)$"), report_start),
            MessageHandler(filters.Regex(r"^(🌙 Night Report|🌙 የማታ ሪፖርት|🌙 Gabaasa Halkan)$"), night_report_start),
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
