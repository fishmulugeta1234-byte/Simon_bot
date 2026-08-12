import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from supabase import create_client, Client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

for _name, _val in [("BOT_TOKEN", BOT_TOKEN), ("SUPABASE_URL", SUPABASE_URL), ("SUPABASE_KEY", SUPABASE_KEY)]:
    if not _val:
        raise RuntimeError(f"Missing required environment variable: {_name}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_USER_IDS = [1622298145, 389487101]

CBE_ACCOUNT = "1000357796532"
TELEBIRR_NUMBER = "0939998090"
ACCOUNT_NAME = "Simon mulugeta"
SUPPORT_HANDLE = "@s_simon_19"
BOT_2_LINK = "https://t.me/Simonoriginbot"

# UI Image Graphics
GENDER_PHOTO_ID = "AgACAgQAAxkBAAFRqwFqfKwio4y4NyZrB_8NyBiuI-tRwgAC6xBrG49R6VNBWlDO5BA76gEAAwIAA3kAAz0E"
BIOMETRICS_PHOTO_ID = "AgACAgQAAxkBAAFRqvFqfKuTupRfry280QYNS3V5LpzljwAC6hBrG49R6VM5n2ngFLTqRAEAAwIAA3kAAz0E"

REMINDER_DELAY_SECONDS = 3 * 60 * 60
PAYMENT_REMINDER_DELAY = 2 * 60 * 60

# ==========================================
# 📋 CONVERSATION STATES
# ==========================================
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
    POST_ACTIVITY,
    POST_EXPERIENCE,
    POST_EQUIPMENT,
    POST_OBSTACLE,
    POST_READINESS,
    POST_HEALTH,
    POST_DIET,
    POST_EATING_STYLE,
) = range(18)


# ==========================================
# 🌐 WEB SERVER FOR RENDER KEEP-ALIVE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot 1 Supabase version is alive!")

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()


# ==========================================
# 🗄️ SUPABASE SYNC HELPERS
# ==========================================
def save_lead_to_supabase(user_data, user):
    try:
        data = {
            "id": int(user.id),
            "full_name": user.full_name,
            "username": user.username or "None",
            "phone_number": user_data.get("phone", ""),
            "goal": user_data.get("goal", "General"),
            "language": user_data.get("lang", "am"),
            "package": user_data.get("duration", ""),
            "is_active": False,
            "baseline_weight": float(user_data.get("weight", 0)) if user_data.get("weight") else 0.0,
            "updated_at": "now()"
        }
        supabase.table("clients").upsert(data).execute()
        logging.info("Successfully saved client core profile to Supabase!")
    except Exception as e:
        logging.error(f"Exception while saving to Supabase: {e}")


# ==========================================
# ⏰ REMINDERS & RECOVERY JOBS
# ==========================================
def _reminder_job_name(prefix, chat_id):
    return f"{prefix}_{chat_id}"

def schedule_reminder(context: ContextTypes.DEFAULT_TYPE, prefix, chat_id, lang, delay=REMINDER_DELAY_SECONDS):
    if context.job_queue is None: return
    job_name = _reminder_job_name(prefix, chat_id)
    for job in context.job_queue.get_jobs_by_name(job_name): job.schedule_removal()
        
    callback = send_onboarding_reminder if prefix == "onboarding_reminder" else (send_payment_abandonment_reminder if prefix == "payment_reminder" else send_assessment_reminder)
    context.job_queue.run_repeating(callback, interval=delay, first=delay, chat_id=chat_id, name=job_name, data={"lang": lang})

def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, prefix, chat_id):
    if context.job_queue is None: return
    job_name = _reminder_job_name(prefix, chat_id)
    for job in context.job_queue.get_jobs_by_name(job_name): job.schedule_removal()

async def send_onboarding_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    text = "👋 <b>ገና አልጨረሱም!</b>\n\nምዝገባዎን ገና አላጠናቀቁም። ከላይ ላለው ጥያቄ በመመለስ ይቀጥሉ፣ ወይም /start ይላኩ።" if lang == "am" else "👋 <b>Still with us?</b>\n\nReply to my last question above to continue, or send /start."
    try: await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e: logging.error(e)

async def send_payment_abandonment_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    text = f"💳 <b>ክፍያ ለመፈጸም እርዳታ ይፈልጋሉ?</b>\n\nሳይመን ያግኙ፦ {SUPPORT_HANDLE}" if lang == "am" else f"💳 <b>Need help with payment?</b>\n\nContact Simon: {SUPPORT_HANDLE}"
    try: await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e: logging.error(e)

async def send_assessment_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    lang = (job.data or {}).get("lang", "am")
    text = "👋 <b>ገና ጥቂት ጥያቄዎች ይቀሩዎታል!</b> እባክዎ ጥያቄዎቹን ይመልሱ።" if lang == "am" else "👋 <b>A few questions left!</b> Please answer to complete your custom plan evaluation."
    try: await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e: logging.error(e)


