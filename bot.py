import os
from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

import google.generativeai as genai

# ✅ Read secrets from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ✅ Configure Gemini correctly
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Simple in-memory storage
free_users = set()
pending_queries = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 🎁 One free question
    if user_id not in free_users:
        free_users.add(user_id)
        response = model.generate_content(text)
        await update.message.reply_text(
            "🎁 Free trial answer:\n\n" + response.text
        )
        return

    # Store question before payment
    pending_queries[user_id] = text

    prices = [LabeledPrice("AI Answer", 5)]  # 5 Stars
    await update.message.reply_invoice(
        title="AskAI Pro – AI Answer",
        description="Get a premium AI-powered response",
        payload=str(user_id),
        provider_token="",      # EMPTY for Stars
        currency="XTR",         # Telegram Stars
        prices=prices,
    )

async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    query = pending_queries.pop(user_id, None)

    if not query:
        await update.message.reply_text("⚠️ Please send your question again.")
        return

    response = model.generate_content(query)
    await update.message.reply_text(
        "✅ Payment received!\n\n🤖 AI Answer:\n" + response.text
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
