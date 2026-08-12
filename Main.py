import logging
import os
import threading
import re  # [NEW UPDATE] Added for phone validation
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

# [NEW UPDATE] Supabase Import
from supabase import create_client, Client

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_IDS = [1622298145, 389487101]  # Both Admin IDs

# Banking & Payment Info
CBE_ACCOUNT = "1000357796532"
TELEBIRR_NUMBER = "0939998090"
ACCOUNT_NAME = "Simon mulugeta"
SUPPORT_HANDLE = "@s_simon_19"
BOT_2_USERNAME = "SimonOrigin_Tracking_Bot"  # [NEW UPDATE] Replace with your actual Bot 2 handle

# Reminder Delays (in seconds)
REMINDER_DELAY_SECONDS = 3 * 60 * 60       # 3 hours for standard steps
PAYMENT_REMINDER_DELAY = 2 * 60 * 60       # 2 hours for payment recovery

# Google Sheets Configuration
GOOGLE_SHEET_NAME = "Fitness Clients"
CREDENTIALS_FILE = "credentials.json"

# [NEW UPDATE] Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client if credentials exist
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None
    logging.warning("Supabase credentials missing. Database sync disabled.")

# Conversation States (Primary Onboarding & Verification)
(
    LANGUAGE,
    GENDER,
    LOCATION,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    PHONE,
    DURATION,
    RECEIPT,
) = range(10)

# Post-Approval Questionnaire States
(
    POST_ACTIVITY,
    POST_EXPERIENCE,
    POST_EQUIPMENT,
    POST_OBSTACLE,
    POST_READINESS,
    POST_HEALTH,
    POST_DIET,
    POST_EATING_STYLE,
) = range(10, 18)


# ==========================================
# 🌐 WEB SERVER FOR RENDER KEEP-ALIVE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot 1 is alive!")

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()


# ==========================================
# 🗄️ SUPABASE SYNC HELPERS [NEW UPDATE]
# ==========================================
def sync_client_to_supabase(user_id, full_name, username, phone=None, goal=None, package=None, language=None):
    if not supabase: return
    try:
        data = {
            "id": user_id,
            "full_name": full_name,
            "username": username or "",
            "updated_at": "now()"
        }
        if phone: data["phone_number"] = phone
        if goal: data["goal"] = goal
        if package: data["package"] = package
        if language: data["language"] = language
        
        supabase.table("clients").upsert(data).execute()
    except Exception as e:
        logging.error(f"Supabase Client Sync Error: {e}")

def record_receipt_in_supabase(user_id, file_id):
    if not supabase: return
    try:
        supabase.table("client_media").insert({
            "client_id": user_id,
            "media_type": "receipt",
            "telegram_file_id": file_id,
            "status": "pending"
        }).execute()
    except Exception as e:
        logging.error(f"Supabase Receipt Sync Error: {e}")

def save_assessment_to_supabase(user_id, baseline_weight):
    if not supabase: return
    try:
        supabase.table("clients").update({
            "baseline_weight": baseline_weight,
            "updated_at": "now()"
        }).eq("id", user_id).execute()
    except Exception as e:
        logging.error(f"Supabase Assessment Sync Error: {e}")


# ==========================================
# 📊 GOOGLE SHEETS & TIMESTAMP SYNC
# ==========================================
def save_lead_to_google_sheet(user_data, user):
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE, scope
        )
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1

        registration_timestamp = datetime.now().strftime("%Y-%b-%d %H:%M:%S")

        row_data = [
            registration_timestamp,
            user.full_name,
            user.username or "None",
            int(user.id),
            user_data.get("phone", ""),
            "Ethiopia" if user_data.get("location_type") == "et" else "Diaspora",
            user_data.get("duration", ""),
            user_data.get("price", ""),
            "Paid",
            user_data.get("gender", "Unknown"),
            int(user_data.get("age", 0)) if user_data.get("age") else 0,
            int(user_data.get("height", 0)) if user_data.get("height") else 0,
            int(user_data.get("weight", 0)) if user_data.get("weight") else 0,
            user_data.get("goal", "General"),
            user_data.get("activity", "Unknown"),
            user_data.get("experience", "Unknown"),
            user_data.get("equipment", "Unknown"),
            user_data.get("obstacle", "Unknown"),
            int(user_data.get("readiness", 0)) if user_data.get("readiness") else 0,
            user_data.get("injuries", "None"),
            user_data.get("diet", "None"),
            user_data.get("eating_style", "Unknown"),
        ]

        sheet.append_row(row_data)
        logging.info("Successfully saved client and timestamp to Google Sheet!")
    except Exception as e:
        logging.error(f"Exception while saving to Google Sheet: {e}")


# ==========================================
# ⏰ REMINDERS & RECOVERY JOBS
# ==========================================
def _reminder_job_name(prefix, chat_id):
    return f"{prefix}_{chat_id}"

def schedule_reminder(context: ContextTypes.DEFAULT_TYPE, prefix, chat_id, lang, delay=REMINDER_DELAY_SECONDS):
    if context.job_queue is None:
        return
    job_name = _reminder_job_name(prefix, chat_id)
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
        
    if prefix == "onboarding_reminder":
        callback = send_onboarding_reminder
    elif prefix == "payment_reminder":
        callback = send_payment_abandonment_reminder
    else:
        callback = send_assessment_reminder

    context.job_queue.run_repeating(
        callback,
        interval=delay,
        first=delay,
        chat_id=chat_id,
        name=job_name,
        data={"lang": lang},
    )

def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, prefix, chat_id):
    if context.job_queue is None:
        return
    job_name = _reminder_job_name(prefix, chat_id)
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()

async def send_onboarding_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    text = (
        "👋 <b>ገና አልጨረሱም!</b>\n\nምዝገባዎን ገና አላጠናቀቁም። ከላይ ላለው ጥያቄ በመመለስ ይቀጥሉ፣ ወይም ከመጀመሪያ ለመጀመር /start ይላኩ።"
        if lang == "am"
        else "👋 <b>Still with us?</b>\n\nYou started registering but haven't finished yet. Reply to my last question above to continue, or send /start to begin again."
    )
    try:
        await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send onboarding reminder to {job.chat_id}: {e}")

