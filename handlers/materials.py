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
from config import SUPERGROUP_CHAT_ID, MATERIALS_TOPIC_ID, ADMIN_IDS
from database import (
    get_worker,
    list_active_projects,
    get_project,
    get_project_by_topic_id,
    create_material_request,
    get_material_request_by_code,
    update_material_request_status,
    get_setting,
)
from google_sheets import append_material_live, update_material_status_live
from handlers.auth import is_authorized, is_admin
from locales import t, get_user_lang

logger = logging.getLogger(__name__)

# Conversation states
MR_SELECT_PROJECT, MR_INPUT_ITEMS, MR_SELECT_URGENCY = range(3)

def build_mr_card_text(req: dict, lang: str = "en") -> str:
    """Formats a structured card for a Material Request in the target language."""
    if lang == "am":
        status_emoji = {
            "PENDING": "⏳ በግምገማ ላይ",
            "APPROVED": "✅ የጸደቀ",
            "IN_TRANSIT": "🚚 በመጓጓዝ ላይ",
            "REJECTED": "❌ ውድቅ የተደረገ"
        }.get(req.get("status", "PENDING"), req.get("status", "PENDING"))

        urgency_emoji = {
            "NORMAL": "🟢 መደበኛ",
            "PRIORITY": "🟡 አስቸኳይ",
            "URGENT": "🔴 እጅግ አስቸኳይ"
        }.get(req.get("urgency", "NORMAL"), req.get("urgency", "NORMAL"))

        manager_info = f"\n👨‍💼 *የገመገመው:* {req['approved_by_name']}" if req.get("approved_by_name") else ""

        return (
            f"📦 *የዕቃ ማዘዣ #{req['mr_code']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *ፕሮጀክት:* {req['project_name']}\n"
            f"👤 *አቅራቢ:* {req['worker_name']} _({req.get('worker_role', 'ሰራተኛ')})_\n"
            f"📅 *ቀንና ሰዓት:* {req['timestamp']}\n"
            f"🚨 *አስቸኳይነት:* {urgency_emoji}\n"
            f"📊 *ሁኔታ:* *{status_emoji}*{manager_info}\n\n"
            f"📋 *የተጠየቁ ዕቃዎችና መጠን:*\n{req['items_description']}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    elif lang == "om":
        status_emoji = {
            "PENDING": "⏳ Qorannoo Irra",
            "APPROVED": "✅ Mirkanaa'e",
            "IN_TRANSIT": "🚚 Imala Irra",
            "REJECTED": "❌ Hin Eeyyamamne"
        }.get(req.get("status", "PENDING"), req.get("status", "PENDING"))

        urgency_emoji = {
            "NORMAL": "🟢 Idilee",
            "PRIORITY": "🟡 Dursa Ol'aanaa",
            "URGENT": "🔴 Ariifachiisaa Ol'aanaa"
        }.get(req.get("urgency", "NORMAL"), req.get("urgency", "NORMAL"))

        manager_info = f"\n👨‍💼 *Mirkaneessaa:* {req['approved_by_name']}" if req.get("approved_by_name") else ""

        return (
            f"📦 *GAAFFII MEESHAA #{req['mr_code']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *Piroojektii:* {req['project_name']}\n"
            f"👤 *Kan Gaafate:* {req['worker_name']} _({req.get('worker_role', 'Hojjataa')})_\n"
            f"📅 *Guyyaa fi Sa'aatii:* {req['timestamp']}\n"
            f"🚨 *Ariifachiisummaa:* {urgency_emoji}\n"
            f"📊 *Haala:* *{status_emoji}*{manager_info}\n\n"
            f"📋 *Meeshaalee fi Hamma:*\n{req['items_description']}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        status_emoji = {
            "PENDING": "⏳ PENDING REVIEW",
            "APPROVED": "✅ APPROVED",
            "IN_TRANSIT": "🚚 IN TRANSIT",
            "REJECTED": "❌ REJECTED"
        }.get(req.get("status", "PENDING"), req.get("status", "PENDING"))

        urgency_emoji = {
            "NORMAL": "🟢 Normal",
            "PRIORITY": "🟡 High Priority",
            "URGENT": "🔴 Urgent / Critical"
        }.get(req.get("urgency", "NORMAL"), req.get("urgency", "NORMAL"))

        manager_info = f"\n👨‍💼 *Handled By:* {req['approved_by_name']}" if req.get("approved_by_name") else ""

        return (
            f"📦 *MATERIAL REQUISITION #{req['mr_code']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ *Project:* {req['project_name']}\n"
            f"👤 *Requested By:* {req['worker_name']} _({req.get('worker_role', 'Worker')})_\n"
            f"📅 *Date & Time:* {req['timestamp']}\n"
            f"🚨 *Urgency:* {urgency_emoji}\n"
            f"📊 *Status:* *{status_emoji}*{manager_info}\n\n"
            f"📋 *Items & Quantities Needed:*\n{req['items_description']}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

def build_mr_action_keyboard(mr_code: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Builds interactive management buttons for the requisition card in the recipient's language."""
    btn_appr = t("mr_btn_approve", lang)
    btn_tran = t("mr_btn_transit", lang)
    btn_rej = t("mr_btn_reject", lang)
    keyboard = [
        [
            InlineKeyboardButton(btn_appr, callback_data=f"mraction_APPROVED_{mr_code}"),
            InlineKeyboardButton(btn_tran, callback_data=f"mraction_IN_TRANSIT_{mr_code}"),
            InlineKeyboardButton(btn_rej, callback_data=f"mraction_REJECTED_{mr_code}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Requisition Wizard ---

async def mr_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /request_material, '📦 Request Material' button, and 'menu_materials' callback."""
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
            context.user_data["mr_project"] = topic_proj["name"]
            context.user_data["mr_topic_id"] = topic_proj.get("topic_id", thread_id)
            prompt_text = t("mr_step1_desc", lang, project=topic_proj["name"])
            await update.message.reply_text(prompt_text, parse_mode="Markdown")
            return MR_INPUT_ITEMS

    # Check if project was provided in command arguments e.g. /request_material Project Alpha
    if context.args:
        arg_project = " ".join(context.args).strip()
        matched = next((p for p in projects if p["name"].lower() == arg_project.lower()), None)
        if matched:
            context.user_data["mr_project"] = matched["name"]
            context.user_data["mr_topic_id"] = matched.get("topic_id", 0)
            prompt_text = t("mr_step1_desc", lang, project=matched["name"])
            await update.message.reply_text(prompt_text, parse_mode="Markdown")
            return MR_INPUT_ITEMS

    keyboard = []
    for proj in projects:
        keyboard.append([InlineKeyboardButton(f"🏗️ {proj['name']}", callback_data=f"mr_proj_{proj['name']}")])
    keyboard.append([InlineKeyboardButton(t("btn_cancel", lang), callback_data="mr_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    prompt_txt = t("mr_select_project", lang)
    if is_cb:
        await update.callback_query.edit_message_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(prompt_txt, reply_markup=reply_markup, parse_mode="Markdown")
    return MR_SELECT_PROJECT

async def mr_project_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    data = query.data
    if data == "mr_cancel":
        cancel_txt = "❌ Requisition cancelled." if lang == "en" else ("❌ የዕቃ ማዘዣው ተሰርዟል።" if lang == "am" else "❌ Gaaffiin meeshaa haqameera.")
        await query.edit_message_text(cancel_txt)
        return ConversationHandler.END

    project_name = data.replace("mr_proj_", "")
    proj = get_project(project_name)
    context.user_data["mr_project"] = project_name
    context.user_data["mr_topic_id"] = proj.get("topic_id", 0) if proj else 0

    prompt_text = t("mr_step1_desc", lang, project=project_name)
    await query.edit_message_text(prompt_text, parse_mode="Markdown")
    return MR_INPUT_ITEMS

async def mr_receive_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    items = update.message.text.strip()

    if len(items) < 3:
        retry_prompt = "Please list the items and quantities needed:" if lang == "en" else (
            "እባክዎ የሚያስፈልጉትን ዕቃዎችና መጠናቸውን ይዘርዝሩ:" if lang == "am" else "Maaloo meeshaalee fi hamma barbaadaman tarreessaa:"
        )
        await update.message.reply_text(retry_prompt)
        return MR_INPUT_ITEMS

    context.user_data["mr_items"] = items

    keyboard = [
        [InlineKeyboardButton(t("urgency_normal", lang), callback_data="mr_urg_NORMAL")],
        [InlineKeyboardButton(t("urgency_urgent", lang), callback_data="mr_urg_PRIORITY")],
        [InlineKeyboardButton(t("urgency_emergency", lang), callback_data="mr_urg_URGENT")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="mr_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        t("mr_step2_urgency", lang),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MR_SELECT_URGENCY

async def mr_urgency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = get_user_lang(user.id)
    data = query.data
    if data == "mr_cancel":
        cancel_txt = "❌ Requisition cancelled." if lang == "en" else ("❌ የዕቃ ማዘዣው ተሰርዟል።" if lang == "am" else "❌ Gaaffiin meeshaa haqameera.")
        await query.edit_message_text(cancel_txt)
        return ConversationHandler.END

    urgency = data.replace("mr_urg_", "")
    worker = get_worker(user.id)
    worker_name = worker["full_name"] if worker else user.full_name
    worker_role = worker["role"] if worker else "Worker"

    project_name = context.user_data.get("mr_project", "General")
    items_desc = context.user_data.get("mr_items", "N/A")

    # Create Requisition Record in SQLite
    req = create_material_request(
        project_name=project_name,
        worker_user_id=user.id,
        worker_name=worker_name,
        worker_role=worker_role,
        items_description=items_desc,
        urgency=urgency
    )

    # Deliver MR Card directly to each Manager in their preferred language with Action Buttons
    for admin_id in ADMIN_IDS:
        try:
            admin_lang = get_user_lang(admin_id)
            admin_card = build_mr_card_text(req, lang=admin_lang)
            admin_action_kb = build_mr_action_keyboard(req["mr_code"], lang=admin_lang)
            admin_alert_title = "📦 *New Material Requisition Submitted!*" if admin_lang == "en" else (
                "📦 *አዲስ የዕቃ ማዘዣ ጥያቄ ቀርቧል!*" if admin_lang == "am" else "📦 *Gaaffiin Meeshaa Haaraan Dhiyaateera!*"
            )
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"{admin_alert_title}\n\n{admin_card}",
                reply_markup=admin_action_kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not deliver MR card to admin {admin_id}: {e}")

    # Optional legacy Supergroup posting
    if SUPERGROUP_CHAT_ID != 0:
        db_mat_topic = int(get_setting("materials_topic_id", "0") or 0)
        target_topic = MATERIALS_TOPIC_ID or db_mat_topic or context.user_data.get("mr_topic_id", 0)
        try:
            sg_card = build_mr_card_text(req, lang="en")
            sg_kb = build_mr_action_keyboard(req["mr_code"], lang="en")
            kwargs = {
                "chat_id": SUPERGROUP_CHAT_ID,
                "text": sg_card,
                "reply_markup": sg_kb,
                "parse_mode": "Markdown"
            }
            if target_topic and target_topic != 0:
                kwargs["message_thread_id"] = target_topic
            await context.bot.send_message(**kwargs)
        except Exception as e:
            logger.debug(f"Supergroup MR notice: {e}")

    # Real-time sync to Google Sheets
    try:
        append_material_live(
            mr_code=req["mr_code"],
            timestamp=req["timestamp"],
            project=req["project_name"],
            worker_name=req["worker_name"],
            role=req.get("worker_role", "Worker"),
            items=req["items_description"],
            urgency=req["urgency"],
            status=req["status"]
        )
    except Exception as e:
        logger.warning(f"Google Sheets sync notice (materials): {e}")

    worker_card = build_mr_card_text(req, lang=lang)
    confirm_text = t("mr_success_confirm", lang, mr_code=req["mr_code"], card=worker_card)

    await query.edit_message_text(confirm_text, parse_mode="Markdown")

    context.user_data.pop("mr_project", None)
    context.user_data.pop("mr_topic_id", None)
    context.user_data.pop("mr_items", None)

    return ConversationHandler.END

async def mr_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    cancel_txt = "❌ Requisition cancelled." if lang == "en" else ("❌ የዕቃ ማዘዣው ተሰርዟል።" if lang == "am" else "❌ Gaaffiin meeshaa haqameera.")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(cancel_txt)
    else:
        await update.message.reply_text(cancel_txt)
    return ConversationHandler.END

# --- Approval Action Handlers (Button clicks & text commands) ---

async def handle_mr_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Approve / In-Transit / Reject buttons on MR cards."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    admin_lang = get_user_lang(user.id)

    if not is_admin(user.id):
        err_msg = "⛔ Only managers/admins can approve or update requests." if admin_lang == "en" else (
            "⛔ ጥያቄዎችን ማጽደቅ የሚችሉት አስተዳዳሪዎች ብቻ ናቸው።" if admin_lang == "am" else "⛔ Gaggeessitoota qofatu eeyyamuu danda'a."
        )
        await query.answer(err_msg, show_alert=True)
        return

    parts = query.data.split("_")
    if len(parts) < 3:
        return

    status = parts[1]
    mr_code = "_".join(parts[2:])

    worker_admin = get_worker(user.id)
    admin_name = worker_admin["full_name"] if worker_admin else user.first_name

    updated_req = update_material_request_status(
        mr_code=mr_code,
        new_status=status,
        approved_by_name=admin_name,
        approved_by_id=user.id
    )

    if not updated_req:
        await query.answer("❌ Request not found.", show_alert=True)
        return

    # Real-time sync status update to Google Sheets
    try:
        update_material_status_live(mr_code, status, admin_name)
    except Exception as e:
        logger.warning(f"Google Sheets sync notice (materials status): {e}")

    new_card_text = build_mr_card_text(updated_req, lang=admin_lang)
    new_keyboard = build_mr_action_keyboard(mr_code, lang=admin_lang)

    try:
        await query.edit_message_text(
            text=new_card_text,
            reply_markup=new_keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.debug(f"Card message already updated: {e}")

    # Notify the requesting worker in their chosen language
    worker_uid = updated_req.get("worker_user_id")
    if worker_uid:
        try:
            worker_lang = get_user_lang(worker_uid)
            status_text = {
                "en": {"APPROVED": "✅ Approved", "IN_TRANSIT": "🚚 In Transit", "REJECTED": "❌ Rejected"},
                "am": {"APPROVED": "✅ ጸድቋል", "IN_TRANSIT": "🚚 በመጓጓዝ ላይ ነው", "REJECTED": "❌ ውድቅ ተደርጓል"},
                "om": {"APPROVED": "✅ Mirkanaa'eera", "IN_TRANSIT": "🚚 Imala irra jira", "REJECTED": "❌ Hin Eeyyamamne"}
            }.get(worker_lang, {}).get(status, status)

            notice_msg = t("mr_status_update_worker", worker_lang, mr_code=mr_code, status=status_text, admin=admin_name)
            await context.bot.send_message(
                chat_id=worker_uid,
                text=notice_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not notify worker {worker_uid}: {e}")

# Text command shortcuts: /approve MR-014 and /reject MR-014
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manager command: /approve MR-014"""
    user = update.effective_user
    lang = get_user_lang(user.id)
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can approve requests.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/approve <MR-ID>` (e.g. `/approve MR-014` or `/approve 14`)", parse_mode="Markdown")
        return

    mr_input = context.args[0]
    worker_admin = get_worker(user.id)
    admin_name = worker_admin["full_name"] if worker_admin else user.first_name

    updated = update_material_request_status(
        mr_code=mr_input,
        new_status="APPROVED",
        approved_by_name=admin_name,
        approved_by_id=user.id
    )

    if not updated:
        await update.message.reply_text(f"❌ Requisition `{mr_input}` not found in database.", parse_mode="Markdown")
        return

    await update.message.reply_text(
        f"✅ *Requisition #{updated['mr_code']} Approved!*\n\n"
        f"🏗️ Project: {updated['project_name']}\n"
        f"👤 Worker: {updated['worker_name']}\n"
        f"📦 Items: {updated['items_description']}",
        parse_mode="Markdown"
    )

async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manager command: /reject MR-014"""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can reject requests.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/reject <MR-ID>` (e.g. `/reject MR-014`)", parse_mode="Markdown")
        return

    mr_input = context.args[0]
    worker_admin = get_worker(user.id)
    admin_name = worker_admin["full_name"] if worker_admin else user.first_name

    updated = update_material_request_status(
        mr_code=mr_input,
        new_status="REJECTED",
        approved_by_name=admin_name,
        approved_by_id=user.id
    )

    if not updated:
        await update.message.reply_text(f"❌ Requisition `{mr_input}` not found in database.", parse_mode="Markdown")
        return

    await update.message.reply_text(
        f"❌ *Requisition #{updated['mr_code']} Rejected.*\n\n"
        f"🏗️ Project: {updated['project_name']}\n"
        f"👤 Worker: {updated['worker_name']}",
        parse_mode="Markdown"
    )

def get_material_request_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("request_material", mr_start),
            CommandHandler("materials", mr_start),
            MessageHandler(filters.Regex(r"^(📦 Request Material|📦 ዕቃ ማዘዣ|📦 Gaaffii Meeshaa)$"), mr_start),
            CallbackQueryHandler(mr_start, pattern=r"^menu_materials$"),
            CallbackQueryHandler(mr_project_selected, pattern=r"^mr_proj_"),
        ],
        states={
            MR_SELECT_PROJECT: [
                CallbackQueryHandler(mr_project_selected, pattern=r"^mr_proj_"),
                CallbackQueryHandler(mr_cancel, pattern=r"^mr_cancel$")
            ],
            MR_INPUT_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, mr_receive_items)],
            MR_SELECT_URGENCY: [
                CallbackQueryHandler(mr_urgency_selected, pattern=r"^mr_urg_"),
                CallbackQueryHandler(mr_cancel, pattern=r"^mr_cancel$")
            ],
        },
        fallbacks=[CommandHandler("cancel", mr_cancel)],
        allow_reentry=True,
    )
