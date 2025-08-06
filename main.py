import json
import logging
import os
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaEmpty, MessageMediaUnsupported

# ------------------ CONFIGURATION --------------------

# ये मान my.telegram.org से प्राप्त करें
# इन्हें सीधे यहां लिखने के बजाय एनवायरनमेंट वेरिएबल में रखना बेहतर है
API_ID = int(os.environ.get("API_ID", 12345)) # अपना API ID यहाँ डालें
API_HASH = os.environ.get("API_HASH", "your_api_hash") # अपना API HASH यहाँ डालें

# आपके बॉट का टोकन, जिसे BotFather से प्राप्त किया गया है
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

# आपकी न्यूमेरिक टेलीग्राम यूजर आईडी (बॉट का मालिक)
OWNER_ID = int(os.environ.get("OWNER_ID", 1251962299))

# सेशन फ़ाइल का नाम (Telethon इसे लॉगिन जानकारी याद रखने के लिए उपयोग करता है)
SESSION_NAME = "my_userbot_session"
SETTINGS_FILE = "settings.json"

# ----------------------------------------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# सेटिंग्स को लोड या इनिशियलाइज़ करें
def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "source_channels": [],
            "destination_channel": None,
            "working": False,
            "owner_id": OWNER_ID, # मालिक को भी सेटिंग्स में सहेजें
        }

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Telethon क्लाइंट को एक यूजर के रूप में शुरू करें (सुनने के लिए)
user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
# Telethon क्लाइंट को एक बॉट के रूप में शुरू करें (भेजने के लिए)
bot_client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)


@user_client.on(events.NewMessage)
async def command_handler(event):
    """कमांड्स को हैंडल करने के लिए"""
    # केवल मालिक ही कमांड का उपयोग कर सकता है
    if event.sender_id != OWNER_ID:
        return

    text = event.raw_text.lower()
    parts = text.split()
    command = parts[0]
    
    settings = load_settings()

    if command == "/start":
        await event.respond(
            "✅ यूजरबॉट-हाइब्रिड सक्रिय है!\n\n"
            "मैं आपके यूजर अकाउंट का उपयोग करके पब्लिक चैनलों को सुनूंगा और आपके बॉट का उपयोग करके संदेश भेजूंगा।\n\n"
            "कमांड्स:\n"
            "`/addsource @channel_username`\n"
            "`/removesource @channel_username`\n"
            "`/setdest @channel_username_or_id`\n"
            "`/list`\n"
            "`/startwork`\n"
            "`/stopwork`"
        )
    elif command == "/addsource" and len(parts) > 1:
        channel = parts[1].strip()
        if channel not in settings["source_channels"]:
            settings["source_channels"].append(channel)
            save_settings(settings)
            await event.respond(f"✅ सोर्स चैनल जोड़ा गया: {channel}")
        else:
            await event.respond(f"ℹ️ {channel} पहले से ही सोर्स में है।")

    elif command == "/removesource" and len(parts) > 1:
        channel = parts[1].strip()
        if channel in settings["source_channels"]:
            settings["source_channels"].remove(channel)
            save_settings(settings)
            await event.respond(f"✅ सोर्स चैनल हटाया गया: {channel}")
        else:
            await event.respond(f"ℹ️ {channel} सोर्स में नहीं मिला।")
            
    elif command == "/setdest" and len(parts) > 1:
        dest = parts[1].strip()
        try:
            # जांचें कि क्या यह एक न्यूमेरिक आईडी है
            settings["destination_channel"] = int(dest)
        except ValueError:
            # वर्ना इसे यूजरनेम मानें
            settings["destination_channel"] = dest
        save_settings(settings)
        await event.respond(f"✅ डेस्टिनेशन चैनल सेट किया गया: {dest}")
        
    elif command == "/list":
        sources = "\n".join(settings['source_channels']) if settings['source_channels'] else "कोई नहीं"
        dest = settings['destination_channel'] or "सेट नहीं है"
        status = 'चालू' if settings['working'] else 'बंद'
        await event.respond(
            f"📋 **वर्तमान सेटिंग्स**\n\n"
            f"**सोर्स चैनल:**\n{sources}\n\n"
            f"**डेस्टिनेशन चैनल:** {dest}\n\n"
            f"**स्टेटस:** {status}",
            parse_mode='md'
        )

    elif command == "/startwork":
        settings["working"] = True
        save_settings(settings)
        await event.respond("✅ काम शुरू कर दिया गया है। नए टेक्स्ट संदेशों को कॉपी किया जाएगा।")

    elif command == "/stopwork":
        settings["working"] = False
        save_settings(settings)
        await event.respond("🛑 काम रोक दिया गया है।")