async def send_payment_abandonment_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    if lang == "am":
        text = (
            "💳 <b>ክፍያ ለመፈጸም እርዳታ ይፈልጋሉ?</b>\n\n"
            "የመረጡትን ፕሮግራም ለማስጀመር ዝግጁ ነን! የክፍያ ሂደቱ ካልገባዎት ወይም ተጨማሪ ጥያቄ ካለዎት በቀጥታ ሳይመን ያግኙ፦\n\n"
            f"📲 <b>እርዳታ ለማግኘት:</b> {SUPPORT_HANDLE}"
        )
    else:
        text = (
            "💳 <b>Need help completing your payment?</b>\n\n"
            "We're ready to build your customized plan! If you have any questions or payment issues, reach out directly to Simon:\n\n"
            f"📲 <b>Contact Simon:</b> {SUPPORT_HANDLE}"
        )
    try:
        await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send payment reminder to {job.chat_id}: {e}")

async def send_assessment_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    text = (
        "👋 <b>ገና ጥቂት ጥያቄዎች ይቀሩዎታል!</b>\n\nክፍያዎ ጸድቋል፣ ነገር ግን የግምገማ ጥያቄዎቹን ገና አላጠናቀቁም። ከላይ ላለው ጥያቄ በመመለስ ዕቅድዎ እንዲዘጋጅ ይርዱን!"
        if lang == "am"
        else "👋 <b>A few questions left!</b>\n\nYour payment is approved, but you haven't finished the quick assessment yet. Answer my last question above so we can start building your plan!"
    )
    try:
        await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send assessment reminder to {job.chat_id}: {e}")


# ==========================================
# 🛑 GLOBAL CANCEL FALLBACK [NEW UPDATE]
# ==========================================
async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🔄 <b>ሂደቱ ተቋርጧል! / Process cancelled.</b>\n\nእንደገና ለመጀመር /start ይበሉ።",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ==========================================
# 📋 FAQ & PRICING CLARITY HELPERS
# ==========================================
def get_faq_text(loc):
    if loc == "et":
        return (
            "📋 <b>የፕሮግራሞች ዝርዝር እና ተደጋጋሚ ጥያቄዎች (FAQ)</b>\n\n"
            "• <b>የምግብ እቅድ (799 ETB):</b> በሰውነትዎ እና በግብዎ ላይ የተመረኮዘ፣ ውጤቱን በግልጽ የሚያሳይ ልዩ የምግብ ዝግጅት እቅድ ከኮች ክትትል ጋር!\n\n"
            "• <b>ፈጣን ጅማሬ / 21 ቀናት (3,500 ETB):</b> የለውጡ የመጀመሪያ አስደናቂ እርምጃ! ለጀማሪዎች ምርጥ ጀምሮ ፈጣን ውጤት ለማምጣት—ቋሚ የስፖርት ዕቅድ፣ 1 የምግብ ዕቅድ፣ 1 ማስተካከያ እና 3 የኮች ክትትሎችን ያካትታል።\n\n"
            "• <b>የሰውነት ለውጥ / 60 ቀናት (7,000 ETB):</b> እውነተኛ የሰውነት መለወጫ ጉዞ! ስብን አቀልጦ ጡንቻን ለመገንባት—በየ 4 ሳምንቱ የሚቀየር ስፖርት፣ የተስተካከለ የምግብ ዕቅድ፣ 8 የሳይመን የግል ክትትሎች እና የአሰራር ግምገማ።\n\n"
            "• <b>Elite / 90 ቀናት (9,500 ETB):</b> ለረጅም ጊዜ የሚዘልቅ ጠንካራ እና አሸናፊ ውጤት! ሙሉ በሙሉ ለእርስዎ የተለየ ስፖርት፣ ያልተወሰነ የምግብ ማስተካከያ፣ ~13 የሳይመን የግል ክትትሎች እና የ24 ሰዓት ቅድሚያ ድጋፍ።\n\n"
            "• <b>Lifestyle / 6 ወራት (18,000 ETB):</b> የአኗኗር ዘይቤዎን በዘላቂነት የሚቀይር አስደናቂ ጉዞ! በየወሩ አዲስ የስፖርት ምዕራፍ፣ ቀጣይነት ያለው እቅድ፣ ወርሃዊ የግብ ማስተካከያ እና የሳይመን የግል ክትትልን ያካተተ።\n\n"
            "• <b>ቪአይፒ / 6 ወራት (30,000 ETB):</b> ፍጹም የ1-ለ-1 ልዩ ድጋፍ እና ከፍተኛው የትኩረት ደረጃ! በየጊዜው የሚስተካከሉ እቅዶች፣ ሳምንታዊ የቪዲዮ ጥሪዎች፣ ያልተወሰነ መልዕክት መለዋወጥ፣ የተጨማሪ ምግብ መምሪያ እና የሳይመን ሙሉ የግል ክትትል!\n\n"
            "<b>ተደጋጋሚ ጥያቄዎች (FAQ)</b>\n\n"
            "• <b>ጥያቄ፡ እንዴት መጀመር እችላለሁ?</b>\n"
            "መልስ፡ መጀመሪያ ግቦችዎን፣ የአካል ብቃት ደረጃዎን እና ቋንቋዎን በመምረጥ ይመዝገቡ፤ ከዚያም የሚፈልጉትን ፓኬጅ ይምረጡ።\n\n"
            "• <b>ጥያቄ፡ ክፍያ እንዴት ይፈጸማል?</b>\n"
            "መልስ፡ ክፍያ ከፈጸሙ በኋላ የክፍያ ማረጋገጫ ፎቶ (Screenshot) ወደ ቦቱ ይላኩ። በአስተዳዳሪው ከተረጋገጠ በኋላ ወዲያውኑ ወደ ፕሮግራሙ መዳረሻ ያገኛሉ።\n\n"
            f"ጥያቄ ካለዎት በቀጥታ ያግኙን፦ {SUPPORT_HANDLE}"
        )
    else:
        return (
            "📋 <b>Program Details & Clarity (FAQ)</b>\n\n"
            "• <b>Meal Plan Only ($29.99):</b> Custom nutrition plan tailored precisely to your goals.\n\n"
            "• <b>Kickstart / 21 Days ($35):</b> Best for beginners building momentum. Includes fixed workout, 1 meal plan, 1 adjustment, and 3 check-ins.\n\n"
            "• <b>Transformation / 60 Days ($89):</b> Best for fat loss & muscle building. Includes workouts updated every 4 weeks, adjusted meal plan, 8 check-ins, and form reviews.\n\n"
            "• <b>Elite / 90 Days ($129):</b> Best for serious long-term results. Fully custom workouts, unlimited meal adjustments, ~13 check-ins, and 24-hr priority support.\n\n"
            "• <b>Lifestyle / 6 Months ($249):</b> Best for permanent lifestyle change. New workout phase monthly, continuous planning, ongoing check-ins, and monthly goal setting.\n\n"
            "• <b>VIP / 6 Months ($449):</b> Maximum 1-on-1 support. Live-adjusted plans, weekly video calls, unlimited messaging & form reviews, and supplement guidance.\n\n"
            f"❓ Questions? Contact Simon directly: {SUPPORT_HANDLE}"
        )

