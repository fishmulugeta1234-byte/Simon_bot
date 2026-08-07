import logging
import os
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
ADMIN_CHAT_IDS = [1622298145, 389487101]  # Both admin chat IDs configured

# Conversation States
(
    LANGUAGE,
    REGION,
    GOAL,
    PACKAGE,
    PHONE,
    WAITING_RECEIPT,
    WEIGHT,
    HEIGHT,
    NOTES,
) = range(9)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the welcome image banner and asks for language preference."""
    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇪🇹 አማርኛ (Amharic)", callback_data="lang_am"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "Welcome to Simon's Transformation Portal! Please select your language / "
        "ወደ ሳይመን የግል የሰውነት ለውጥ መግቢያ እንኳን በደህና መጡ። እባክዎ ቋንቋ ይምረጡ፦\n\n"
        "💡 *Tip: Type /faq anytime to compare all program tiers and pricing.*"
    )

    try:
        with open("welcome.jpeg", "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file, caption=welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
    except FileNotFoundError:
        logger.error("welcome.jpeg file not found in the project directory!")
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

    return LANGUAGE


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays detailed program tiers and investment guide FAQ for all clients."""
    faq_text = (
        "📌 **Simon Origin — Program Tiers & Investment Guide**\n\n"
        "🥗 **Meal Plan Only**\n"
        "• **Investment:** 799 ETB\n"
        "• **Focus:** Customized standalone nutrition and macro guidance.\n\n"
        "🥉 **Kickstart (21 Days)**[span_1](start_span)[span_1](end_span)\n"
        "• **Investment:** 3,500 ETB[span_2](start_span)[span_2](end_span)\n"
        "• **Best for:** Beginners building momentum[span_3](start_span)[span_3](end_span).\n"
        "• **Includes:** Fixed workout plan, 1 meal plan, 1 total adjustment, weekly check-ins (3 total), and basic progress tracking[span_4](start_span)[span_4](end_span).\n\n"
        "🥈 **Transformation (60 Days)**[span_5](start_span)[span_5](end_span)\n"
        "• **Investment:** 7,000 ETB / $110 USD[span_6](start_span)[span_6](end_span)\n"
        "• **Best for:** Fat loss and muscle-building with consistent coaching[span_7](start_span)[span_7](end_span).\n"
        "• **Includes:** Workouts updated every 4 weeks, adjusted meal plan, check-ins every 4 weeks, up to 5 form reviews/month, and basic habit coaching[span_8](start_span)[span_8](end_span).\n\n"
        "🥇 **Elite (90 Days)**[span_9](start_span)[span_9](end_span)\n"
        "• **Investment:** 9,500 ETB[span_10](start_span)[span_10](end_span)\n"
        "• **Best for:** Serious long-term results[span_11](start_span)[span_11](end_span).\n"
        "• **Includes:** Fully custom workouts, unlimited meal plan adjustments, weekly check-ins (~13), anytime exercise form reviews, bi-weekly progress reviews, and 24-hr priority support[span_12](start_span)[span_12](end_span).\n\n"
        "💎 **Lifestyle (6 Months)**[span_13](start_span)[span_13](end_span)\n"
        "• **Investment:** 18,000 ETB[span_14](start_span)[span_14](end_span)\n"
        "• **Best for:** Permanent lifestyle change[span_15](start_span)[span_15](end_span).\n"
        "• **Includes:** New workout phase monthly, continuous meal plans, unlimited progress reviews, long-term habit coaching, monthly goal-setting sessions, and plateau-solving strategies[span_16](start_span)[span_16](end_span).\n\n"
        "👑 **VIP (6 Months)**[span_17](start_span)[span_17](end_span)\n"
        "• **Investment:** 30,000 ETB[span_18](start_span)[span_18](end_span)\n"
        "• **Best for:** Highest level of 1-on-1 support[span_19](start_span)[span_19](end_span).\n"
        "• **Includes:** Live-adjusted workouts, on-demand meal plans, weekly 30-45 min video calls, unlimited form reviews, travel/restaurant nutrition guidance, direct accountability outreach, and same-day priority support[span_20](start_span)[span_20](end_span).\n\n"
        "💡 **Ready to begin?** Send `/start` to launch the onboarding portal!"
    )
    await update.message.reply_text(faq_text, parse_mode="Markdown")