# ==========================================
# 📋 PRICING & FAQ HELPERS
# ==========================================
def get_faq_text(loc):
    if loc == "et":
        return (
            "📋 <b>የፕሮግራሞች ዝርዝር እና ተደጋጋሚ ጥያቄዎች (FAQ)</b>\n\n"
            "• <b>የምግብ እቅድ (ለ 2 ወራት) (1,200 ETB):</b> በሰውነትዎ እና በግብዎ ላይ የተመረኮዘ ልዩ የምግብ ዝግጅት እቅድ!\n"
            "• <b>ፈጣን ጅማሬ / 21 ቀናት (4,500 ETB):</b> ለጀማሪዎች ምርጥ ጀምሮ ፈጣን ውጤት ለማምጣት።\n"
            "• <b>የሰውነት ለውጥ / 60 ቀናት (8,900 ETB):</b> እውነተኛ የሰውነት መለወጫ ጉዞ ከሙሉ ክትትል ጋር።\n"
            "• <b>Elite / 90 ቀናት (12,500 ETB):</b> ለረጅም ጊዜ የሚዘልቅ ጠንካራ እና አሸናፊ ውጤት።\n"
            "• <b>Lifestyle / 6 ወራት (24,000 ETB):</b> የአኗኗር ዘይቤዎን በዘላቂነት የሚቀይር አስደናቂ ጉዞ።\n"
            "• <b>ቪአይፒ / 6 ወራት (39,000 ETB):</b> ፍጹም የ1-ለ-1 ልዩ ድጋፍ እና ከፍተኛው የትኩረት ደረጃ!\n\n"
            f"ጥያቄ ካለዎት በቀጥታ ያግኙን፦ {SUPPORT_HANDLE}"
        )
    else:
        return (
            "📋 <b>Program Details & Clarity (FAQ)</b>\n\n"
            "• <b>Meal Plan Only (2 Months) ($39.99):</b> Custom nutrition plan tailored precisely to your goals.\n"
            "• <b>Kickstart / 21 Days ($50):</b> Best for beginners building momentum.\n"
            "• <b>Transformation / 60 Days ($119):</b> Best for fat loss & muscle building.\n"
            "• <b>Elite / 90 Days ($159):</b> Best for serious long-term results.\n"
            "• <b>Lifestyle / 6 Months ($299):</b> Best for permanent lifestyle change.\n"
            "• <b>VIP / 6 Months ($549):</b> Maximum 1-on-1 support and weekly calls.\n\n"
            f"❓ Questions? Contact Simon directly: {SUPPORT_HANDLE}"
        )

def get_pricing_keyboard(lang, loc_type):
    faq_btn_text = "📋 የፕሮግራም ዝርዝር ማየት (FAQ)" if lang == "am" else "📋 View Program Details (FAQ)"
    back_btn_text = "🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back"
    if lang == "am":
        if loc_type == "et":
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 የምግብ እቅድ (ለ 2 ወራት) — 1,200 ETB", callback_data="dur_Meal_Plan_Only_(2_Months)_1200ETB")],
                [InlineKeyboardButton("🥉 ፈጣን ጅማሬ (21 ቀናት) — 4,500 ETB", callback_data="dur_Kickstart_(21_Days)_4500ETB")],
                [InlineKeyboardButton("🥈 የሰውነት ለውጥ (60 ቀናት) — 8,900 ETB", callback_data="dur_Transformation_(60_Days)_8900ETB")],
                [InlineKeyboardButton("🥇 Elite (90 ቀናት) — 12,500 ETB", callback_data="dur_Elite_Transformation_(90_Days)_12500ETB")],
                [InlineKeyboardButton("💎 Lifestyle (6 ወራት) — 24,000 ETB", callback_data="dur_Lifestyle_Coaching_(6_Months)_24000ETB")],
                [InlineKeyboardButton("👑 ቪአይፒ (6 ወራት) — 39,000 ETB", callback_data="dur_VIP_Coaching_(6_Months)_39000ETB")],
                [InlineKeyboardButton(back_btn_text, callback_data="nav_back_phone")],
            ]
        else:
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 Meal Plan Only (2 Months) — $39.99", callback_data="dur_Meal_Plan_Only_(2_Months)_$39.99")],
                [InlineKeyboardButton("🥉 Kickstart (21 Days) — $50", callback_data="dur_Kickstart_(21_Days)_$50")],
                [InlineKeyboardButton("🥈 Transformation (60 Days) — $119", callback_data="dur_Transformation_(60_Days)_$119")],
                [InlineKeyboardButton("🥇 Elite (90 Days) — $159", callback_data="dur_Elite_Transformation_(90_Days)_$159")],
                [InlineKeyboardButton("💎 Lifestyle (6 Months) — $299", callback_data="dur_Lifestyle_Coaching_(6_Months)_$299")],
                [InlineKeyboardButton("👑 VIP (6 Months) — $549", callback_data="dur_VIP_Coaching_(6_Months)_$549")],
                [InlineKeyboardButton(back_btn_text, callback_data="nav_back_phone")],
            ]
    else:
        if loc_type == "et":
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 Meal Plan Only (2 Months) — 1,200 ETB", callback_data="dur_Meal_Plan_Only_(2_Months)_1200ETB")],
                [InlineKeyboardButton("🥉 Kickstart (21 Days) — 4,500 ETB", callback_data="dur_Kickstart_(21_Days)_4500ETB")],
                [InlineKeyboardButton("🥈 Transformation (60 Days) — 8,900 ETB", callback_data="dur_Transformation_(60_Days)_8900ETB")],
                [InlineKeyboardButton("🥇 Elite (90 Days) — 12,500 ETB", callback_data="dur_Elite_Transformation_(90_Days)_12500ETB")],
                [InlineKeyboardButton("💎 Lifestyle (6 Months) — 24,000 ETB", callback_data="dur_Lifestyle_Coaching_(6_Months)_24000ETB")],
                [InlineKeyboardButton("👑 VIP (6 Months) — 39,000 ETB", callback_data="dur_VIP_Coaching_(6_Months)_39000ETB")],
                [InlineKeyboardButton(back_btn_text, callback_data="nav_back_phone")],
            ]
        else:
            return [
                [InlineKeyboardButton(faq_btn_text, callback_data=f"faq_{loc_type}")],
                [InlineKeyboardButton("🥗 Meal Plan Only (2 Months) — $39.99", callback_data="dur_Meal_Plan_Only_(2_Months)_$39.99")],
                [InlineKeyboardButton("🥉 Kickstart (21 Days) — $50", callback_data="dur_Kickstart_(21_Days)_$50")],
                [InlineKeyboardButton("🥈 Transformation (60 Days) — $119", callback_data="dur_Transformation_(60_Days)_$119")],
                [InlineKeyboardButton("🥇 Elite (90 Days) — $159", callback_data="dur_Elite_Transformation_(90_Days)_$159")],
                [InlineKeyboardButton("💎 Lifestyle (6 Months) — $299", callback_data="dur_Lifestyle_Coaching_(6_Months)_$299")],
                [InlineKeyboardButton("👑 VIP (6 Months) — $549", callback_data="dur_VIP_Coaching_(6_Months)_$549")],
                [InlineKeyboardButton(back_btn_text, callback_data="nav_back_phone")],
            ]