def get_pricing_keyboard(lang, loc_type):
    faq_btn_text = "📋 የፕሮግራም ዝርዝር ማየት (FAQ)" if lang == "am" else "📋 View Program Details (FAQ)"
    if lang == "am":
        if loc_type == "et":
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 የምግብ እቅድ ብቻ — 799 ETB", callback_data="dur_Meal_Plan_Only_799ETB")],
                [InlineKeyboardButton("🥉 ፈጣን ጅማሬ (21 ቀናት) — 3,500 ETB", callback_data="dur_Kickstart_(21_Days)_3500ETB")],
                [InlineKeyboardButton("🥈 የሰውነት ለውጥ (60 ቀናት) — 7,000 ETB", callback_data="dur_Transformation_(60_Days)_7000ETB")],
                [InlineKeyboardButton("🥇 Elite (90 ቀናት) — 9,500 ETB", callback_data="dur_Elite_Transformation_(90_Days)_9500ETB")],
                [InlineKeyboardButton("💎 Lifestyle (6 ወራት) — 18,000 ETB", callback_data="dur_Lifestyle_Coaching_(6_Months)_18000ETB")],
                [InlineKeyboardButton("👑 ቪአይፒ (6 ወራት) — 30,000 ETB", callback_data="dur_VIP_Coaching_(6_Months)_30000ETB")],
            ]
        else:
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 የምግብ እቅድ ብቻ — $29.99", callback_data="dur_Meal_Plan_Only_$29.99")],
                [InlineKeyboardButton("🥉 ፈጣን ጅማሬ (21 ቀናት) — $35", callback_data="dur_Kickstart_(21_Days)_$35")],
                [InlineKeyboardButton("🥈 የሰውነት ለውጥ (60 ቀናት) — $89", callback_data="dur_Transformation_(60_Days)_$89")],
                [InlineKeyboardButton("🥇 Elite (90 ቀናት) — $129", callback_data="dur_Elite_Transformation_(90_Days)_$129")],
                [InlineKeyboardButton("💎 Lifestyle (6 ወራት) — $249", callback_data="dur_Lifestyle_Coaching_(6_Months)_$249")],
                [InlineKeyboardButton("👑 ቪአይፒ (6 ወራት) — $449", callback_data="dur_VIP_Coaching_(6_Months)_$449")],
            ]
    else:
        if loc_type == "et":
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 Meal Plan Only — 799 ETB", callback_data="dur_Meal_Plan_Only_799ETB")],
                [InlineKeyboardButton("🥉 Kickstart (21 Days) — 3,500 ETB", callback_data="dur_Kickstart_(21_Days)_3500ETB")],
                [InlineKeyboardButton("🥈 Transformation (60 Days) — 7,000 ETB", callback_data="dur_Transformation_(60_Days)_7000ETB")],
                [InlineKeyboardButton("🥇 Elite (90 Days) — 9,500 ETB", callback_data="dur_Elite_Transformation_(90_Days)_9500ETB")],
                [InlineKeyboardButton("💎 Lifestyle (6 Months) — 18,000 ETB", callback_data="dur_Lifestyle_Coaching_(6_Months)_18000ETB")],
                [InlineKeyboardButton("👑 VIP (6 Months) — 30,000 ETB", callback_data="dur_VIP_Coaching_(6_Months)_30000ETB")],
            ]
        else:
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 Meal Plan Only — $29.99", callback_data="dur_Meal_Plan_Only_$29.99")],
                [InlineKeyboardButton("🥉 Kickstart (21 Days) — $35", callback_data="dur_Kickstart_(21_Days)_$35")],
                [InlineKeyboardButton("🥈 Transformation (60 Days) — $89", callback_data="dur_Transformation_(60_Days)_$89")],
                [InlineKeyboardButton("🥇 Elite (90 Days) — $129", callback_data="dur_Elite_Transformation_(90_Days)_$129")],
                [InlineKeyboardButton("💎 Lifestyle (6 Months) — $249", callback_data="dur_Lifestyle_Coaching_(6_Months)_$249")],
                [InlineKeyboardButton("👑 VIP (6 Months) — $449", callback_data="dur_VIP_Coaching_(6_Months)_$449")],
            ]

