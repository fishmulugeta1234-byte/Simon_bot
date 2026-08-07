import logging
import sqlite3
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
logger = logging.getLogger(__name__)

# CONFIGURATION
TOKEN = "8765027788:AAEvkGMDXd8i3EdtqVYgdrnEA4j4Lbdxk4U"
ADMIN_CHAT_IDS = [1622298145, 389487101]

# Database Setup & Helper Functions
DB_NAME = "bot_database.db"

def init_db():
    """Initializes the SQLite database and clients table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            user_id INTEGER PRIMARY KEY,
            region TEXT,
            goal TEXT,
            package TEXT,
            phone TEXT,
            step TEXT,
            receipt_file_id TEXT,
            weight TEXT,
            height TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def db_get_client(user_id):
    """Retrieves client state dictionary from database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def db_set_client(user_id, **kwargs):
    """Inserts or updates client state parameters in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM clients WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute("INSERT INTO clients (user_id) VALUES (?)", (user_id,))
        conn.commit()
        
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE clients SET {key} = ? WHERE user_id = ?", (value, user_id))
        
    conn.commit()
    conn.close()

def db_delete_client(user_id):
    """Removes client record from database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Conversation States (for initial onboarding steps)
LANGUAGE, REGION, GOAL, PACKAGE, PHONE = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for language preference."""
    user = update.effective_user
    db_delete_client(user.id)

    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇪🇹 አማርኛ (Amharic)", callback_data="lang_am"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "ወደ ሳይመን የግል የሰውነት ለውጥ መግቢያ እንኳን በደህና መጡ። "
        "ከእርስዎ አካል ጋር ሙሉ በሙሉ የተጣጣሙ 1-ለ-1 የተዘጋጁ የስልጠና እና የምግብ እቅዶችን እንሰራለን።\n\n"
        "እባክዎ ቋንቋ ይምረጡ፦\n\n"
        "💡 *Tip: Type /faq anytime to compare all program tiers and pricing.*\n"
        "*(በማንኛውም ጊዜ ሂደቱን ለማቋረጥ /cancel ማስተካከል ይችላሉ)*"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    return LANGUAGE


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays detailed program tiers and investment guide FAQ for all clients."""
    faq_text = (
        "📌 **Simon Origin — Program Tiers & Investment Guide**\n\n"
        "🥗 **Meal Plan Only**\n"
        "• **Investment:** 799 ETB\n"
        "• **Focus:** Customized standalone nutrition and macro guidance.\n\n"
        "🥉 **Kickstart (21 Days)**\n"
        "• **Investment:** 3,500 ETB\n"
        "• **Best for:** Beginners building momentum.\n"
        "• **Includes:** Fixed workout plan, 1 meal plan, 1 total adjustment, weekly check-ins (3 total), and basic progress tracking.\n\n"
        "🥈 **Transformation (60 Days)**\n"
        "• **Investment:** 7,000 ETB / $110 USD\n"
        "• **Best for:** Fat loss and muscle-building with consistent coaching.\n"
        "• **Includes:** Workouts updated every 4 weeks, adjusted meal plan, check-ins every 4 weeks, up to 5 form reviews/month, and basic habit coaching.\n\n"
        "🥇 **Elite (90 Days)**\n"
        "• **Investment:** 9,500 ETB\n"
        "• **Best for:** Serious long-term results.\n"
        "• **Includes:** Fully custom workouts, unlimited meal plan adjustments, weekly check-ins (~13), anytime exercise form reviews, bi-weekly progress reviews, and 24-hr priority support.\n\n"
        "💎 **Lifestyle (6 Months)**\n"
        "• **Investment:** 18,000 ETB\n"
        "• **Best for:** Permanent lifestyle change.\n"
        "• **Includes:** New workout phase monthly, continuous meal plans, unlimited progress reviews, long-term habit coaching, monthly goal-setting sessions, and plateau-solving strategies.\n\n"
        "👑 **VIP (6 Months)**\n"
        "• **Investment:** 30,000 ETB\n"
        "• **Best for:** Highest level of 1-on-1 support.\n"
        "• **Includes:** Live-adjusted workouts, on-demand meal plans, weekly 30-45 min video calls, unlimited form reviews, travel/restaurant nutrition guidance, direct accountability outreach, and same-day priority support.\n\n"
        "💡 **Ready to begin?** Send `/start` to launch the onboarding portal!"
    )
    await update.message.reply_text(faq_text, parse_mode="Markdown")


