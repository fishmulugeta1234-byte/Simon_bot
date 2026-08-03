import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
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
ADMIN_USER_IDS = [1622298145, 389487101]  # Both Admin IDs added

# Banking & Payment Info
CBE_ACCOUNT = "1000357796532"
TELEBIRR_NUMBER = "0939998090"
ACCOUNT_NAME = "Simon mulugeta"

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
    DURATION,
    RECEIPT,
) = range(15)


# ==========================================
# 🚀 STEP 1: /START & EARLY LEAD LOGGING
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()  # Reset session data

    # 🚨 SECRET EARLY ADMIN LOG: Sent to all Admin IDs
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

    # Language Selection Markup
    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇪🇹 አማርኛ (Amharic)", callback_data="lang_am"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to Simon's Transformation Portal! Please select your language / እባክዎ ቋንቋ ይምረጡ፦",
        reply_markup=reply_markup,
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

    keyboard = [
        [
            InlineKeyboardButton(
                "👨 Male / ወንድ" if lang == "am" else "👨 Male", callback_data="gen_male"
            ),
            InlineKeyboardButton(
                "👩 Female / ሴት" if lang == "am" else "👩 Female",
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
async def gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    gender = query.data.split("_")[1]
    context.user_data["gender"] = gender
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (Ethiopia)", callback_data="loc_et")],
        [InlineKeyboardButton("🇺🇸 / 🇨🇦 USA / Canada", callback_data="loc_diaspora")],
        [InlineKeyboardButton("🇪🇺 / 🇬🇧 Europe / UK", callback_data="loc_diaspora")],
        [
            InlineKeyboardButton(
                "🇦🇪 Middle East / 🌍 ሌላ ሀገር", callback_data="loc_diaspora"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📍 <b>እባክዎ የሚኖሩበትን ሀገር ይምረጡ፦</b>"
        if lang == "am"
        else "📍 <b>Please select your current country of residence:</b>"
    )
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
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


async def height_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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


async def weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
                "🔥 ስብ መቀነስ / ቦርጭ ማጥፋት" if lang == "am" else "🔥 Fat Loss / Tummy Reduction",
                callback_data="goal_fat_loss",
            )
        ],
        [
            InlineKeyboardButton(
                "💪 የሰውነት ጡንቻ መገንባት" if lang == "am" else "💪 Muscle Building",
                callback_data="goal_muscle",
            )
        ],
        [
            InlineKeyboardButton(
                "⚡ የጉልበት እና ብቃት ማሳደግ" if lang == "am" else "⚡ Athletic Performance",
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
                "🛋️ እንቅስቃሴ የሌለው (የተቀመጠ)" if lang == "am" else "🛋️ Sedentary (Office Job)",
                callback_data="act_sedentary",
            )
        ],
        [
            InlineKeyboardButton(
                "🚶 መካከለኛ (በሳምንት 1-3 ቀን)" if lang == "am" else "🚶 Moderate (1-3 days/wk)",
                callback_data="act_moderate",
            )
        ],
        [
            InlineKeyboardButton(
                "🏋️ ከፍተኛ (በሳምንት 4+ ቀን)" if lang == "am" else "🏋️ High Activity (4+ days/wk)",
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
async def activity_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    activity = query.data.split("_")[1]
    context.user_data["activity"] = activity
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [
            InlineKeyboardButton(
                "🟢 ገና ጀማሪ (Beginner)" if lang == "am" else "🟢 Beginner (New to gym)",
                callback_data="exp_beginner",
            )
        ],
        [
            InlineKeyboardButton(
                "🟡 መካከለኛ (Intermediate)" if lang == "am" else "🟡 Intermediate (Knows basics)",
                callback_data="exp_intermediate",
            )
        ],
        [
            InlineKeyboardButton(
                "🔴 ልምድ ያለው (Advanced)" if lang == "am" else "🔴 Advanced (Stuck at plateau)",
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


async def experience_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    exp = query.data.split("_")[1]
    context.user_data["experience"] = exp
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [
            InlineKeyboardButton(
                "🍱 የምግብ ሥርዓት አለመጠበቅ (Diet)" if lang == "am" else "🍱 Bad Diet & Nutrition",
                callback_data="obs_diet",
            )
        ],
        [
            InlineKeyboardButton(
                "⏰ የጊዜ እጥረት (Lack of Time)" if lang == "am" else "⏰ Lack of Time",
                callback_data="obs_time",
            )
        ],
        [
            InlineKeyboardButton(
                "📉 ወጥነት ማጣት (Inconsistency)" if lang == "am" else "📉 Lack of Consistency",
                callback_data="obs_consistency",
            )
        ],
        [
            InlineKeyboardButton(
                "❓ ምን መሥራት እንዳለብኝ አላውቅም (No Plan)" if lang == "am" else "❓ No Structured Plan",
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


async def obstacle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    obs = query.data.split("_")[1]
    context.user_data["obstacle"] = obs
    lang = context.user_data.get("lang", "am")

    keyboard = [
        [
            InlineKeyboardButton(
                "⚡ 10 - ዛሬውኑ ለመጀመር 100% ዝግጁ ነኝ!" if lang == "am" else "⚡ 10 - Ready to start today!",
                callback_data="read_10",
            )
        ],
        [
            InlineKeyboardButton(
                "📈 7-9 - ዝግጁ ነኝ፣ ትክክለኛ ፕሮግራም ብቻ ነው የሚያስፈልገኝ" if lang == "am" else "📈 7-9 - Ready with the right plan",
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
# 🩺 STEP 7: HEALTH & DIETARY PROFILING
# ==========================================
async def readiness_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    return HEALTH_INJURIES


async def health_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["injuries"] = update.message.text.strip()

    text = (
        "🥗 <b>ማንኛውም የማይስማማዎት ወይም የማይወዱት ምግብ አለ?</b>\n<i>(ከሌለ 'የለም' ብለው ይጻፉ)</i>"
        if lang == "am"
        else "🥗 <b>Do you have any food allergies or severe dislikes?</b>\n<i>(If none, reply 'None')</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return DIET_RESTRICTIONS


# ==========================================
# ⏱️ STEP 8: DURATION & PRICING
# ==========================================
async def diet_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "am")
    context.user_data["diet"] = update.message.text.strip()
    loc_type = context.user_data.get("location_type", "et")

    if loc_type == "et":
        keyboard = [
            [
                InlineKeyboardButton(
                    "⚡ 8-ሳምንት (2 ወር) — 3,500 ETB",
                    callback_data="dur_8w_3500ETB",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔥 12-ሳምንት (3 ወር) — 5,000 ETB ⭐",
                    callback_data="dur_12w_5000ETB",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏆 24-ሳምንት (6 ወር) — 9,000 ETB",
                    callback_data="dur_24w_9000ETB",
                )
            ],
        ]
        text = "⏱️ <b>ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦</b>"
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    "⚡ 8-Week Kickstart — $60 USD", callback_data="dur_8w_$60USD"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔥 12-Week Transformation — $100 USD ⭐",
                    callback_data="dur_12w_$100USD",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏆 24-Week VIP Elite — $180 USD", callback_data="dur_24w_$180USD"
                )
            ],
        ]
        text = "⏱️ <b>Select your transformation timeframe:</b>"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return DURATION


# ==========================================
# 💳 STEP 9: PAYMENT & RECEIPT UPLOAD
# ==========================================
async def duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    dur_info = query.data.split("_")[1:]
    duration_str = dur_info[0]
    price_str = dur_info[1]

    context.user_data["duration"] = duration_str
    context.user_data["price"] = price_str

    lang = context.user_data.get("lang", "am")
    loc_type = context.user_data.get("location_type", "et")

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
            f"💳 <b>Payment Instructions (Diaspora)</b>\n\n"
            f"⏱️ <b>Selected Program:</b> {duration_str}\n"
            f"💰 <b>Total Fee:</b> <b>{price_str}</b> <i>(or local currency equivalent)</i>\n\n"
            f"📲 <b>How to Pay:</b>\n"
            f"Use <b>TapTap Send</b>, <b>Remitly</b>, or <b>WorldRemit</b> to transfer directly to our Ethiopian bank account:\n"
            f"• <b>CBE Account:</b> <code>{CBE_ACCOUNT}</code>\n"
            f"• <b>Telebirr:</b> <code>{TELEBIRR_NUMBER}</code>\n"
            f"• <b>Account Name:</b> {ACCOUNT_NAME}\n\n"
            f"📸 Once completed, please send a <b>clear screenshot or photo</b> of your receipt below."
        )

    await query.edit_message_text(pay_text, parse_mode="HTML")
    return RECEIPT


# ==========================================
# 📥 STEP 10: RECEIPT PROCESSING & ADMIN CARDS
# ==========================================
async def receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo = update.message.photo[-1]
    lang = context.user_data.get("lang", "am")

    loc = (
        "🇪🇹 Ethiopia"
        if context.user_data.get("location_type") == "et"
        else "🌎 Diaspora"
    )

    admin_card = (
        f"📥 <b>NEW PAID INTAKE RECEIVED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Client:</b> {user.full_name} (@{user.username or 'No_Username'})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"📍 <b>Location:</b> {loc}\n"
        f"⏱️ <b>Program:</b> {context.user_data.get('duration')} ({context.user_data.get('price')})\n\n"
        f"📊 <b>Body Profile:</b>\n"
        f"• <b>Gender:</b> {context.user_data.get('gender')} | <b>Age:</b> {context.user_data.get('age')} yrs\n"
        f"• <b>Height:</b> {context.user_data.get('height')} cm | <b>Weight:</b> {context.user_data.get('weight')} kg\n"
        f"• <b>Goal:</b> {context.user_data.get('goal')} | <b>Activity:</b> {context.user_data.get('activity')}\n\n"
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

    # Broadcast intake card + receipt to ALL Admin IDs
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

    confirm_msg = (
        "🎉 <b>የክፍያ ደረሰኝዎ ደርሶናል!</b>\n\n"
        "ሲሞን መረጃዎን እየገመገመ ይገኛል። በ24 ሰዓታት ውስጥ የተዘጋጀውን ፕሮግራምዎን በዚህ ቻት ይላክልዎታል። እናመሰግናለን!"
        if lang == "am"
        else "🎉 <b>Receipt Received!</b>\n\n"
        "Simon is reviewing your intake data. You will receive your customized program directly in this chat within 24 hours. Welcome aboard!"
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
            text="✅ <b>Payment Approved!</b> Simon has verified your receipt. Expect your PDF plan and welcome voice note shortly!",
            parse_mode="HTML",
        )
        await query.edit_message_caption(
            caption=query.message.caption
            + "\n\n<b>STATUS:</b> ✅ APPROVED BY SIMON",
            parse_mode="HTML",
        )
    elif action == "reject":
        await context.bot.send_message(
            chat_id=client_id,
            text="❌ <b>Payment Alert:</b> We could not verify your receipt screenshot. Please contact Simon directly to double-check.",
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
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
            ACTIVITY: [CallbackQueryHandler(activity_choice, pattern="^act_")],
            EXPERIENCE: [CallbackQueryHandler(experience_choice, pattern="^exp_")],
            OBSTACLE: [CallbackQueryHandler(obstacle_choice, pattern="^obs_")],
            READINESS: [CallbackQueryHandler(readiness_choice, pattern="^read_")],
            HEALTH_INJURIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, health_input)
            ],
            DIET_RESTRICTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, diet_input)
            ],
            DURATION: [CallbackQueryHandler(duration_choice, pattern="^dur_")],
            RECEIPT: [MessageHandler(filters.PHOTO, receipt_upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action_callback, pattern="^adm_"))

    print("⚡ Simon Telegram Bot is live and running...")
    app.run_polling()


if __name__ == "__main__":
    main()
