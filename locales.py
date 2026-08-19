# Multi-language translations for Telegram Site Management Bot
# Supported: English (en), Amharic (am), Afaan Oromoo (om)

LANGUAGES = {
    "en": {"name": "English"},
    "am": {"name": "አማርኛ"},
    "om": {"name": "Afaan Oromoo"},
}

STRINGS = {
    # --- Navigation & Buttons ---
    "btn_main_menu": {
        "en": "📱 Main Menu",
        "am": "📱 ዋና ማውጫ",
        "om": "📱 Baafata Guddaa"
    },
    "btn_day_report": {
        "en": "☀️ Day Report",
        "am": "☀️ የቀን ሪፖርት",
        "om": "☀️ Gabaasa Guyyaa"
    },
    "btn_night_report": {
        "en": "🌙 Night Report",
        "am": "🌙 የማታ ሪፖርት",
        "om": "🌙 Gabaasa Halkan"
    },
    "btn_request_material": {
        "en": "📦 Request Material",
        "am": "📦 ዕቃ ማዘዣ",
        "om": "📦 Gaaffii Meeshaa"
    },
    "btn_project_status": {
        "en": "📊 Project Status",
        "am": "📊 የፕሮጀክት ሁኔታ",
        "om": "📊 Haala Piroojektii"
    },
    "btn_projects": {
        "en": "🏗️ All Projects",
        "am": "🏗️ ሁሉም ፕሮጀክቶች",
        "om": "🏗️ Piroojektii Hundaa"
    },
    "btn_my_profile": {
        "en": "👤 My Profile",
        "am": "👤 የኔ መረጃ",
        "om": "👤 Profaayilii Koo"
    },
    "btn_admin_panel": {
        "en": "🎛️ Manager Panel",
        "am": "🎛️ የአስተዳዳሪ ሰሌዳ",
        "om": "🎛️ Gabatee Gaggeessaa"
    },
    "btn_language": {
        "en": "🌐 Language / ቋንቋ / Afaan",
        "am": "🌐 ቋንቋ / Language / Afaan",
        "om": "🌐 Afaan / Language / ቋንቋ"
    },
    "btn_sync_sheets": {
        "en": "🔄 Sync Sheets",
        "am": "🔄 ጉግል ሺት አመሳስል",
        "om": "🔄 Google Sheets Wal-simsiisi"
    },
    "btn_export_excel": {
        "en": "📥 Export Excel",
        "am": "📥 ኤክሴል አውርድ",
        "om": "📥 Excel Buusi"
    },
    "btn_cancel": {
        "en": "❌ Cancel",
        "am": "❌ ሰርዝ",
        "om": "❌ Dhiisi"
    },
    "btn_skip_photo": {
        "en": "⏩ Skip Photo",
        "am": "⏩ ፎቶ ዝለል",
        "om": "⏩ Suuraa Darbi"
    },

    # --- Language Selection ---
    "choose_language": {
        "en": "🌐 *Choose Your Preferred Language:*\nይምረጡ | Filadhaa:",
        "am": "🌐 *የሚፈልጉትን ቋንቋ ይምረጡ:*\nይምረጡ | Choose | Filadhaa:",
        "om": "🌐 *Afaan barbaaddan filadhaa:*\nFiladhaa | Choose | ይምረጡ:"
    },
    "language_updated": {
        "en": "✅ Language changed to *English*.",
        "am": "✅ ቋንቋ ወደ *አማርኛ* ተቀይሯል።",
        "om": "✅ Afaan gara *Afaan Oromoo*tti jijjiirameera."
    },

    # --- Onboarding & Auth ---
    "onboarding_welcome": {
        "en": "👋 *Welcome to the Site Management Bot!*\n\nLet's get you set up. What is your *Full Name*?",
        "am": "👋 *እንኳን ወደ ሳይት ማኔጅመንት ቦት በደህና መጡ!*\n\nመለያዎን ለማዘጋጀት እባክዎ *ሙሉ ስምዎን* ያስገቡ:",
        "om": "👋 *Baga nagaan gara Bootii Saayitii dhuftan!*\n\nQophii xumuruuf maaloo *Maqaa Keessan Guutuu* galchaa:"
    },
    "onboarding_select_role": {
        "en": "Nice to meet you, *{name}*!\n\nSelect your *Role / Position* on site:",
        "am": "እንኳን ተዋወቅን *{name}*!\n\nእባክዎ በሳይቱ ላይ ያለዎትን *የስራ ድርሻ (ሚና)* ይምረጡ:",
        "om": "Baga wal barre *{name}*!\n\nMaaloo *Gahee Hojii* keessan filadhaa:"
    },
    "role_foreman": {
        "en": "Site Foreman",
        "am": "የሳይት ፎርማን",
        "om": "Foormaanii Saayitii"
    },
    "role_engineer": {
        "en": "Site Engineer",
        "am": "የሳይት መሃንዲስ",
        "om": "Injinara Saayitii"
    },
    "role_pm": {
        "en": "Project Manager",
        "am": "የፕሮጀክት ስራ አስኪያጅ",
        "om": "Hojii Gaggeessaa Piroojektii"
    },
    "role_safety": {
        "en": "Safety Officer",
        "am": "የደህንነት ኦፊሰር",
        "om": "Ofisara Nageenyaa"
    },
    "role_surveyor": {
        "en": "Quantity Surveyor",
        "am": "የቁሳቁስ መሃንዲስ (QS)",
        "om": "Injinara Qabeenyaa"
    },
    "role_subcontractor": {
        "en": "Subcontractor Lead",
        "am": "ንዑስ ስራ ተቋራጭ",
        "om": "Hoggansa Kontiraaktaraa"
    },
    "onboarding_approved_instant": {
        "en": "🎉 *Registration Complete!*\n\n👤 *Name:* {name}\n👷 *Role:* {role}\n\nUse the buttons below to log reports and material requests:",
        "am": "🎉 *ምዝገባዎ ተጠናቋል!*\n\n👤 *ስም:* {name}\n👷 *የስራ ድርሻ:* {role}\n\nሪፖርት እና የዕቃ ጥያቄዎችን ለማስገባት ከታች ያሉትን ቁልፎች ይጠቀሙ:",
        "om": "🎉 *Galmeen Xumurameera!*\n\n👤 *Maqaa:* {name}\n👷 *Gahee Hojii:* {role}\n\nGabaasaa fi meeshaa gaafachuuf qabduuwwan armaan gadii fayyadamaa:"
    },
    "onboarding_pending_approval": {
        "en": "⏳ *Registration Submitted!*\n\n👤 *Name:* {name}\n👷 *Role:* {role}\n\nYour account is pending manager approval. You will receive a notification once approved.",
        "am": "⏳ *የምዝገባ ጥያቄዎ ተልኳል!*\n\n👤 *ስም:* {name}\n👷 *የስራ ድርሻ:* {role}\n\nመለያዎ በአስተዳዳሪ እስኪጸድቅ ድረስ እባክዎ ይጠብቁ። ሲጸድቅ ማሳወቂያ ይደርስዎታል።",
        "om": "⏳ *Iyyanni Galmee Ergameera!*\n\n👤 *Maqaa:* {name}\n👷 *Gahee Hojii:* {role}\n\nEeyyama gaggeessaa eegaa jira. Yeroo mirkanaa'u beeksisni isiniif ergama."
    },
    "unauthorized_msg": {
        "en": "⚠️ You must first register with `/start` before submitting reports.",
        "am": "⚠️ ሪፖርት ከማስገባትዎ በፊት እባክዎ መጀመሪያ በ `/start` ይመዝገቡ።",
        "om": "⚠️ Gabaasa erguun dura mee `/start` fayyadamuun galmaa'aa."
    },
    "pending_msg": {
        "en": "⏳ Your account is pending manager approval. Please wait until approved.",
        "am": "⏳ መለያዎ በአስተዳዳሪ እየታየ ነው። እባክዎ እስኪጸድቅ ድረስ ይጠብቁ።",
        "om": "⏳ Herregni keessan mirkanaa'uu eegaa jira. Mee hanga eeyyamamutti eegaa."
    },

    # --- Shift Reports Wizard ---
    "rep_select_project": {
        "en": "Select the *Project* you are reporting for:",
        "am": "ሪፖርት የሚያቀርቡለትን *ፕሮጀክት* ይምረጡ:",
        "om": "Piroojektii gabaasa dhiyeessitaniif filadhaa:"
    },
    "rep_select_shift": {
        "en": "🏗️ *Project:* {project}\n\nSelect the *Working Shift*:",
        "am": "🏗️ *ፕሮጀክት:* {project}\n\nየስራ *ፈረቃ* ይምረጡ:",
        "om": "🏗️ *Piroojektii:* {project}\n\n*Gareen Hojii* filadhaa:"
    },
    "rep_step1_work": {
        "en": "📋 *{shift_label} Report — {project}*\n\nStep 1/5: *What work was completed {time_scope}?*\n(Type a summary or record a 🎙️ Voice Message):",
        "am": "📋 *{shift_label} ሪፖርት — {project}*\n\nደረጃ 1/5: *{time_scope} ምን ስራ ተጠናቀቀ?*\n(በጽሁፍ ይግለጹ ወይም በ 🎙️ የድምጽ መልዕክት ይላኩ):",
        "om": "📋 *{shift_label} Gabaasa — {project}*\n\nSadarkaa 1/5: *{time_scope} hojiin maaltu xumurame?*\n(Barreeffamaan ykn 🎙️ Sagaleen ergaa):"
    },
    "rep_step2_plan": {
        "en": "Step 2/5: *What is the plan {time_scope}?*\n(List scheduled tasks or send a 🎙️ Voice Message):",
        "am": "ደረጃ 2/5: *{time_scope} እቅድዎ ምንድን ነው?*\n(የታቀዱ ስራዎችን በጽሁፍ ይዘርዝሩ ወይም በ 🎙️ ድምጽ ይላኩ):",
        "om": "Sadarkaa 2/5: *{time_scope} karoora maaltu qabama?*\n(Hojiiwwan karoorfaman tarreessaa ykn 🎙️ Sagaleen ergaa):"
    },
    "rep_step3_blockers": {
        "en": "Step 3/5: *Any {blocker_prompt}?*\n(Type *None* if no issues, or describe the problem):",
        "am": "ደረጃ 3/5: *ያጋጠሙ {blocker_prompt}?*\n(ምንም ችግር ከሌለ *የለም* ወይም *None* ይበሉ፣ ካለ በዝርዝር ይግለጹ):",
        "om": "Sadarkaa 3/5: *{blocker_prompt} maaltu mudate?*\n(Rakkoon yoo hin jirre *Hinjiru* ykn *None* jedhaa, yoo jiraate ibsaa):"
    },
    "rep_step4_photo": {
        "en": "Step 4/5: 📸 *Site Progress Photos*\n\nSend a photo showing the work done, or click *Skip Photo* below:",
        "am": "ደረጃ 4/5: 📸 *የሳይት ስራ ፎቶ*\n\nየተሰራውን ስራ የሚያሳይ ፎቶ ይላኩ፣ ወይም ከታች *ፎቶ ዝለል* የሚለውን ይጫኑ:",
        "om": "Sadarkaa 4/5: 📸 *Suuraa Hojii Saayitii*\n\nSuuraa hojii xumuramee ergaa, ykn armaan gaditti *Suuraa Darbi* filadhaa:"
    },
    "rep_step5_progress": {
        "en": "Step 5/5: *Overall Project Completion Percentage:*\n\nCurrent Progress: {bar}\nSelect updated percentage below or *type any number (0-100)*:",
        "am": "ደረጃ 5/5: *አጠቃላይ የፕሮጀክት እድገት በመቶኛ (%):*\n\nየአሁን እድገት: {bar}\nየተሻሻለውን ቁጥር ከታች ይምረጡ ወይም *ይጻፉ (0-100)*:",
        "om": "Sadarkaa 5/5: *Sadarkaa Raawwii Piroojektii Guutuu (%):*\n\nHaala amma jiru: {bar}\nParsantaa haaraa filadhaa ykn *lakkoofsa barreessaa (0-100)*:"
    },
    "rep_success_confirm": {
        "en": "🎉 *{shift_badge} Report Logged!* (Report #{report_id}){photo_note}\n\n{card}",
        "am": "🎉 *{shift_badge} ሪፖርት ተመዝግቧል!* (ሪፖርት #{report_id}){photo_note}\n\n{card}",
        "om": "🎉 *{shift_badge} Gabaasni Galmaa'eera!* (Gabaasa #{report_id}){photo_note}\n\n{card}"
    },

    # --- Material Requests Wizard ---
    "mr_select_project": {
        "en": "📦 *Material Requisition (#MR)*\n\nSelect the *Project* needing materials/tools:",
        "am": "📦 *የዕቃ እና ቁሳቁስ ማዘዣ (#MR)*\n\nዕቃው የሚፈለግበትን *ፕሮጀክት* ይምረጡ:",
        "om": "📦 *Gaaffii Meeshaa fi Meeshaalee (#MR)*\n\nPiroojektii meeshaan barbaachisu filadhaa:"
    },
    "mr_step1_desc": {
        "en": "📦 *Material Request — {project}*\n\nStep 1/2: *What items and quantities do you need?*\n(e.g., `50 bags Cement, 20 pcs 16mm Rebar, 2 Wheelbarrows`):",
        "am": "📦 *የዕቃ ማዘዣ — {project}*\n\nደረጃ 1/2: *ምን ዓይነት ዕቃዎች እና በምን ያህል መጠን ያስፈልጋሉ?*\n(ምሳሌ: `50 ቦርሳ ሲሚንቶ፣ 20 ባለ 16ሚሜ ብረት፣ 2 ጋሪ`):",
        "om": "📦 *Gaaffii Meeshaa — {project}*\n\nSadarkaa 1/2: *Meeshaalee fi hamma meeqatu barbaachisa?*\n(Fkn: `Simintoo kiisha 50, Sibiila 16mm 20, Gaarii 2`):"
    },
    "mr_step2_urgency": {
        "en": "Step 2/2: *Select Urgency Level:*",
        "am": "ደረጃ 2/2: *የአስቸኳይነት ደረጃ ይምረጡ:*",
        "om": "Sadarkaa 2/2: *Sadarkaa Ariifachiisummaa filadhaa:*"
    },
    "urgency_normal": {
        "en": "🟢 Normal (2-3 Days)",
        "am": "🟢 መደበኛ (በ2-3 ቀናት ውስጥ)",
        "om": "🟢 Idilee (Guyyoota 2-3)"
    },
    "urgency_urgent": {
        "en": "🟡 Urgent (Tomorrow)",
        "am": "🟡 አስቸኳይ (ለነገ)",
        "om": "🟡 Ariifachiisaa (Boriif)"
    },
    "urgency_emergency": {
        "en": "🔴 Emergency (Immediate Site Stoppage)",
        "am": "🔴 እጅግ አስቸኳይ (ስራ የሚያቆም)",
        "om": "🔴 Ariifachiisaa Ol'aanaa (Hojii Dhaaba)"
    },
    "mr_success_confirm": {
        "en": "✅ *Material Requisition Submitted!* (#{mr_code})\n\n{card}\n\nNotification dispatched to managers.",
        "am": "✅ *የዕቃ ማዘዣ ጥያቄዎ ተልኳል!* (#{mr_code})\n\n{card}\n\nለአስተዳዳሪዎች ማሳወቂያ ተልኳል።",
        "om": "✅ *Gaaffiin Meeshaa Ergameera!* (#{mr_code})\n\n{card}\n\nBeeksisni gara gaggeessitootaatti ergameera."
    },
}

def t(key: str, lang: str = "en", **kwargs) -> str:
    """Translates a key into the target language with variable interpolation."""
    lang = lang if lang in LANGUAGES else "en"
    lang_dict = STRINGS.get(key, {})
    template = lang_dict.get(lang) or lang_dict.get("en") or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template

def get_user_lang(user_id: int) -> str:
    """Fetches user language from database with fallback to English."""
    from database import get_worker_lang
    try:
        return get_worker_lang(user_id) or "en"
    except Exception:
        return "en"
