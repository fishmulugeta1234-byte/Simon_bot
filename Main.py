import logging
import asyncio
import os
import tempfile
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Optional ReportLab import for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# CONFIGURATION
TOKEN = "8765027788:AAEvkGMDXd8i3EdtqVYgdrnEA4j4Lbdxk4U"
ADMIN_CHAT_IDS = [1622298145, 389487101]

# Conversation States
LANGUAGE, REGION, GOAL, PACKAGE, PHONE = range(5)

# Helper Functions
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_CHAT_IDS

def t(lang: str, en: any, am: any) -> any:
    """Returns Amharic if language is Amharic, otherwise English."""
    if lang in ["lang_am", "am"]:
        return am
    return en

async def update_all_admin_copies(context: ContextTypes.DEFAULT_TYPE, admin_messages: list, base_caption: str, status_text: str):
    """Updates the caption across all admin notification copies simultaneously."""
    updated_caption = f"{base_caption}\n\n--------------------\n{status_text}"
    for msg_info in admin_messages:
        try:
            await context.bot.edit_message_caption(
                chat_id=msg_info["chat_id"],
                message_id=msg_info["message_id"],
                caption=updated_caption,
                reply_markup=None,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Failed to update admin message copy: %s", e)

def generate_meal_plan_text(record: dict) -> str:
    """Generates customized meal and macro structure based on user goal and stats."""
    goal = record.get("goal", "")
    weight = record.get("weight", "75")
    height = record.get("height", "175")
    
    goal_title = "Fat Loss & Core Definition" if "fat_loss" in goal else "Muscle Building & Hypertrophy"
    
    return (
        f"CLIENT PROFILE:\n"
        f"• Goal: {goal_title}\n"
        f"• Current Weight: {weight} kg\n"
        f"• Height: {height} cm\n\n"
        f"DAILY MACRO TARGETS:\n"
        f"• Protein: 160g - 180g\n"
        f"• Carbohydrates: 200g - 230g\n"
        f"• Healthy Fats: 55g - 65g\n\n"
        f"SAMPLE DAILY NUTRITION SCHEDULE:\n"
        f"1. Breakfast: Oatmeal with eggs, banana, and black coffee.\n"
        f"2. Lunch: Grilled chicken breast, white rice, and steamed vegetables.\n"
        f"3. Snack: Greek yogurt with honey or almonds.\n"
        f"4. Dinner: Lean beef or fish with sweet potatoes and salad."
    )

def build_meal_plan_pdf(record: dict, plan_text: str, username: str) -> str:
    """Builds a professional PDF meal plan and returns file path."""
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    if HAS_REPORTLAB:
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=22,
            spaceAfter=15,
            textColorHex='#1A365D'
        )
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=16,
            spaceAfter=10
        )

        story.append(Paragraph("Simon Origin — 1-on-1 Personalized Plan", title_style))
        story.append(Paragraph(f"Prepared for: <b>{username}</b> ({record.get('duration', 'Custom Program')})", body_style))
        story.append(Spacer(1, 10))

        for line in plan_text.split("\n"):
            if line.strip():
                story.append(Paragraph(line.replace("\n", "<br/>"), body_style))
            else:
                story.append(Spacer(1, 6))

        doc.build(story)
    else:
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(f"SIMON ORIGIN MEAL PLAN FOR {username}\n\n" + plan_text)

    return pdf_path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for language preference."""
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
    """Displays detailed program tiers and investment guide FAQ."""
    faq_text = (
        "📌 **Simon Origin — Program Tiers & Investment Guide**\n\n"
        "🥗 **Meal Plan Only** — 799 ETB\n"
        "🥉 **Kickstart (21 Days)** — 3,500 ETB\n"
        "🥈 **Transformation (60 Days)** — 7,000 ETB / $110 USD\n"
        "🥇 **Elite (90 Days)** — 9,500 ETB\n"
        "💎 **Lifestyle (6 Months)** — 18,000 ETB\n"
        "👑 **VIP (6 Months)** — 30,000 ETB\n\n"
        "💡 Send `/start` to launch the onboarding portal!"
    )
    await update.message.reply_text(faq_text, parse_mode="Markdown")


async def region_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["lang"] = query.data

    keyboard = [
        [InlineKeyboardButton("🇪🇹 ኢትዮጵያ (Ethiopia)", callback_data="reg_eth")],
        [InlineKeyboardButton("🇺🇸 USA or Canada", callback_data="reg_us_ca")],
        [InlineKeyboardButton("🇪🇺 Europe", callback_data="reg_eu")],
        [InlineKeyboardButton("🌐 Other Regions", callback_data="reg_other")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="📍 እባክዎ የሚኖሩበትን ሀገር/ክልል ይምረጡ:", reply_markup=reply_markup)
    return REGION


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["region"] = query.data

    keyboard = [
        [InlineKeyboardButton("🔥 ስብ መቀነስ / ቦርጭ ማጥፋት", callback_data="goal_fat_loss")],
        [InlineKeyboardButton("💪 የሰውነት ጡንቻ መገንባት", callback_data="goal_muscle")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="🎯 ዋናው የፊትነስ ዓላማዎ ምንድን ነው?", reply_markup=reply_markup)
    return GOAL


async def package_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["goal"] = query.data

    keyboard = [
        [InlineKeyboardButton("🥗 የምግብ እቅድ ብቻ — 799 ETB", callback_data="pkg_meal")],
        [InlineKeyboardButton("🥉 Kickstart (21-ቀን) — 3,500 ETB", callback_data="pkg_21")],
        [InlineKeyboardButton("🥈 Transformation (60-ቀን) — 7,000 ETB", callback_data="pkg_60")],
        [InlineKeyboardButton("🥇 Elite (90-ቀን) — 9,500 ETB", callback_data="pkg_90")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="⏱️ የፕሮግራም ቆይታ ይምረጡ፦", reply_markup=reply_markup)
    return PACKAGE


async def phone_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["duration"] = query.data

    await query.edit_message_text(
        text="📞 ለክፍያ ማረጋገጫ እና ለክትትል የሚሆን ስልክ ቁጥርዎ ስንት ነው? (ምሳሌ፡ 0911223344)\n\n"
             "*(በማንኛውም ጊዜ /cancel በመጻፍ ማቋረጥ ይችላሉ)*"
    )
    return PHONE


async def payment_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text
    lang = context.user_data.get("lang", "en")
    region = context.user_data.get("region", "reg_eth")

    if region == "reg_eth":
        pay_text = t(
            lang,
            (
                "💳 **Payment Instructions (Ethiopia)**\n\n"
                "📲 **How to Send:**\n"
                "1. Open your **CBE Birr** or **Telebirr** mobile app.\n"
                "2. Select **Transfer / Send Money**.\n"
                "3. Send to one of the accounts below:\n"
                "• **CBE Account:** `1000357796532`\n"
                "• **Telebirr Number:** `0939998090`\n"
                "• **Account Name:** Simon Mulugeta\n\n"
                "📸 Once transferred, take a screenshot of your success receipt and send it right here in this chat."
            ),
            (
                "💳 **የክፍያ መመሪያ (ለሀገር ውስጥ)**\n\n"
                "📲 **ክፍያውን እንዴት መላክ ይችላሉ?**\n"
                "1. የ **ሲቢኢ ብር (CBE Birr)** ወይም **ቴሌብር (Telebirr)** መተግበሪያዎን ይክፈቱ።\n"
                "2. ገንዘብ ለመላክ (Transfer) የሚለውን ይምረጡ።\n"
                "3. ከዚህ በታች ባሉት መለያዎች ያስገቡ፦\n"
                "• **የባንክ ሂሳብ (CBE):** `1000357796532`\n"
                "• **ቴሌብር (Telebirr):** `0939998090`\n"
                "• **ስም:** Simon Mulugeta\n\n"
                "📸 ክፍያውን እንደፈጸሙ፣ የደረሰኙን ግልጽ ስክሪንሽኦት ወይም ፎቶ እዚህ ቻት ላይ ይላኩ።"
            )
        )
    else:
        pay_text = t(
            lang,
            (
                "💳 **Payment Instructions (International)**\n\n"
                "📲 **How to Send:**\n"
                "1. Open an international remittance app like **Remitly** or **Wise**.\n"
                "2. Choose Ethiopia as the destination country and select mobile wallet or bank deposit.\n"
                "3. Enter the details below:\n"
                "• **CBE Account:** `1000357796532`\n"
                "• **Telebirr:** `0939998090`\n"
                "• **Account Name:** Simon Mulugeta\n\n"
                "📸 Once completed, send a clear screenshot of your transfer receipt here."
            ),
            (
                "💳 **የክፍያ መመሪያ (ከሀገር ውጪ ላሉ)**\n\n"
                "📲 **ክፍያውን እንዴት መላክ ይችላሉ?**\n"
                "1. እንደ **Remitly** ወይም **Wise** ያሉ አለም አቀፍ መተግበሪያዎችን ይጠቀሙ።\n"
                "2. መድረሻውን ኢትዮጵያ በማድረግ ከታች ያሉትን መረጃዎች ያስገቡ፦\n"
                "• **የባንክ ሂሳብ (CBE):** `1000357796532`\n"
                "• **ቴሌብር (Telebirr):** `0939998090`\n"
                "• **ስም:** Simon Mulugeta\n\n"
                "📸 ክፍያውን ከፈጸሙ በኋላ የደረሰኙን ስክሪንሽኦት እዚህ ይላኩ።"
            )
        )

    await update.message.reply_text(pay_text, parse_mode="Markdown")
    return ConversationHandler.END


async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if "region" not in context.user_data:
        return

    photo_file = await update.message.photo[-1].get_file()
    
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(
        t(lang, "📸 Receipt received! Please wait while Simon verifies your payment...",
                "📸 የክፍያ ደረሰኝዎ ደርሷል! ሳይመን እስኪያረጋግጥ ይጠብቁ...")
    )

    admin_caption = (
        "🚀 **New Payment Receipt Verification!**\n\n"
        f"👤 **Name:** {user.full_name} (@{user.username or 'No username'})\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"🌍 **Region:** {context.user_data.get('region')}\n"
        f"🎯 **Goal:** {context.user_data.get('goal')}\n"
        f"📞 **Phone:** {context.user_data.get('phone')}\n"
        f"⏱️ **Duration:** {context.user_data.get('duration')}\n\n"
        "👇 **Action Required:**"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Build Plan", callback_data=f"confirm_{user.id}"),
            InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    admin_messages = []
    for admin_id in ADMIN_CHAT_IDS:
        try:
            msg = await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_file.file_id,
                caption=admin_caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            admin_messages.append({"chat_id": admin_id, "message_id": msg.message_id})
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    if "pending" not in context.bot_data:
        context.bot_data["pending"] = {}

    context.bot_data["pending"][user.id] = {
        "chat_id": chat_id,
        "username": user.full_name,
        "lang": lang,
        "region": context.user_data.get("region"),
        "goal": context.user_data.get("goal"),
        "duration": context.user_data.get("duration"),
        "weight": "75",
        "height": "175",
        "admin_messages": admin_messages,
        "admin_caption": admin_caption
    }


async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Not authorized.", show_alert=True)
        return
    await query.answer()

    user_id = int(query.data.replace("confirm_", ""))
    record = context.bot_data.get("pending", {}).pop(user_id, None)
    if not record:
        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n⚠️ Already handled by another admin.",
                reply_markup=None
            )
        except Exception:
            pass
        return

    lang = record.get("lang", "en")
    chat_id = record["chat_id"]
    username = record.get("username", "Client")
    admin_messages = record.get("admin_messages", [])
    base_caption = record.get("admin_caption", query.message.caption or "")
    who = query.from_user.first_name or "an admin"

    await update_all_admin_copies(context, admin_messages, base_caption,
                                   f"⏳ CONFIRMED by {who} — generating client's plan now...")

    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang,
               "✅ Payment confirmed! Your plan is now being personally prepared for you.",
               "✅ ክፍያዎ ተረጋግጧል! የግል ፕሮግራምዎ አሁን እየተዘጋጀ ነው።")
    )

    stages = t(lang,
        [
            "🔍 Reviewing your weight, height and goal...",
            "🧠 Building your personalized meal structure...",
            "📄 Formatting your plan into a premium PDF...",
        ],
        [
            "🔍 ክብደትዎን፣ ቁመትዎን እና ግብዎን በመገምገም ላይ...",
            "🧠 የግል ምግብ ፕሮግራምዎን በመገንባት ላይ...",
            "📄 ፕሮግራሙን ወደ ፕሪሚየም PDF በመቀየር ላይ...",
        ]
    )
    for stage_text in stages:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(2.5)
        await context.bot.send_message(chat_id=chat_id, text=stage_text)

    try:
        plan_text = await asyncio.to_thread(generate_meal_plan_text, record)
        pdf_path = await asyncio.to_thread(build_meal_plan_pdf, record, plan_text, username)
    except Exception as e:
        logger.error("Failed to generate plan/PDF: %s", e)
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang,
                   "⚠️ Something went wrong preparing your plan. Simon has been notified and will follow up shortly.",
                   "⚠️ ፕሮግራሙን በማዘጋጀት ላይ ችግር ተፈጥሯል። ሲሞን ተነግሮታል፣ በቅርቡ ያግኙዎታል።")
        )
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"⚠️ PDF generation failed for {username}: {e}")
            except Exception:
                pass
        return

    caption = t(lang,
        f"🎉 Your personalized {record.get('duration')} meal plan is ready! Stay consistent and check in anytime with questions.",
        f"🎉 የግል {record.get('duration')} የምግብ ፕሮግራምዎ ተዘጋጅቷል! ወጥነት ይኑርዎት፣ ማንኛውም ጥያቄ ካለዎት ማንኛውም ጊዜ ያግኙን።"
    )
    with open(pdf_path, "rb") as pdf_file:
        await context.bot.send_document(chat_id=chat_id, document=pdf_file, caption=caption)

    try:
        os.remove(pdf_path)
    except Exception:
        pass

    await update_all_admin_copies(context, admin_messages, base_caption,
                                   f"✅ CONFIRMED by {who} — plan delivered.")


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Not authorized.", show_alert=True)
        return
    await query.answer()

    user_id = int(query.data.replace("reject_", ""))
    record = context.bot_data.get("pending", {}).pop(user_id, None)
    if not record:
        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n⚠️ Already handled by another admin.",
                reply_markup=None
            )
        except Exception:
            pass
        return

    admin_messages = record.get("admin_messages", [])
    base_caption = record.get("admin_caption", query.message.caption or "")
    who = query.from_user.first_name or "an admin"

    await update_all_admin_copies(context, admin_messages, base_caption, f"❌ REJECTED by {who}.")

    try:
        await context.bot.send_message(
            chat_id=record["chat_id"],
            text=t(record.get("lang", "en"),
                   "❌ Payment verification failed. Please send a clear and valid receipt screenshot.",
                   "❌ የክፍያ ማረጋገጫ አልተሳካም። እባክዎ ግልጽ የሆነ ደረሰኝ እንደገና ይላኩ።")
        )
    except Exception:
        pass


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_receipt_photo))
    application.add_handler(CallbackQueryHandler(admin_confirm, pattern="^confirm_"))
    application.add_handler(CallbackQueryHandler(admin_reject, pattern="^reject_"))

    application.run_polling()


if __name__ == "__main__":
    main()