async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    text = get_faq_text(loc)

    back_text = "🔙 ወደ ዋጋዎች መመለስ" if lang == "am" else "🔙 Back to Pricing"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(back_text, callback_data=f"back_pricing_{loc}")]])
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def back_to_pricing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_type = query.data.split("_")[2]
    lang = context.user_data.get("lang", "am")

    keyboard = get_pricing_keyboard(lang, loc_type)
    text = (
        "⏱️ <b>ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦</b>\n\n💡 <i>እያንዳንዱ ፓኬጅ ምንን እንደሚያካትት ለማየት ከላይ ያለውን የዝርዝር መግለጫ (FAQ) ቁልፍ መጫን ይችላሉ።</i>"
        if lang == "am"
        else ("⏱️ <b>Select your transformation timeframe:</b>\n\n💡 <i>Tap the FAQ button above anytime to see what each tier includes.</i>")
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==========================================
# 🚀 STEP 1: /START & EARLY LEAD LOGGING
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()
    cancel_reminder(context, "onboarding_reminder", user.id)
    cancel_reminder(context, "payment_reminder", user.id)
    cancel_reminder(context, "assessment_reminder", user.id)

    # [NEW UPDATE] Log initial lead to Supabase
    sync_client_to_supabase(user.id, user.full_name, user.username)

    user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
    admin_log_msg = (
        f"🚨 <b>NEW LEAD STARTED BOT!</b>\n"
        f"👤 <b>User:</b> {user_link} (@{user.username or 'No_Username'})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>"
    )
    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_log_msg, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Failed to log early lead to admin {admin_id}: {e}")

    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇪🇹 አማርኛ (Amharic)", callback_data="lang_am"),
        ]
    ]
    await update.message.reply_text(
        "Welcome to Simon's Transformation Portal! Please select your language / እባክዎ ቋንቋ ይምረጡ፦",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return LANGUAGE


# ==========================================
# 👤 STEP 2: GENDER SELECTION
# ==========================================
async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    schedule_reminder(context, "onboarding_reminder", update.effective_user.id, lang)

    keyboard = [
        [
            InlineKeyboardButton("👨 ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"),
            InlineKeyboardButton("👩 ሴት" if lang == "am" else "👩 Female", callback_data="gen_female"),
        ]
    ]
    text = "👤 <b>ጾታዎን ይምረጡ፦</b>" if lang == "am" else "👤 <b>Select your gender:</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return GENDER


# ==========================================
# 📍 STEP 3: LOCATION SELECTION
# ==========================================
async def gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    gender = query.data.split("_")[1]
    context.user_data["gender"] = gender
    lang = context.user_data.get("lang", "am")

    if lang == "am":
        keyboard = [
            [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (በሀገር ውስጥ)", callback_data="loc_et")],
            [InlineKeyboardButton("🇺🇸 / 🇨🇦 አሜሪካ / ካናዳ", callback_data="loc_diaspora")],
            [InlineKeyboardButton("🇪🇺 / 🇬🇧 አውሮፓ / እንግሊዝ", callback_data="loc_diaspora")],
            [InlineKeyboardButton("🇦🇪 Middle East / 🌍 ሌላ ሀገር", callback_data="loc_diaspora")],
        ]
        text = "📍 <b>እባክዎ የሚኖሩበትን ሀገር ይምረጡ፦</b>"
    else:
        keyboard = [
            [InlineKeyboardButton("🇪🇹 Ethiopia (Local)", callback_data="loc_et")],
            [InlineKeyboardButton("🇺🇸 / 🇨🇦 USA / Canada", callback_data="loc_diaspora")],
            [InlineKeyboardButton("🇪🇺 / 🇬🇧 Europe / UK", callback_data="loc_diaspora")],
            [InlineKeyboardButton("🇦🇪 Middle East / 🌍 Other", callback_data="loc_diaspora")],
        ]
        text = "📍 <b>Please select your current country of residence:</b>"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return LOCATION


# ==========================================
# 📊 STEP 4: VITAL BODY STATS
# ==========================================
async def location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    location_type = query.data.split("_")[1]
    context.user_data["location_type"] = location_type
    lang = context.user_data.get("lang", "am")

    teaser_msg = (
        "⏳ <b>በግምት በ3 ደቂቃ ውስጥ የእርስዎን ዕቅድ እናዘጋጃለን — እናስጀምር!</b>"
        if lang == "am"
        else "⏳ <b>In about 3 minutes I'll put together your plan — let's get started!</b>"
    )
    await query.edit_message_text(teaser_msg, parse_mode="HTML")

    age_prompt = "🎂 <b>ዕድሜዎ ስንት ነው?</b> (ምሳሌ፡ 25)" if lang == "am" else "🎂 <b>How old are you?</b> (e.g., 25)"
    await query.message.reply_text(age_prompt, parse_mode="HTML")
    return AGE

async def age_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    age_text = update.message.text.strip()

    if not age_text.isdigit() or not (12 <= int(age_text) <= 100):
        error_msg = "❌ እባክዎ ትክክለኛ ዕድሜ በቁጥር ያስገቡ (12-100)፦" if lang == "am" else "❌ Please enter a valid age as a number (12-100):"
        await update.message.reply_text(error_msg)
        return AGE

    context.user_data["age"] = age_text
    text = "📏 <b>ቁመትዎ በሴንቲሜትር (cm) ስንት ነው?</b> (ምሳሌ፡ 175)" if lang == "am" else "📏 <b>What is your height in centimeters (cm)?</b> (e.g., 175)"
    await update.message.reply_text(text, parse_mode="HTML")
    return HEIGHT

async def height_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    height_text = update.message.text.strip()

    if not height_text.isdigit() or not (100 <= int(height_text) <= 250):
        error_msg = "❌ እባክዎ ትክክለኛ ቁመት በሴንቲሜትር ያስገቡ (100-250)፦" if lang == "am" else "❌ Please enter a valid height in cm (100-250):"
        await update.message.reply_text(error_msg)
        return HEIGHT

    context.user_data["height"] = height_text
    text = "⚖️ <b>የአሁኑ ክብደትዎ በኪሎግራም (kg) ስንት ነው?</b> (ምሳሌ፡ 75)" if lang == "am" else "⚖️ <b>What is your current weight in kilograms (kg)?</b> (e.g., 75)"
    await update.message.reply_text(text, parse_mode="HTML")
    return WEIGHT

async def weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    weight_text = update.message.text.strip()

    if not weight_text.isdigit() or not (30 <= int(weight_text) <= 300):
        error_msg = "❌ እባክዎ ትክክለኛ ክብደት በኪሎግራም ያስገቡ (30-300)፦" if lang == "am" else "❌ Please enter a valid weight in kg (30-300):"
        await update.message.reply_text(error_msg)
        return WEIGHT

    context.user_data["weight"] = weight_text
    keyboard = [
        [InlineKeyboardButton("🔥 ስብ መቀነስ / ቦርጭ ማጥፋት" if lang == "am" else "🔥 Fat Loss / Tummy Reduction", callback_data="goal_fat_loss")],
        [InlineKeyboardButton("💪 የሰውነት ጡንቻ መገንባት" if lang == "am" else "💪 Muscle Building", callback_data="goal_muscle")],
        [InlineKeyboardButton("⚡ የጉልበት እና ብቃት ማሳደግ" if lang == "am" else "⚡ Athletic Performance", callback_data="goal_performance")],
    ]
    text = "🎯 <b>ዋናው የፊትነስ ዓላማዎ ምንድን ነው?</b>" if lang == "am" else "🎯 <b>What is your primary fitness goal?</b>"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return GOAL


# ==========================================
# 📞 STEP 5: GOAL & PHONE VERIFICATION (UPGRADED)
# ==========================================
async def goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    goal = "_".join(query.data.split("_")[1:])
    context.user_data["goal"] = goal
    lang = context.user_data.get("lang", "am")

    text = (
        "📞 <b>ለማረጋገጫ እና ክትትል የሚሆን ስልክ ቁጥርዎ ስንት ነው?</b> (ምሳሌ፡ 0911223344)"
        if lang == "am"
        else "📞 <b>What is your phone number for verification & follow-up?</b> (e.g., +251911223344 or 0911223344)"
    )
    await query.edit_message_text(text, parse_mode="HTML")
    return PHONE

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    raw_phone = update.message.text.strip()
    
    # [NEW UPDATE] Robust Phone Validation Regex for Ethiopian & Standard numbers
    clean_phone = re.sub(r'[\s\-]', '', raw_phone)
    pattern = r'^(?:\+251|251|0)?(9|7)\d{8}$'

    if not re.match(pattern, clean_phone):
        error_msg = (
            "❌ <b>እባክዎ ትክክለኛ የስልክ ቁጥር ያስገቡ!</b>\nምሳሌ፦ 0911223344 ወይም +251911223344"
            if lang == "am"
            else "❌ <b>Please enter a valid phone number!</b>\ne.g., 0911223344 or +251911223344"
        )
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return PHONE

    context.user_data["phone"] = clean_phone
    
    # [NEW UPDATE] Sync Goal and Validated Phone to Supabase
    user = update.effective_user
    sync_client_to_supabase(
        user_id=user.id, 
        full_name=user.full_name, 
        username=user.username, 
        phone=clean_phone, 
        goal=context.user_data.get("goal"),
        language=lang
    )

    loc_type = context.user_data.get("location_type", "et")
    keyboard = get_pricing_keyboard(lang, loc_type)

    text = (
        "⏱️ <b>ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦</b>\n\n💡 <i>እያንዳንዱ ፓኬጅ ምንን እንደሚያካትት ለማየት ከላይ ያለውን የዝርዝር መግለጫ (FAQ) ቁልፍ መጫን ይችላሉ።</i>"
        if lang == "am"
        else "⏱️ <b>Select your transformation timeframe:</b>\n\n💡 <i>Tap the FAQ button above anytime to see what each tier includes.</i>"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return DURATION


# ==========================================
# ⏱️ STEP 6: DURATION & PAYMENT
# ==========================================
async def duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if "Meal_Plan_Only" in data:
        duration_str = "Meal Plan Only"
        price_str = "799 ETB" if "799" in data else "$29.99"
    else:
        dur_info = data.split("_")[1:]
        price_str = dur_info[-1]
        duration_str = " ".join(dur_info[:-1])

    context.user_data["duration"] = duration_str
    context.user_data["price"] = price_str

    # [NEW UPDATE] Sync chosen package to Supabase
    sync_client_to_supabase(
        user_id=update.effective_user.id,
        full_name=update.effective_user.full_name,
        username=update.effective_user.username,
        package=duration_str
    )

    lang = context.user_data.get("lang", "am")
    loc_type = context.user_data.get("location_type", "et")

    # Schedule Payment Recovery Reminder if they abandon at receipt upload
    cancel_reminder(context, "onboarding_reminder", update.effective_user.id)
    schedule_reminder(context, "payment_reminder", update.effective_user.id, lang, delay=PAYMENT_REMINDER_DELAY)

    if lang == "am":
        pay_text = (
            f"💳 <b>የክፍያ መመሪያ ({'ለሀገር ውስጥ' if loc_type == 'et' else 'ለዲያስፖራ/ውጭ ሀገር'})</b>\n\n"
            f"⏱️ <b>የተመረጠው ፕሮግራም፦</b> {duration_str}\n"
            f"💰 <b>ክፍያ መጠን፦</b> <b>{price_str}</b>\n\n"
            f"እባክዎ ክፍያውን በሚከተሉት የባንክ ሂሳቦች ያስገቡ፦\n"
            f"• <b>CBE Bank:</b> <code>{CBE_ACCOUNT}</code>\n"
            f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
            f"• <b>ስም:</b> {ACCOUNT_NAME}\n\n"
            f"📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን <b>ግልጽ ስክሪንሽኦት ወይም ፎቶ</b> እዚህ ይላኩ።\n\n"
            f"❓ <b>ጥያቄ ካለዎት በቀጥታ ያግኙን፦</b> {SUPPORT_HANDLE}"
        )
    else:
        pay_text = (
            f"💳 <b>Payment Instructions ({'Local' if loc_type == 'et' else 'Diaspora'})</b>\n\n"
            f"⏱️ <b>Selected Program:</b> {duration_str}\n"
            f"💰 <b>Total Fee:</b> <b>{price_str}</b>\n\n"
            f"Please make the transfer to the following accounts:\n"
            f"• <b>CBE Bank:</b> <code>{CBE_ACCOUNT}</code>\n"
            f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
            f"• <b>Account Name:</b> {ACCOUNT_NAME}\n\n"
            f"📸 Once completed, please send a <b>clear screenshot or photo</b> of your receipt below.\n\n"
            f"❓ <b>Questions? Contact Simon directly:</b> {SUPPORT_HANDLE}"
        )

    await query.edit_message_text(pay_text, parse_mode="HTML")
    return RECEIPT


# ==========================================
# 📥 STEP 7: RECEIPT UPLOAD & WAITING FOR APPROVAL
# ==========================================
async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo = update.message.photo[-1]
    lang = context.user_data.get("lang", "am")
    loc_type = context.user_data.get("location_type", "et")

    # [NEW UPDATE] Log receipt to Supabase
    record_receipt_in_supabase(user.id, photo.file_id)

    loc = "🇪🇹 Ethiopia" if loc_type == "et" else "🌎 Diaspora"
    registration_timestamp = datetime.now().strftime("%Y-%b-%d %H:%M:%S")

    # [NEW UPDATE] Upgraded Admin Deep Links (WhatsApp + Telegram)
    tg_deep_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
    raw_phone = context.user_data.get('phone', 'N/A')
    wa_phone = re.sub(r'^0', '251', raw_phone) if raw_phone != 'N/A' else ""
    wa_link = f"<a href='https://wa.me/{wa_phone}'>{raw_phone}</a>" if wa_phone else "N/A"

    admin_card = (
        f"📥 <b>NEW PAYMENT RECEIPT UPLOADED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Client:</b> {tg_deep_link} (@{user.username or 'No_Username'})\n"
        f"📞 <b>Phone:</b> {wa_link}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>Uploaded At:</b> {registration_timestamp}\n"
        f"🌐 <b>Language:</b> {'Amharic' if lang == 'am' else 'English'}\n"
        f"📍 <b>Location:</b> {loc}\n"
        f"⏱️ <b>Program:</b> {context.user_data.get('duration')} ({context.user_data.get('price')})\n\n"
        f"📊 <b>Body Profile:</b>\n"
        f"• <b>Gender:</b> {context.user_data.get('gender')} | <b>Age:</b> {context.user_data.get('age')} yrs\n"
        f"• <b>Height:</b> {context.user_data.get('height')} cm | <b>Weight:</b> {context.user_data.get('weight')} kg\n"
        f"• <b>Goal:</b> {context.user_data.get('goal')}"
    )

    admin_keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Payment", callback_data=f"adm_confirm_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{user.id}"),
        ]
    ]

    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=admin_card,
                reply_markup=InlineKeyboardMarkup(admin_keyboard),
                parse_mode="HTML",
            )
        except Exception as e:
            logging.error(f"Failed to send receipt to admin {admin_id}: {e}")

    cancel_reminder(context, "payment_reminder", user.id)

    wait_msg = (
        "⏳ <b>የክፍያ ደረሰኝዎ ደርሶናል!</b>\n\nሳይመን ክፍያዎን እስኪያረጋግጥ እባክዎ ትንሽ ይጠብቁ። ክፍያው እንደጸደቀ ቀጣዮቹን አጫጭር ጥያቄዎች እንቀጥላለን!"
        if lang == "am"
        else "⏳ <b>Receipt received!</b>\n\nPlease wait while Simon verifies your payment. Once approved, we will continue with your remaining quick questions!"
    )

    await update.message.reply_text(wait_msg, parse_mode="HTML")
    return ConversationHandler.END


