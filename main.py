import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
from flask import Flask
from threading import Thread

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_ID = 1340555782
WAITING_FOR_BROADCAST = 1
USERS_FILE = 'users.json'

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Encryptonite Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "service": "telegram-bot"}

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def add_user(user_id, username, first_name):
    users = load_users()
    users[str(user_id)] = {
        'username': username,
        'first_name': first_name,
        'blocked': False
    }
    save_users(users)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"
    first_name = user.first_name or "User"
    
    add_user(user_id, username, first_name)
    
    welcome_text = (
        "Hey there! 👋 Welcome to Encryptonite, where your secrets are safe from everyone... even us.\n\n"
        "Ready to lock down your texts? Tap the button below to launch the Mini App and start "
        "encrypting/decrypting messages instantly. We take privacy so seriously, we don't even know "
        "what you ate for breakfast. Seriously."
    )
    
    keyboard = [
        [InlineKeyboardButton("🔐 Launch Encryptonite", url="https://t.me/TextEncryptBot/encryptonite")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    if user_id != ADMIN_ID:
        admin_notification = (
            f"🆕 New User Started Bot:\n\n"
            f"👤 Name: {first_name}\n"
            f"🔖 Username: @{username}\n"
            f"🆔 User ID: {user_id}\n"
            f"🔗 Profile: tg://user?id={user_id}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📢 Broadcast Mode Activated\n\n"
        "Send me the message you want to broadcast to all users.\n"
        "Send /cancel to cancel the broadcast."
    )
    return WAITING_FOR_BROADCAST

async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broadcast_msg = update.message.text
    users = load_users()
    
    total_users = len(users)
    success_count = 0
    blocked_count = 0
    
    await update.message.reply_text(
        f"📤 Broadcasting message to {total_users} users...\n"
        "This may take a moment."
    )
    
    for user_id, user_data in users.items():
        try:
            await context.bot.send_message(chat_id=int(user_id), text=broadcast_msg)
            success_count += 1
        except Exception as e:
            blocked_count += 1
            user_data['blocked'] = True
            logger.error(f"Failed to send to {user_id}: {e}")
    
    save_users(users)
    
    summary = (
        f"✅ Broadcast Complete!\n\n"
        f"📊 Summary:\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Successfully Delivered: {success_count}\n"
        f"❌ Blocked/Failed: {blocked_count}"
    )
    await update.message.reply_text(summary)
    
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def run_bot():
    token = os.environ.get('BOT_TOKEN')
    
    if not token:
        logger.error("BOT_TOKEN not found!")
        return
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            WAITING_FOR_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)]
    )
    application.add_handler(broadcast_handler)
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("🌐 Flask server started")
    run_bot()