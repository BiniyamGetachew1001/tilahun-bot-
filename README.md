# 🏗️ Telegram Site & Project Management Bot

An automated, 1-on-1 text-first Telegram bot designed for site construction, field operations, employee financial loans/advances, and team management. It operates directly in private Direct Messages (no Telegram group required!), manages numbered material requisitions, tracks project progress, handles employee loan requests, broadcasts announcements to all staff, and triggers automated daily cutoff reminders.

---

## ⚡ Key Features

1. **Direct Bot-Only Architecture (No Supergroup Required)**:
   - Eliminates complex group/forum topic setup.
   - All interactions happen 1-on-1 in Telegram DMs between workers and the bot.
   - Manager approval alerts, shift reports, and material requests route directly to Managers' DMs with interactive action buttons.

2. **📢 Admin Broadcast & Announcement System (`/broadcast`)**:
   - Managers can broadcast company announcements (rich text, photos with captions) to all registered and approved employees.
   - Interactive preview with audience headcount before broadcasting.
   - High-throughput delivery with rate-limiting and a final delivery report (e.g. `Delivered: 15/15 workers`).
   - Announcements archive accessible to employees via `/announcements`.

3. **💰 Employee Loans & Financial Advances Management (`/request_loan`, `/finance`)**:
   - **Employee Request Form**: Step-by-step wizard for workers to request `Salary Advance`, `Personal Loan`, or `Expense Reimbursement` with amount validation, reason, and repayment terms.
   - **Manager Review**: Instant DM notification to managers with action buttons: `[✅ Approve]`, `[❌ Reject]`, `[💵 Mark Disbursed]`.
   - **Repayment Tracking (`/record_repayment`)**: Managers can record payroll deductions or cash repayments against active loan codes (`#LN-001`), automatically calculating remaining balances.
   - **Worker Self-Service (`/my_loans`)**: Workers can check their borrowed amounts, total repaid, and remaining balance anytime.
   - **Financial Dashboard (`/finance`)**: Summary metrics of pending requests, total disbursed, total repaid, and outstanding company balances.

4. **Worker Identity, Not Just Handles**:
   - Stores real **Full Name + Role** tied to immutable Telegram User IDs upon `/start`.
   - Every report, material request, and loan application is auto-tagged with their verified identity.

5. **Numbered Material Requisitions (`#MR-001`)**:
   - Sequential human-readable codes (`#MR-001`, `#MR-014`).
   - Interactive buttons on cards: `[✅ Approve]`, `[🚚 In Transit]`, `[❌ Reject]`.
   - Text commands for managers: `/approve MR-014` or `/reject MR-014`.
   - Real-time updates directly on the card + DM notification to the requesting worker.

6. **Automated Cutoff Reminders (7:00 PM / 7:00 AM)**:
   - Scheduler checks every active project at Day cutoff (`19:00`) and Night cutoff (`07:00`).
   - Sends friendly nudges directly to workers who haven't submitted reports today.
   - Dispatches a consolidated missed report alert directly to Managers.

7. **Unified Multi-Tab Database & Excel Export (`/export_sheets`)**:
   - Single clean relational SQLite database (`site_manager.db`) with optional PostgreSQL support.
   - Managers can run `/export_sheets` at any time to download an Excel file with 7 structured tabs:
     - 📑 `Projects`
     - 📑 `Reports`
     - 📑 `MaterialRequests`
     - 📑 `FinancialRequests`
     - 📑 `Announcements`
     - 📑 `Issues`
     - 📑 `Workers`

8. **Multilingual Support**:
   - Supports **English**, **Amharic (አማርኛ)**, and **Afaan Oromoo**.
   - Switch language anytime using `/language`.

---

## 🚀 Quick Setup Guide

### 1. Configure `.env`
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and fill in:
* `BOT_TOKEN`: Token from `@BotFather`
* `ADMIN_IDS`: Your numeric Telegram User ID (e.g. `12345678`)
* `DEFAULT_CURRENCY`: Currency code (default `ETB`)
* `SUPERGROUP_CHAT_ID`: Set to `0` for pure Bot-Only mode (or set group ID if legacy group posting is desired).

### 2. Run the Bot
```powershell
python main.py
```

---

## 📋 Available Commands

| Command | Role | Description |
| :--- | :--- | :--- |
| `/start` | All | Register Name + Role / Open bottom navigation menu |
| `/menu` | All | Interactive Actions Dashboard & Buttons |
| `/report` | Workers | Submit progress report wizard (☀️ Day / 🌙 Night, Voice/Text, Progress %) |
| `/night_report` | Workers | Direct shortcut to submit a 🌙 Night Shift progress report |
| `/request_material` | Workers | Submit material requisition (`#MR-XXX`) |
| `/request_loan` or `/advance` | Workers | Apply for Salary Advance, Personal Loan, or Expense Reimbursement |
| `/my_loans` | Workers | View active loans, repaid amounts, and outstanding balance |
| `/announcements` | All | View recent official company announcements |
| `/status` | All | Real-time project snapshot, deadline countdown & progress bar |
| `/projects` | All | View all active projects with visual progress bars and deadlines |
| `/profile` | All | View worker identity, status, and active loan balance |
| `/language` | All | Change language: English / አማርኛ / Afaan Oromoo |
| `/admin` | Managers | Interactive Controller Dashboard |
| `/finance` | Managers | Company financial management board (metrics, pending loans, balances) |
| `/broadcast` or `/announce`| Managers | Broadcast announcement message/photo to all employees |
| `/record_repayment` | Managers | Record repayment or salary deduction for a loan code (`#LN-XXX`) |
| `/approve <MR-ID>` | Managers | Approve a material request (e.g. `/approve MR-001`) |
| `/reject <MR-ID>` | Managers | Reject a material request |
| `/create_project` | Managers | Wizard to create a new project with a deadline |
| `/export_sheets` | Managers | Download 7-tab master Excel export |
| `/sync_sheets` | Managers | Synchronize live data with Google Sheets |
| `/workers` | Managers | View team roster and approval status |
| `/approve_worker <ID>` | Managers | Approve a pending worker account |
| `/weekly_report` | Managers | 7-day employee consistency & missed report breakdown |
| `/check_reports` | Managers | Manually trigger Day & Night cutoff checks |