@user_client.on(events.NewMessage)
async def message_copier(event):
    """संदेशों को कॉपी करने वाला मुख्य हैंडलर"""
    settings = load_settings()

    # अगर बॉट काम नहीं कर रहा है, या कोई डेस्टिनेशन नहीं है, तो कुछ न करें
    if not settings["working"] or not settings["destination_channel"]:
        return

    # जांचें कि क्या संदेश किसी सोर्स चैनल से है
    # हम चैनल के यूजरनेम या आईडी की जांच कर सकते हैं
    chat = await event.get_chat()
    chat_username = f"@{chat.username}" if chat.username else None
    
    if chat.id not in settings["source_channels"] and chat_username not in settings["source_channels"]:
        return
        
    # --- केवल टेक्स्ट संदेशों को कॉपी करें ---
    # 1. सुनिश्चित करें कि संदेश में टेक्स्ट है।
    # 2. सुनिश्चित करें कि संदेश में कोई मीडिया (फोटो, वीडियो, आदि) नहीं है।
    if event.message.text and (event.message.media is None or isinstance(event.message.media, (MessageMediaEmpty, MessageMediaUnsupported))):
        message_text = event.message.text
        
        try:
            # बॉट क्लाइंट का उपयोग करके संदेश भेजें
            await bot_client.send_message(settings["destination_channel"], message_text)
            logger.info(f"✅ '{chat.title}' से टेक्स्ट संदेश कॉपी किया गया।")
        except Exception as e:
            logger.error(f"डेस्टिनेशन चैनल '{settings['destination_channel']}' पर संदेश भेजने में त्रुटि: {e}")
            # अगर कोई गंभीर त्रुटि है, तो मालिक को सूचित करें
            if "chat not found" in str(e).lower() or "invalid peer" in str(e).lower():
                settings["working"] = False
                save_settings(settings)
                await user_client.send_message(OWNER_ID, f"🚨 डेस्टिनेशन चैनल '{settings['destination_channel']}' में समस्या के कारण काम रोक दिया गया है। कृपया जांचें।")

async def main():
    # पहले यूजर क्लाइंट में लॉग इन करें
    await user_client.start()
    logger.info("यूजर क्लाइंट (सुनने के लिए) शुरू हो गया है।")
    
    # बॉट क्लाइंट पहले ही शुरू हो चुका है
    logger.info("बॉट क्लाइंट (भेजने के लिए) शुरू हो गया है।")
    
    # सुनिश्चित करें कि आपका यूजर अकाउंट सोर्स चैनलों का सदस्य है
    settings = load_settings()
    for channel in settings.get("source_channels", []):
        try:
            await user_client.get_entity(channel)
            logger.info(f"आपका यूजर अकाउंट '{channel}' का सदस्य है।")
        except Exception:
            logger.warning(f"चेतावनी: आपका यूजर अकाउंट '{channel}' का सदस्य नहीं है या चैनल मौजूद नहीं है। कृपया इसे ज्वाइन करें।")

    print("\n✅ बॉट अब चल रहा है। कमांड भेजने के लिए अपने अकाउंट से खुद को संदेश भेजें (या किसी भी चैट में)।")
    print("बॉट को रोकने के लिए CTRL+C दबाएँ।")
    
    # स्क्रिप्ट को हमेशा चालू रखें
    await user_client.run_until_disconnected()


if __name__ == "__main__":
    with user_client:
        user_client.loop.run_until_complete(main())
