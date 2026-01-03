from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import openai
from openai import OpenAI
import json
import os
import json
from oauth2client.service_account import ServiceAccountCredentials


import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

def run_dummy_server():
    port = int(os.getenv("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()



# -------- CONFIG --------

SHEET_NAME = "Budget"

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")



# -------- GOOGLE SHEETS SETUP --------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]


google_creds_dict = json.loads(GOOGLE_CREDS_JSON)

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds_dict, scope
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).worksheet("Expenses") 


ALLOWED_CATEGORIES = [
    "outside food",
    "miscellaneous",
    "household",
    "Travel",
    "Shopping",
    "Medical",
    "Credit Card",
    "SIP"
]


client_ai = OpenAI(api_key=OPENAI_API_KEY)

async def parse_expense_ai(text: str):
    system_prompt = f"""
        You are an expense parser.
        Extract structured data from user input.

        Return ONLY valid JSON in this format:
        {{
        "expense": "",
        "amount": number,
        "category": "",
        "person": ""
        }}

        Allowed categories ONLY:
        {ALLOWED_CATEGORIES}

        Rules:
        - Category must be closest match from allowed list
        - Amount must be numeric
        - If person not mentioned, return empty string
        """

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0
    )

    content = response.choices[0].message.content
    return json.loads(content)




# -------- BOT FUNCTIONS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send data as:\nItem, Amount, Category\n\nExample:\nCoffee, 120, Food"
    )

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        parsed = await parse_expense_ai(text)

        expense = parsed["expense"]
        amount = parsed["amount"]
        category = parsed["category"]
        person = parsed["person"] or update.message.from_user.username

        # Validation
        if category not in ALLOWED_CATEGORIES:
            raise ValueError("Invalid category")

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet.append_row([date, expense, amount, category, person])

        await update.message.reply_text(
            f"✅ Added!\n\n"
            f"Expense: {expense}\n"
            f"Amount: ₹{amount}\n"
            f"Category: {category}\n"
            f"Person: {person}"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error:\n{str(e)}"
        )

# -------- MAIN --------
print("BOT_TOKEN:",BOT_TOKEN)
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))

print("Bot running...")
threading.Thread(target=run_dummy_server, daemon=True).start()
app.run_polling(close_loop=False)
