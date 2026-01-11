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

from openai import OpenAI

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logger.info(f"DEBUG BOT_TOKEN loaded: {bool(BOT_TOKEN)}")
logger.info(f"DEBUG OPENAI_API_KEY loaded: {bool(OPENAI_API_KEY)}")

if not BOT_TOKEN:
    sys.exit("❌ BOT_TOKEN missing")

if not OPENAI_API_KEY:
    sys.exit("❌ OPENAI_API_KEY missing")

# -------------------------------------------------
# OPENAI CLIENT (FAST + STABLE)
# -------------------------------------------------
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_NAME = "gpt-4o-mini"  # fast + cheap + reliable

logger.info("✅ OpenAI client initialized")

# -------------------------------------------------
# STATE (IN-MEMORY)
# -------------------------------------------------
FREE_MESSAGES = 3
user_message_count = {}
pending_queries = {}

# -------------------------------------------------
# ASYNC AI CALL (FAST)
# -------------------------------------------------
async def generate_ai_reply(text: str) -> str:
    loop = asyncio.get_running_loop()

    def call_openai():
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful, concise AI assistant."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            max_tokens=300,
            temperature=0.5,
        )
        return response.choices[0].message.content

    return await loop.run_in_executor(None, call_openai)

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
            logger.exception(f"❌ OpenAI error: {e}")
            await update.message.reply_text(
                "⚠️ AI is busy. Please try again."
            )
        return

    # ⭐ PAID MESSAGE
    pending_queries[user_id] = text

    prices = [LabeledPrice("AI Answer", 5)]  # 5 Telegram Stars

    await update.message.reply_invoice(
        title="AskAI Pro – AI Answer",
        description="Premium AI-powered response",
        payload=str(user_id),
        provider_token="",   # REQUIRED EMPTY for Telegram Stars
        currency="XTR",
        prices=prices,
    )

# -------------------------------------------------
# PRE-CHECKOUT HANDLER (MANDATORY)
# -------------------------------------------------
async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

# -------------------------------------------------
# PAYMENT SUCCESS HANDLER
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
        logger.exception(f"❌ OpenAI error after payment: {e}")
        await update.message.reply_text(
            "⚠️ AI error after payment. Please try again."
        )

# -------------------------------------------------
# START BOT
# -------------------------------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

logger.info("🤖 Bot polling started")

app.run_polling(drop_pending_updates=True)
