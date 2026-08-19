import logging
import datetime
import pytz
from telegram.ext import ContextTypes
from config import (
    SUPERGROUP_CHAT_ID,
    ADMIN_IDS,
    DAY_CUTOFF_HOUR,
    DAY_CUTOFF_MINUTE,
    NIGHT_CUTOFF_HOUR,
    NIGHT_CUTOFF_MINUTE,
    TIMEZONE_STR
)
from database import list_active_projects, get_today_report_for_project, list_all_workers

logger = logging.getLogger(__name__)

async def check_missing_day_reports(context: ContextTypes.DEFAULT_TYPE):
    """Checks missing Day shift reports at day cutoff (e.g. 7:00 PM)."""
    await _check_shift_reports(context, shift_type="DAY")

async def check_missing_night_reports(context: ContextTypes.DEFAULT_TYPE):
    """Checks missing Night shift reports at morning cutoff (e.g. 7:00 AM)."""
    await _check_shift_reports(context, shift_type="NIGHT")

async def _check_shift_reports(context: ContextTypes.DEFAULT_TYPE, shift_type: str = "DAY"):
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    projects = list_active_projects()

    shift_label = "Night Shift 🌙" if shift_type == "NIGHT" else "Day Shift ☀️"
    command_hint = "/night_report" if shift_type == "NIGHT" else "/report"

    missing_projects = []

    for proj in projects:
        proj_name = proj["name"]
        topic_id = proj.get("topic_id", 0)
        
        report_today = get_today_report_for_project(proj_name, today_str, shift_type=shift_type)
        if not report_today:
            missing_projects.append(proj)

            # Send alert directly to the project topic if configured
            if SUPERGROUP_CHAT_ID != 0:
                try:
                    kwargs = {
                        "chat_id": SUPERGROUP_CHAT_ID,
                        "text": (
                            f"⚠️ *{shift_label.upper()} REPORT CUTOFF REMINDER*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🏗️ *Project:* {proj_name}\n"
                            f"📅 *Date:* {today_str}\n\n"
                            f"No *{shift_label}* progress report has been submitted for this project today.\n"
                            f"Site foremen / shift leads, please run `{command_hint}` to log shift progress."
                        ),
                        "parse_mode": "Markdown"
                    }
                    if topic_id and topic_id != 0:
                        kwargs["message_thread_id"] = topic_id

                    await context.bot.send_message(**kwargs)
                except Exception as e:
                    logger.error(f"Failed to send cutoff reminder to topic for {proj_name}: {e}")

    # Notify admins/managers with a summary of all missing projects
    if missing_projects and ADMIN_IDS:
        missing_names = "\n".join([f"• 🏗️ *{p['name']}*" for p in missing_projects])
        admin_alert_text = (
            f"🚨 *{shift_label} Cutoff Alert ({today_str} {now.strftime('%H:%M')})*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"The following {len(missing_projects)} project(s) have *not submitted* a {shift_label} report today:\n\n"
            f"{missing_names}\n\n"
            f"Reminders were automatically posted to the respective topics."
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_alert_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id} about missing reports: {e}")

    # Nudge workers who have not submitted a report today
    try:
        workers = list_all_workers()
        for w in workers:
            w_id = w.get("user_id")
            if w.get("is_approved") == 1 and w_id not in ADMIN_IDS:
                # Check if worker submitted any report today
                from database import db_fetchone
                rep = db_fetchone("SELECT id FROM reports WHERE worker_user_id = ? AND date_str = ? LIMIT 1", (w_id, today_str))
                if not rep:
                    try:
                        await context.bot.send_message(
                            chat_id=w_id,
                            text=(
                                f"🔔 *Friendly Cutoff Reminder*\n\n"
                                f"Hi *{w['full_name']}*, you haven't submitted your *{shift_label}* report for today yet.\n"
                                f"Please take a minute to submit it using `{command_hint}` or tap the button in `/menu`."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"Worker reminder check notice: {e}")

async def send_weekly_admin_digest(context: ContextTypes.DEFAULT_TYPE):
    """Compiles and sends the 7-day Worker Activity & Missing Report Digest directly to admins."""
    if not ADMIN_IDS:
        return

    logger.info("📊 Generating weekly worker activity digest for admins...")
    try:
        from database import get_weekly_worker_summary
        from handlers.admin import format_weekly_worker_summary_text

        summary_data = get_weekly_worker_summary(days=7)
        chunks = format_weekly_worker_summary_text(summary_data)

        for admin_id in ADMIN_IDS:
            try:
                for chunk in chunks:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=chunk,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.warning(f"Could not deliver weekly digest to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error compiling weekly admin digest: {e}")

def setup_cutoff_scheduler(application):
    """Schedules Day/Night shift cutoff checks and weekly admin digests."""
    job_queue = application.job_queue
    if not job_queue:
        logger.warning("JobQueue is not available. Ensure python-telegram-bot[job-queue] is installed.")
        return

    try:
        tz = pytz.timezone(TIMEZONE_STR)
    except Exception:
        tz = None

    # 1. Day Shift cutoff (e.g. 19:00)
    day_time = datetime.time(hour=DAY_CUTOFF_HOUR, minute=DAY_CUTOFF_MINUTE, tzinfo=tz)
    job_queue.run_daily(check_missing_day_reports, time=day_time, name="day_cutoff_check")
    logger.info(f"Day cutoff reminder scheduled for {DAY_CUTOFF_HOUR:02d}:{DAY_CUTOFF_MINUTE:02d} ({TIMEZONE_STR}).")

    # 2. Night Shift cutoff (e.g. 07:00 AM)
    night_time = datetime.time(hour=NIGHT_CUTOFF_HOUR, minute=NIGHT_CUTOFF_MINUTE, tzinfo=tz)
    job_queue.run_daily(check_missing_night_reports, time=night_time, name="night_cutoff_check")
    logger.info(f"Night cutoff reminder scheduled for {NIGHT_CUTOFF_HOUR:02d}:{NIGHT_CUTOFF_MINUTE:02d} ({TIMEZONE_STR}).")

    # 3. Weekly Worker Digest for Admins (Every Sunday at 20:00 / 8:00 PM)
    weekly_time = datetime.time(hour=20, minute=0, tzinfo=tz)
    job_queue.run_daily(send_weekly_admin_digest, time=weekly_time, days=(6,), name="weekly_admin_digest")
    logger.info(f"Weekly admin digest scheduled for Sundays at 20:00 ({TIMEZONE_STR}).")
