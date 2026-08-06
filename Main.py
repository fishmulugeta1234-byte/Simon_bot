from datetime import datetime
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
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
# ⚙️ YOUR CONFIGURATION & CONSTANTS
# ==========================================
BOT_TOKEN = "8765027788:AAEvkGMDXd8i3EdtqVYgdrnEA4j4Lbdxk4U"
ADMIN_USER_IDS = [1622298145, 389487101]  # Both Admin IDs

# Banking & Payment Info
CBE_ACCOUNT = "1000357796532"
TELEBIRR_NUMBER = "0939998090"
ACCOUNT_NAME = "Simon mulugeta"
SUPPORT_HANDLE = "@s_simon_19"

# Google Sheets Configuration
GOOGLE_SHEET_NAME = "Fitness Clients"
CREDENTIALS_FILE = "credentials.json"

# Conversation States
(
    LANGUAGE,
    GENDER,
    LOCATION,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    ACTIVITY,
    EXPERIENCE,
    OBSTACLE,
    READINESS,
    HEALTH_INJURIES,
    DIET_RESTRICTIONS,
    PHONE,
    DURATION,
    RECEIPT,
) = range(16)


# ==========================================
# 🌐 WEB SERVER FOR RENDER KEEP-ALIVE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Bot is alive!")


def run_web_server():
  server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
  server.serve_forever()


# ==========================================
# 📊 GOOGLE SHEETS & TIMESTAMP SYNC FUNCTION
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

    # Generate exact registration timestamp with short month format (e.g. 2026-Aug-06 07:41:17)
    registration_timestamp = datetime.now().strftime("%Y-%b-%d %H:%M:%S")

    row_data = [
        registration_timestamp,
        user.full_name,
        user.username or "None",
        int(user.id),
        user_data.get("phone", ""),
        (
            "Ethiopia"
            if user_data.get("location_type") == "et"
            else "Diaspora"
        ),
        user_data.get("duration", ""),
        user_data.get("price", ""),
        "Paid",
        user_data.get("gender", "Unknown"),
        int(user_data.get("age", 0)) if user_data.get("age") else 0,
        (
            int(user_data.get("height", 0)) if user_data.get("height") else 0
        ),
        (
            int(user_data.get("weight", 0)) if user_data.get("weight") else 0
        ),
        user_data.get("goal", "General"),
        user_data.get("activity", "Unknown"),
        user_data.get("experience", "Unknown"),
        user_data.get("obstacle", "Unknown"),
        (
            int(user_data.get("readiness", 0))
            if user_data.get("readiness")
            else 0
        ),
        user_data.get("injuries", "None"),
        user_data.get("diet", "None"),
    ]

    sheet.append_row(row_data)
    logging.info("Successfully saved client and timestamp to Google Sheet!")
  except Exception as e:
    logging.error(f"Exception while saving to Google Sheet: {e}")


