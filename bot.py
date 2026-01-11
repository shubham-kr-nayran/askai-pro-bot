import os
import sys
import logging
import asyncio

from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)

import google.generativeai as genai

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

logger.info("🚀 Bot starting...")

# -------------------------------------------------
# ENV VARIABLES
# -------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logger.info(f"DEBUG BOT_TOKEN loaded: {bool(BOT_TOKEN)}")
logger.info(f"DEBUG GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")

if not BOT_TOKEN:
    sys.exit("❌ BOT_TOKEN missing")

if not GEMINI_API_KEY:
    sys.exit("❌ GEMINI_API_KEY missing")

# -------------------------------------------------
# GEMINI SETUP (FAST MODEL)
# -------------------------------------------------
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash"),
    generation_config={
        "temperature": 0.5,
        "max_output_tokens": 400,  # smaller = faster
    }
)

logger.info("✅ Gemini initialized")

# -------------------------------------------------
# STATE (IN-MEMORY)
# -------------------------------------------------
FREE_MESSAGES = 3
user_message_count = {}
pending_queries = {}

# -------------------------------------------------
# AI CALL (ASYNC WRAPPER FOR SPEED)
# -------------------------------------------------
async def generate_ai_reply(text: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: model.generate_content(text)
    )
    return response.text

# -------------------------------------------------
# MESSAGE HANDLER
# -------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    logger.info(f"📩 Message from {user_id}: {text}")

    count = user_message_count.get(user_id, 0)
    user_message_count[user_id] = count + 1

    # 🎁 FREE MESSAGES
    if count < FREE_MESSAGES:
        try:
            reply = await generate_ai_reply(text)
            await update.message.reply_text(
                f"🎁 Free answer ({count+1}/{FREE_MESSAGES}):\n\n{reply}"
            )
        except Exception as e:
            logger.exception(f"❌ Gemini error: {e}")
            await update.message.reply_text(
                "⚠️ AI is busy. Try again in a moment."
            )
        return

    # ⭐ PAID MESSAGE
    pending_queries[user_id] = text

    prices = [LabeledPrice("AI Answer", 5)]  # 5 Stars

    await update.message.reply_invoice(
        title="AskAI Pro – AI Answer",
        description="Premium AI-powered response",
        payload=str(user_id),
        provider_token="",   # REQUIRED EMPTY for Stars
        currency="XTR",
        prices=prices,
    )

# -------------------------------------------------
# PRE-CHECKOUT (MANDATORY FOR STARS)
# -------------------------------------------------
async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

# -------------------------------------------------
# PAYMENT SUCCESS
# -------------------------------------------------
async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logger.info(f"💰 Payment received from {user_id}")

    query = pending_queries.pop(user_id, None)

    if not query:
        await update.message.reply_text("⚠️ Please send your question again.")
        return

    try:
        reply = await generate_ai_reply(query)
        await update.message.reply_text(
            "✅ Payment received!\n\n🤖 AI Answer:\n" + reply
        )
    except Exception as e:
        logger.exception(f"❌ Gemini error after payment: {e}")
        await update.message.reply_text(
            "⚠️ AI error after payment. Please try again."
        )

# -------------------------------------------------
# START APP
# -------------------------------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

logger.info("🤖 Bot polling started")

app.run_polling(drop_pending_updates=True)


