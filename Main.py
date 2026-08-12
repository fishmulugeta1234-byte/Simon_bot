import logging
import os
import threading
from datetime import datetime
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

# Banking & Payment Info
CBE_ACCOUNT = "1000357796532"
TELEBIRR_NUMBER = "0939998090"
ACCOUNT_NAME = "Simon mulugeta"
SUPPORT_HANDLE = "@s_simon_19"
BOT_2_LINK = "https://t.me/Simonoriginbot"

REMINDER_DELAY_SECONDS = 3 * 60 * 60
PAYMENT_REMINDER_DELAY = 2 * 60 * 60

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


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot 1 Supabase version is alive!")

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()


def save_lead_to_supabase(user_data, user):
    try:
        data = {
            "id": int(user.id),
            "full_name": user.full_name,
            "username": user.username or "None",
            "phone": user_data.get("phone", ""),
            "location_type": "Ethiopia" if user_data.get("location_type") == "et" else "Diaspora",
            "package": user_data.get("duration", ""),
            "price": user_data.get("price", ""),
            "payment_status": "Paid",
            "gender": user_data.get("gender", "Unknown"),
            "age": int(user_data.get("age", 0)) if user_data.get("age") else 0,
            "height": int(user_data.get("height", 0)) if user_data.get("height") else 0,
            "weight": int(user_data.get("weight", 0)) if user_data.get("weight") else 0,
            "goal": user_data.get("goal", "General"),
            "activity": user_data.get("activity", "Unknown"),
            "experience": user_data.get("experience", "Unknown"),
            "equipment": user_data.get("equipment", "Unknown"),
            "obstacle": user_data.get("obstacle", "Unknown"),
            "readiness": int(user_data.get("readiness", 0)) if user_data.get("readiness") else 0,
            "injuries": user_data.get("injuries", "None"),
            "diet": user_data.get("diet", "None"),
            "eating_style": user_data.get("eating_style", "Unknown"),
            "is_active": True,
            "language": user_data.get("lang", "am")
        }
        supabase.table("clients").upsert(data).execute()
        logging.info("Successfully saved client to Supabase!")
    except Exception as e:
        logging.error(f"Exception while saving to Supabase: {e}")


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
    text = "👋 <b>ገና ጥቂት ጥያቄዎች ይቀሩዎታል!</b>" if lang == "am" else "👋 <b>A few questions left!</b>"
    try: await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="HTML")
    except Exception as e: logging.error(e)


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
            ]

async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    text = get_faq_text(loc)
    back_text = "🔙 ወደ ዋጋዎች መመለስ" if lang == "am" else "🔙 Back to Pricing"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(back_text, callback_data=f"back_pricing_{loc}")]]), parse_mode="HTML")

