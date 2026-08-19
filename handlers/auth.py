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
)

logger = logging.getLogger(__name__)

# Conversation states for Onboarding
ASK_NAME, ASK_ROLE = range(2)

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
    Returns the persistent bottom Reply Keyboard customized for the user role.
    Workers get reporting & request shortcuts; Admins also get management buttons.
    """
    if is_admin(user_id):
        keyboard = [
            [KeyboardButton("☀️ Day Report"), KeyboardButton("🌙 Night Report")],
            [KeyboardButton("📦 Request Material"), KeyboardButton("📊 Project Status")],
            [KeyboardButton("🎛️ Manager Panel"), KeyboardButton("🏗️ Projects")],
            [KeyboardButton("🔄 Sync Sheets"), KeyboardButton("📥 Export Excel")],
        ]
    else:
        keyboard = [
            [KeyboardButton("☀️ Day Report"), KeyboardButton("🌙 Night Report")],
            [KeyboardButton("📦 Request Material"), KeyboardButton("📊 Project Status")],
            [KeyboardButton("🏗️ Projects"), KeyboardButton("📱 Main Menu")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_main_inline_menu(user_id: int) -> InlineKeyboardMarkup:
    """Builds an interactive inline dashboard hub for /start and /menu."""
    if is_admin(user_id):
        keyboard = [
            [
                InlineKeyboardButton("☀️ Day Report", callback_data="menu_day_report"),
                InlineKeyboardButton("🌙 Night Report", callback_data="menu_night_report"),
            ],
            [
                InlineKeyboardButton("📦 Request Material", callback_data="menu_materials"),
                InlineKeyboardButton("📊 Project Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton("🏗️ All Projects", callback_data="menu_projects"),
                InlineKeyboardButton("📈 Update Progress", callback_data="menu_progress"),
            ],
            [
                InlineKeyboardButton("🎛️ Manager Panel", callback_data="menu_admin"),
                InlineKeyboardButton("📥 Export Excel", callback_data="menu_export"),
            ],
            [
                InlineKeyboardButton("🔄 Sync Google Sheets", callback_data="menu_sync"),
                InlineKeyboardButton("👥 Team Roster", callback_data="menu_workers"),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("☀️ Day Report", callback_data="menu_day_report"),
                InlineKeyboardButton("🌙 Night Report", callback_data="menu_night_report"),
            ],
            [
                InlineKeyboardButton("📦 Request Material", callback_data="menu_materials"),
                InlineKeyboardButton("📊 Project Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton("🏗️ View Projects", callback_data="menu_projects"),
                InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)

def build_role_picker_keyboard() -> InlineKeyboardMarkup:
    """Builds quick-select role buttons during onboarding."""
    keyboard = [
        [
            InlineKeyboardButton("👷 Site Foreman", callback_data="role_Site Foreman"),
            InlineKeyboardButton("⚡ Lead Electrician", callback_data="role_Lead Electrician"),
        ],
        [
            InlineKeyboardButton("🏗️ Structural Engineer", callback_data="role_Structural Engineer"),
            InlineKeyboardButton("📋 Site Supervisor", callback_data="role_Site Supervisor"),
        ],
        [
            InlineKeyboardButton("📦 Procurement Officer", callback_data="role_Procurement Officer"),
            InlineKeyboardButton("🔨 Mason / Worker", callback_data="role_Mason/Worker"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /start."""
    user = update.effective_user
    worker = get_worker(user.id)

    if worker:
        if worker.get("is_approved") or user.id in ADMIN_IDS or not REQUIRE_APPROVAL:
            role_badge = f" ({worker['role']})" if worker.get("role") else ""
            admin_note = "\n⭐ *You have Manager/Admin access.*" if is_admin(user.id) else ""
            reply_keyboard = get_main_reply_keyboard(user.id)
            inline_menu = build_main_inline_menu(user.id)

            await update.message.reply_text(
                f"👋 Welcome back, *{worker['full_name']}*{role_badge}!{admin_note}\n\n"
                f"Use the buttons on your screen or the menu below to get started immediately:",
                reply_markup=reply_keyboard,
                parse_mode="Markdown"
            )
            await update.message.reply_text(
                "📱 *Quick Actions Hub:*",
                reply_markup=inline_menu,
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"⏳ Hello *{worker['full_name']}*, your registration is pending approval by a Site Manager.\n"
                f"You will receive a notification once approved.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

    # New user onboarding
    await update.message.reply_text(
        "👋 *Welcome to the Site & Project Management Bot!*\n\n"
        "To get started, please enter your *Full Name* (e.g., Abebe Bikila):",
        parse_mode="Markdown"
    )
    return ASK_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles name input during onboarding."""
    full_name = update.message.text.strip()
    if len(full_name) < 2:
        await update.message.reply_text("Please enter a valid full name:")
        return ASK_NAME

    context.user_data["onboarding_name"] = full_name
    await update.message.reply_text(
        f"Thank you, *{full_name}*.\n\n"
        "Now, please select your *Role on site* using the buttons below, or type your custom role in chat:",
        reply_markup=build_role_picker_keyboard(),
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
        is_admin=is_user_adm
    )

    reply_keyboard = get_main_reply_keyboard(user_id)
    inline_menu = build_main_inline_menu(user_id)

    if auto_approve:
        welcome_text = (
            f"✅ *Registration Complete!*\n\n"
            f"👤 *Name:* {full_name}\n"
            f"💼 *Role:* {role}\n"
            f"🆔 *User ID:* `{user_id}`\n\n"
            f"You can now use the on-screen buttons below to submit reports and manage site operations!"
        )
        if is_query:
            await target.edit_message_text(welcome_text, parse_mode="Markdown")
            await context.bot.send_message(
                chat_id=user_id,
                text="📱 *Quick Actions Hub:*",
                reply_markup=inline_menu,
            )
            # Send message with persistent reply keyboard
            await context.bot.send_message(
                chat_id=user_id,
                text="⚡ *Navigation buttons activated on your keyboard.*",
                reply_markup=reply_keyboard,
                parse_mode="Markdown"
            )
        else:
            await target.message.reply_text(welcome_text, reply_markup=reply_keyboard, parse_mode="Markdown")
            await target.message.reply_text("📱 *Quick Actions Hub:*", reply_markup=inline_menu, parse_mode="Markdown")
    else:
        pending_text = (
            f"📝 *Registration Received!*\n\n"
            f"👤 *Name:* {full_name}\n"
            f"💼 *Role:* {role}\n\n"
            f"⏳ Your account is pending manager approval. You will receive a notification once activated."
        )
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
                        f"🆔 *Telegram ID:* `{user_id}`\n"
                        f"Username: @{user_obj.username or 'N/A'}"
                    ),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")

    context.user_data.pop("onboarding_name", None)
    return ConversationHandler.END

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /menu — opens the interactive Quick Actions Hub."""
    user = update.effective_user
    reply_kb = get_main_reply_keyboard(user.id)
    inline_kb = build_main_inline_menu(user.id)

    await update.message.reply_text(
        "🎛️ *Site Management Main Menu*\n\n"
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
    if not worker:
        await update.message.reply_text("⚠️ You are not registered yet. Use `/start` to register.", parse_mode="Markdown")
        return

    admin_tag = " ⭐ (Site Manager)" if is_admin(user.id) else ""
    status_tag = "✅ Approved / Active" if worker.get("is_approved") else "⏳ Pending Approval"

    text = (
        f"👤 *WORKER PROFILE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 *Name:* {worker['full_name']}{admin_tag}\n"
        f"💼 *Role:* {worker['role']}\n"
        f"🆔 *User ID:* `{worker['user_id']}`\n"
        f"📊 *Status:* {status_tag}\n"
        f"📅 *Registered:* {worker.get('registered_at', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
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
        
        await query.edit_message_text(
            f"✅ *Worker Approved*\n\n"
            f"👤 Worker: *{w_name}* (`{target_uid}`)\n"
            f"Approved by: {admin_user.first_name}",
            parse_mode="Markdown"
        )
        # Notify the worker
        try:
            worker_reply_kb = get_main_reply_keyboard(target_uid)
            await context.bot.send_message(
                chat_id=target_uid,
                text="🎉 *Your account has been approved by Site Management!*",
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
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_ROLE: [
                CallbackQueryHandler(receive_role_button, pattern=r"^role_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_role_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        allow_reentry=True,
    )