# ==========================================
# 📋 FAQ COMMAND & PRICING HELPER
# ==========================================
def get_faq_text(loc):
  if loc == "et":
    return (
        "📋 <b>Simon's Fitness Programs: Local Tier Guide (ETB)</b>\n\n"
        "• <b>Meal Plan Only — 799 ETB:</b> Custom nutrition plan tailored to"
        " your goals.\n\n"
        "• <b>Kickstart (21 Days) — 3,500 ETB:</b> Best for beginners building"
        " momentum. Includes fixed workout, 1 meal plan, 1 adjustment, and 3"
        " check-ins.\n\n"
        "• <b>Transformation (60 Days) — 7,000 ETB:</b> Best for fat loss &"
        " muscle building. Includes workout updated every 4 weeks, adjusted meal"
        " plan, 8 check-ins, and form reviews.\n\n"
        "• <b>Elite (90 Days) — 9,500 ETB:</b> Best for serious long-term"
        " results. Fully custom workouts, unlimited meal adjustments, ~13"
        " check-ins, and 24-hr priority support. <i>(⚠️ Only 5 spots available"
        " this month!)</i>\n\n"
        "• <b>Lifestyle (6 Months) — 18,000 ETB:</b> Best for permanent lifestyle"
        " change. New workout phase monthly, continuous planning, ongoing"
        " check-ins, and monthly goal setting.\n\n"
        "• <b>VIP (6 Months) — 30,000 ETB:</b> Maximum 1-on-1 support."
        " Live-adjusted plans, weekly video calls, unlimited messaging & form"
        " reviews, and supplement guidance.\n\n"
        f"❓ Have questions? Contact Simon directly at {SUPPORT_HANDLE}"
    )
  else:
    return (
        "📋 <b>Simon's Fitness Programs: Diaspora Tier Guide (USD)</b>\n\n"
        "• <b>Meal Plan Only — $29.99:</b> Custom nutrition plan tailored to"
        " your goals.\n\n"
        "• <b>Kickstart (21 Days) — $35:</b> Best for beginners building"
        " momentum. Includes fixed workout, 1 meal plan, 1 adjustment, and 3"
        " check-ins.\n\n"
        "• <b>Transformation (60 Days) — $89:</b> Best for fat loss & muscle"
        " building. Includes workout updated every 4 weeks, adjusted meal plan,"
        " 8 check-ins, and form reviews.\n\n"
        "• <b>Elite (90 Days) — $129:</b> Best for serious long-term results."
        " Fully custom workouts, unlimited meal adjustments, ~13 check-ins, and"
        " 24-hr priority support. <i>(⚠️ Only 5 spots available this"
        " month!)</i>\n\n"
        "• <b>Lifestyle (6 Months) — $249:</b> Best for permanent lifestyle"
        " change. New workout phase monthly, continuous planning, ongoing"
        " check-ins, and monthly goal setting.\n\n"
        "• <b>VIP (6 Months) — $449:</b> Maximum 1-on-1 support. Live-adjusted"
        " plans, weekly video calls, unlimited messaging & form reviews, and"
        " supplement guidance.\n\n"
        f"❓ Have questions? Contact Simon directly at {SUPPORT_HANDLE}"
    )


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  loc_type = context.user_data.get("location_type")

  if loc_type == "et":
    await update.message.reply_text(get_faq_text("et"), parse_mode="HTML")
  elif loc_type == "diaspora":
    await update.message.reply_text(get_faq_text("diaspora"), parse_mode="HTML")
  else:
    keyboard = [
        [
            InlineKeyboardButton(
                "🇪🇹 Local Pricing (ETB)", callback_data="faq_et"
            )
        ],
        [
            InlineKeyboardButton(
                "🌎 Diaspora Pricing (USD)", callback_data="faq_diaspora"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 <b>Simon's Fitness Programs</b>\n\nPlease select your region to view"
        " the correct program pricing tiers:",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )


async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  loc = query.data.split("_")[1]
  text = get_faq_text(loc)
  await query.edit_message_text(text, parse_mode="HTML")


# ==========================================
# 🚀 STEP 1: /START & EARLY LEAD LOGGING
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  user = update.effective_user
  context.user_data.clear()

  admin_log_msg = (
      f"🚨 <b>NEW LEAD STARTED BOT!</b>\n"
      f"👤 <b>User:</b> {user.full_name} (@{user.username or 'No_Username'})\n"
      f"🆔 <b>ID:</b> <code>{user.id}</code>"
  )
  for admin_id in ADMIN_USER_IDS:
    try:
      await context.bot.send_message(
          chat_id=admin_id, text=admin_log_msg, parse_mode="HTML"
      )
    except Exception as e:
      logging.error(f"Failed to log early lead to admin {admin_id}: {e}")

  keyboard = [
      [
          InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
          InlineKeyboardButton("🇪🇹 አማርኛ (Amharic)", callback_data="lang_am"),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  await update.message.reply_text(
      "Welcome to Simon's Transformation Portal! Please select your language /"
      " እባክዎ ቋንቋ ይምረጡ፦\n\n<i>(Type /faq anytime to compare program tiers)</i>",
      reply_markup=reply_markup,
  )
  return LANGUAGE


# ==========================================
# 👤 STEP 2: GENDER SELECTION
# ==========================================
async def language_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  lang = query.data.split("_")[1]
  context.user_data["lang"] = lang

  keyboard = [
      [
          InlineKeyboardButton(
              "👨 ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"
          ),
          InlineKeyboardButton(
              "👩 ሴት" if lang == "am" else "👩 Female",
              callback_data="gen_female",
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = "👤 <b>ጾታዎን ይምረጡ፦</b>" if lang == "am" else "👤 <b>Select your gender:</b>"
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return GENDER


# ==========================================
# 📍 STEP 3: LOCATION SELECTION & TEASER LINE
# ==========================================
async def gender_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
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
        [
            InlineKeyboardButton(
                "🇦🇪 Middle East / 🌍 ሌላ ሀገር", callback_data="loc_diaspora"
            )
        ],
    ]
    text = "📍 <b>እባክዎ የሚኖሩበትን ሀገር ይምረጡ፦</b>"
  else:
    keyboard = [
        [InlineKeyboardButton("🇪🇹 Ethiopia (Local)", callback_data="loc_et")],
        [
            InlineKeyboardButton(
                "🇺🇸 / 🇨🇦 USA / Canada", callback_data="loc_diaspora"
            )
        ],
        [
            InlineKeyboardButton(
                "🇪🇺 / 🇬🇧 Europe / UK", callback_data="loc_diaspora"
            )
        ],
        [
            InlineKeyboardButton(
                "🇦🇪 Middle East / 🌍 Other", callback_data="loc_diaspora"
            )
        ],
    ]
    text = "📍 <b>Please select your current country of residence:</b>"

  reply_markup = InlineKeyboardMarkup(keyboard)
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return LOCATION


# ==========================================
# 📊 STEP 4: VITAL BODY STATS (WITH TEASER)
# ==========================================
async def location_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  location_type = query.data.split("_")[1]
  context.user_data["location_type"] = location_type
  lang = context.user_data.get("lang", "am")

  # Send the requested teaser message before asking for age/height/weight
  if lang == "am":
    teaser_msg = (
        "⏳ <b>በግምት በ3 ደቂቃ ውስጥ የእርስዎን ብጁ (Custom) ዕቅድ እናዘጋጃለን።</b>\n"
        "ክብረወሰናችን፦ ከ2024 ጀምሮ ከ200 በላይ ሰዎችን ሰውነት ለውጠናል — አሁን የእርስዎ መሠረት"
        " ይጀምራል!"
    )
  else:
    teaser_msg = (
        "⏳ <b>In about 3 minutes I'll put together your custom plan.</b>\nOver"
        " 200 clients transformed since 2024 — let's get started!"
    )

  await query.edit_message_text(teaser_msg, parse_mode="HTML")

  # Prompt for age immediately after
  age_prompt = (
      "🎂 <b>ዕድሜዎ ስንት ነው?</b> (ምሳሌ፡ 25)"
      if lang == "am"
      else "🎂 <b>How old are you?</b> (e.g., 25)"
  )
  await query.message.reply_text(age_prompt, parse_mode="HTML")
  return AGE


async def age_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  lang = context.user_data.get("lang", "am")
  age_text = update.message.text.strip()

  if not age_text.isdigit() or not (12 <= int(age_text) <= 100):
    error_msg = (
        "❌ እባክዎ ትክክለኛ ዕድሜ በቁጥር ያስገቡ (12-100)፦"
        if lang == "am"
        else "❌ Please enter a valid age as a number (12-100):"
    )
    await update.message.reply_text(error_msg)
    return AGE

  context.user_data["age"] = age_text

  text = (
      "📏 <b>ቁመትዎ በሴንቲሜትር (cm) ስንት ነው?</b> (ምሳሌ፡ 175)"
      if lang == "am"
      else "📏 <b>What is your height in centimeters (cm)?</b> (e.g., 175)"
  )
  await update.message.reply_text(text, parse_mode="HTML")
  return HEIGHT


async def height_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  lang = context.user_data.get("lang", "am")
  height_text = update.message.text.strip()

  if not height_text.isdigit() or not (100 <= int(height_text) <= 250):
    error_msg = (
        "❌ እባክዎ ትክክለኛ ቁመት በሴንቲሜትር ያስገቡ (100-250)፦"
        if lang == "am"
        else "❌ Please enter a valid height in cm (100-250):"
    )
    await update.message.reply_text(error_msg)
    return HEIGHT

  context.user_data["height"] = height_text

  text = (
      "⚖️ <b>የአሁኑ ክብደትዎ በኪሎግራም (kg) ስንት ነው?</b> (ምሳሌ፡ 75)"
      if lang == "am"
      else "⚖️ <b>What is your current weight in kilograms (kg)?</b> (e.g., 75)"
  )
  await update.message.reply_text(text, parse_mode="HTML")
  return WEIGHT


async def weight_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  lang = context.user_data.get("lang", "am")
  weight_text = update.message.text.strip()

  if not weight_text.isdigit() or not (30 <= int(weight_text) <= 300):
    error_msg = (
        "❌ እባክዎ ትክክለኛ ክብደት በኪሎግራም ያስገቡ (30-300)፦"
        if lang == "am"
        else "❌ Please enter a valid weight in kg (30-300):"
    )
    await update.message.reply_text(error_msg)
    return WEIGHT

  context.user_data["weight"] = weight_text

  keyboard = [
      [
          InlineKeyboardButton(
              "🔥 ስብ መቀነስ / ቦርጭ ማጥፋት"
              if lang == "am"
              else "🔥 Fat Loss / Tummy Reduction",
              callback_data="goal_fat_loss",
          )
      ],
      [
          InlineKeyboardButton(
              "💪 የሰውነት ጡንቻ መገንባት"
              if lang == "am"
              else "💪 Muscle Building",
              callback_data="goal_muscle",
          )
      ],
      [
          InlineKeyboardButton(
              "⚡ የጉልበት እና ብቃት ማሳደግ"
              if lang == "am"
              else "⚡ Athletic Performance",
              callback_data="goal_performance",
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = (
      "🎯 <b>ዋናው የፊትነስ ዓላማዎ ምንድን ነው?</b>"
      if lang == "am"
      else "🎯 <b>What is your primary fitness goal?</b>"
  )
  await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return GOAL


# ==========================================
# 🎯 STEP 5: GOAL & ACTIVITY LEVEL
# ==========================================
async def goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  query = update.callback_query
  await query.answer()

  goal = query.data.split("_")[1]
  context.user_data["goal"] = goal
  lang = context.user_data.get("lang", "am")

  keyboard = [
      [
          InlineKeyboardButton(
              "🛋️ እንቅስቃሴ የሌለው (የተቀመጠ)"
              if lang == "am"
              else "🛋️ Sedentary (Office Job)",
              callback_data="act_sedentary",
          )
      ],
      [
          InlineKeyboardButton(
              "🚶 መካከለኛ (በሳምንት 1-3 ቀን)"
              if lang == "am"
              else "🚶 Moderate (1-3 days/wk)",
              callback_data="act_moderate",
          )
      ],
      [
          InlineKeyboardButton(
              "🏋️ ከፍተኛ (በሳምንት 4+ ቀን)"
              if lang == "am"
              else "🏋️ High Activity (4+ days/wk)",
              callback_data="act_high",
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = (
      "🏃 <b>ዕለታዊ እንቅስቃሴዎ ምን ይመስላል?</b>"
      if lang == "am"
      else "🏃 <b>What is your daily activity level?</b>"
  )
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return ACTIVITY


# ==========================================
# ⭐ STEP 6: HIGH-QUALIFYING QUESTIONS
# ==========================================
async def activity_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  activity = query.data.split("_")[1]
  context.user_data["activity"] = activity
  lang = context.user_data.get("lang", "am")

  keyboard = [
      [
          InlineKeyboardButton(
              "🟢 ገና ጀማሪ" if lang == "am" else "🟢 Beginner (New to gym)",
              callback_data="exp_beginner",
          )
      ],
      [
          InlineKeyboardButton(
              "🟡 መካከለኛ"
              if lang == "am"
              else "🟡 Intermediate (Knows basics)",
              callback_data="exp_intermediate",
          )
      ],
      [
          InlineKeyboardButton(
              "🔴 ልምድ ያለው"
              if lang == "am"
              else "🔴 Advanced (Stuck at plateau)",
              callback_data="exp_advanced",
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = (
      "🏋️ <b>የስፖርት ወይም የጂም ልምድዎ ምን ይመስላል?</b>"
      if lang == "am"
      else "🏋️ <b>What is your training experience level?</b>"
  )
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return EXPERIENCE


async def experience_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  exp = query.data.split("_")[1]
  context.user_data["experience"] = exp
  lang = context.user_data.get("lang", "am")

  keyboard = [
      [
          InlineKeyboardButton(
              "🍱 የምግብ ሥርዓት አለመጠበቅ"
              if lang == "am"
              else "🍱 Bad Diet & Nutrition",
              callback_data="obs_diet",
          )
      ],
      [
          InlineKeyboardButton(
              "⏰ የጊዜ እጥረት" if lang == "am" else "⏰ Lack of Time",
              callback_data="obs_time",
          )
      ],
      [
          InlineKeyboardButton(
              "📉 ወጥነት ማጣት" if lang == "am" else "📉 Lack of Consistency",
              callback_data="obs_consistency",
          )
      ],
      [
          InlineKeyboardButton(
              "❓ ምን መሥራት እንዳለብኝ አለማወቅ"
              if lang == "am"
              else "❓ No Structured Plan",
              callback_data="obs_plan",
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = (
      "🚧 <b>አሁን ላይ ለውጥ እንዳያመጡ ትልቁ ፈተናዎ ምንድን ነው?</b>"
      if lang == "am"
      else "🚧 <b>What is your biggest obstacle right now?</b>"
  )
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return OBSTACLE


async def obstacle_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  obs = query.data.split("_")[1]
  context.user_data["obstacle"] = obs
  lang = context.user_data.get("lang", "am")

  keyboard = [
      [
          InlineKeyboardButton(
              "⚡ 10 - ዛሬውኑ ለመጀመር 100% ዝግጁ ነኝ!"
              if lang == "am"
              else "⚡ 10 - Ready to start today!",
              callback_data="read_10",
          )
      ],
      [
          InlineKeyboardButton(
              "📈 7-9 - ዝግጁ ነኝ፣ ትክክለኛ ፕሮግራም ብቻ ነው የሚያስፈልገኝ"
              if lang == "am"
              else "📈 7-9 - Ready with the right plan",
              callback_data="read_7-9",
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  text = (
      "🔥 <b>ከ1-10 ባለው ደረጃ፣ ሰውነትዎን ለመለወጥ አሁን ምን ያህል ተዘጋጅተዋል?</b>"
      if lang == "am"
      else "🔥 <b>On a scale of 1–10, how ready are you to transform your body?</b>"
  )
  await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return READINESS


# ==========================================
# 🩺 STEP 7: HEALTH, DIET & PHONE COLLECTION
# ==========================================
async def readiness_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  readiness = query.data.split("_")[1]
  context.user_data["readiness"] = readiness
  lang = context.user_data.get("lang", "am")

  text = (
      "🩹 <b>ማንኛውም የሰውነት ጉዳት ወይም የጤና ሁኔታ አለብዎት?</b>\n<i>(ከሌለ 'የለም' ብለው"
      " ይጻፉ)</i>"
      if lang == "am"
      else "🩹 <b>Do you have any injuries or medical conditions?</b>\n<i>(If"
      " none, reply 'None')</i>"
  )
  await query.edit_message_text(text, parse_mode="HTML")
  return HEALTH_INJURIES


async def health_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  lang = context.user_data.get("lang", "am")
  context.user_data["injuries"] = update.message.text.strip()

  text = (
      "🥗 <b>ማንኛውም የማይስማማዎት ወይም የማይወዱት ምግብ አለ?</b>\n<i>(ከሌለ 'የለም' ብለው"
      " ይጻፉ)</i>"
      if lang == "am"
      else "🥗 <b>Do you have any food allergies or severe dislikes?</b>\n<i>(If"
      " none, reply 'None')</i>"
  )
  await update.message.reply_text(text, parse_mode="HTML")
  return DIET_RESTRICTIONS


async def diet_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  lang = context.user_data.get("lang", "am")
  context.user_data["diet"] = update.message.text.strip()

  text = (
      "📞 <b>ለቀጣይ ክትትል የሚሆን ስልክ ቁጥርዎ ስንት ነው?</b> (ምሳሌ፡ 0911223344)"
      if lang == "am"
      else (
          "📞 <b>What is your phone number for follow-up?</b> (e.g.,"
          " +251911223344 or 0911223344)"
      )
  )
  await update.message.reply_text(text, parse_mode="HTML")
  return PHONE


async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  lang = context.user_data.get("lang", "am")
  context.user_data["phone"] = update.message.text.strip()
  loc_type = context.user_data.get("location_type", "et")

  if lang == "am":
    if loc_type == "et":
      keyboard = [
          [
              InlineKeyboardButton(
                  "🥗 የምግብ እቅድ ብቻ (Meal Plan Only) — 799 ETB",
                  callback_data="dur_Meal_Plan_Only_799ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥉 Kickstart (21-ቀን ፈጣን ጅማሬ) — 3,500 ETB",
                  callback_data="dur_Kickstart_(21_Days)_3500ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥈 Transformation (60-ቀን የሰውነት ለውጥ) — 7,000 ETB",
                  callback_data="dur_Transformation_(60_Days)_7000ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥇 Elite (90-ቀን ከፍተኛ ደረጃ) ⚠️ (በዚህ ወር 5 ቦታዎች ብቻ!) —"
                  " 9,500 ETB",
                  callback_data="dur_Elite_Transformation_(90_Days)_9500ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "💎 Lifestyle (6-ወር የአኗኗር ዘይቤ) — 18,000 ETB",
                  callback_data="dur_Lifestyle_Coaching_(6_Months)_18000ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "👑 VIP (6-ወር ቪአይፒ) — 30,000 ETB",
                  callback_data="dur_VIP_Coaching_(6_Months)_30000ETB",
              )
          ],
      ]
    else:
      keyboard = [
          [
              InlineKeyboardButton(
                  "🥗 የምግብ እቅድ ብቻ (Meal Plan Only) — $29.99",
                  callback_data="dur_Meal_Plan_Only_$29.99",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥉 Kickstart (21-ቀን ፈጣን ጅማሬ) — $35",
                  callback_data="dur_Kickstart_(21_Days)_$35",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥈 Transformation (60-ቀን የሰውነት ለውጥ) — $89",
                  callback_data="dur_Transformation_(60_Days)_$89",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥇 Elite (90-ቀን ከፍተኛ ደረጃ) ⚠️ (Only 5 spots this month!)"
                  " — $129",
                  callback_data="dur_Elite_Transformation_(90_Days)_$129",
              )
          ],
          [
              InlineKeyboardButton(
                  "💎 Lifestyle (6-ወር የአኗኗር ዘይቤ) — $249",
                  callback_data="dur_Lifestyle_Coaching_(6_Months)_$249",
              )
          ],
          [
              InlineKeyboardButton(
                  "👑 VIP (6-ወር ቪአይፒ) — $449",
                  callback_data="dur_VIP_Coaching_(6_Months)_$449",
              )
          ],
      ]
  else:
    if loc_type == "et":
      keyboard = [
          [
              InlineKeyboardButton(
                  "🥗 Meal Plan Only — 799 ETB",
                  callback_data="dur_Meal_Plan_Only_799ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥉 Kickstart (21 Days) — 3,500 ETB",
                  callback_data="dur_Kickstart_(21_Days)_3500ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥈 Transformation (60 Days) — 7,000 ETB",
                  callback_data="dur_Transformation_(60_Days)_7000ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥇 Elite (90 Days) ⚠️ (Only 5 spots this month!) — 9,500"
                  " ETB",
                  callback_data="dur_Elite_Transformation_(90_Days)_9500ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "💎 Lifestyle (6 Months) — 18,000 ETB",
                  callback_data="dur_Lifestyle_Coaching_(6_Months)_18000ETB",
              )
          ],
          [
              InlineKeyboardButton(
                  "👑 VIP (6 Months) — 30,000 ETB",
                  callback_data="dur_VIP_Coaching_(6_Months)_30000ETB",
              )
          ],
      ]
    else:
      keyboard = [
          [
              InlineKeyboardButton(
                  "🥗 Meal Plan Only — $29.99",
                  callback_data="dur_Meal_Plan_Only_$29.99",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥉 Kickstart (21 Days) — $35",
                  callback_data="dur_Kickstart_(21_Days)_$35",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥈 Transformation (60 Days) — $89",
                  callback_data="dur_Transformation_(60_Days)_$89",
              )
          ],
          [
              InlineKeyboardButton(
                  "🥇 Elite (90 Days) ⚠️ (Only 5 spots this month!) — $129",
                  callback_data="dur_Elite_Transformation_(90_Days)_$129",
              )
          ],
          [
              InlineKeyboardButton(
                  "💎 Lifestyle (6 Months) — $249",
                  callback_data="dur_Lifestyle_Coaching_(6_Months)_$249",
              )
          ],
          [
              InlineKeyboardButton(
                  "👑 VIP (6 Months) — $449",
                  callback_data="dur_VIP_Coaching_(6_Months)_$449",
              )
          ],
      ]

  text = (
      "⏱️ <b>ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦</b>\n\n"
      "⚠️ <i>ማስታወሻ፦ ለኤሊት (Elite) ፓኬጅ በዚህ ወር ተቀባይነት ያላቸው <b>5 ሰዎች ብቻ</b>"
      " ናቸው!\n\n</i>"
      "💡 <i>የምርጫ ልዩነቶችን ለማየት /faq የሚለውን ትዕዛዝ መጠቀም ይችላሉ።</i>"
      if lang == "am"
      else (
          "⏱️ <b>Select your transformation timeframe:</b>\n\n⚠️ <i>Note: Only"
          " accepting 5 new Elite clients this month!\n\n</i>💡 <i>Type /faq"
          " anytime to review tier differences.</i>"
      )
  )
  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
  return DURATION


# ==========================================
# ⏱️ STEP 8: DURATION & PRICING
# ==========================================
async def duration_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  data = query.data
  if "Meal_Plan_Only" in data:
    duration_str = "Meal Plan Only"
    price_str = (
        "799 ETB" if "799" in data else ("$29.99" if "$29.99" in data else "$29.99")
    )
  else:
    dur_info = data.split("_")[1:]
    duration_str = dur_info[0]
    price_str = dur_info[1]

  context.user_data["duration"] = duration_str
  context.user_data["price"] = price_str

  lang = context.user_data.get("lang", "am")
  loc_type = context.user_data.get("location_type", "et")

  if lang == "am":
    if loc_type == "et":
      pay_text = (
          f"💳 <b>የክፍያ መመሪያ (ለሀገር ውስጥ)</b>\n\n"
          f"⏱️ <b>የተመረጠው ፕሮግራም፦</b> {duration_str}\n"
          f"💰 <b>ክፍያ መጠን፦</b> <b>{price_str}</b>\n\n"
          f"እባክዎ ክፍያውን በሚከተሉት የባንክ ሂሳቦች ያስገቡ፦\n"
          f"• <b>CBE Bank:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>ስም:</b> {ACCOUNT_NAME}\n\n"
          f"📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን <b>ግልጽ ስክሪንሽኦት ወይም ፎቶ</b> እዚህ"
          f" ይላኩ።\n\n"
          f"❓ <b>ጥያቄ ካለዎት በቀጥታ ያግኙን፦</b> {SUPPORT_HANDLE}"
      )
    else:
      pay_text = (
          f"💳 <b>የክፍያ መመሪያ (ለዲያስፖራ/ውጭ ሀገር)</b>\n\n"
          f"⏱️ <b>የተመረጠው ፕሮግራም፦</b> {duration_str}\n"
          f"💰 <b>ክፍያ መጠን፦</b> <b>{price_str}</b>\n\n"
          f"በ <b>International Card ወይም Remittance (Wise / Western Union /"
          f" Telebirr)</b> በመጠቀም በቀጥታ መክፈል ይችላሉ፦\n"
          f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>የመለያ ስም:</b> {ACCOUNT_NAME}\n\n"
          f"📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን <b>ግልጽ ስክሪንሽኦት ወይም ፎቶ</b> እዚህ"
          f" ይላኩ።\n\n"
          f"❓ <b>ጥያቄ ካለዎት በቀጥታ ያግኙን፦</b> {SUPPORT_HANDLE}"
      )
  else:
    if loc_type == "et":
      pay_text = (
          f"💳 <b>Payment Instructions (Local)</b>\n\n"
          f"⏱️ <b>Selected Program:</b> {duration_str}\n"
          f"💰 <b>Total Fee:</b> <b>{price_str}</b>\n\n"
          f"Please make the transfer to the following accounts:\n"
          f"• <b>CBE Bank:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>Account Name:</b> {ACCOUNT_NAME}\n\n"
          f"📸 Once completed, please send a <b>clear screenshot or photo</b> of"
          f" your receipt below.\n\n"
          f"❓ <b>Questions? Contact Simon directly:</b> {SUPPORT_HANDLE}"
      )
    else:
      pay_text = (
          f"💳 <b>Payment Instructions (Diaspora)</b>\n\n"
          f"⏱️ <b>Selected Program:</b> {duration_str}\n"
          f"💰 <b>Total Fee:</b> <b>{price_str}</b>\n\n"
          f"📲 <b>How to Pay:</b>\n"
          f"Use <b>International Cards, Wise, or Remittance apps (Western Union"
          f" / Telebirr)</b> to complete payment:\n"
          f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>Account Name:</b> {ACCOUNT_NAME}\n\n"
          f"📸 Once completed, please send a <b>clear screenshot or photo</b> of"
          f" your receipt below.\n\n"
          f"❓ <b>Questions? Contact Simon directly:</b> {SUPPORT_HANDLE}"
      )

  await query.edit_message_text(pay_text, parse_mode="HTML")
  return RECEIPT


# ==========================================
# 📥 STEP 9: RECEIPT PROCESSING & GOOGLE SHEET SYNC
# ==========================================
async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  user = update.effective_user
  photo = update.message.photo[-1]
  lang = context.user_data.get("lang", "am")
  loc_type = context.user_data.get("location_type", "et")

  loc = "🇪🇹 Ethiopia" if loc_type == "et" else "🌎 Diaspora"

  # Generate exact registration timestamp with short month format (e.g. 2026-Aug-06 07:41:17)
  registration_timestamp = datetime.now().strftime("%Y-%b-%d %H:%M:%S")

  # Save lead and timestamp directly to Google Sheet
  save_lead_to_google_sheet(context.user_data, user)

  admin_card = (
      f"📥 <b>NEW PAID INTAKE RECEIVED!</b>\n"
      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
      f"👤 <b>Client:</b> {user.full_name} (@{user.username or 'No_Username'})\n"
      f"📞 <b>Phone:</b> {context.user_data.get('phone')}\n"
      f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
      f"📅 <b>Registered At:</b> {registration_timestamp}\n"
      f"🌐 <b>Language:</b> {'Amharic' if lang == 'am' else 'English'}\n"
      f"📍 <b>Location:</b> {loc}\n"
      f"⏱️ <b>Program:</b> {context.user_data.get('duration')}"
      f" ({context.user_data.get('price')})\n\n"
      f"📊 <b>Body Profile:</b>\n"
      f"• <b>Gender:</b> {context.user_data.get('gender')} | <b>Age:</b>"
      f" {context.user_data.get('age')} yrs\n"
      f"• <b>Height:</b> {context.user_data.get('height')} cm |"
      f" <b>Weight:</b> {context.user_data.get('weight')} kg\n"
      f"• <b>Goal:</b> {context.user_data.get('goal')} | <b>Activity:</b>"
      f" {context.user_data.get('activity')}\n\n"
      f"⭐ <b>Qualification Profile:</b>\n"
      f"• <b>Experience:</b> {context.user_data.get('experience')}\n"
      f"• <b>Obstacle:</b> {context.user_data.get('obstacle')}\n"
      f"• <b>Readiness Score:</b> {context.user_data.get('readiness')}/10\n\n"
      f"🩺 <b>Health & Preferences:</b>\n"
      f"• <b>Injuries:</b> {context.user_data.get('injuries')}\n"
      f"• <b>Diet Dislikes:</b> {context.user_data.get('diet')}"
  )

  admin_keyboard = [
      [
          InlineKeyboardButton(
              "✅ Confirm Payment", callback_data=f"adm_confirm_{user.id}"
          ),
          InlineKeyboardButton(
              "❌ Reject", callback_data=f"adm_reject_{user.id}"
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(admin_keyboard)

  for admin_id in ADMIN_USER_IDS:
    try:
      await context.bot.send_photo(
          chat_id=admin_id,
          photo=photo.file_id,
          caption=admin_card,
          reply_markup=reply_markup,
          parse_mode="HTML",
      )
    except Exception as e:
      logging.error(f"Failed to send receipt to admin {admin_id}: {e}")

  if lang == "am":
    confirm_msg = (
        "🎉 <b>ደስ ብሎናል! የክፍያ ደረሰኝዎ በሰላም ደርሶናል!</b>\n\n"
        "📋 <b>ቀጣይ እርምጃችን ምን ይሆናል?</b>\n"
        "• ሳይመን ያስገቡትን መረጃ እና ደረሰኝ አሁን እየገመገመ ይገኛል።\n"
        "• እርስዎ ይህንን ታላቅ መንገድ ጀምረዋል፤ አብረን አስደናቂ ለውጥ እናመጣለን እንዲሁም ግቦችዎን እንዲመቱ"
        " እግዝዎታለሁ! የተዘጋጀውን የሥልጠና እና የምግብ ፕሮግራምዎን <b>በ24 ሰዓታት ውስጥ</b>"
        " እዚሁ ቻት ላይ ይላክልዎታል።\n\n"
        "💪 <i>ወደ አዲሱ እና ጠንካራው ማንነትዎ ለሚያደርጉት ጉዞ እንኳን ደስ አለዎት!</i>"
    )
  else:
    confirm_msg = (
        "🎉 <b>Receipt Successfully Received!</b>\n\n"
        "📋 <b>Next Steps:</b>\n"
        "• Simon is currently reviewing your assessment data and receipt.\n"
        "• You are starting this great path, and we are going to create your"
        " amazing transformation together to help you achieve your goals! You"
        " will receive your fully customized plan <b>within 24 hours</b>"
        " directly in this chat.\n\n"
        "💪 <i>Welcome aboard, let's build something amazing together!</i>"
    )

  await update.message.reply_text(confirm_msg, parse_mode="HTML")
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
            "✅ <b>Payment Approved!</b> Simon has verified your receipt. You"
            " are starting this incredible path, and we're going to build your"
            " amazing transformation together! Expect your custom plan shortly."
        ),
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
            "❌ <b>Payment Alert:</b> We could not verify your receipt"
            " screenshot. Please contact Simon directly to double-check."
        ),
        parse_mode="HTML",
    )
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n<b>STATUS:</b> ❌ REJECTED",
        parse_mode="HTML",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  await update.message.reply_text("Process cancelled.")
  return ConversationHandler.END


# ==========================================
# 🏁 MAIN ENTRY POINT WITH PERSISTENCE
# ==========================================
def main():
  threading.Thread(target=run_web_server, daemon=True).start()

  # Enable persistence so users never lose their progress if they drop off halfway
  persistence = PicklePersistence(filepath="bot_persistence")

  app = (
      ApplicationBuilder()
      .token(BOT_TOKEN)
      .persistence(persistence)
      .build()
  )

  # Add standalone FAQ command and callback handlers
  app.add_handler(CommandHandler("faq", faq_command))
  app.add_handler(CallbackQueryHandler(faq_callback, pattern="^faq_"))

  conv_handler = ConversationHandler(
      entry_points=[CommandHandler("start", start)],
      states={
          LANGUAGE: [CallbackQueryHandler(language_choice, pattern="^lang_")],
          GENDER: [CallbackQueryHandler(gender_choice, pattern="^gen_")],
          LOCATION: [CallbackQueryHandler(location_choice, pattern="^loc_")],
          AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_input)],
          HEIGHT: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, height_input)
          ],
          WEIGHT: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, weight_input)
          ],
          GOAL: [CallbackQueryHandler(goal_choice, pattern="^goal_")],
          ACTIVITY: [CallbackQueryHandler(activity_choice, pattern="^act_")],
          EXPERIENCE: [
              CallbackQueryHandler(experience_choice, pattern="^exp_")
          ],
          OBSTACLE: [CallbackQueryHandler(obstacle_choice, pattern="^obs_")],
          READINESS: [CallbackQueryHandler(readiness_choice, pattern="^read_")],
          HEALTH_INJURIES: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, health_input)
          ],
          DIET_RESTRICTIONS: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, diet_input)
          ],
          PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input)],
          DURATION: [CallbackQueryHandler(duration_choice, pattern="^dur_")],
          RECEIPT: [MessageHandler(filters.PHOTO, receipt_upload)],
      },
      fallbacks=[CommandHandler("cancel", cancel)],
      name="onboarding_conversation",
      persistent=True,
  )

  app.add_handler(conv_handler)
  app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))

  print(
      "⚡ Simon Telegram Bot with Persistence, Google Sheets, & Teaser Lines is"
      " live..."
  )
  app.run_polling()


if __name__ == "__main__":
  main()