async def region_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles language selection and asks for region."""
    query = update.callback_query
    await query.answer()
    context.user_data["language"] = query.data

    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵя (Ethiopia)", callback_data="reg_eth")],
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

    # Full tier options available for all clients (Local and International)
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
        text="📞 ለክፍያ ማረጋገጫ እና ለክትትል የሚሆን ስልክ ቁጥርዎ ስንት ነው? (ምሳሌ፡ 0911223344)"
    )
    return PHONE


async def payment_instructions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receives phone number and displays payment details."""
    context.user_data["phone"] = update.message.text
    region = context.user_data.get("region")
    pkg = context.user_data.get("package")

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
    return WAITING_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives receipt photo, sends weight.jpeg visual, and asks for current weight."""
    photo_file = await update.message.photo[-1].get_file()
    context.user_data["receipt_file_id"] = photo_file.file_id

    weight_caption = (
        "🎉 **ደስ ብሎናል! የክፍያ ደረሰኝዎ በሰላም ደርሶናል!**\n\n"
        "እንኳን ደህና መጡ! ፕሮግራምዎ ተከፍቷል። ሳይመን ብጁ ፕሮግራምዎን ከመሥራቱ በፊት, መሰረታዊ የሰውነት መለኪያዎችን እንውሰድ።\n\n"
        "⚖️ **የአሁኑ ክብደትዎ በኪሎግራም ስንት ነው?** (ምሳሌ፡ 78)"
    )

    try:
        with open("weight.jpeg", "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file, caption=weight_caption, parse_mode="Markdown"
            )
    except FileNotFoundError:
        logger.error("weight.jpeg file not found in the project directory!")
        await update.message.reply_text(weight_caption, parse_mode="Markdown")

    return WEIGHT


async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores weight and asks for height."""
    context.user_data["weight"] = update.message.text
    await update.message.reply_text(
        "📏 **ቁመትዎ በሴንቲሜትር ስንት ነው?** (ምሳሌ፡ 178)"
    )
    return HEIGHT


async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores height and asks for injuries/notes."""
    context.user_data["height"] = update.message.text
    await update.message.reply_text(
        "🩹 **ማንኛውም የሰውነት ጉዳት፣ የጤና ሁኔታ ወይም የማይስማማዎት ምግብ አለ?** *(ከሌለ 'የለም' ብለው ይጻፉ)*"
    )
    return NOTES


async def finish_onboarding(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Stores notes, sends success.jpeg confirmation to user, and forwards card to both admins."""
    context.user_data["notes"] = update.message.text
    user = update.effective_user

    success_caption = (
        "✅ **መረጃው ሙሉ በሙሉ ተመዝግቧል!**\n\n"
        "ሳይመን መረጃዎን እና የክፍያ ደረሰኝዎን ተቀብሏል። የተስተካከለው የ1-ለ-1 የሰውነት ለውጥ ፕሮግራምዎ **በ24 ሰዓታት ውስጥ** እዚሁ ቻት ላይ ይላክልዎታል።"
    )

    try:
        with open("success.jpeg", "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file, caption=success_caption, parse_mode="Markdown"
            )
    except FileNotFoundError:
        logger.error("success.jpeg file not found in the project directory!")
        await update.message.reply_text(success_caption, parse_mode="Markdown")

    admin_text = (
        "🚀 **New Client Registration!**\n\n"
        f"👤 **Name:** {user.full_name} (@{user.username or 'No username'})\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"🌍 **Region:** {context.user_data.get('region')}\n"
        f"🎯 **Goal:** {context.user_data.get('goal')}\n"
        f"📞 **Phone:** {context.user_data.get('phone')}\n"
        f"⏱️ **Program:** {context.user_data.get('package')}\n"
        f"⚖️ **Weight:** {context.user_data.get('weight')} kg\n"
        f"📏 **Height:** {context.user_data.get('height')} cm\n"
        f"🩹 **Notes/Injuries:** {context.user_data.get('notes')}"
    )

    receipt_id = context.user_data.get("receipt_file_id")
    
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=receipt_id, caption=admin_text, parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send admin notification to {admin_id}: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation."""
    await update.message.reply_text("Process canceled. Send /start to begin again.")
    return ConversationHandler.END


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [CallbackQueryHandler(region_handler, pattern="^lang_")],
            REGION: [CallbackQueryHandler(goal_handler, pattern="^reg_")],
            GOAL: [CallbackQueryHandler(package_handler, pattern="^goal_")],
            PACKAGE: [CallbackQueryHandler(phone_request, pattern="^pkg_")],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_instructions)],
            WAITING_RECEIPT: [MessageHandler(filters.PHOTO, receive_receipt)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weight)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_height)],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_onboarding)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("faq", faq_command))
    application.run_polling()


if __name__ == "__main__":
    main()
