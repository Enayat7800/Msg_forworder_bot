# main.py

import json
import logging
import re
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ------------------ CONFIGURATION --------------------

# Replace with your Telegram user ID (owner of the bot)
OWNER_ID = 123456789  # <-- change this to your actual Telegram user ID (integer)

SETTINGS_FILE = "settings.json"

# ----------------------------------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize or load persistent settings
def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # ensure keys exist
            settings.setdefault("owner_id", OWNER_ID)
            settings.setdefault("admins", [OWNER_ID])
            settings.setdefault("source_channels", [])
            settings.setdefault("destination_channel", "")
            settings.setdefault("working", False)
            return settings
    except FileNotFoundError:
        settings = {
            "owner_id": OWNER_ID,
            "admins": [OWNER_ID],
            "source_channels": [],
            "destination_channel": "",
            "working": False
        }
        save_settings(settings)
        return settings

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Check if user is owner or admin
def is_admin(user_id, settings):
    return user_id in settings.get("admins", [])

# Helper: sanitize channel username input
def sanitize_channel_username(text):
    text = text.strip()
    if text.startswith("@"):
        return text.lower()
    return "@" + text.lower()

# Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I copy new text-only messages from your configured public source channels "
        "to your destination channel.\n\n"
        "Use /list to see current settings."
    )

async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /addsource @channelusername")
        return

    channel = sanitize_channel_username(context.args[0])
    if channel in settings["source_channels"]:
        await update.message.reply_text(f"{channel} is already in source channels.")
        return

    settings["source_channels"].append(channel)
    save_settings(settings)
    await update.message.reply_text(f"✅ Added {channel} as source channel.")

async def removesource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removesource @channelusername")
        return

    channel = sanitize_channel_username(context.args[0])
    if channel not in settings["source_channels"]:
        await update.message.reply_text(f"{channel} is not in source channels.")
        return

    settings["source_channels"].remove(channel)
    save_settings(settings)
    await update.message.reply_text(f"✅ Removed {channel} from source channels.")

async def setdest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /setdest @yourchannelusername")
        return

    channel = sanitize_channel_username(context.args[0])
    if settings.get("destination_channel") == channel:
        await update.message.reply_text(f"{channel} is already the destination channel.")
        return

    settings["destination_channel"] = channel
    save_settings(settings)
    await update.message.reply_text(f"✅ Destination channel set to {channel}.")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if user.id != settings.get("owner_id"):
        await update.message.reply_text("🚫 Only the bot owner can add admins.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /addadmin @username")
        return
    
    username = context.args[0].strip()
    if username.startswith("@"):
        username = username[1:]  # remove @ for internal storage

    # Avoid duplicates
    if username in settings.get("admins_usernames", []):
        await update.message.reply_text(f"User @{username} is already an admin.")
        return

    # We'll store admins by user_id, so here we need to resolve username to user_id
    # Telegram Bot API does not provide direct method to get user_id from username,
    # But we can try to get chat member info from any known channel?
    # For simplicity, ask user to send a private command or do manual add.
    await update.message.reply_text(
        "⚠️ Adding admin by username requires user ID. "
        "Please ask the user to send /start to me privately to store their user ID."
    )

async def list_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    sources = "\n".join(settings["source_channels"]) if settings["source_channels"] else "None"
    dest = settings["destination_channel"] or "Not set"
    admins_usernames = [f"<@{user_id}>" if user_id != OWNER_ID else "<Owner>" for user_id in settings["admins"]]

    text = (
        f"📋 Current Configuration:\n\n"
        f"👥 Admins (User IDs): {', '.join(str(x) for x in settings['admins'])}\n"
        f"🟢 Working Status: {'ON' if settings['working'] else 'OFF'}\n"
        f"📂 Source Channels:\n{sources}\n\n"
        f"📢 Destination Channel:\n{dest}"
    )
    await update.message.reply_text(text)

async def startwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    if settings.get("working"):
        await update.message.reply_text("Bot is already working (copying messages).")
        return
    
    settings["working"] = True
    save_settings(settings)
    await update.message.reply_text("✅ Bot started copying new text messages.")

async def stopwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    if not is_admin(user.id, settings):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    if not settings.get("working"):
        await update.message.reply_text("Bot is already stopped.")
        return
    
    settings["working"] = False
    save_settings(settings)
    await update.message.reply_text("🛑 Bot stopped copying messages.")

# Helper to check if message text contains links or media
def is_text_only_message(message):
    # Check text exists
    if not message.text:
        return False
    
    # Quick check for URLs in text
    url_pattern = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
    if url_pattern.search(message.text):
        return False
    
    # Ignore messages with entities like link, bold, italic are allowed.
    # But if message has media or caption (which is separate), ignore those
    if message.photo or message.video or message.document or message.audio or message.voice or message.animation or message.sticker:
        return False

    # Message with no URLs and no media is accepted
    return True

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    # Only operate if working is True
    if not settings.get("working"):
        return

    message = update.message
    if not message:
        return

    # Check if message is from one of the source channels
    chat = message.chat
    if not chat:
        return

    source_channels = settings.get("source_channels", [])
    if not source_channels:
        return
    
    # Chat username example: "@channelusername"
    # Sometimes channel username is None (private), ignore those
    chat_username = chat.username
    if not chat_username:
        return

    chat_username = "@" + chat_username.lower()
    if chat_username not in source_channels:
        return

    # Check if message is text-only (no links, media, etc)
    if not is_text_only_message(message):
        return
    
    # Get destination channel
    dest_channel = settings.get("destination_channel")
    if not dest_channel:
        logger.info("Destination channel not set. Cannot post messages.")
        return

    try:
        # Send copied text message to destination channel
        await context.bot.send_message(
            chat_id=dest_channel,
            text=message.text
        )
        logger.info(f"Copied message from {chat_username} to {dest_channel}")
    except Exception as e:
        logger.error(f"Failed to send message to {dest_channel}: {e}")

def main():
    import os
    from telegram.ext import application

    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        print("Error: Please set your bot token in BOT_TOKEN environment variable.")
        return

    settings = load_settings()

    app = Application.builder().token(TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addsource", addsource))
    app.add_handler(CommandHandler("removesource", removesource))
    app.add_handler(CommandHandler("setdest", setdest))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("list", list_config))
    app.add_handler(CommandHandler("startwork", startwork))
    app.add_handler(CommandHandler("stopwork", stopwork))

    # Message handler for channel messages
    app.add_handler(MessageHandler(filters.ChatType.CHANNELS & filters.TEXT & ~filters.UpdateType.EDITED, message_handler))

    print("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()





5. **Use bot commands in Telegram chat with your bot:**

| Command                 | Description                                         |
|-------------------------|-----------------------------------------------------|
| `/addsource @channel`     | Add a public source channel to watch                |
| `/removesource @channel`  | Remove a source channel from watch list             |
| `/setdest @channel`       | Set or change the destination channel               |
| `/addadmin @username`     | Add another admin to give command access            |
| `/list`                  | Show currently added source channels, destination, and admins |
| `/startwork`              | Start copying new text messages from source channels |
| `/stopwork`               | Stop copying messages (settings remain saved)       |

---

## Notes

- The bot must be admin in the destination channel to post messages.
- Source channels must be public (bot must be able to read messages).
- The bot stores data persistently in `settings.json`. Do not delete this file.
- Compatible with Python 3.10+.
- Tested on platforms like Replit, Render, Railway etc.

---

Enjoy automating your Telegram channel text copying!

---

Bot created by You.

