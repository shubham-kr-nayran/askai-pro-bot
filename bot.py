import os
import sys
import logging

from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

import google.generativeai as genai

# -------------------------------------------------
# BASIC LOGGING (VERY IMPORTANT)
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

logger.info("🚀 Bot starting...")

# -------------------------------------------------
# LOAD ENV VARIABLES
# -------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logger.info(f"DEBUG BOT_TOKEN loaded: {bool(BOT_TOKEN)}")
logger.info(f"DEBUG GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is missing")
    sys.exit("STOPPED: BOT_TOKEN env variable not set")

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY is missing")
    sys.exit("STOPPED: GEMINI_API_KEY env variable not set")

# -------------------------------------------------
# INIT GEMINI (STABLE SDK)
# -------------------------------------------------
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    logger.info("✅ Gemini initialized successfully")
except Exception as e:
    logger.exception("❌ Gemini init failed")
    sys.exit(1)

# -------------------------------------------------
# IN-MEMORY STATE
# -------------------------------------------------
free_users = set()
pending_queries = {}

# -------------------------------------------------
# MESSAGE HANDLER
# -------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    logger.info(f"📩 Message from {user_id}: {text}")

    # 🎁 ONE FREE MESSAGE
    if user_id not in free_users:
        free_users.add(user_id)
        try:
            response = model.generate_content(text)
            await update.message.reply_text(
                "🎁 Free trial answer:\n\n" + response.text
            )
            logger.info(f"🎁 Free answer sent to {user_id}")
        except Exception:
            logger.exception("❌ Gemini generation failed")
            await update.message.reply_text("⚠️ AI error. Try again.")
        return

    # ⭐ PAID FLOW
    pending_queries[user_id] = text
    prices = [LabeledPrice("AI Answer", 5)]  # 5 Stars

    logger.info(f"⭐ Sending Stars invoice to {user_id}")

    await update.message.reply_invoice(
        title="AskAI Pro – AI Answer",
        description="Premium AI-powered response",
        payload=str(user_id),
        provider_token="",      # REQUIRED EMPTY for Stars
        currency="XTR",         # Telegram Stars
        prices=prices,
    )

# -------------------------------------------------
# PAYMENT SUCCESS HANDLER
# -------------------------------------------------
async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logger.info(f"💰 Payment received from {user_id}")

    query = pending_queries.pop(user_id, None)

    if not query:
        logger.warning("⚠️ No pending query found")
        await update.message.reply_text("Please send your question again.")
        return

    try:
        response = model.generate_content(query)
        await update.message.reply_text(
            "✅ Payment received!\n\n🤖 AI Answer:\n" + response.text
        )
        logger.info(f"✅ Paid answer sent to {user_id}")
    except Exception:
        logger.exception("❌ Gemini generation failed after payment")
        await update.message.reply_text("⚠️ AI error. Please try again.")

# -------------------------------------------------
# APP START
# -------------------------------------------------
try:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🤖 Bot polling started")
    app.run_polling()
except Exception:
    logger.exception("❌ Bot failed to start")
    sys.exit(1)
