import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Telegram Bot Credentials ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SUPERGROUP_CHAT_ID = int(os.getenv("SUPERGROUP_CHAT_ID", "0"))  # e.g. -1001234567890

# --- Admin Telegram User IDs (for access control & approvals) ---
# Format in .env: ADMIN_IDS=12345678,87654321
raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

# Whether new workers require manager approval before they can submit reports
REQUIRE_APPROVAL = os.getenv("REQUIRE_APPROVAL", "True").lower() in ("true", "1", "yes")

# --- Cutoff Times for Reports (Local Time) ---
DAY_CUTOFF_HOUR = int(os.getenv("DAY_CUTOFF_HOUR", os.getenv("CUTOFF_HOUR", "19")))  # 19:00 = 7:00 PM
DAY_CUTOFF_MINUTE = int(os.getenv("DAY_CUTOFF_MINUTE", os.getenv("CUTOFF_MINUTE", "0")))

NIGHT_CUTOFF_HOUR = int(os.getenv("NIGHT_CUTOFF_HOUR", "7"))  # 07:00 = 7:00 AM (Next morning)
NIGHT_CUTOFF_MINUTE = int(os.getenv("NIGHT_CUTOFF_MINUTE", "0"))

TIMEZONE_STR = os.getenv("TIMEZONE", "Africa/Addis_Ababa")

# --- Telegram Supergroup Forum Topic Thread IDs ---
# Map project names to their respective forum Topic Thread IDs in Telegram.
# thread_id: 0 or None means general topic / main group chat.
DEFAULT_PROJECTS = {
    "Project Alpha": int(os.getenv("TOPIC_PROJECT_ALPHA", "0")),
    "Project Beta": int(os.getenv("TOPIC_PROJECT_BETA", "0")),
    "Project Gamma": int(os.getenv("TOPIC_PROJECT_GAMMA", "0")),
}

# Dedicated Topic for Material Requisitions (if 0, posts to the specific project topic)
MATERIALS_TOPIC_ID = int(os.getenv("TOPIC_MATERIALS", "0"))

# Dedicated Topic for Urgent Alerts / Issues
ISSUES_TOPIC_ID = int(os.getenv("TOPIC_ISSUES", "0"))

# --- Database & Storage ---
DB_PATH = BASE_DIR / "site_manager.db"
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
