import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Telegram Bot Credentials ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8891345663:AAGdwG2CDqOPwXBou-reFvDWf8ZBsrMmwWM")
SUPERGROUP_CHAT_ID = int(os.getenv("SUPERGROUP_CHAT_ID", "-1004307508548"))

# --- Admin Telegram User IDs (for access control & approvals) ---
raw_admin_ids = os.getenv("ADMIN_IDS", "1602040402")
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
DEFAULT_PROJECTS = {
    "Project Alpha": int(os.getenv("TOPIC_PROJECT_ALPHA", "7")),
    "Project Beta": int(os.getenv("TOPIC_PROJECT_BETA", "9")),
    "Project Gamma": int(os.getenv("TOPIC_PROJECT_GAMMA", "10")),
}

# Dedicated Topic for Material Requisitions
MATERIALS_TOPIC_ID = int(os.getenv("TOPIC_MATERIALS", "13"))

# Dedicated Topic for Urgent Alerts / Issues
ISSUES_TOPIC_ID = int(os.getenv("TOPIC_ISSUES", "16"))

# --- Database & Storage ---
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = BASE_DIR / "site_manager.db"
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
