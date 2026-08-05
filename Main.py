import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
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

# Notion Configuration (Token pulled securely from Render environment variables)
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "YOUR_NOTION_INTEGRATION_SECRET_HERE")
NOTION_DATABASE_ID = "3b3e7db3-44ce-81c4-b09d-002711ca0f56"

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
# 📓 NOTION ORGANIZED SYNC FUNCTION
# ==========================================
def save_lead_to_notion(user_data, user):
  if not NOTION_TOKEN or NOTION_TOKEN == "YOUR_NOTION_INTEGRATION_SECRET_HERE":
    logging.warning("Notion token not configured. Skipping Notion sync.")
    return

  url = "https://api.notion.com/v1/pages"
  headers = {
      "Authorization": f"Bearer {NOTION_TOKEN}",
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28",
  }

  payload = {
      "parent": {"database_id": NOTION_DATABASE_ID},
      "properties": {
          "Name": {"title": [{"text": {"content": user.full_name}}]},
          "Phone": {"phone_number": user_data.get("phone", "")},
          "Telegram ID": {"number": int(user.id)},
          "Username": {
              "rich_text": [{"text": {"content": user.username or "None"}}]
          },
          "Program": {
              "rich_text": [{"text": {"content": user_data.get("duration", "")}}]
          },
          "Price": {
              "rich_text": [{"text": {"content": user_data.get("price", "")}}]
          },
          "Status": {"status": {"name": "Paid"}},
          "Location": {
              "select": {
                  "name": (
                      "Ethiopia"
                      if user_data.get("location_type") == "et"
                      else "Diaspora"
                  )
              }
          },
          "Goal": {"select": {"name": user_data.get("goal", "General")}},
          "Age": {
              "number": (
                  int(user_data.get("age", 0)) if user_data.get("age") else 0
              )
          },
          "Height": {
              "number": (
                  int(user_data.get("height", 0))
                  if user_data.get("height")
                  else 0
              )
          },
          "Weight": {
              "number": (
                  int(user_data.get("weight", 0))
                  if user_data.get("weight")
                  else 0
              )
          },
          "Gender": {"select": {"name": user_data.get("gender", "Unknown")}},
          "Experience": {
              "select": {"name": user_data.get("experience", "Unknown")}
          },
          "Obstacle": {
              "select": {"name": user_data.get("obstacle", "Unknown")}
          },
          "Readiness": {
              "number": (
                  int(user_data.get("readiness", 0))
                  if user_data.get("readiness")
                  else 0
              )
          },
          "Injuries": {
              "rich_text": [
                  {"text": {"content": user_data.get("injuries", "None")}}
              ]
          },
          "Diet Dislikes": {
              "rich_text": [
                  {"text": {"content": user_data.get("diet", "None")}}
              ]
          },
      },
  }

  try:
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
      logging.error(f"Failed to save to Notion: {response.text}")
    else:
      logging.info("Successfully saved client to Notion database!")
  except Exception as e:
    logging.error(f"Exception while saving to Notion: {e}")


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
      " እባክዎ ቋንቋ ይምረጡ፦",
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
# 📍 STEP 3: LOCATION SELECTION
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
# 📊 STEP 4: VITAL BODY STATS
# ==========================================
async def location_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
  query = update.callback_query
  await query.answer()

  location_type = query.data.split("_")[1]
  context.user_data["location_type"] = location_type
  lang = context.user_data.get("lang", "am")

  text = (
      "🎂 <b>ዕድሜዎ ስንት ነው?</b> (ምሳሌ፡ 25)"
      if lang == "am"
      else "🎂 <b>How old are you?</b> (e.g., 25)"
  )
  await query.edit_message_text(text, parse_mode="HTML")
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
                "🥇 Elite Transformation (90 Days) — 9,500 ETB",
                callback_data="dur_Elite_Transformation_(90_Days)_9500ETB",
            )
        ],
        [
            InlineKeyboardButton(
                "💎 Lifestyle Coaching (6 Months) — 18,000 ETB",
                callback_data="dur_Lifestyle_Coaching_(6_Months)_18000ETB",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 VIP Coaching (6 Months) — 30,000 ETB",
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
                "🥇 Elite Transformation (90 Days) — $129",
                callback_data="dur_Elite_Transformation_(90_Days)_$129",
            )
        ],
        [
            InlineKeyboardButton(
                "💎 Lifestyle Coaching (6 Months) — $249",
                callback_data="dur_Lifestyle_Coaching_(6_Months)_$249",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 VIP Coaching (6 Months) — $449",
                callback_data="dur_VIP_Coaching_(6_Months)_$449",
            )
        ],
    ]

  text = (
      "⏱️ <b>ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦</b>"
      if lang == "am"
      else "⏱️ <b>Select your transformation timeframe:</b>"
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
    price_str = "799 ETB" if "799" in data else "$29.99"
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
          f"📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን <b>ግልጽ ስክሪንሽኦት ወይም ፎቶ</b> እዚህ ይላኩ።"
      )
    else:
      pay_text = (
          f"💳 <b>የክፍያ መመሪያ (ለዲያስፖራ/ውጭ ሀገር)</b>\n\n"
          f"⏱️ <b>የተመረጠው ፕሮግራም፦</b> {duration_str}\n"
          f"💰 <b>ክፍያ መጠን፦</b> <b>{price_str}</b>\n\n"
          f"በ <b>Grey.co</b> virtual account በመጠቀም በቀጥታ መክፈል ይችላሉ፦\n"
          f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>የመለያ ስም:</b> {ACCOUNT_NAME}\n\n"
          f"📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን <b>ግልጽ ስክሪንሽኦት ወይም ፎቶ</b> እዚህ ይላኩ።"
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
          " your receipt below."
      )
    else:
      pay_text = (
          f"💳 <b>Payment Instructions (Diaspora)</b>\n\n"
          f"⏱️ <b>Selected Program:</b> {duration_str}\n"
          f"💰 <b>Total Fee:</b> <b>{price_str}</b>\n\n"
          f"📲 <b>How to Pay:</b>\n"
          f"Use your <b>Grey.co</b> virtual account to complete payment:\n"
          f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
          f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
          f"• <b>Account Name:</b> {ACCOUNT_NAME}\n\n"
          f"📸 Once completed, please send a <b>clear screenshot or photo</b> of"
          " your receipt below."
      )

  await query.edit_message_text(pay_text, parse_mode="HTML")
  return RECEIPT


