import os
import json
from datetime import datetime
from flask import Flask, request

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------- GOOGLE SHEETS ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)
sheet = client.open("Budget").worksheet("Expenses")

# ---------------- OPENAI ----------------
client_ai = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_CATEGORIES = [
    "Outside food",
    "Miscellaneous",
    "Household",
    "Travel",
    "Shopping",
    "Medical",
    "Credit Card",
    "SIP"
]

# ---------------- AI PARSER ----------------
async def parse_expense_ai(text: str):
    system_prompt = f"""
You are an expense parser.
Return ONLY valid JSON.

Format:
{{
  "expense": "",
  "amount": number,
  "category": "",
  "person": ""
}}

Allowed categories:
{ALLOWED_CATEGORIES}
"""

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
    )

    return json.loads(response.choices[0].message.content)

# ---------------- BOT HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send any expense in natural language.\n\n"
        "Example:\nPaid 300 rupees at cafe by Sumanth"
    )

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parsed = await parse_expense_ai(update.message.text)

        expense = parsed["expense"]
        amount = parsed["amount"]
        category = parsed["category"]
        person = parsed["person"] or update.message.from_user.username

        if category not in ALLOWED_CATEGORIES:
            raise ValueError("Invalid category")

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([date, expense, amount, category, person])

        await update.message.reply_text(
            f"✅ Added\n\n"
            f"Expense: {expense}\n"
            f"Amount: ₹{amount}\n"
            f"Category: {category}\n"
            f"Person: {person}"
        )

    except Exception as e:
        await update.message.reply_text(
            "❌ Couldn't understand.\nTry:\nPaid 300 rupees at cafe"
        )

# ---------------- TELEGRAM APP ----------------
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))

# ---------------- FLASK WEB SERVER ----------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "OK", 200

# ---------------- STARTUP ----------------
if __name__ == "__main__":
    telegram_app.initialize()
    telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    telegram_app.start()

    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
