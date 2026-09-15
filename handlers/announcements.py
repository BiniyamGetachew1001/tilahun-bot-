import logging
import asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.error import Forbidden, BadRequest
from database import (
    list_all_workers,
    get_worker,
    save_announcement,
    list_recent_announcements,
)
from handlers.auth import is_admin
from locales import t, get_user_lang

logger = logging.getLogger(__name__)

BC_INPUT_MSG, BC_CONFIRM = range(2)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /broadcast, /announce, and manager button."""
    user = update.effective_user
    if not is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Only managers/admins can broadcast announcements.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Only managers/admins can broadcast announcements.")
        return ConversationHandler.END

    lang = get_user_lang(user.id)
    text = t("broadcast_prompt", lang)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

    return BC_INPUT_MSG

async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captures text or photo with caption for the broadcast."""
    user = update.effective_user
    lang = get_user_lang(user.id)

    photo_id = None
    msg_text = ""

    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        msg_text = update.message.caption or ""
    elif update.message.text:
        msg_text = update.message.text.strip()

    if not msg_text and not photo_id:
        await update.message.reply_text("Please provide announcement text or a photo with a caption:")
        return BC_INPUT_MSG

    context.user_data["bc_text"] = msg_text
    context.user_data["bc_photo_id"] = photo_id

    # Get audience count
    all_workers = list_all_workers()
    target_workers = [w for w in all_workers if w.get("is_approved") == 1]
    if not target_workers:
        target_workers = all_workers

    context.user_data["bc_target_count"] = len(target_workers)

    confirm_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send Now to All", callback_data="bc_confirm_send"),
            InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel"),
        ]
    ])

    preview_snippet = msg_text if len(msg_text) <= 300 else (msg_text[:300] + "...")
    confirm_text = (
        f"📢 *BROADCAST ANNOUNCEMENT PREVIEW*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{preview_snippet}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 Photo: {'Yes (Attached)' if photo_id else 'None'}\n"
        f"👥 Target Audience: *{len(target_workers)} active workers*\n\n"
        f"Ready to broadcast this message to all workers' direct messages?"
    )

    await update.message.reply_text(confirm_text, reply_markup=confirm_markup, parse_mode="Markdown")
    return BC_CONFIRM

async def broadcast_confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes sending announcement to all workers."""
    query = update.callback_query
    await query.answer()

    if query.data == "bc_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return ConversationHandler.END

    msg_text = context.user_data.get("bc_text", "")
    photo_id = context.user_data.get("bc_photo_id")
    admin_user = query.from_user
    admin_worker = get_worker(admin_user.id)
    admin_name = admin_worker.get("full_name", admin_user.first_name) if admin_worker else admin_user.first_name

    await query.edit_message_text("⏳ *Broadcasting announcement to all employees... Please wait.*", parse_mode="Markdown")

    all_workers = list_all_workers()
    target_workers = [w for w in all_workers if w.get("is_approved") == 1]
    if not target_workers:
        target_workers = all_workers

    total_count = len(target_workers)
    success_count = 0
    failed_count = 0

    for w in target_workers:
        w_id = w.get("user_id")
        w_lang = w.get("language") or "en"
        announcement_header = t("announcement_banner", w_lang, sender=admin_name)
        full_message = announcement_header + msg_text
        try:
            if photo_id:
                if len(full_message) <= 1024:
                    await context.bot.send_photo(chat_id=w_id, photo=photo_id, caption=full_message, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=w_id, text=full_message, parse_mode="Markdown")
                    await context.bot.send_photo(chat_id=w_id, photo=photo_id)
            else:
                await context.bot.send_message(chat_id=w_id, text=full_message, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)  # Telegram rate limit prevention
        except (Forbidden, BadRequest) as e:
            logger.warning(f"Could not deliver announcement to worker {w_id}: {e}")
            failed_count += 1
        except Exception as e:
            logger.error(f"Error sending broadcast to {w_id}: {e}")
            failed_count += 1

    # Save announcement to DB
    save_announcement(
        admin_id=admin_user.id,
        admin_name=admin_name,
        title="Official Announcement",
        message_text=msg_text,
        photo_file_id=photo_id,
        sent_count=success_count
    )

    admin_lang = get_user_lang(admin_user.id)
    report_text = t("broadcast_sent_report", admin_lang,
                    success_count=success_count,
                    total_count=total_count,
                    failed_count=failed_count)

    await query.message.reply_text(report_text, parse_mode="Markdown")

    context.user_data.pop("bc_text", None)
    context.user_data.pop("bc_photo_id", None)
    context.user_data.pop("bc_target_count", None)
    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Broadcast cancelled.")
    else:
        await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

async def announcements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /announcements — displays recent company announcements."""
    user = update.effective_user
    lang = get_user_lang(user.id)
    recent = list_recent_announcements(limit=5)

    if not recent:
        await update.message.reply_text(
            t("announcements_none", lang),
            parse_mode="Markdown"
        )
        return

    title_str = (
        "📢 *የቅርብ ጊዜ ይፋዊ ማስታወቂያዎች*" if lang == "am" else (
            "📢 *BEEKSISA SAAYITII DHIHOO*" if lang == "om" else
            "📢 *RECENT SITE ANNOUNCEMENTS*"
        )
    )
    by_str = "በ" if lang == "am" else ("Kan erge" if lang == "om" else "by")
    lines = [title_str, "━━━━━━━━━━━━━━━━━━━━"]
    for a in recent:
        lines.append(
            f"📅 *{a['timestamp']}* — {by_str} {a['admin_name']}\n"
            f"{a['message_text']}\n"
            f"────────────────────"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def get_broadcast_wizard():
    return ConversationHandler(
        entry_points=[
            CommandHandler("broadcast", broadcast_start),
            CommandHandler("announce", broadcast_start),
            CallbackQueryHandler(broadcast_start, pattern=r"^(admin_broadcast|menu_broadcast)$"),
            MessageHandler(filters.Regex(r"^(📢 Broadcast Message|📢 ማስታወቂያ መልቀቅ|📢 Beeksisa Dabarsoo)"), broadcast_start),
        ],
        states={
            BC_INPUT_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_message),
                MessageHandler(filters.PHOTO, receive_broadcast_message),
            ],
            BC_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm_send, pattern=r"^bc_confirm_send$"),
                CallbackQueryHandler(broadcast_cancel, pattern=r"^bc_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", broadcast_cancel),
            CallbackQueryHandler(broadcast_cancel, pattern=r"^bc_cancel$"),
        ],
        allow_reentry=True,
    )