# ==========================================
# 📥 STEP 9: RECEIPT PROCESSING & NOTION SYNC
# ==========================================
async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  user = update.effective_user
  photo = update.message.photo[-1]
  lang = context.user_data.get("lang", "am")
  loc_type = context.user_data.get("location_type", "et")

  loc = "🇪🇹 Ethiopia" if loc_type == "et" else "🌎 Diaspora"

  save_lead_to_notion(context.user_data, user)

  admin_card = (
      f"📥 <b>NEW PAID INTAKE RECEIVED!</b>\n"
      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
      f"👤 <b>Client:</b> {user.full_name} (@{user.username or 'No_Username'})\n"
      f"📞 <b>Phone:</b> {context.user_data.get('phone')}\n"
      f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
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
        "• በእርስዎ ግብ እና ሁኔታ ልክ በጥንቃቄ የተዘጋጀውን የሥልጠና እና የምግብ ፕሮግራምዎን"
        " <b>በ24 ሰዓታት ውስጥ</b> እዚሁ ቻት ላይ ይላክልዎታል።\n\n"
        "💪 <i>ወደ አዲሱ እና ጠንካራው ማንነትዎ ለሚያደርጉት ጉዞ እንኳን ደስ አለዎት! አብረን"
        " አስደናቂ ለውጥ እናመጣለን!</i>"
    )
  else:
    confirm_msg = (
        "🎉 <b>Receipt Successfully Received!</b>\n\n"
        "📋 <b>Next Steps:</b>\n"
        "• Simon is currently reviewing your assessment data and receipt.\n"
        "• You will receive your fully customized workout & nutrition plan"
        " <b>within 24 hours</b> directly in this chat.\n\n"
        "💪 <i>Welcome aboard, let's get to work!</i>"
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
            "✅ <b>Payment Approved!</b> Simon has verified your receipt."
            " Expect your plan shortly!"
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
# 🏁 MAIN ENTRY POINT
# ==========================================
def main():
  threading.Thread(target=run_web_server, daemon=True).start()

  app = ApplicationBuilder().token(BOT_TOKEN).build()

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
  )

  app.add_handler(conv_handler)
  app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))

  print("⚡ Simon Telegram Bot with Meal Plan Only Tier is live...")
  app.run_polling()


if __name__ == "__main__":
  main()
