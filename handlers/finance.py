import logging
import datetime
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
from config import ADMIN_IDS, DEFAULT_CURRENCY
from database import (
    get_worker,
    create_financial_request,
    get_financial_request_by_code,
    update_financial_request_status,
    record_loan_repayment,
    get_worker_loans,
    get_worker_active_loan_balance,
    list_pending_financial_requests,
    list_all_financial_requests,
    get_financial_summary,
)
from handlers.auth import is_authorized, is_admin
from locales import t, get_user_lang

logger = logging.getLogger(__name__)

# Conversation states for Requesting Loan / Advance
FIN_TYPE, FIN_AMOUNT, FIN_REASON, FIN_TERMS = range(4)

# Conversation states for Recording Repayment
REPAY_INPUT_CODE, REPAY_INPUT_AMOUNT, REPAY_INPUT_NOTE = range(4, 7)

# --- Employee Loan / Financial Request Flow ---

def build_fin_type_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(t("loan_type_advance", lang), callback_data="fintype_SALARY_ADVANCE"),
            InlineKeyboardButton(t("loan_type_loan", lang), callback_data="fintype_PERSONAL_LOAN"),
        ],
        [
            InlineKeyboardButton(t("loan_type_expense", lang), callback_data="fintype_EXPENSE_REIMBURSEMENT"),
        ],
        [
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="fin_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_repayment_terms_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(t("loan_term_next_salary", lang), callback_data="finterm_Next Salary")],
        [InlineKeyboardButton(t("loan_term_2_months", lang), callback_data="finterm_2 Months")],
        [InlineKeyboardButton(t("loan_term_3_months", lang), callback_data="finterm_3 Months")],
        [InlineKeyboardButton(t("loan_term_immediate", lang), callback_data="finterm_Immediate")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="fin_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_loan_admin_card(req: dict, lang: str = "en") -> str:
    """Formats a detailed notification card for financial requests."""
    status_icons = {
        "en": {
            "PENDING": "⏳ PENDING REVIEW",
            "APPROVED": "✅ APPROVED",
            "REJECTED": "❌ REJECTED",
            "DISBURSED": "💵 DISBURSED / ACTIVE",
            "REPAID": "🎉 FULLY REPAID",
            "CANCELLED": "🚫 CANCELLED",
        },
        "am": {
            "PENDING": "⏳ በግምገማ ላይ",
            "APPROVED": "✅ የጸደቀ",
            "REJECTED": "❌ ውድቅ የተደረገ",
            "DISBURSED": "💵 የተከፈለ (ያላለቀ)",
            "REPAID": "🎉 ሙሉ በሙሉ የተመለሰ",
            "CANCELLED": "🚫 የተሰረዘ",
        },
        "om": {
            "PENDING": "⏳ Qorannoo Irra",
            "APPROVED": "✅ Mirkanaa'e",
            "REJECTED": "❌ Hin Eeyyamamne",
            "DISBURSED": "💵 Kaffalame (Haftee qaba)",
            "REPAID": "🎉 Guutuutti Deebi'e",
            "CANCELLED": "🚫 Haqameera",
        }
    }
    lang_key = lang if lang in ("am", "om") else "en"
    status_badge = status_icons[lang_key].get(req.get("status", "PENDING"), req.get("status", "PENDING"))
    amt = f"{req.get('amount', 0.0):,.2f} {req.get('currency', 'ETB')}"
    repaid = f"{req.get('amount_repaid', 0.0):,.2f} {req.get('currency', 'ETB')}"
    type_display = req.get("request_type", "").replace("_", " ").title()

    plan_am = req.get('repayment_plan') or 'ከደመወዝ የሚቀነስ'
    plan_om = req.get('repayment_plan') or "Mindaa irraa kan hir'atu"
    plan_en = req.get('repayment_plan') or 'Standard payroll deduction'

    if lang == "am":
        card = (
            f"💰 *የገንዘብ ጥያቄ #{req.get('req_code')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *ሰራተኛ:* {req.get('worker_name')} _({req.get('worker_role')})_\n"
            f"📋 *ዓይነት:* {type_display}\n"
            f"💵 *የተጠየቀው መጠን:* `{amt}`\n"
            f"💳 *እስካሁን የተመለሰው:* `{repaid}`\n"
            f"📌 *ሁኔታ:* {status_badge}\n"
            f"📅 *ቀን:* {req.get('timestamp')}\n\n"
            f"📝 *ምክንያት / ዓላማ:*\n{req.get('reason')}\n\n"
            f"🤝 *የአመላለስ እቅድ:*\n{plan_am}\n"
        )
        if req.get("approved_by_name"):
            card += f"\n✍️ *የገመገመው:* {req.get('approved_by_name')}"
        if req.get("notes"):
            card += f"\n💬 *ማስታወሻ:* {req.get('notes')}"
    elif lang == "om":
        card = (
            f"💰 *GAAFFII FAAYINAANSII #{req.get('req_code')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Hojjataa:* {req.get('worker_name')} _({req.get('worker_role')})_\n"
            f"📋 *Gosa:* {type_display}\n"
            f"💵 *Hamma:* `{amt}`\n"
            f"💳 *Kan Deebi'e:* `{repaid}`\n"
            f"📌 *Haala:* {status_badge}\n"
            f"📅 *Guyyaa:* {req.get('timestamp')}\n\n"
            f"📝 *Sababa:*\n{req.get('reason')}\n\n"
            f"🤝 *Karoora Deebisii:*\n{plan_om}\n"
        )
        if req.get("approved_by_name"):
            card += f"\n✍️ *Mirkaneessaa:* {req.get('approved_by_name')}"
        if req.get("notes"):
            card += f"\n💬 *Yaada:* {req.get('notes')}"
    else:
        card = (
            f"💰 *FINANCIAL REQUEST #{req.get('req_code')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Worker:* {req.get('worker_name')} _({req.get('worker_role')})_\n"
            f"📋 *Type:* {type_display}\n"
            f"💵 *Amount:* `{amt}`\n"
            f"💳 *Repaid So Far:* `{repaid}`\n"
            f"📌 *Status:* {status_badge}\n"
            f"📅 *Date:* {req.get('timestamp')}\n\n"
            f"📝 *Reason / Purpose:*\n{req.get('reason')}\n\n"
            f"🤝 *Repayment Plan:*\n{plan_en}\n"
        )
        if req.get("approved_by_name"):
            card += f"\n✍️ *Reviewed By:* {req.get('approved_by_name')}"
        if req.get("notes"):
            card += f"\n💬 *Notes:* {req.get('notes')}"

    card += "\n━━━━━━━━━━━━━━━━━━━━"
    return card

def build_loan_action_keyboard(req_code: str, status: str = "PENDING", lang: str = "en") -> InlineKeyboardMarkup:
    """Admin action buttons for financial requests in target language."""
    btn_approve = "✅ አጽድቅ" if lang == "am" else ("✅ Mirkaneessi" if lang == "om" else "✅ Approve")
    btn_reject = "❌ ውድቅ አድርግ" if lang == "am" else ("❌ Didi" if lang == "om" else "❌ Reject")
    btn_disburse = "💵 ገንዘቡ ተከፍሏል" if lang == "am" else ("💵 Kaffalameera" if lang == "om" else "💵 Mark Disbursed")
    btn_repay = "💳 ክፍያ መዝግብ" if lang == "am" else ("💳 Kaffaltii Galmeessi" if lang == "om" else "💳 Record Repayment")
    btn_cancel_appr = "❌ ፍቃድ ሰርዝ" if lang == "am" else ("❌ Eeyyama Haqi" if lang == "om" else "❌ Cancel Approval")

    keyboard = []
    if status == "PENDING":
        keyboard.append([
            InlineKeyboardButton(btn_approve, callback_data=f"loanact_approve_{req_code}"),
            InlineKeyboardButton(btn_reject, callback_data=f"loanact_reject_{req_code}"),
        ])
    elif status == "APPROVED":
        keyboard.append([
            InlineKeyboardButton(btn_disburse, callback_data=f"loanact_disburse_{req_code}"),
            InlineKeyboardButton(btn_cancel_appr, callback_data=f"loanact_reject_{req_code}"),
        ])
    elif status == "DISBURSED":
        keyboard.append([
            InlineKeyboardButton(btn_repay, callback_data=f"loanact_repay_{req_code}"),
        ])
    return InlineKeyboardMarkup(keyboard)

async def request_loan_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /request_loan, /advance, and persistent menu button."""
    user = update.effective_user
    is_cb = bool(update.callback_query)

    if is_cb:
        await update.callback_query.answer()

    if not is_authorized(user.id):
        worker = get_worker(user.id)
        msg_txt = "⚠️ You must first register with `/start` before requesting financial assistance." if not worker else "⏳ Your account is pending manager approval. Please wait until approved."
        if is_cb:
            await update.callback_query.edit_message_text(msg_txt, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg_txt, parse_mode="Markdown")
        return ConversationHandler.END

    lang = get_user_lang(user.id)
    text = t("loan_step1_type", lang)
    reply_markup = build_fin_type_keyboard(lang)

    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return FIN_TYPE

async def receive_fin_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "fin_cancel":
        await query.edit_message_text("❌ Request cancelled.")
        return ConversationHandler.END

    req_type = data.replace("fintype_", "")
    context.user_data["fin_type"] = req_type

    user = update.effective_user
    lang = get_user_lang(user.id)
    prompt_amount = t("loan_step2_amount", lang, currency=DEFAULT_CURRENCY)

    await query.edit_message_text(prompt_amount, parse_mode="Markdown")
    return FIN_AMOUNT

async def receive_fin_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    raw_text = update.message.text.strip().replace(",", "")

    try:
        amount = float(raw_text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(t("loan_invalid_amount", lang), parse_mode="Markdown")
        return FIN_AMOUNT

    context.user_data["fin_amount"] = amount
    prompt_reason = t("loan_step3_reason", lang)
    await update.message.reply_text(prompt_reason, parse_mode="Markdown")
    return FIN_REASON

async def receive_fin_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(user.id)
    reason = update.message.text.strip()

    if len(reason) < 3:
        await update.message.reply_text("Please provide a brief reason for the request:")
        return FIN_REASON

    context.user_data["fin_reason"] = reason
    prompt_terms = t("loan_step4_terms", lang)
    reply_markup = build_repayment_terms_keyboard(lang)

    await update.message.reply_text(prompt_terms, reply_markup=reply_markup, parse_mode="Markdown")
    return FIN_TERMS

async def receive_fin_terms_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "fin_cancel":
        await query.edit_message_text("❌ Request cancelled.")
        return ConversationHandler.END

    terms = query.data.replace("finterm_", "")
    return await _complete_financial_request(query, context, terms, is_query=True)

async def receive_fin_terms_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    terms = update.message.text.strip()
    return await _complete_financial_request(update, context, terms, is_query=False)

async def _complete_financial_request(target, context: ContextTypes.DEFAULT_TYPE, terms: str, is_query: bool = False) -> int:
    user_id = target.from_user.id if is_query else target.effective_user.id
    worker = get_worker(user_id)
    worker_name = worker.get("full_name", "Worker") if worker else "Worker"
    worker_role = worker.get("role", "Staff") if worker else "Staff"
    lang = get_user_lang(user_id)

    req_type = context.user_data.get("fin_type", "SALARY_ADVANCE")
    amount = context.user_data.get("fin_amount", 0.0)
    reason = context.user_data.get("fin_reason", "General need")

    # Create request in DB
    req = create_financial_request(
        worker_user_id=user_id,
        worker_name=worker_name,
        worker_role=worker_role,
        request_type=req_type,
        amount=amount,
        reason=reason,
        repayment_plan=terms,
        currency=DEFAULT_CURRENCY
    )

    # Notify all admins in their private DMs with interactive action buttons in their preferred language
    for admin_id in ADMIN_IDS:
        try:
            admin_lang = get_user_lang(admin_id)
            admin_card = build_loan_admin_card(req, lang=admin_lang)
            admin_markup = build_loan_action_keyboard(req["req_code"], status="PENDING", lang=admin_lang)
            admin_title = "🔔 *New Financial Request Submitted!*" if admin_lang == "en" else (
                "🔔 *አዲስ የገንዘብ ጥያቄ ቀርቧል!*" if admin_lang == "am" else "🔔 *Gaaffiin Faayinaansii Haaraan Dhiyaateera!*"
            )
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"{admin_title}\n\n{admin_card}",
                reply_markup=admin_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not deliver loan request notification to admin {admin_id}: {e}")

    # Confirm to worker in worker's language
    worker_card = build_loan_admin_card(req, lang=lang)
    confirm_text = t("loan_submitted_success", lang, req_code=req["req_code"], card=worker_card)
    if is_query:
        await target.edit_message_text(confirm_text, parse_mode="Markdown")
    else:
        await target.message.reply_text(confirm_text, parse_mode="Markdown")

    context.user_data.pop("fin_type", None)
    context.user_data.pop("fin_amount", None)
    context.user_data.pop("fin_reason", None)
    return ConversationHandler.END

async def fin_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Financial request cancelled.")
    else:
        await update.message.reply_text("❌ Financial request cancelled.")
    return ConversationHandler.END

# --- Admin Loan Action Handlers ---

async def handle_loan_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Approve, Reject, Disburse actions clicked by Managers."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not is_admin(user.id):
        await query.answer("⛔ Only managers/admins can review financial requests.", show_alert=True)
        return

    admin_worker = get_worker(user.id)
    admin_name = admin_worker.get("full_name", user.first_name) if admin_worker else user.first_name

    data = query.data
    parts = data.split("_")
    action = parts[1]
    req_code = parts[2]

    req = get_financial_request_by_code(req_code)
    if not req:
        await query.edit_message_text("❌ Request not found.")
        return

    worker_id = req["worker_user_id"]
    worker_lang = get_user_lang(worker_id)
    amt_str = f"{req['amount']:,.2f} {req.get('currency', 'ETB')}"

    admin_lang = get_user_lang(user.id)
    if action == "approve":
        updated_req = update_financial_request_status(
            req_code=req_code,
            new_status="APPROVED",
            approved_by_name=admin_name,
            approved_by_id=user.id,
            notes="Approved by management"
        )
        updated_card = build_loan_admin_card(updated_req, lang=admin_lang)
        new_markup = build_loan_action_keyboard(req_code, status="APPROVED", lang=admin_lang)
        await query.edit_message_text(updated_card, reply_markup=new_markup, parse_mode="Markdown")

        # Notify worker in their preferred language
        try:
            worker_msg = t("loan_approved_worker_msg", worker_lang, req_code=req_code, amount=amt_str, admin=admin_name)
            await context.bot.send_message(
                chat_id=worker_id,
                text=worker_msg,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "reject":
        updated_req = update_financial_request_status(
            req_code=req_code,
            new_status="REJECTED",
            approved_by_name=admin_name,
            approved_by_id=user.id,
            notes="Rejected by management"
        )
        updated_card = build_loan_admin_card(updated_req, lang=admin_lang)
        await query.edit_message_text(updated_card, parse_mode="Markdown")

        # Notify worker in their preferred language
        try:
            worker_msg = t("loan_rejected_worker_msg", worker_lang, req_code=req_code, amount=amt_str, admin=admin_name)
            await context.bot.send_message(
                chat_id=worker_id,
                text=worker_msg,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "disburse":
        updated_req = update_financial_request_status(
            req_code=req_code,
            new_status="DISBURSED",
            approved_by_name=admin_name,
            approved_by_id=user.id,
            notes="Disbursed / Paid out"
        )
        updated_card = build_loan_admin_card(updated_req, lang=admin_lang)
        new_markup = build_loan_action_keyboard(req_code, status="DISBURSED", lang=admin_lang)
        await query.edit_message_text(updated_card, reply_markup=new_markup, parse_mode="Markdown")

        # Notify worker in their preferred language
        try:
            worker_msg = t("loan_disbursed_worker_msg", worker_lang, req_code=req_code, amount=amt_str)
            await context.bot.send_message(
                chat_id=worker_id,
                text=worker_msg,
                parse_mode="Markdown"
            )
        except Exception:
            pass

# --- Worker Self-Service: /my_loans ---

async def my_loans_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /my_loans — displays worker's active requests and outstanding balance."""
    user = update.effective_user
    worker = get_worker(user.id)
    lang = get_user_lang(user.id)

    if not worker:
        await update.message.reply_text("⚠️ Please register first with `/start`.", parse_mode="Markdown")
        return

    loans = get_worker_loans(user.id)
    balance = get_worker_active_loan_balance(user.id)

    if not loans:
        await update.message.reply_text(t("my_loans_none", lang), parse_mode="Markdown")
        return

    status_emojis = {
        "en": {
            "PENDING": "⏳ Pending",
            "APPROVED": "✅ Approved",
            "DISBURSED": "💵 Disbursed",
            "REPAID": "🎉 Repaid",
            "REJECTED": "❌ Rejected",
        },
        "am": {
            "PENDING": "⏳ በግምገማ ላይ",
            "APPROVED": "✅ የጸደቀ",
            "DISBURSED": "💵 የተከፈለ",
            "REPAID": "🎉 የተመለሰ",
            "REJECTED": "❌ ውድቅ የተደረገ",
        },
        "om": {
            "PENDING": "⏳ Qorannoo Irra",
            "APPROVED": "✅ Mirkanaa'e",
            "DISBURSED": "💵 Kaffalame",
            "REPAID": "🎉 Deebi'e",
            "REJECTED": "❌ Didi",
        }
    }
    lang_key = lang if lang in ("am", "om") else "en"
    st_dict = status_emojis[lang_key]

    lbl_title = t("my_loans_title", lang)
    lbl_worker = "👤 *ሰራተኛ:*" if lang == "am" else ("👤 *Hojjataa:*" if lang == "om" else "👤 *Employee:*")
    lbl_bal = t("my_loans_outstanding", lang, balance=f"{balance:,.2f} {DEFAULT_CURRENCY}")
    lbl_recent = "📋 *የቅርብ ጊዜ ጥያቄዎች:*" if lang == "am" else ("📋 *Gaaffiiwwan Dhihoo:*" if lang == "om" else "📋 *Recent Requests:*")

    lines = [
        lbl_title,
        "━━━━━━━━━━━━━━━━━━━━",
        f"{lbl_worker} {worker['full_name']} _({worker['role']})_",
        lbl_bal,
        "━━━━━━━━━━━━━━━━━━━━\n",
        lbl_recent
    ]

    for ln in loans[:10]:
        st = st_dict.get(ln["status"], ln["status"])
        amt = f"{ln['amount']:,.2f} {ln.get('currency', 'ETB')}"
        rep = f"{ln.get('amount_repaid', 0.0):,.2f}"
        lbl_amt = "መጠን" if lang == "am" else ("Hamma" if lang == "om" else "Amount")
        lbl_rep = "የተመለሰ" if lang == "am" else ("Deebi'e" if lang == "om" else "Repaid")
        lbl_st = "ሁኔታ" if lang == "am" else ("Haala" if lang == "om" else "Status")
        lines.append(
            f"• *#{ln['req_code']}* ({ln['request_type'].replace('_', ' ').title()})\n"
            f"  {lbl_amt}: `{amt}` | {lbl_rep}: `{rep}`\n"
            f"  {lbl_st}: {st} | Date: {ln['date_str']}"
        )

    hint_msg = (
        "\n💡 _አዲስ ብድር ወይም ቅድመ ክፍያ ለመጠየቅ /request_loan ይጠቀሙ።_" if lang == "am" else (
            "\n💡 _Liqii ykn kaffaltii duraa gaafachuuf /request_loan fayyadamaa._" if lang == "om" else
            "\n💡 _Need assistance? Run /request_loan to submit a new request._"
        )
    )
    lines.append(hint_msg)
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# --- Manager Financial Dashboard: /finance ---

def build_finance_dashboard_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📋 View Pending Requests", callback_data="finmenu_pending"),
            InlineKeyboardButton("💳 Record Repayment", callback_data="finmenu_repay_start"),
        ],
        [
            InlineKeyboardButton("📊 All Active Loans", callback_data="finmenu_all"),
            InlineKeyboardButton("📥 Export Financial Excel", callback_data="admin_export_excel"),
        ],
        [
            InlineKeyboardButton("« Back to Admin Panel", callback_data="admin_back_to_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def finance_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manager command /finance — overview of all company advances, loans, and repayments."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Only managers/admins can access the Financial Management Board.")
        return

    summary = get_financial_summary()
    text = (
        f"💼 *COMPANY FINANCIAL & LOAN MANAGEMENT*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ *Pending Review Requests:* {summary['pending_count']} ({summary['pending_amount']:,.2f} {DEFAULT_CURRENCY})\n"
        f"💵 *Total Approved/Disbursed:* {summary['total_disbursed_or_approved']:,.2f} {DEFAULT_CURRENCY}\n"
        f"💳 *Total Repayments Collected:* {summary['total_repaid']:,.2f} {DEFAULT_CURRENCY}\n"
        f"📉 *Current Outstanding Balance:* `{summary['outstanding_balance']:,.2f} {DEFAULT_CURRENCY}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Select an action below:"
    )

    reply_markup = build_finance_dashboard_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def finance_menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "finmenu_pending":
        pending = list_pending_financial_requests()
        if not pending:
            await query.edit_message_text(
                "✅ *No Pending Requests*\n\nAll employee financial requests have been reviewed.",
                reply_markup=build_finance_dashboard_keyboard(),
                parse_mode="Markdown"
            )
            return

        for req in pending[:5]:
            card = build_loan_admin_card(req)
            markup = build_loan_action_keyboard(req["req_code"], status="PENDING")
            await context.bot.send_message(chat_id=query.from_user.id, text=card, reply_markup=markup, parse_mode="Markdown")

    elif data == "finmenu_all":
        all_reqs = list_all_financial_requests(limit=15)
        if not all_reqs:
            await query.edit_message_text("No financial records found.", reply_markup=build_finance_dashboard_keyboard())
            return

        lines = ["📊 *Recent Financial Requests & Loans:*", "━━━━━━━━━━━━━━━━━━━━"]
        for r in all_reqs:
            rem = max(0.0, float(r["amount"]) - float(r.get("amount_repaid") or 0.0))
            lines.append(
                f"• *#{r['req_code']}* — {r['worker_name']} ({r['worker_role']})\n"
                f"  Type: {r['request_type']} | Amount: `{r['amount']:,.2f}` | Rem: `{rem:,.2f}`\n"
                f"  Status: {r['status']} | Date: {r['date_str']}"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        await query.edit_message_text("\n".join(lines), reply_markup=build_finance_dashboard_keyboard(), parse_mode="Markdown")

# --- Repayment Recording Flow for Admins ---

async def record_repayment_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /record_repayment or inline button."""
    user = update.effective_user
    if not is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Admin access only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Admin access only.")
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "💳 *Record Loan Repayment / Salary Deduction*\n\n"
            "Please enter the *Loan Code* (e.g., `LN-001` or `LN-004`):",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "💳 *Record Loan Repayment / Salary Deduction*\n\n"
            "Please enter the *Loan Code* (e.g., `LN-001` or `LN-004`):",
            parse_mode="Markdown"
        )
    return REPAY_INPUT_CODE

async def receive_repay_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    req = get_financial_request_by_code(code)

    if not req:
        await update.message.reply_text(f"❌ Could not find request `{code}`. Please verify and enter a valid code (e.g. `LN-001`):")
        return REPAY_INPUT_CODE

    context.user_data["repay_req_code"] = req["req_code"]
    balance = max(0.0, float(req["amount"]) - float(req.get("amount_repaid") or 0.0))

    await update.message.reply_text(
        f"👤 *Worker:* {req['worker_name']} _({req['worker_role']})_\n"
        f"💵 *Total Loan:* {req['amount']:,.2f} {req.get('currency', 'ETB')}\n"
        f"💳 *Already Repaid:* {req.get('amount_repaid', 0.0):,.2f}\n"
        f"📉 *Remaining Unpaid:* `{balance:,.2f} {req.get('currency', 'ETB')}`\n\n"
        f"Enter the *repayment amount* to credit now (e.g., `1500`):",
        parse_mode="Markdown"
    )
    return REPAY_INPUT_AMOUNT

async def receive_repay_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_amount = update.message.text.strip().replace(",", "")
    try:
        amount = float(raw_amount)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount. Please enter a valid positive number:")
        return REPAY_INPUT_AMOUNT

    context.user_data["repay_amount"] = amount
    await update.message.reply_text(
        "📝 Enter a short note or reference (e.g., `Deducted from Sept payroll`, `Cash paid`):",
        parse_mode="Markdown"
    )
    return REPAY_INPUT_NOTE

async def receive_repay_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note = update.message.text.strip()
    req_code = context.user_data.get("repay_req_code")
    amount = context.user_data.get("repay_amount", 0.0)

    admin_user = update.effective_user
    admin_worker = get_worker(admin_user.id)
    admin_name = admin_worker.get("full_name", admin_user.first_name) if admin_worker else admin_user.first_name

    updated_req = record_loan_repayment(
        req_code=req_code,
        amount=amount,
        recorded_by_id=admin_user.id,
        recorded_by_name=admin_name,
        notes=note
    )

    if not updated_req:
        await update.message.reply_text("❌ Error recording repayment.")
        return ConversationHandler.END

    rem_bal = max(0.0, float(updated_req["amount"]) - float(updated_req.get("amount_repaid") or 0.0))
    status_label = "🎉 FULLY REPAID" if updated_req["status"] == "REPAID" else f"Active (Remaining: {rem_bal:,.2f})"

    await update.message.reply_text(
        f"✅ *Repayment Successfully Recorded!*\n\n"
        f"📌 *Loan Code:* `#{req_code}`\n"
        f"👤 *Worker:* {updated_req['worker_name']}\n"
        f"💵 *Amount Repaid Now:* `{amount:,.2f} {updated_req.get('currency', 'ETB')}`\n"
        f"💳 *Total Repaid So Far:* `{updated_req['amount_repaid']:,.2f}`\n"
        f"📉 *Remaining Balance:* `{rem_bal:,.2f}`\n"
        f"🏷️ *Status:* {status_label}\n"
        f"📝 *Note:* {note}",
        parse_mode="Markdown"
    )

    # Notify worker in their preferred language
    try:
        worker_id = updated_req["worker_user_id"]
        worker_lang = get_user_lang(worker_id)
        amt_curr = f"{amount:,.2f} {updated_req.get('currency', 'ETB')}"
        tot_rep = f"{updated_req['amount_repaid']:,.2f} {updated_req.get('currency', 'ETB')}"
        rem_str = f"{rem_bal:,.2f} {updated_req.get('currency', 'ETB')}"
        repay_msg = t("loan_repayment_worker_msg", worker_lang,
                      amount=amt_curr,
                      req_code=req_code,
                      total_repaid=tot_rep,
                      remaining=rem_str,
                      status=status_label)
        await context.bot.send_message(
            chat_id=worker_id,
            text=repay_msg,
            parse_mode="Markdown"
        )
    except Exception:
        pass

    context.user_data.pop("repay_req_code", None)
    context.user_data.pop("repay_amount", None)
    return ConversationHandler.END

# --- Wizard Handlers for Main ---

def get_financial_request_wizard():
    return ConversationHandler(
        entry_points=[
            CommandHandler("request_loan", request_loan_start),
            CommandHandler("advance", request_loan_start),
            MessageHandler(filters.Regex(r"^(💰 Request Loan|💰 የገንዘብ ብድር|💰 Liqii)"), request_loan_start),
            CallbackQueryHandler(request_loan_start, pattern=r"^menu_loan_request$"),
        ],
        states={
            FIN_TYPE: [
                CallbackQueryHandler(receive_fin_type, pattern=r"^(fintype_|fin_cancel)"),
            ],
            FIN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fin_amount),
            ],
            FIN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fin_reason),
            ],
            FIN_TERMS: [
                CallbackQueryHandler(receive_fin_terms_button, pattern=r"^(finterm_|fin_cancel)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fin_terms_text),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", fin_cancel_command),
            CallbackQueryHandler(fin_cancel_command, pattern=r"^fin_cancel$"),
        ],
        allow_reentry=True,
    )

def get_repayment_wizard():
    return ConversationHandler(
        entry_points=[
            CommandHandler("record_repayment", record_repayment_start),
            CallbackQueryHandler(record_repayment_start, pattern=r"^finmenu_repay_start$"),
        ],
        states={
            REPAY_INPUT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_repay_code),
            ],
            REPAY_INPUT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_repay_amount),
            ],
            REPAY_INPUT_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_repay_note),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", fin_cancel_command),
            CallbackQueryHandler(fin_cancel_command, pattern=r"^fin_cancel$"),
        ],
        allow_reentry=True,
    )
