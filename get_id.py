import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from config import BOT_TOKEN

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    topic_info = f" | Topic/Thread ID: `{msg.message_thread_id}`" if msg and msg.is_topic_message else ""
    
    print("\n" + "="*50)
    print(f"📩 Message Received!")
    print(f"👤 Sender: {user.full_name} (@{user.username or 'No handle'})")
    print(f"🆔 Sender User ID (for ADMIN_IDS): {user.id}")
    print(f"👥 Chat Title: {chat.title or 'Private Chat'}")
    print(f"💬 Chat Type: {chat.type}")
    print(f"🏷️ Supergroup Chat ID: {chat.id}")
    if msg and msg.is_topic_message:
        print(f"📌 Topic Thread ID: {msg.message_thread_id}")
    print("="*50 + "\n")

    response = (
        f"🔍 Telegram IDs Detected:\n\n"
        f"👤 Your User ID: {user.id} (Put in ADMIN_IDS)\n"
        f"🏷️ Supergroup Chat ID: {chat.id} (Put in SUPERGROUP_CHAT_ID)\n"
    )
    if msg and msg.is_topic_message:
        response += f"📌 Topic Thread ID: {msg.message_thread_id}\n"

    try:
        await msg.reply_text(response)
    except Exception as e:
        print(f"Could not reply in chat: {e}")

def main():
    print("="*60)
    print("🤖 ID Discovery Tool Running...")
    print("1. Add @TilahunSiteBot to your Supergroup / Channel / Chat.")
    print("2. Send ANY message in the group or topic (e.g., 'hello' or '/id').")
    print("3. The Chat ID, User ID, and Topic IDs will appear below!")
    print("="*60)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_any_message))
    app.run_polling()

if __name__ == "__main__":
    main()