async def region_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles language selection and asks for region."""
    query = update.callback_query
    await query.answer()
    context.user_data["language"] = query.data

    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (Ethiopia)", callback_data="reg_eth")],
        [InlineKeyboardButton("🇺🇸 USA or Canada", callback_data="reg_us_ca")],
        [InlineKeyboardButton("🇪🇺 Europe", callback_data="reg_eu")],
        [InlineKeyboardButton("🌐 Other Regions", callback_data="reg_other")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📍 እባክዎ የሚኖሩበትን ሀገር/ክልል ይምረጡ (Select your region):",
        reply_markup=reply_markup,
    )
    return REGION


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles region selection and asks for fitness goal."""
    query = update.callback_query
    await query.answer()
    context.user_data["region"] = query.data

    keyboard = [
        [
            InlineKeyboardButton(
                "🔥 ስብ መቀነስ / ቦርጭ ማጥፋት", callback_data="goal_fat_loss"
            )
        ],
        [
            InlineKeyboardButton(
                "💪 የሰውነት ጡንቻ መገንባት", callback_data="goal_muscle"
            )
        ],
        [
            InlineKeyboardButton(
                "⚡ የጉልበት እና ብቃት ማሳደግ", callback_data="goal_performance"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="🎯 ዋናው የፊትነስ ዓላማዎ ምንድን ነው?", reply_markup=reply_markup
    )
    return GOAL


async def package_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles goal selection and shows full pricing tiers for all regions."""
    query = update.callback_query
    await query.answer()
    context.user_data["goal"] = query.data

    keyboard = [
        [
            InlineKeyboardButton(
                "🥗 የምግብ እቅድ ብቻ — 799 ETB", callback_data="pkg_meal"
            )
        ],
        [
            InlineKeyboardButton(
                "🥉 Kickstart (21-ቀን) — 3,500 ETB", callback_data="pkg_21"
            )
        ],
        [
            InlineKeyboardButton(
                "🥈 Transformation (60-ቀን) — 7,000 ETB ($110 USD)",
                callback_data="pkg_60",
            )
        ],
        [
            InlineKeyboardButton(
                "🥇 Elite (90-ቀን) — 9,500 ETB", callback_data="pkg_90"
            )
        ],
        [
            InlineKeyboardButton(
                "💎 Lifestyle (6-ወር) — 18,000 ETB", callback_data="pkg_180"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 VIP (6-ወር) — 30,000 ETB", callback_data="pkg_vip"
            )
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="⏱️ ለስንት ጊዜያት መለወጥ ይፈልጋሉ? (የፕሮግራም ቆይታ ይምረጡ)፦",
        reply_markup=reply_markup,
    )
    return PACKAGE


async def phone_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles package selection and asks for phone number."""
    query = update.callback_query
    await query.answer()
    context.user_data["package"] = query.data

    await query.edit_message_text(
        text="📞 ለክፍያ ማረጋገጫ እና ለክትትል የሚሆን ስልክ ቁጥርዎ ስንት ነው? (ምሳሌ፡ 0911223344)\n\n"
             "*(በማንኛውም ጊዜ ' /cancel ' በመጻፍ ማቋረጥ ይችላሉ)*"
    )
    return PHONE


async def payment_instructions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receives phone number, displays payment details, and saves state to SQLite."""
    user = update.effective_user
    phone = update.message.text
    region = context.user_data.get("region")
    goal = context.user_data.get("goal")
    pkg = context.user_data.get("package")

    db_set_client(
        user.id,
        region=region,
        goal=goal,
        package=pkg,
        phone=phone,
        step="waiting_receipt"
    )

    if region == "reg_eth":
        pay_text = (
            "💳 **የክፍያ መመሪያ (ለሀገር ውስጥ)**\n\n"
            f"⏱️ **የተመረጠው ፕሮግራም፦** {pkg}\n"
            "💰 **ክፍያ መጠን፦** እንደመረጡት ፓኬጅ\n\n"
            "እባክዎ ክፍያውን በሚከተሉት የባንክ ሂሳቦች ያስገቡ፦\n"
            "• **CBE Bank:** `1000357796532`\n"
            "• **Telebirr:** `0939998090`\n"
            "• **ስም:** Simon mulugeta\n\n"
            "📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን **ግልጽ ስክሪንሽኦት ወይም ፎቶ** እዚህ ይላኩ።"
        )
    else:
        pay_text = (
            "💳 **Payment Instructions (USA, Canada, Europe & Other)**\n\n"
            f"⏱️ **Selected Program:** {pkg}\n"
            "💰 **Total Fee:** Based on selected package ($110 USD for Transformation)\n\n"
            "📲 **How to Pay:**\n"
            "You can easily send payments using **Remitly** or your preferred remittance app:\n"
            "• **CBE Account:** `1000357796532`\n"
            "• **Telebirr (International):** `0939998090`\n"
            "• **Account Name:** Simon Mulugeta\n\n"
            "📸 Once completed, please send a **clear screenshot or photo** of your transfer receipt below."
        )

    await update.message.reply_text(pay_text, parse_mode="Markdown")
    return ConversationHandler.END


async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receives receipt photo from client and sends approval buttons to admins."""
    user = update.effective_user
    state = db_get_client(user.id)

    if not state or state.get("step") != "waiting_receipt":
        return

    photo_file = await update.message.photo[-1].get_file()
    db_set_client(
        user.id,
        receipt_file_id=photo_file.file_id,
        step="waiting_approval"
    )

    await update.message.reply_text(
        "📸 **የክፍያ ደረሰኝዎ ደርሷል!**\n\nሳይመን ክፍያዎን እስኪያረጋግጥ እባክዎ ትንሽ ይጠብቁ...",
        parse_mode="Markdown"
    )

    admin_text = (
        "🚀 **New Payment Receipt Verification!**\n\n"
        f"👤 **Name:** {user.full_name} (@{user.username or 'No username'})\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"🌍 **Region:** {state.get('region')}\n"
        f"🎯 **Goal:** {state.get('goal')}\n"
        f"📞 **Phone:** {state.get('phone')}\n"
        f"⏱️ **Program:** {state.get('package')}\n\n"
        "👇 **Please review the receipt and select an action:**"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept Payment", callback_data=f"accept_{user.id}"),
            InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_file.file_id,
                caption=admin_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send payment verification to admin {admin_id}: {e}")


async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin clicks on Accept or Reject buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("accept_") or data.startswith("reject_"):
        action, user_id_str = data.split("_")
        client_id = int(user_id_str)
        state = db_get_client(client_id)

        if not state:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n⚠️ *Session expired or client data not found.*",
                parse_mode="Markdown"
            )
            return

        if action == "accept":
            db_set_client(client_id, step="weight")
            await query.edit_message_caption(
                caption=(query.message.caption or "").replace(
                    "👇 **Please review the receipt and select an action:**",
                    "✅ **STATUS: PAYMENT ACCEPTED & APPROVED**"
                ),
                reply_markup=None,
                parse_mode="Markdown"
            )

            try:
                await context.bot.send_message(
                    chat_id=client_id,
                    text=(
                        "🎉 **ደስ ብሎናል! የክፍያ ደረሰኝዎ ጸድቋል!**\n\n"
                        "እንኳን ደህና መጡ! ፕሮግራምዎ ተከፍቷል። ሳይመን ብጁ ፕሮግራምዎን ከመሥራቱ በፊት, መሰረታዊ የሰውነት መለኪያዎችን እንውሰድ።\n\n"
                        "⚖️ **የአሁኑ ክብደትዎ በኪሎግራም ስንት ነው?** (ምሳሌ፡ 78)\n\n"
                        "*(እባክዎ ቁጥር ብቻ ያስገቡ)*"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to message client {client_id}: {e}")

        elif action == "reject":
            db_set_client(client_id, step="waiting_receipt")
            await query.edit_message_caption(
                caption=(query.message.caption or "").replace(
                    "👇 **Please review the receipt and select an action:**",
                    "❌ **STATUS: PAYMENT REJECTED**"
                ),
                reply_markup=None,
                parse_mode="Markdown"
            )

            try:
                await context.bot.send_message(
                    chat_id=client_id,
                    text=(
                        "❌ **የክፍያ ማረጋገጫ አልተሳካም።** እባክዎ ትክክለኛ እና ግልጽ የሆነ የደረሰኝ ስክሪንሽኦት እንደገና ይላኩ።"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to message client {client_id}: {e}")


async def client_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text input from client during weight, height, and notes steps."""
    user = update.effective_user
    state = db_get_client(user.id)

    if not state:
        return

    step = state.get("step")
    text = update.message.text.strip()

    if step == "waiting_approval":
        await update.message.reply_text(
            "⏳ እባክዎ ሳይመን የክፍያ ደረሰኝዎን እስኪያረጋግጥ ይጠብቁ...",
            parse_mode="Markdown"
        )
        return

    elif step == "weight":
        try:
            w_val = float(text)
            if w_val <= 0 or w_val > 400:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ **ልክ ያልሆነ ቁጥር!** እባክዎ ትክክለኛ ክብደትዎን በኪሎግራም ያስገቡ (ምሳሌ፡ 78)፦",
                parse_mode="Markdown"
            )
            return

        db_set_client(user.id, weight=text, step="height")
        await update.message.reply_text(
            "📏 **ቁመትዎ በሴንቲሜትር ስንት ነው?** (ምሳሌ፡ 178)\n\n"
            "*(እባክዎ ቁጥር ብቻ ያስገቡ)*",
            parse_mode="Markdown"
        )

    elif step == "height":
        try:
            h_val = float(text)
            if h_val <= 50 or h_val > 250:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ **ልክ ያልሆነ ቁጥር!** እባክዎ ትክክለኛ ቁመትዎን በሴንቲሜትር ያስገቡ (ምሳሌ፡ 178)፦",
                parse_mode="Markdown"
            )
            return

        db_set_client(user.id, height=text, step="notes")
        await update.message.reply_text(
            "🩹 **ማንኛውም የሰውነት ጉዳት፣ የጤና ሁኔታ ወይም የማይስማማዎት ምግብ አለ?** *(ከሌለ 'የለም' ብለው ይጻፉ)*",
            parse_mode="Markdown"
        )

    elif step == "notes":
        db_set_client(user.id, notes=text)
        state = db_get_client(user.id)

        success_text = (
            "✅ **መረጃው ሙሉ በሙሉ ተመዝግቧል!**\n\n"
            "ሳይመን መረጃዎን እና የክፍያ ደረሰኝዎን ተቀብሏል። የተስተካከለው የ1-ለ-1 የሰውነት ለውጥ ፕሮግራምዎ **በ24 ሰዓታት ውስጥ** እዚሁ ቻት ላይ ይላክልዎታል።"
        )
        await update.message.reply_text(success_text, parse_mode="Markdown")

        admin_summary = (
            "🚀 **New Client Registration Completed!**\n\n"
            f"👤 **Name:** {user.full_name} (@{user.username or 'No username'})\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"🌍 **Region:** {state.get('region')}\n"
            f"🎯 **Goal:** {state.get('goal')}\n"
            f"📞 **Phone:** {state.get('phone')}\n"
            f"⏱️ **Program:** {state.get('package')}\n"
            f"⚖️ **Weight:** {state.get('weight')} kg\n"
            f"📏 **Height:** {state.get('height')} cm\n"
            f"🩹 **Notes/Injuries:** {state.get('notes')}"
        )

        receipt_id = state.get("receipt_file_id")
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_id,
                    caption=admin_summary,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send final summary to admin {admin_id}: {e}")

        # Clean up database record upon completion
        db_delete_client(user.id)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation."""
    user = update.effective_user
    db_delete_client(user.id)
    await update.message.reply_text("Process canceled. Send /start to begin again.")
    return ConversationHandler.END


def main():
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [CallbackQueryHandler(region_handler, pattern="^lang_")],
            REGION: [CallbackQueryHandler(goal_handler, pattern="^reg_")],
            GOAL: [CallbackQueryHandler(package_handler, pattern="^goal_")],
            PACKAGE: [CallbackQueryHandler(phone_request, pattern="^pkg_")],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_instructions)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_receipt_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, client_text_handler))
    application.add_handler(CallbackQueryHandler(admin_action_handler, pattern="^(accept_|reject_)"))

    application.run_polling()


if __name__ == "__main__":
    main()
