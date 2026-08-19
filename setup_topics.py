import asyncio
import os
import sys
import re
from telegram import Bot

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import BOT_TOKEN, SUPERGROUP_CHAT_ID, BASE_DIR
from database import init_db, add_or_update_project, set_setting

# Telegram topic icon colors:
# 0x6FB9F0 (blue), 0xFFD67E (yellow), 0xCB86DB (violet), 0x8EEE98 (green), 0xFF93B2 (pink), 0xFB6F5F (red)
DEFAULT_TOPICS = [
    {"name": "📌 General Announcements", "type": "announcements", "color": 0x6FB9F0},
    {"name": "🏗️ Project Alpha", "type": "project", "proj_name": "Project Alpha", "color": 0x8EEE98},
    {"name": "🏢 Project Beta", "type": "project", "proj_name": "Project Beta", "color": 0xFFD67E},
    {"name": "🚧 Project Gamma", "type": "project", "proj_name": "Project Gamma", "color": 0xCB86DB},
    {"name": "📦 Material Requisitions", "type": "materials", "color": 0xFF93B2},
    {"name": "⚠️ Issues & Blockers", "type": "issues", "color": 0xFB6F5F},
]

async def create_all_topics():
    if not SUPERGROUP_CHAT_ID or SUPERGROUP_CHAT_ID == 0:
        print("❌ Error: SUPERGROUP_CHAT_ID is not configured in .env!")
        return

    init_db()
    bot = Bot(token=BOT_TOKEN)

    print("\n" + "="*60)
    print(f"🚀 Initializing Forum Topics in Supergroup: {SUPERGROUP_CHAT_ID}")
    print("="*60 + "\n")

    created_ids = {}

    for t in DEFAULT_TOPICS:
        try:
            print(f"⏳ Creating topic: {t['name']}...")
            topic = await bot.create_forum_topic(
                chat_id=SUPERGROUP_CHAT_ID,
                name=t["name"],
                icon_color=t.get("color")
            )
            thread_id = topic.message_thread_id
            print(f"   ✅ Created successfully! (Thread ID: {thread_id})")

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

            # Send a welcome message in the new topic
            welcome_msg = (
                f"👋 *Welcome to {t['name']}!*\n\n"
                f"This topic is managed by @TilahunSiteBot for real-time site updates."
            )
            await bot.send_message(
                chat_id=SUPERGROUP_CHAT_ID,
                message_thread_id=thread_id,
                text=welcome_msg,
                parse_mode="Markdown"
            )

        except Exception as e:
            print(f"   ❌ Failed to create topic '{t['name']}': {e}")

    # Update .env file with new IDs
    update_env_file(created_ids)

    print("\n" + "="*60)
    print("🎉 All Forum Topics created & configured successfully in Database and .env!")
    print("="*60 + "\n")

def update_env_file(created_ids: dict):
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    content = env_path.read_text(encoding="utf-8")

    mapping = {
        "Project Alpha": "TOPIC_PROJECT_ALPHA",
        "Project Beta": "TOPIC_PROJECT_BETA",
        "Project Gamma": "TOPIC_PROJECT_GAMMA",
        "TOPIC_MATERIALS": "TOPIC_MATERIALS",
        "TOPIC_ISSUES": "TOPIC_ISSUES",
    }

    for key, var_name in mapping.items():
        if key in created_ids:
            val = created_ids[key]
            if re.search(rf"^{var_name}=.*$", content, flags=re.MULTILINE):
                content = re.sub(rf"^{var_name}=.*$", f"{var_name}={val}", content, flags=re.MULTILINE)
            else:
                content += f"\n{var_name}={val}"

    env_path.write_text(content, encoding="utf-8")

def main():
    asyncio.run(create_all_topics())

if __name__ == "__main__":
    main()