# ==========================================
# 🚀 POST-APPROVAL RESUME CALLBACK & QUESTIONS
# ==========================================
async def resume_assessment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    schedule_reminder(context, "assessment_reminder", update.effective_user.id, lang)

    if lang == "am":
        text = "🏃 <b>ዕለታዊ እንቅስቃሴዎ ምን ይመስላል?</b>"
        keyboard = [
            [InlineKeyboardButton("🛋️ እንቅስቃሴ የሌለው (የተቀመጠ)", callback_data="pact_sedentary")],
            [InlineKeyboardButton("🚶 መካከለኛ (በሳምንት 1-3 ቀን)", callback_data="pact_moderate")],
            [InlineKeyboardButton("🏋️ ከፍተኛ (በሳምንት 4+ ቀን)", callback_data="pact_high")],
        ]
    else:
        text = "🏃 <b>What is your daily activity level?</b>"
        keyboard = [
            [InlineKeyboardButton("🛋️ Sedentary (Office Job)", callback_data="pact_sedentary")],
            [InlineKeyboardButton("🚶 Moderate (1-3 days/wk)", callback_data="pact_moderate")],
            [InlineKeyboardButton("🏋️ High Activity (4+ days/wk)", callback_data="pact_high")],
        ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_ACTIVITY

async def post_activity_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    activity = query.data.split("_")[1]
    context.user_data["activity"] = activity
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [InlineKeyboardButton("🟢 ገና ጀማሪ" if lang == "am" else "🟢 Beginner (New to gym)", callback_data="pexp_beginner")],
        [InlineKeyboardButton("🟡 መካከለኛ" if lang == "am" else "🟡 Intermediate (Knows basics)", callback_data="pexp_intermediate")],
        [InlineKeyboardButton("🔴 ልምድ ያለው" if lang == "am" else "🔴 Advanced (Stuck at plateau)", callback_data="pexp_advanced")],
    ]
    text = "🏋️ <b>የስፖርት ወይም የጂም ልምድዎ ምን ይመስላል?</b>" if lang == "am" else "🏋️ <b>What is your training experience level?</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EXPERIENCE

