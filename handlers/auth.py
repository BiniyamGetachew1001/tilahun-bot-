import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import ADMIN_IDS, REQUIRE_APPROVAL
from database import (
    get_worker,
    register_worker,
    set_worker_approval,
    list_all_workers,
    get_worker_lang,
    set_worker_lang,
)
from locales import t, get_user_lang, LANGUAGES

logger = logging.getLogger(__name__)

# Conversation states for Onboarding
ASK_LANG, ASK_NAME, ASK_ROLE = range(3)

def is_authorized(user_id: int) -> bool:
    """Check if the user is registered and approved (or is an admin)."""
    if user_id in ADMIN_IDS:
        return True
    worker = get_worker(user_id)
    if not worker:
        return False
    if not REQUIRE_APPROVAL:
        return True
    return bool(worker.get("is_approved", 0))

def is_admin(user_id: int) -> bool:
    """Check if the user is in ADMIN_IDS or flagged admin in DB."""
    if user_id in ADMIN_IDS:
        return True
    worker = get_worker(user_id)
    return bool(worker and worker.get("is_admin", 0))

def get_main_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """
    Returns the persistent bottom Reply Keyboard customized for the user role & language.
    """
    lang = get_user_lang(user_id)
    btn_day = t("btn_day_report", lang)
    btn_night = t("btn_night_report", lang)
    btn_mr = t("btn_request_material", lang)
    btn_status = t("btn_project_status", lang)
    btn_projects = t("btn_projects", lang)
    btn_menu = t("btn_main_menu", lang)
    btn_lang = t("btn_language", lang)
    btn_admin = t("btn_admin_panel", lang)
    btn_sync = t("btn_sync_sheets", lang)
    btn_export = t("btn_export_excel", lang)

    if is_admin(user_id):
        keyboard = [
            [KeyboardButton(btn_day), KeyboardButton(btn_night)],
            [KeyboardButton(btn_mr), KeyboardButton(btn_status)],
            [KeyboardButton(btn_admin), KeyboardButton(btn_projects)],
            [KeyboardButton(btn_sync), KeyboardButton(btn_export)],
            [KeyboardButton(btn_lang), KeyboardButton(btn_menu)],
        ]
    else:
        keyboard = [
            [KeyboardButton(btn_day), KeyboardButton(btn_night)],
            [KeyboardButton(btn_mr), KeyboardButton(btn_status)],
            [KeyboardButton(btn_projects), KeyboardButton(btn_lang)],
            [KeyboardButton(btn_menu)],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_language_picker_keyboard(prefix: str = "lang_") -> InlineKeyboardMarkup:
    """Builds inline language selector buttons."""
    keyboard = [
        [
            InlineKeyboardButton("English", callback_data=f"{prefix}en"),
            InlineKeyboardButton("አማርኛ", callback_data=f"{prefix}am"),
            InlineKeyboardButton("Afaan Oromoo", callback_data=f"{prefix}om"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_main_inline_menu(user_id: int) -> InlineKeyboardMarkup:
    """Builds an interactive inline dashboard hub for /start and /menu."""
    lang = get_user_lang(user_id)
    if is_admin(user_id):
        keyboard = [
            [
                InlineKeyboardButton(t("btn_day_report", lang), callback_data="menu_day_report"),
                InlineKeyboardButton(t("btn_night_report", lang), callback_data="menu_night_report"),
            ],
            [
                InlineKeyboardButton(t("btn_request_material", lang), callback_data="menu_materials"),
                InlineKeyboardButton(t("btn_project_status", lang), callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton(t("btn_projects", lang), callback_data="menu_projects"),
                InlineKeyboardButton("📈 Update Progress", callback_data="menu_progress"),
            ],
            [
                InlineKeyboardButton(t("btn_admin_panel", lang), callback_data="menu_admin"),
                InlineKeyboardButton(t("btn_export_excel", lang), callback_data="menu_export"),
            ],
            [
                InlineKeyboardButton(t("btn_sync_sheets", lang), callback_data="menu_sync"),
                InlineKeyboardButton("👥 Team Roster", callback_data="menu_workers"),
            ],
            [
                InlineKeyboardButton("🌐 Switch Language / ቋንቋ / Afaan", callback_data="menu_language"),
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(t("btn_day_report", lang), callback_data="menu_day_report"),
                InlineKeyboardButton(t("btn_night_report", lang), callback_data="menu_night_report"),
            ],
            [
                InlineKeyboardButton(t("btn_request_material", lang), callback_data="menu_materials"),
                InlineKeyboardButton(t("btn_project_status", lang), callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton(t("btn_projects", lang), callback_data="menu_projects"),
                InlineKeyboardButton(t("btn_my_profile", lang), callback_data="menu_profile"),
            ],
            [
                InlineKeyboardButton("🌐 Switch Language / ቋንቋ / Afaan", callback_data="menu_language"),
            ]
        ]
    return InlineKeyboardMarkup(keyboard)

def build_role_picker_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Builds quick-select role buttons during onboarding in target language."""
    keyboard = [
        [
            InlineKeyboardButton(f"👷 {t('role_foreman', lang)}", callback_data=f"role_{t('role_foreman', 'en')}"),
            InlineKeyboardButton(f"🏗️ {t('role_engineer', lang)}", callback_data=f"role_{t('role_engineer', 'en')}"),
        ],
        [
            InlineKeyboardButton(f"📋 {t('role_pm', lang)}", callback_data=f"role_{t('role_pm', 'en')}"),
            InlineKeyboardButton(f"🛡️ {t('role_safety', lang)}", callback_data=f"role_{t('role_safety', 'en')}"),
        ],
        [
            InlineKeyboardButton(f"📐 {t('role_surveyor', lang)}", callback_data=f"role_{t('role_surveyor', 'en')}"),
            InlineKeyboardButton(f"🔨 {t('role_subcontractor', lang)}", callback_data=f"role_{t('role_subcontractor', 'en')}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /language or /lang — opens language selection menu."""
    user = update.effective_user
    current_lang = get_user_lang(user.id)
    text = t("choose_language", current_lang)
    reply_markup = build_language_picker_keyboard(prefix="setlang_")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def language_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles language selection button click from /language or menu."""
    query = update.callback_query
    await query.answer()

    data = query.data
    lang_code = data.replace("setlang_", "").replace("lang_", "")
    user_id = query.from_user.id

    if lang_code in LANGUAGES:
        set_worker_lang(user_id, lang_code)
        confirm_text = t("language_updated", lang_code)
        reply_kb = get_main_reply_keyboard(user_id)
        inline_menu = build_main_inline_menu(user_id)

        await query.edit_message_text(confirm_text, parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=user_id,
            text="📱 " + t("btn_main_menu", lang_code),
            reply_markup=reply_kb
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /start."""
    user = update.effective_user
    worker = get_worker(user.id)

    if worker:
        lang = worker.get("language") or "en"
        if worker.get("is_approved") or user.id in ADMIN_IDS or not REQUIRE_APPROVAL:
            role_badge = f" ({worker['role']})" if worker.get("role") else ""
            admin_note = "\n⭐ *Manager / Admin*" if is_admin(user.id) else ""
            reply_keyboard = get_main_reply_keyboard(user.id)
            inline_menu = build_main_inline_menu(user.id)

            await update.message.reply_text(
                f"👋 *Welcome back, {worker['full_name']}*{role_badge}!{admin_note}\n\n"
                f"📱 {t('btn_main_menu', lang)}:",
                reply_markup=reply_keyboard,
                parse_mode="Markdown"
            )
            await update.message.reply_text(
                "📱 *Actions Hub:*",
                reply_markup=inline_menu,
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                t("pending_msg", lang),
                parse_mode="Markdown"
            )
            return ConversationHandler.END

    # New user onboarding - Step 1: Language selection
    context.user_data["onboarding_lang"] = "en"
    reply_markup = build_language_picker_keyboard(prefix="oblang_")

    await update.message.reply_text(
        "🌐 *Welcome! Please choose your language:*\n"
        "ቋንቋ ይምረጡ | Afaan filadhaa:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ASK_LANG

async def receive_onboarding_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles initial language selection during onboarding."""
    query = update.callback_query
    await query.answer()

    data = query.data
    lang_code = data.replace("oblang_", "")
    if lang_code not in LANGUAGES:
        lang_code = "en"

    context.user_data["onboarding_lang"] = lang_code
    welcome_text = t("onboarding_welcome", lang_code)

    await query.edit_message_text(welcome_text, parse_mode="Markdown")
    return ASK_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles name input during onboarding."""
    full_name = update.message.text.strip()
    lang = context.user_data.get("onboarding_lang", "en")

    if len(full_name) < 2:
        await update.message.reply_text("Please enter a valid full name:")
        return ASK_NAME

    context.user_data["onboarding_name"] = full_name
    prompt_text = t("onboarding_select_role", lang, name=full_name)

    await update.message.reply_text(
        prompt_text,
        reply_markup=build_role_picker_keyboard(lang),
        parse_mode="Markdown"
    )
    return ASK_ROLE

async def receive_role_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles manual text input for role during onboarding."""
    role = update.message.text.strip()
    return await _complete_registration(update, context, role, is_query=False)

async def receive_role_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles quick-select button click for role during onboarding."""
    query = update.callback_query
    await query.answer()
    role = query.data.replace("role_", "")
    return await _complete_registration(query, context, role, is_query=True)

async def _complete_registration(target, context: ContextTypes.DEFAULT_TYPE, role: str, is_query: bool = False) -> int:
    full_name = context.user_data.get("onboarding_name", "Worker")
    lang = context.user_data.get("onboarding_lang", "en")
    user_id = target.from_user.id if is_query else target.effective_user.id
    user_obj = target.from_user if is_query else target.effective_user
    is_user_adm = user_id in ADMIN_IDS

    # Auto-approve admins or if approval is not required
    auto_approve = is_user_adm or (not REQUIRE_APPROVAL)
    register_worker(
        user_id=user_id,
        full_name=full_name,
        role=role,
        is_approved=auto_approve,
        is_admin=is_user_adm,
        language=lang
    )

    reply_keyboard = get_main_reply_keyboard(user_id)
    inline_menu = build_main_inline_menu(user_id)

    if auto_approve:
        welcome_text = t("onboarding_approved_instant", lang, name=full_name, role=role)
        if is_query:
            await target.edit_message_text(welcome_text, parse_mode="Markdown")
            await context.bot.send_message(
                chat_id=user_id,
                text="📱 *Quick Actions Hub:*",
                reply_markup=inline_menu,
            )
            await context.bot.send_message(
                chat_id=user_id,
                text="⚡ *Navigation buttons active on keyboard.*",
                reply_markup=reply_keyboard,
                parse_mode="Markdown"
            )
        else:
            await target.message.reply_text(welcome_text, reply_markup=reply_keyboard, parse_mode="Markdown")
            await target.message.reply_text("📱 *Quick Actions Hub:*", reply_markup=inline_menu, parse_mode="Markdown")
    else:
        pending_text = t("onboarding_pending_approval", lang, name=full_name, role=role)
        if is_query:
            await target.edit_message_text(pending_text, parse_mode="Markdown")
        else:
            await target.message.reply_text(pending_text, parse_mode="Markdown")

        # Notify site admins / managers with inline approval buttons
        approval_kb = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_worker_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_worker_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(approval_kb)

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🔔 *New Worker Registration Request:*\n\n"
                        f"👤 *Name:* {full_name}\n"
                        f"💼 *Role:* {role}\n"
                        f"🌐 *Language:* {LANGUAGES.get(lang, {}).get('name', 'English')}\n"
                        f"🆔 *Telegram ID:* `{user_id}`\n"
                        f"Username: @{user_obj.username or 'N/A'}"
                    ),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")

    context.user_data.pop("onboarding_name", None)
    context.user_data.pop("onboarding_lang", None)
    return ConversationHandler.END

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /menu — opens the interactive Quick Actions Hub."""
    user = update.effective_user
    lang = get_user_lang(user.id)
    reply_kb = get_main_reply_keyboard(user.id)
    inline_kb = build_main_inline_menu(user.id)

    await update.message.reply_text(
        f"🎛️ *{t('btn_main_menu', lang)}*\n\n"
        "Choose an action using the buttons below:",
        reply_markup=reply_kb,
        parse_mode="Markdown"
    )
    await update.message.reply_text(
        "📱 *Interactive Quick Actions:*",
        reply_markup=inline_kb,
        parse_mode="Markdown"
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /profile — shows worker identity, status, and permissions."""
    user = update.effective_user
    worker = get_worker(user.id)
    lang = get_user_lang(user.id)

    if not worker:
        await update.message.reply_text(t("unauthorized_msg", lang), parse_mode="Markdown")
        return

    admin_tag = " ⭐ (Site Manager)" if is_admin(user.id) else ""
    status_tag = "✅ Approved / Active" if worker.get("is_approved") else "⏳ Pending Approval"
    lang_display = LANGUAGES.get(worker.get("language", "en"), {}).get("name", "English")

    text = (
        f"👤 *WORKER PROFILE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 *Name:* {worker['full_name']}{admin_tag}\n"
        f"💼 *Role:* {worker['role']}\n"
        f"🌐 *Language:* {lang_display}\n"
        f"🆔 *User ID:* `{worker['user_id']}`\n"
        f"📊 *Status:* {status_tag}\n"
        f"📅 *Registered:* {worker.get('registered_at', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 _To change language, type /language or tap 🌐 Language button._"
    )
    reply_kb = get_main_reply_keyboard(user.id)
    await update.message.reply_text(text, reply_markup=reply_kb, parse_mode="Markdown")

async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Registration cancelled. Type `/start` to begin again.", parse_mode="Markdown")
    return ConversationHandler.END

async def handle_worker_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicks Approve or Reject on worker registration."""
    query = update.callback_query
    await query.answer()

    admin_user = query.from_user
    if not is_admin(admin_user.id):
        await query.edit_message_text("⛔ You are not authorized to perform this action.")
        return

    data = query.data
    if data.startswith("approve_worker_"):
        target_uid = int(data.replace("approve_worker_", ""))
        set_worker_approval(target_uid, True)
        worker = get_worker(target_uid)
        w_name = worker["full_name"] if worker else str(target_uid)
        w_lang = worker.get("language", "en") if worker else "en"
        
        await query.edit_message_text(
            f"✅ *Worker Approved*\n\n"
            f"👤 Worker: *{w_name}* (`{target_uid}`)\n"
            f"Approved by: {admin_user.first_name}",
            parse_mode="Markdown"
        )
        # Notify the worker in their language
        try:
            worker_reply_kb = get_main_reply_keyboard(target_uid)
            approved_msg = "🎉 *Your account has been approved by Site Management!*" if w_lang == "en" else (
                "🎉 *የመለያ ምዝገባ ጥያቄዎ በአስተዳዳሪ ጸድቋል!*" if w_lang == "am" else "🎉 *Herregni keessan gaggeessaadhaan mirkanaa'eera!*"
            )
            await context.bot.send_message(
                chat_id=target_uid,
                text=approved_msg,
                reply_markup=worker_reply_kb,
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=target_uid,
                text="📱 *Quick Actions Hub:*",
                reply_markup=build_main_inline_menu(target_uid),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not send approval message to worker {target_uid}: {e}")

    elif data.startswith("reject_worker_"):
        target_uid = int(data.replace("reject_worker_", ""))
        set_worker_approval(target_uid, False)
        worker = get_worker(target_uid)
        w_name = worker["full_name"] if worker else str(target_uid)
        
        await query.edit_message_text(
            f"❌ *Worker Rejected*\n\n"
            f"👤 Worker: *{w_name}* (`{target_uid}`)\n"
            f"Handled by: {admin_user.first_name}",
            parse_mode="Markdown"
        )

def get_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            ASK_LANG: [
                CallbackQueryHandler(receive_onboarding_lang, pattern=r"^oblang_"),
            ],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_ROLE: [
                CallbackQueryHandler(receive_role_button, pattern=r"^role_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_role_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        allow_reentry=True,
    )