async def back_to_pricing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_type = query.data.split("_")[2]
    lang = context.user_data.get("lang", "am")
    keyboard = get_pricing_keyboard(lang, loc_type)
    text = "⏱️ <b>የፕሮግራም ቆይታ ይምረጡ፦</b>" if lang == "am" else "⏱️ <b>Select your transformation timeframe:</b>"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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
    keyboard = [[InlineKeyboardButton("👨 ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"), InlineKeyboardButton("👩 ሴት" if lang == "am" else "👩 Female", callback_data="gen_female")]]
    await query.edit_message_text("👤 <b>ጾታዎን ይምረጡ፦</b>" if lang == "am" else "👤 <b>Select your gender:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return GENDER

async def gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["gender"] = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (በሀገር ውስጥ)", callback_data="loc_et")],
        [InlineKeyboardButton("🌍 ከሀገር ውጭ (Diaspora)", callback_data="loc_diaspora")]
    ]
    await query.edit_message_text("📍 <b>እባክዎ የሚኖሩበትን አካባቢ ይምረጡ፦</b>" if lang == "am" else "📍 <b>Select your region:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return LOCATION

async def location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["location_type"] = query.data.split("_")[1]
    lang = context.user_data.get("lang", "am")
    await query.edit_message_text("⏳ <b>እቅድዎን እያዘጋጀን ነው... እባክዎ ዕድሜዎን ይጻፉ (ምሳሌ፡ 25)፦</b>" if lang == "am" else "⏳ <b>Please enter your age (e.g., 25):</b>", parse_mode="HTML")
    return AGE

async def age_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["age"] = update.message.text.strip()
    lang = context.user_data.get("lang", "am")
    await update.message.reply_text("📏 <b>ቁመትዎ በሴንቲሜትር (cm) ስንት ነው?</b>" if lang == "am" else "📏 <b>Height in cm?</b>", parse_mode="HTML")
    return HEIGHT

async def height_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["height"] = update.message.text.strip()
    lang = context.user_data.get("lang", "am")
    await update.message.reply_text("⚖️ <b>ክብደትዎ በኪሎግራም (kg) ስንት ነው?</b>" if lang == "am" else "⚖️ <b>Weight in kg?</b>", parse_mode="HTML")
    return WEIGHT

async def weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["weight"] = update.message.text.strip()
    lang = context.user_data.get("lang", "am")
    keyboard = [
        [InlineKeyboardButton("🔥 ስብ መቀነስ" if lang == "am" else "🔥 Fat Loss", callback_data="goal_fat_loss")],
        [InlineKeyboardButton("💪 ጡንቻ መገንባት" if lang == "am" else "💪 Muscle", callback_data="goal_muscle")]
    ]
    await update.message.reply_text("🎯 <b>ዋናው ዓላማዎ ምንድን ነው?</b>" if lang == "am" else "🎯 <b>Primary goal?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return GOAL

async def goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["goal"] = "_".join(query.data.split("_")[1:])
    lang = context.user_data.get("lang", "am")
    await query.edit_message_text("📞 <b>ስልክ ቁጥርዎ ስንት ነው? (ምሳሌ፡ 0911223344)</b>" if lang == "am" else "📞 <b>Phone number?</b>", parse_mode="HTML")
    return PHONE

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text.strip()
    lang = context.user_data.get("lang", "am")
    loc_type = context.user_data.get("location_type", "et")
    keyboard = get_pricing_keyboard(lang, loc_type)
    await update.message.reply_text("⏱️ <b>የፕሮግራም ቆይታ ይምረጡ፦</b>" if lang == "am" else "⏱️ <b>Select your timeframe:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return DURATION

async def duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
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
    lang = context.user_data.get("lang", "am")

    cancel_reminder(context, "onboarding_reminder", update.effective_user.id)
    schedule_reminder(context, "payment_reminder", update.effective_user.id, lang, delay=PAYMENT_REMINDER_DELAY)

    pay_text = (
        f"💳 <b>የክፍያ መመሪያ</b>\n\n• ፓኬጅ፦ {duration_str}\n• ዋጋ፦ <b>{price_str}</b>\n\n"
        f"• <b>CBE:</b> <code>{CBE_ACCOUNT}</code>\n• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n\n"
        f"📸 ክፍያውን ፈጽመው የደረሰኙን ስክሪንሾት ይላኩ!" if lang == "am" else
        f"💳 <b>Payment Instructions</b>\n\n• Package: {duration_str}\n• Fee: <b>{price_str}</b>\n\nSend receipt screenshot below!"
    )
    await query.edit_message_text(pay_text, parse_mode="HTML")
    return RECEIPT

async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo = update.message.photo[-1]
    admin_card = f"📥 <b>NEW RECEIPT!</b>\nClient: {user.full_name} (`{user.id}`)\nProgram: {context.user_data.get('duration')} ({context.user_data.get('price')})"
    admin_keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data=f"adm_confirm_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{user.id}")]]

    for admin_id in ADMIN_USER_IDS:
        try: await context.bot.send_photo(chat_id=admin_id, photo=photo.file_id, caption=admin_card, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="HTML")
        except Exception: pass

    cancel_reminder(context, "payment_reminder", user.id)
    await update.message.reply_text("⏳ ደረሰኝዎ ደርሶናል! ሳይመን እስኪያረጋግጥ ይጠብቁ።", parse_mode="HTML")
    return ConversationHandler.END

async def admin_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, client_id_str = query.data.split("_")[1:]
    client_id = int(client_id_str)

    if action == "confirm":
        try: supabase.table("clients").update({"is_active": True}).eq("id", client_id).execute()
        except Exception: pass
        await context.bot.send_message(chat_id=client_id, text="✅ <b>Payment Approved!</b>", parse_mode="HTML")
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>STATUS:</b> ✅ APPROVED", parse_mode="HTML")
    elif action == "reject":
        await context.bot.send_message(chat_id=client_id, text="❌ Payment verification failed.", parse_mode="HTML")
        await query.edit_message_caption(caption=query.message.caption + "\n\n<b>STATUS:</b> ❌ REJECTED", parse_mode="HTML")

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
        fallbacks=[], name="onboarding", persistent=True,
    )
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))
    app.run_polling()

if __name__ == "__main__":
    main()