async def post_experience_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    exp = query.data.split("_")[1]
    context.user_data["experience"] = exp
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [InlineKeyboardButton("🏠 በቤት ውስጥ (መሳሪያ የለም)" if lang == "am" else "🏠 Home (No Equipment)", callback_data="peqp_home_none")],
        [InlineKeyboardButton("🏡 በቤት ውስጥ (አነስተኛ መሳሪያ አለኝ)" if lang == "am" else "🏡 Home (Some Equipment)", callback_data="peqp_home_some")],
        [InlineKeyboardButton("🏋️ ወደ ጂም እሄዳለሁ" if lang == "am" else "🏋️ I Go to a Gym", callback_data="peqp_gym")],
    ]
    text = "🏋️ <b>የስፖርት መሳሪያ አለዎት ወይስ ወደ ጂም ይሄዳሉ?</b>" if lang == "am" else "🏋️ <b>Do you have workout equipment, or do you go to a gym?</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EQUIPMENT

async def post_equipment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    equipment = "_".join(query.data.split("_")[1:])
    context.user_data["equipment"] = equipment
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [InlineKeyboardButton("🍱 የምግብ ሥርዓት አለመጠበቅ" if lang == "am" else "🍱 Bad Diet & Nutrition", callback_data="pobs_diet")],
        [InlineKeyboardButton("⏰ የጊዜ እጥረት" if lang == "am" else "⏰ Lack of Time", callback_data="pobs_time")],
        [InlineKeyboardButton("📉 ወጥነት ማጣት" if lang == "am" else "📉 Lack of Consistency", callback_data="pobs_consistency")],
        [InlineKeyboardButton("❓ ምን መሥራት እንዳለብኝ አለማወቅ" if lang == "am" else "❓ No Structured Plan", callback_data="pobs_plan")],
    ]
    text = "🚧 <b>አሁን ላይ ለውጥ እንዳያመጡ ትልቁ ፈተናዎ ምንድን ነው?</b>" if lang == "am" else "🚧 <b>What is your biggest obstacle right now?</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_OBSTACLE

