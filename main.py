from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from openai import OpenAI
import json
import os
from flask import Flask
from threading import Thread

# -------- FLASK KEEP-ALIVE SERVER --------
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    # Render provides the PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# -------- CONFIG --------
SHEET_NAME = "Budget"
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# -------- GOOGLE SHEETS SETUP --------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).worksheet("Expenses") 

ALLOWED_CATEGORIES = ["outside food", "miscellaneous", "household", "Travel", "Shopping", "Medical", "Credit Card", "SIP"]

client_ai = OpenAI(api_key=OPENAI_API_KEY)

async def parse_expense_ai(text: str):
    system_prompt = f"""
        You are an expense parser. Return ONLY valid JSON:
        {{ "expense": "", "amount": number, "category": "", "person": "" }}
        Allowed categories: {ALLOWED_CATEGORIES}
        """
    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
        temperature=0
    )
    return json.loads(response.choices[0].message.content)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send expense details (e.g., 'Coffee 120')")

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        parsed = await parse_expense_ai(text)
        
        expense = parsed["expense"]
        amount = parsed["amount"]
        category = parsed["category"]
        person = parsed["person"] or update.message.from_user.username
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet.append_row([date, expense, amount, category, person])
        await update.message.reply_text(f"✅ Added: {expense} - ₹{amount} ({category})")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# -------- MAIN EXECUTION --------
if __name__ == '__main__':
    # 1. Start the Flask server in a background thread
    Thread(target=run_flask).start()
    
    # 2. Start the Telegram Bot
    print("Bot is starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))
    
    app.run_polling()
