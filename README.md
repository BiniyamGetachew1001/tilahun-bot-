# 🏗️ Telegram Site & Project Management Bot

An automated, text-first Telegram bot designed for construction and site project teams. It routes worker reports into Telegram Supergroup **Forum Topics**, manages numbered material requisitions, enforces worker identity and access control, tracks project status, and triggers automated daily cutoff reminders.

---

## ⚡ Key Features (All 7 Requirements Implemented)

1. **Worker Identity, Not Just Handles**:
   - Stores real **Full Name + Role** tied to immutable Telegram User IDs upon `/start`.
   - Every report and material request is auto-tagged with their verified identity (e.g. `👤 Reported by: Abebe Bikila (Site Foreman)`).

2. **Real-Time `/status` Command**:
   - Managers can run `/status` (or `/status ProjectAlpha`) anytime to get an immediate snapshot:
     - 🕒 Last daily report date, author & recap.
     - 📦 Open / pending material requisitions (`#MR-001`, `#MR-002`, ...).
     - 🚨 Unresolved issues & blockers.

3. **Automated Cutoff Reminders (7:00 PM)**:
   - Built-in scheduler checks every active project at the cutoff time (default `19:00`).
   - If no report was logged for a project today, it alerts that project's forum topic and notifies managers.

4. **Deferred Photo Uploads (Phase 2 Ready)**:
   - Phase 1 focuses on 100% frictionless text reporting.
   - The database schema includes `photo_file_ids` so photo proof-of-work attachments can be toggled on later without migrations.

5. **Numbered Material Requisitions (`#MR-001`)**:
   - Requisitions receive sequential human-readable codes (`#MR-001`, `#MR-014`).
   - Interactive buttons on cards: `[✅ Approve]` `[🚚 In Transit]` `[❌ Reject]`.
   - Text commands for managers: `/approve MR-014` or `/reject MR-014`.
   - Real-time updates directly on the card + DM notification to the requesting worker.

6. **Unified Multi-Tab Database & Excel Export (`/export_sheets`)**:
   - Single clean relational SQLite database (`site_manager.db`).
   - Managers can run `/export_sheets` at any time to receive a single Excel file with 4 structured tabs:
     - 📑 `Reports`
     - 📑 `MaterialRequests`
     - 📑 `Issues`
     - 📑 `Workers`

7. **Access Control From Day One**:
   - Unregistered/unapproved users cannot submit reports or requisitions.
   - Managers receive instant approval alerts with `[Approve]` / `[Reject]` buttons when new workers sign up.

---

## 🚀 Quick Setup Guide

### 1. Configure `.env`
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and fill in:
* `BOT_TOKEN`: Token from `@BotFather`
* `SUPERGROUP_CHAT_ID`: Your Telegram Supergroup ID (e.g. `-1001234567890`)
* `ADMIN_IDS`: Your numeric Telegram User ID (e.g. `12345678`)

### 2. How to Get Topic IDs in Telegram Supergroup
1. In your Supergroup, enable **Topics** in Group Settings.
2. Create topics (e.g., *Project Alpha*, *Project Beta*, *Material Requisitions*).
3. In Telegram Desktop or Web, right-click any message inside a Topic and select **Copy Link**.
4. The link looks like `https://t.me/c/1234567890/28` — `28` is your **Topic Thread ID**!
5. Put these IDs in `.env`.

### 3. Run the Bot
```powershell
python main.py
```

---

## 📋 Available Commands

| Command | Role | Description |
| :--- | :--- | :--- |
| `/admin` or `/control` | Managers | **Interactive Controller Dashboard** (Buttons to create projects, deadlines, view progress) |
| `/start` | All | Register Name + Role / Access onboarding menu |
| `/report` | Workers | Submit progress report wizard (☀️ Day / 🌙 Night, Voice/Text, Progress %) |
| `/night_report` | Workers | Direct shortcut to submit a 🌙 Night Shift progress report |
| `/progress` | All | Quick command to update or view visual project progress bars |
| `/status` | All | Real-time project snapshot, deadline countdown & progress bar |
| `/request_material` | Workers | Submit material requisition (`#MR-XXX`) |
| `/approve <MR-ID>` | Managers | Approve a material request (e.g. `/approve MR-001`) |
| `/reject <MR-ID>` | Managers | Reject a material request |
| `/export_sheets` | Managers | Download 5-tab Excel export (`Projects`, `Reports`, `MaterialRequests`, `Issues`, `Workers`) |
| `/projects` | All | View all active projects with visual progress bars and deadlines |
| `/create_project` | Managers | Wizard to create a new project + Telegram Topic with a deadline |
| `/workers` | Managers | View team roster and approval status |
| `/approve_worker <ID>` | Managers | Approve a pending worker account |
| `/weekly_report` | Managers | **Weekly Worker Activity Digest** (7-day employee breakdown & missed reports) |
| `/check_reports` | Managers | Manually trigger Day & Night cutoff checks |