async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    text = get_faq_text(loc)
    back_text = "🔙 ወደ ዋጋዎች መመለስ" if lang == "am" else "🔙 Back to Pricing"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(back_text, callback_data=f"back_pricing_{loc}")] ]), parse_mode="HTML")

async def back_to_pricing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_type = query.data.split("_")[2]
    lang = context.user_data.get("lang", "am")
    keyboard = get_pricing_keyboard(lang, loc_type)
    text = "⏱️ <b>የፕሮግራም ቆይታ ይምረጡ፦</b>" if lang == "am" else "⏱️ <b>Select your transformation timeframe:</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==========================================
# 🚀 STEP-BY-STEP FLOW HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()
    cancel_reminder(context, "onboarding_reminder", user.id)
    cancel_reminder(context, "payment_reminder", user.id)
    cancel_reminder(context, "assessment_reminder", user.id)

    keyboard = [[InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")]]
    await update.message.reply_text("Welcome! Please select your language / ቋንቋ ይምረጡ፦", reply_markup=InlineKeyboardMarkup(keyboard))
    return LANGUAGE

async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    schedule_reminder(context, "onboarding_reminder", update.effective_user.id, lang)
    keyboard = [
        [InlineKeyboardButton("👨 ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"), InlineKeyboardButton("👩 ሴት" if lang == "am" else "👩 Female", callback_data="gen_female")]
    ]
    
    # Send photo for Gender choice
    await query.message.reply_photo(
        photo=GENDER_PHOTO_ID,
        caption="👤 <b>ጾታዎን ይምረጡ፦</b>" if lang == "am" else "👤 <b>Select your gender:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    return GENDER

async def gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "nav_back_lang":
        keyboard = [[InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")]]
        await query.edit_message_text("Welcome! Please select your language / ቋንቋ ይምረጡ፦", reply_markup=InlineKeyboardMarkup(keyboard))
        return LANGUAGE

    context.user_data["gender"] = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (በሀገር ውስጥ)", callback_data="loc_et")],
        [InlineKeyboardButton("🌍 ከሀገር ውጭ (Diaspora)", callback_data="loc_diaspora")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_lang")]
    ]
    await query.edit_message_text("📍 <b>እባክዎ የሚኖሩበትን አካባቢ ይምረጡ፦</b>" if lang == "am" else "📍 <b>Select your region:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return LOCATION

async def location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "nav_back_gender":
        lang = context.user_data.get("lang", "am")
        keyboard = [
            [InlineKeyboardButton("👨 ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"), InlineKeyboardButton("👩 ሴት" if lang == "am" else "👩 Female", callback_data="gen_female")]
        ]
        await query.message.reply_photo(
            photo=GENDER_PHOTO_ID,
            caption="👤 <b>ጾታዎን ይምረጡ፦</b>" if lang == "am" else "👤 <b>Select your gender:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        try:
            await query.message.delete()
        except Exception:
            pass
        return GENDER

    context.user_data["location_type"] = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_gender")]])
    
    # Text-only for Age prompt (no photo for age as requested)
    await query.message.reply_text(
        "⏳ <b>እቅድዎን እያዘጋጀን ነው... እባክዎ ዕድሜዎን በቁጥር ይጻፉ (ምሳሌ፡ 25)፦</b>" if lang == "am" else "⏳ <b>Please enter your age as a number (e.g., 25):</b>",
        reply_markup=back_kb,
        parse_mode="HTML"
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    return AGE

async def age_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    text = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_gender")]])

    if not text.isdigit() or not (10 <= int(text) <= 120):
        error_msg = "❌ ይቅርታ፣ ሀሳብዎን በትክክል አልተረዳሁም። እባክዎ ትክክለኛ ዕድሜ በቁጥር ያስገቡ (ምሳሌ፡ 25)፦" if lang == "am" else "❌ I didn't catch that. Please enter a valid age as a number (e.g., 25):"
        await update.message.reply_text(error_msg, reply_markup=back_kb)
        return AGE

    context.user_data["age"] = text
    back_kb_height = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_age")]])
    
    # Show photo for height as requested
    await update.message.reply_photo(
        photo=BIOMETRICS_PHOTO_ID,
        caption="📏 <b>ቁመትዎ በሴንቲሜትር (cm) ስንት ነው? (ምሳሌ፡ 175)</b>" if lang == "am" else "📏 <b>Height in cm? (e.g., 175)</b>",
        reply_markup=back_kb_height,
        parse_mode="HTML"
    )
    return HEIGHT

async def height_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    text = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_age")]])

    if not text.isdigit() or not (50 <= int(text) <= 250):
        error_msg = "❌ ይቅርታ፣ ሀሳብዎን በትክክል አልተረዳሁም። እባክዎ ትክክለኛ ቁመት በሴንቲሜትር በቁጥር ያስገቡ (ምሳሌ፡ 175)፦" if lang == "am" else "❌ I didn't catch that. Please enter a valid height in cm as a number (e.g., 175):"
        await update.message.reply_photo(
            photo=BIOMETRICS_PHOTO_ID,
            caption=error_msg,
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        return HEIGHT

    context.user_data["height"] = text
    back_kb_weight = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_height")]])
    await update.message.reply_photo(
        photo=BIOMETRICS_PHOTO_ID,
        caption="⚖️ <b>ክብደትዎ በኪሎግራም (kg) ስንት ነው? (ምሳሌ፡ 75)</b>" if lang == "am" else "⚖️ <b>Weight in kg? (e.g., 75)</b>",
        reply_markup=back_kb_weight,
        parse_mode="HTML"
    )
    return WEIGHT

async def weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    text = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_height")]])

    if not text.isdigit() or not (20 <= int(text) <= 300):
        error_msg = "❌ ይቅርታ፣ ሀሳብዎን በትክክል አልተረዳሁም። እባክዎ ትክክለኛ ክብደት በኪሎግራም በቁጥር ያስገቡ (ምሳሌ፡ 75)፦" if lang == "am" else "❌ I didn't catch that. Please enter a valid weight in kg as a number (e.g., 75):"
        await update.message.reply_photo(
            photo=BIOMETRICS_PHOTO_ID,
            caption=error_msg,
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        return WEIGHT

    context.user_data["weight"] = text
    keyboard = [
        [InlineKeyboardButton("🔥 ስብ መቀነስ" if lang == "am" else "🔥 Fat Loss", callback_data="goal_fat_loss")],
        [InlineKeyboardButton("💪 ጡንቻ መገንባት" if lang == "am" else "💪 Muscle", callback_data="goal_muscle")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_weight")]
    ]
    await update.message.reply_text("🎯 <b>ዋናው ዓላማዎ ምንድን ነው?</b>" if lang == "am" else "🎯 <b>Primary goal?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return GOAL

async def goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_weight":
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_height")]])
        await query.message.reply_photo(
            photo=BIOMETRICS_PHOTO_ID,
            caption="⚖️ <b>ክብደትዎ በኪሎግራም (kg) ስንት ነው? (ምሳሌ፡ 75)</b>" if lang == "am" else "⚖️ <b>Weight in kg? (e.g., 75)</b>",
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        try:
            await query.message.delete()
        except Exception:
            pass
        return WEIGHT

    context.user_data["goal"] = "_".join(query.data.split("_")[1:])
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_goal")]])
    
    phone_prompt = (
        "📞 <b>ለክፍያ ማረጋገጫ፣ ለዕቅድ ማድረሻ እና ለቀጣይ ክትትል የሚሆን ትክክለኛ የስልክ ቁጥርዎ ያስፈልገናል። እባክዎ ቁጥርዎን ያስገቡ (ምሳሌ፡ 0911223344)፦</b>"
        if lang == "am"
        else "📞 <b>We need your phone number for payment confirmation, plan delivery, and follow-up. Please enter your number (e.g., 0911223344):</b>"
    )
    await query.edit_message_text(phone_prompt, reply_markup=back_kb, parse_mode="HTML")
    return PHONE

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    text = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_goal")]])

    # Phone Guardrail: Must contain at least 9 digits
    clean_phone = re.sub(r"\D", "", text)
    if len(clean_phone) < 9:
        error_msg = "❌ እባክዎ ትክክለኛ የስልክ ቁጥር ያስገቡ (ምሳሌ፡ 0911223344)፦" if lang == "am" else "❌ Please enter a valid phone number (e.g., 0911223344):"
        await update.message.reply_text(error_msg, reply_markup=back_kb)
        return PHONE

    context.user_data["phone"] = text
    loc_type = context.user_data.get("location_type", "et")
    keyboard = get_pricing_keyboard(lang, loc_type)
    await update.message.reply_text("⏱️ <b>የፕሮግራም ቆይታ ይምረጡ፦</b>" if lang == "am" else "⏱️ <b>Select your timeframe:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return DURATION

async def duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    
    if query.data == "nav_back_phone":
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_goal")]])
        await query.edit_message_text(
            "📞 <b>ለክፍያ ማረጋገጫ፣ ለዕቅድ ማድረሻ እና ለቀጣይ ክትትል የሚሆን ትክክለኛ የስልክ ቁጥርዎ ያስፈልገናል። እባክዎ ቁጥርዎን ያስገቡ (ምሳሌ፡ 0911223344)፦</b>"
            if lang == "am"
            else "📞 <b>We need your phone number for payment confirmation, plan delivery, and follow-up. Please enter your number (e.g., 0911223344):</b>",
            reply_markup=back_kb, parse_mode="HTML"
        )
        return PHONE

    data = query.data
    if "Meal_Plan_Only" in data:
        duration_str = "Meal Plan Only (2 Months)"
        price_str = "1,200 ETB" if "1200" in data else "$39.99"
    else:
        dur_info = data.split("_")[1:]
        price_str = dur_info[-1]
        duration_str = " ".join(dur_info[:-1])

    context.user_data["duration"] = duration_str
    context.user_data["price"] = price_str
    loc_type = context.user_data.get("location_type", "et")

    cancel_reminder(context, "onboarding_reminder", update.effective_user.id)
    schedule_reminder(context, "payment_reminder", update.effective_user.id, lang, delay=PAYMENT_REMINDER_DELAY)

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_dur")]])

    if loc_type == "diaspora":
        pay_text = (
            f"💳 <b>Payment Instructions (Diaspora)</b>\n\n• Package: {duration_str}\n• Fee: <b>{price_str}</b>\n\n"
            f"You can use <b>Telebirr Remit</b> or other remittance services to transfer funds to:\n\n"
            f"• <b>CBE:</b> <code>{CBE_ACCOUNT}</code> ({ACCOUNT_NAME})\n"
            f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code> ({ACCOUNT_NAME})\n\n"
            f"📸 Once transferred, send your payment receipt screenshot below!"
        )
    else:
        pay_text = (
            f"💳 <b>የክፍያ መመሪያ</b>\n\n• ፓኬጅ፦ {duration_str}\n• ዋጋ፦ <b>{price_str}</b>\n\n"
            f"• <b>CBE:</b> <code>{CBE_ACCOUNT}</code>\n• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n\n"
            f"📸 ክፍያውን ፈጽመው የደረሰኙን ስክሪንሾት ይላኩ!"
        )
    await query.edit_message_text(pay_text, reply_markup=back_kb, parse_mode="HTML")
    return RECEIPT

async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = context.user_data.get("lang", "am")

    # Guardrail: Ensure they uploaded an image screenshot
    if not update.message.photo:
        error_text = "❌ እባክዎ የክፍያዎን የደረሰኝ ስክሪንሾት (Photo) ይላኩ፦" if lang == "am" else "❌ Please send a photo/screenshot of your payment receipt:"
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_dur")]])
        await update.message.reply_text(error_text, reply_markup=back_kb)
        return RECEIPT

    photo = update.message.photo[-1]
    context.user_data["receipt_photo_id"] = photo.file_id
    
    cancel_reminder(context, "payment_reminder", user.id)
    schedule_reminder(context, "assessment_reminder", user.id, lang)

    keyboard = [
        [InlineKeyboardButton("🛋️ እንቅስቃሴ የሌለው (በብዛት ተቀምጬ የምውል)", callback_data="pact_sedentary")],
        [InlineKeyboardButton("🚶 መካከለኛ ተንቀሳቃሽነት (ቀላል እንቅስቃሴ ያለው)", callback_data="pact_moderate")],
        [InlineKeyboardButton("🏃 በጣም ንቁ (የተንቀሳቃሽነት ስራ ወይም ስፖርተኛ)", callback_data="pact_high")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_act")]
    ]
    await update.message.reply_text(
        "📸 <b>ደረሰኝዎ ደርሶናል!</b>\n\nለእርስዎ የሚሆን ፍጹም የሆነ ፕሮግራም ለማዘጋጀት አሁን ጥቂት ቀላል ጥያቄዎችን እንመልስ፦\n\n"
        "🏃 <b>1. የዕለት ተዕለት እንቅስቃሴዎ ምን ይመስላል?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return POST_ACTIVITY

async def post_activity_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_act":
        loc_type = context.user_data.get("location_type", "et")
        keyboard = get_pricing_keyboard(lang, loc_type)
        await query.edit_message_text("⏱️ <b>የፕሮግራም ቆይታ ይምረጡ፦</b>" if lang == "am" else "⏱️ <b>Select your timeframe:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return DURATION

    context.user_data["activity"] = query.data.split("_")[1]
    keyboard = [
        [InlineKeyboardButton("🟢 ሙሉ ጀማሪ (ገና ጀማሪ ነኝ)", callback_data="pexp_beginner")],
        [InlineKeyboardButton("🟡 መካከለኛ (መሰረታዊ ነገሮችን አውቃለሁ)", callback_data="pexp_intermediate")],
        [InlineKeyboardButton("🔴 ልምድ ያለው (ጂም የቆየሁ)", callback_data="pexp_advanced")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_exp")]
    ]
    await query.edit_message_text("🏆 <b>2. የአካል ብቃት ልምድዎ ምን ይመስላል?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EXPERIENCE

async def post_experience_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_exp":
        keyboard = [
            [InlineKeyboardButton("🛋️ እንቅስቃሴ የሌለው (በብዛት ተቀምጬ የምውል)", callback_data="pact_sedentary")],
            [InlineKeyboardButton("🚶 መካከለኛ ተንቀሳቃሽነት (ቀላል እንቅስቃሴ ያለው)", callback_data="pact_moderate")],
            [InlineKeyboardButton("🏃 በጣም ንቁ (የተንቀሳቃሽነት ስራ ወይም ስፖርተኛ)", callback_data="pact_high")],
            [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_act")]
        ]
        await query.edit_message_text("🏃 <b>1. የዕለት ተዕለት እንቅስቃሴዎ ምን ይመስላል?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return POST_ACTIVITY

    context.user_data["experience"] = query.data.split("_")[1]
    keyboard = [
        [InlineKeyboardButton("🏠 ምንም መሳሪያ የለም (ቤት ውስጥ)", callback_data="peqp_none")],
        [InlineKeyboardButton("🎒 አነስተኛ መሳሪያዎች (ዳምቤል/ላስቲክ)", callback_data="peqp_some")],
        [InlineKeyboardButton("🏋️ ሙሉ ጂም ቤት እሄዳለሁ", callback_data="peqp_gym")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_eqp")]
    ]
    await query.edit_message_text("🏋️‍♂️ <b>3. ምን ዓይነት የስፖርት መሣሪያዎች አሉዎት?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EQUIPMENT

async def post_equipment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_eqp":
        keyboard = [
            [InlineKeyboardButton("🟢 ሙሉ ጀማሪ (ገና ጀማሪ ነኝ)", callback_data="pexp_beginner")],
            [InlineKeyboardButton("🟡 መካከለኛ (መሰረታዊ ነገሮችን አውቃለሁ)", callback_data="pexp_intermediate")],
            [InlineKeyboardButton("🔴 ልምድ ያለው (ጂም የቆየሁ)", callback_data="pexp_advanced")],
            [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_exp")]
        ]
        await query.edit_message_text("🏆 <b>2. የአካል ብቃት ልምድዎ ምን ይመስላል?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return POST_EXPERIENCE

    context.user_data["equipment"] = query.data.split("_")[1]
    keyboard = [
        [InlineKeyboardButton("⏰ የጊዜ እጥረት (ለስፖርትም ሆነ ምግብ ለማዘጋጀት)", callback_data="pobs_time")],
        [InlineKeyboardButton("🍱 የተስተካከለ የአመጋገብ ሥርዓት አለማወቅ", callback_data="pobs_diet")],
        [InlineKeyboardButton("📉 ወጥነት ማጣት (ጀምሮ ማቋረጥ)", callback_data="pobs_consistency")],
        [InlineKeyboardButton("🍔 ጤናማ ያልሆነ የምግብ ምርጫ / ጣፋጭ መብዛት", callback_data="pobs_food")],
        [InlineKeyboardButton("❓ ትክክለኛ የሥልጠና እቅድ አለማወቅ", callback_data="pobs_plan")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_obs")]
    ]
    await query.edit_message_text("🚧 <b>4. አሁን ላይ ለውጥ እንዳያመጡ ትልቁ ፈተናዎ ወይም ችግርዎ ምንድን ነው?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_OBSTACLE

async def post_obstacle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_obs":
        keyboard = [
            [InlineKeyboardButton("🏠 ምንም መሳሪያ የለም (ቤት ውስጥ)", callback_data="peqp_none")],
            [InlineKeyboardButton("🎒 አነስተኛ መሳሪያዎች (ዳምቤል/ላስቲክ)", callback_data="peqp_some")],
            [InlineKeyboardButton("🏋️ ሙሉ ጂም ቤት እሄዳለሁ", callback_data="peqp_gym")],
            [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_eqp")]
        ]
        await query.edit_message_text("🏋️‍♂️ <b>3. ምን ዓይነት የስፖርት መሣሪያዎች አሉዎት?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return POST_EQUIPMENT

    context.user_data["obstacle"] = "_".join(query.data.split("_")[1:])
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_readiness")]])
    
    await query.edit_message_text(
        "⭐ <b>5. ለዚህ ለውጥ ምን ያህል ተዘጋጅተዋል? (እባክዎ ከ 1 እስከ 10 ባለው ቁጥር ብቻ ይጻፉ)</b>",
        reply_markup=back_kb,
        parse_mode="HTML"
    )
    return POST_READINESS

async def post_readiness_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    text = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_readiness")]])

    if not text.isdigit() or not (1 <= int(text) <= 10):
        error_msg = "❌ እባክዎ ከ 1 እስከ 10 ያለ ቁጥር ብቻ ያስገቡ (ምሳሌ፡ 8)፦" if lang == "am" else "❌ Please enter a number between 1 and 10:"
        await update.message.reply_text(error_msg, reply_markup=back_kb)
        return POST_READINESS

    context.user_data["readiness"] = text
    back_kb_health = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_health")]])
    await update.message.reply_text("⚠️ <b>6. ያሉብዎት የጤና እክሎች ወይም አሮጌ ጉዳቶች አሉ? (እባክዎ በጽሁፍ ይጻፉ፣ ከሌለ 'የለም' ይበሉ)</b>", reply_markup=back_kb_health, parse_mode="HTML")
    return POST_HEALTH

async def post_health_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["injuries"] = update.message.text.strip()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_diet")]])

    await update.message.reply_text("🥗 <b>7. ልዩ የምግብ ምርጫዎች ወይም አለርጂዎች አሉዎት? (እባክዎ በጽሁፍ በግልጽ ይጻፉ)</b>", reply_markup=back_kb, parse_mode="HTML")
    return POST_DIET

async def post_diet_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["diet"] = update.message.text.strip()

    keyboard = [
        [InlineKeyboardButton("📉 ከ 2 ጊዜ በታች", callback_data="peat_under2")],
        [InlineKeyboardButton("⚖️ 3 ጊዜ", callback_data="peat_3")],
        [InlineKeyboardButton("📈 ከ 3 ጊዜ በላይ", callback_data="peat_over3")],
        [InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_diet_choice")]
    ]
    await update.message.reply_text("🍽️ <b>8. በቀን ስንት ጊዜ መመገብ ይወዳሉ?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return POST_EATING_STYLE

async def post_eating_style_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    if query.data == "nav_back_diet_choice":
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ተመለስ (Back)" if lang == "am" else "🔙 Back", callback_data="nav_back_health")]])
        await query.edit_message_text("⚠️ <b>6. ያሉብዎት የጤና እክሎች ወይም አሮጌ ጉዳቶች አሉ? (እባክዎ በጽሁፍ ይጻፉ፣ ከሌለ 'የለም' ይበሉ)</b>", reply_markup=back_kb, parse_mode="HTML")
        return POST_HEALTH

    context.user_data["eating_style"] = query.data.split("_")[1]
    user = update.effective_user
    
    # Save core lead profile directly to Supabase
    save_lead_to_supabase(context.user_data, user)
    cancel_reminder(context, "assessment_reminder", user.id)

    # Notify Admin with Complete Card
    admin_card = (
        f"📥 <b>NEW COMPLETE CLIENT SUBMISSION!</b>\n"
        f"Client: {user.full_name} (`{user.id}`)\n"
        f"Program: {context.user_data.get('duration')} ({context.user_data.get('price')})\n"
        f"Phone: {context.user_data.get('phone')}\n\n"
        f"<b>Core Biometrics:</b>\n"
        f"• Gender: {context.user_data.get('gender')}\n"
        f"• Age: {context.user_data.get('age')}\n"
        f"• Height: {context.user_data.get('height')} cm\n"
        f"• Weight: {context.user_data.get('weight')} kg\n"
        f"• Goal: {context.user_data.get('goal')}\n\n"
        f"<b>Assessment Data:</b>\n"
        f"• Activity: {context.user_data.get('activity')}\n"
        f"• Experience: {context.user_data.get('experience')}\n"
        f"• Equipment: {context.user_data.get('equipment')}\n"
        f"• Obstacle: {context.user_data.get('obstacle')}\n"
        f"• Readiness: {context.user_data.get('readiness')}/10\n"
        f"• Health/Injuries: {context.user_data.get('injuries')}\n"
        f"• Diet Restrictions: {context.user_data.get('diet')}\n"
        f"• Eating Pattern: {context.user_data.get('eating_style')}"
    )
    admin_keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data=f"adm_confirm_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{user.id}")]]

    photo_id = context.user_data.get("receipt_photo_id")
    for admin_id in ADMIN_USER_IDS:
        try: 
            if photo_id:
                await context.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=admin_card, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=admin_id, text=admin_card, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="HTML")
        except Exception: pass

    completion_text = (
        "🎉 <b>ምዝገባዎ እና መረጃዎ ሙሉ በሙሉ ተጠናቀዋል!</b>\n\n"
        "ሳይመን መረጃዎን እና ክፍያዎን እያረጋገጠ ነው። ክፍያው እንደተረጋገጠ ወደ **Bot #2 (Client Portal)** መግቢያ ሊንክ ወዲያውኑ ይላክልዎታል።"
        if lang == "am"
        else
        "🎉 <b>Registration and assessment complete!</b>\n\n"
        "Simon is reviewing your details and payment. As soon as confirmed, your direct link to **Bot #2 (Client Portal)** will be sent here!"
    )

    await query.edit_message_text(completion_text, parse_mode="HTML")
    return ConversationHandler.END


# ==========================================
# ⚙️ ADMIN ACTION CALLBACKS (SECURED)
# ==========================================
async def admin_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Security Guardrail: Only authorized admins can confirm/reject
    if query.from_user.id not in ADMIN_USER_IDS:
        await query.answer("❌ Unauthorized action.", show_alert=True)
        return

    action, client_id_str = query.data.split("_")[1:]
    client_id = int(client_id_str)

    if action == "confirm":
        try: 
            supabase.table("clients").update({"is_active": True, "payment_status": "Paid"}).eq("id", client_id).execute()
        except Exception as e:
            logging.error(f"Failed to activate client in Supabase: {e}")
        
        portal_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open Client Portal (Bot #2)", url=BOT_2_LINK)]
        ])

        await context.bot.send_message(
            chat_id=client_id, 
            text="✅ <b>Payment Approved! / ክፍያዎ ተረጋግጧል!</b>\n\nYour account is now active. Click the button below to open your portal and get started! 👇", 
            reply_markup=portal_button,
            parse_mode="HTML"
        )
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>STATUS:</b> ✅ APPROVED", parse_mode="HTML")
    elif action == "reject":
        await context.bot.send_message(chat_id=client_id, text="❌ Payment verification failed. Please contact support.", parse_mode="HTML")
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>STATUS:</b> ❌ REJECTED", parse_mode="HTML")


# ==========================================
# 🏁 MAIN ENTRY POINT
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
            GENDER: [CallbackQueryHandler(gender_choice, pattern="^(gen_|nav_back_lang)")],
            LOCATION: [CallbackQueryHandler(location_choice, pattern="^(loc_|nav_back_gender)")],
            AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, age_input),
                CallbackQueryHandler(location_choice, pattern="^nav_back_gender$")
            ],
            HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, height_input),
                CallbackQueryHandler(location_choice, pattern="^nav_back_age$")
            ],
            WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, weight_input),
                CallbackQueryHandler(location_choice, pattern="^nav_back_height$")
            ],
            GOAL: [
                CallbackQueryHandler(goal_choice, pattern="^(goal_|nav_back_weight)")
            ],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input),
                CallbackQueryHandler(goal_choice, pattern="^nav_back_goal$")
            ],
            DURATION: [CallbackQueryHandler(duration_choice, pattern="^(dur_|nav_back_phone)")],
            RECEIPT: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), receipt_upload),
                CallbackQueryHandler(duration_choice, pattern="^nav_back_dur$")
            ],
            POST_ACTIVITY: [CallbackQueryHandler(post_activity_choice, pattern="^(pact_|nav_back_act)")],
            POST_EXPERIENCE: [CallbackQueryHandler(post_experience_choice, pattern="^(pexp_|nav_back_exp)")],
            POST_EQUIPMENT: [CallbackQueryHandler(post_equipment_choice, pattern="^(peqp_|nav_back_eqp)")],
            POST_OBSTACLE: [CallbackQueryHandler(post_obstacle_choice, pattern="^(pobs_|nav_back_obs)")],
            POST_READINESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_readiness_input),
                CallbackQueryHandler(post_equipment_choice, pattern="^nav_back_readiness$")
            ],
            POST_HEALTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_health_input),
                CallbackQueryHandler(post_obstacle_choice, pattern="^nav_back_health$")
            ],
            POST_DIET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_diet_input),
                CallbackQueryHandler(post_readiness_input, pattern="^nav_back_diet$")
            ],
            POST_EATING_STYLE: [CallbackQueryHandler(post_eating_style_choice, pattern="^(peat_|nav_back_diet_choice)")],
        },
        fallbacks=[], name="onboarding", persistent=True,
    )
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))
    app.run_polling()

if __name__ == "__main__":
    main()
