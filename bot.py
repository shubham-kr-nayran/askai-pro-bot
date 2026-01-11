import os
from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)
import google.generativeai as genai

BOT_TOKEN = os.getenv("8218121021:AAFsC_7bLOdlLTbJxuT7Dj3EaLHIvkX50Nk")
GEMINI_API_KEY = os.getenv("AIzaSyCLQeDlouTS7zAekqhzx0bvYgEWVfUrQDs")

genai.configure(api_key=AIzaSyCLQeDlouTS7zAekqhzx0bvYgEWVfUrQDs)
model = genai.GenerativeModel("gemini-pro")

# Store free usage (simple version)
free_users = set()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 1 free message
    if user_id not in free_users:
        free_users.add(user_id)
        response = model.generate_content(text)
        await update.message.reply_text(
            "🎁 Free trial answer:\n\n" + response.text
        )
        return

    # Ask for Stars payment
    prices = [LabeledPrice("AI Answer", 5)]  # 5 Stars
    await update.message.reply_invoice(
        title="AskAI Pro – AI Answer",
        description="Get a premium AI-powered response",
        payload="askai_pro",
        provider_token="",     # EMPTY for Stars
        currency="XTR",        # Telegram Stars
        prices=prices,
    )

async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    response = model.generate_content(query)
    await update.message.reply_text(
        "✅ Payment received!\n\n🤖 AI Answer:\n" + response.text
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