async def post_obstacle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    obs = query.data.split("_")[1]
    context.user_data["obstacle"] = obs
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [InlineKeyboardButton("⚡ 10 - ዛሬውኑ ለመጀመር 100% ዝግጁ ነኝ!" if lang == "am" else "⚡ 10 - Ready to start today!", callback_data="pread_10")],
        [InlineKeyboardButton("📈 7-9 - ዝግጁ ነኝ፣ ትክክለኛ ፕሮግራም ብቻ ነው የሚያስፈልገኝ" if lang == "am" else "📈 7-9 - Ready with the right plan", callback_data="pread_7-9")],
    ]
    text = "🔥 <b>ከ1-10 ባለው ደረጃ፣ ሰውነትዎን ለመለወጥ አሁን ምን ያህል ተዘጋጅተዋል?</b>" if lang == "am" else "🔥 <b>On a scale of 1–10, how ready are you to transform your body?</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_READINESS

async def post_readiness_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    readiness = query.data.split("_")[1]
    context.user_data["readiness"] = readiness
    lang = context.user_data.get("lang", "am")

    text = (
        "🩹 <b>ማንኛውም የሰውነት ጉዳት ወይም የጤና ሁኔታ አለብዎት?</b>\n<i>(ከሌለ 'የለም' ብለው ይጻፉ)</i>"
        if lang == "am"
        else "🩹 <b>Do you have any injuries or medical conditions?</b>\n<i>(If none, reply 'None')</i>"
    )
    await query.edit_message_text(text, parse_mode="HTML")
    return POST_HEALTH

async def post_health_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["injuries"] = update.message.text.strip()

    text = (
        "🥗 <b>ማንኛውም የማይስማማዎት ወይም የማይወዱት ምግብ አለ?</b>\n<i>(ከሌለ 'የለም' ብለው ይጻፉ)</i>"
        if lang == "am"
        else "🥗 <b>Do you have any food allergies or severe dislikes?</b>\n<i>(If none, reply 'None')</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return POST_DIET

async def post_diet_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["diet"] = update.message.text.strip()

    keyboard = [
        [InlineKeyboardButton("🍳 በቤት አበስላለሁ" if lang == "am" else "🍳 Cook at home", callback_data="peat_home")],
        [InlineKeyboardButton("🍽️ ብዙ ጊዜ ውጭ እበላለሁ" if lang == "am" else "🍽️ Mostly eat out", callback_data="peat_out")],
        [InlineKeyboardButton("🔄 ሁለቱንም እቀላቅላለሁ" if lang == "am" else "🔄 Mix of both", callback_data="peat_mix")],
        [InlineKeyboardButton("⏱️ ለማብሰል ጊዜ የለኝም" if lang == "am" else "⏱️ No time to cook", callback_data="peat_notime")],
    ]
    text = "🍽️ <b>እንዴት ነው በተለምዶ የሚመገቡት?</b>" if lang == "am" else "🍽️ <b>How do you usually eat?</b>"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EATING_STYLE

async def post_eating_style_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    eating_style = query.data.split("_")[1]
    context.user_data["eating_style"] = eating_style

    user = update.effective_user
    lang = context.user_data.get("lang", "am")

    cancel_reminder(context, "assessment_reminder", user.id)
    
    # Keep Google Sheets Sync Intact
    save_lead_to_google_sheet(context.user_data, user)
    
    # [NEW UPDATE] Save Baseline Assessment to Supabase
    save_assessment_to_supabase(user.id, context.user_data.get('weight', 0))

    completion_timestamp = datetime.now().strftime("%Y-%b-%d %H:%M:%S")
    user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
    admin_completion_card = (
        f"🚀 <b>CLIENT COMPLETED FULL ASSESSMENT!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Client:</b> {user_link} (@{user.username or 'No_Username'})\n"
        f"📞 <b>Phone:</b> {context.user_data.get('phone')}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>Completed At:</b> {completion_timestamp}\n"
        f"🌐 <b>Language:</b> {'Amharic' if lang == 'am' else 'English'}\n"
        f"📍 <b>Location:</b> {'Ethiopia' if context.user_data.get('location_type') == 'et' else 'Diaspora'}\n"
        f"⏱️ <b>Program:</b> {context.user_data.get('duration')} ({context.user_data.get('price')})\n\n"
        f"📊 <b>Full Body & Fitness Profile:</b>\n"
        f"• <b>Gender:</b> {context.user_data.get('gender')} | <b>Age:</b> {context.user_data.get('age')} yrs\n"
        f"• <b>Height:</b> {context.user_data.get('height')} cm | <b>Weight:</b> {context.user_data.get('weight')} kg\n"
        f"• <b>Goal:</b> {context.user_data.get('goal')}\n"
        f"• <b>Activity Level:</b> {context.user_data.get('activity')}\n"
        f"• <b>Experience:</b> {context.user_data.get('experience')}\n"
        f"• <b>Equipment/Location:</b> {context.user_data.get('equipment')}\n"
        f"• <b>Main Obstacle:</b> {context.user_data.get('obstacle')}\n"
        f"• <b>Readiness (1-10):</b> {context.user_data.get('readiness')}\n"
        f"• <b>Injuries/Health:</b> {context.user_data.get('injuries')}\n"
        f"• <b>Dietary Notes:</b> {context.user_data.get('diet')}\n"
        f"• <b>Eating Style:</b> {context.user_data.get('eating_style')}"
    )

    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_completion_card, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Failed to send completion summary to admin {admin_id}: {e}")

    if lang == "am":
        confirm_msg = (
            "🎉 <b>እንኳን ደስ አለዎት! መረጃዎ ሙሉ በሙሉ ተመዝግቧል!</b>\n\n"
            "📋 <b>ቀጣይ እርምጃችን ምን ይሆናል?</b>\n"
            "• ሳይመን ያስገቡትን ሙሉ መረጃ በመጠቀም ዕቅድዎን አሁን ማዘጋጀት ጀምሯል።\n"
            "• የተዘጋጀውን የሥልጠና እና የምግብ ፕሮግራምዎን <b>በ24 ሰዓታት ውስጥ</b> እዚሁ ቻት ላይ ይላክልዎታል።\n\n"
            "💪 <i>አብረን አስደናቂ ለውጥ እናመጣለን!</i>"
        )
    else:
        confirm_msg = (
            "🎉 <b>Assessment Successfully Completed!</b>\n\n"
            "📋 <b>Next Steps:</b>\n"
            "• Simon is now building your fully customized training and nutrition plan based on your full assessment.\n"
            "• You will receive your complete plan <b>within 24 hours</b> directly in this chat.\n\n"
            "💪 <i>Let's build something amazing together!</i>"
        )

    await query.edit_message_text(confirm_msg, parse_mode="HTML")
    return ConversationHandler.END


# ==========================================
# ⚙️ ADMIN ACTION CALLBACKS
# ==========================================
async def admin_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, client_id_str = query.data.split("_")[1:]
    client_id = int(client_id_str)

    if action == "confirm":
        await context.bot.send_message(
            chat_id=client_id,
            text=(
                "✅ <b>Payment Approved by Simon!</b> Click below to finish your remaining quick questions so we can build your plan:"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Continue Assessment", callback_data="resume_assessment")]]),
            parse_mode="HTML",
        )
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n<b>STATUS:</b> ✅ APPROVED BY SIMON",
            parse_mode="HTML",
        )
    elif action == "reject":
        await context.bot.send_message(
            chat_id=client_id,
            text=(
                f"❌ <b>Payment Alert:</b> We could not verify your receipt screenshot. Please contact Simon directly at {SUPPORT_HANDLE}."
            ),
            parse_mode="HTML",
        )
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n<b>STATUS:</b> ❌ REJECTED",
            parse_mode="HTML",
        )


# ==========================================
# 🚀 ADMIN DISPATCH COMMAND (BOT #2 HANDOFF) [NEW UPDATE]
# ==========================================
async def admin_send_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        return

    try:
        client_id = int(context.args[0])
        meal_url = context.args[1]
        workout_url = context.args[2]
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ **Usage:** `/send_plan <client_id> <meal_pdf_url> <workout_pdf_url>`",
            parse_mode="Markdown"
        )
        return

    # Update Supabase active status
    if supabase:
        try:
            supabase.table("clients").update({
                "meal_plan_url": meal_url,
                "workout_plan_url": workout_url,
                "is_active": True
            }).eq("id", client_id).execute()
        except Exception as e:
            logging.error(f"Failed to update URLs in Supabase: {e}")

    keyboard = [
        [InlineKeyboardButton("🥗 View Meal Plan (PDF)", url=meal_url)],
        [InlineKeyboardButton("🏋️ View Workout Plan (PDF)", url=workout_url)],
        [InlineKeyboardButton("🚀 Open Tracking Bot (Bot #2)", url=f"https://t.me/{BOT_2_USERNAME}")]
    ]

    dispatch_text = (
        "🎉 **የግል ስልጠና እቅድዎ ዝግጁ ነው! / Your Custom Plan is Ready!**\n\n"
        "የእርስዎን የቪዲዮ/PDF ስልጠናዎች ከታች ካሉት አዝራሮች በመጫን ማግኘት ይችላሉ።\n\n"
        "የቀን ተቀን እንቅስቃሴዎን ለማስመዝገብ እና ለመከታተል አሁኑኑ ወደ **Tracking Bot** በመሄድ /start ይበሉ!"
    )

    try:
        await context.bot.send_message(
            chat_id=client_id,
            text=dispatch_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Plan & Bot #2 link sent to client `{client_id}`!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send plan to client `{client_id}`: {e}")


# ==========================================
# 🏁 MAIN ENTRY POINT WITH PERSISTENCE
# ==========================================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    persistence = PicklePersistence(filepath="bot_persistence")
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    app.add_handler(CallbackQueryHandler(faq_callback, pattern="^faq_"))
    app.add_handler(CallbackQueryHandler(back_to_pricing_callback, pattern="^back_pricing_"))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [CallbackQueryHandler(language_choice, pattern="^lang_")],
            GENDER: [CallbackQueryHandler(gender_choice, pattern="^gen_")],
            LOCATION: [CallbackQueryHandler(location_choice, pattern="^loc_")],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_input)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height_input)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_input)],
            GOAL: [CallbackQueryHandler(goal_choice, pattern="^goal_")],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input)],
            DURATION: [CallbackQueryHandler(duration_choice, pattern="^dur_")],
            RECEIPT: [MessageHandler(filters.PHOTO, receipt_upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],  # [NEW UPDATE] Added global cancel fallback
        name="onboarding_conversation",
        persistent=True,
    )

    post_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(resume_assessment, pattern="^resume_assessment$")],
        states={
            POST_ACTIVITY: [CallbackQueryHandler(post_activity_choice, pattern="^pact_")],
            POST_EXPERIENCE: [CallbackQueryHandler(post_experience_choice, pattern="^pexp_")],
            POST_EQUIPMENT: [CallbackQueryHandler(post_equipment_choice, pattern="^peqp_")],
            POST_OBSTACLE: [CallbackQueryHandler(post_obstacle_choice, pattern="^pobs_")],
            POST_READINESS: [CallbackQueryHandler(post_readiness_choice, pattern="^pread_")],
            POST_HEALTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_health_input)],
            POST_DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_diet_input)],
            POST_EATING_STYLE: [CallbackQueryHandler(post_eating_style_choice, pattern="^peat_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],  # [NEW UPDATE] Added global cancel fallback
        name="post_payment_conversation",
        persistent=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(post_conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))
    app.add_handler(CommandHandler("send_plan", admin_send_plan))  # [NEW UPDATE] Admin command to send plan and Bot #2 link

    print("⚡ Upgraded Bot #1 is LIVE with Supabase, phone validation & payment recovery...")
    app.run_polling()

if __name__ == "__main__":
    main()
