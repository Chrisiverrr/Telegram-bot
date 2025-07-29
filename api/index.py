# api/index.py
import asyncio
import aiohttp
import logging
from telegram import Bot
from fastapi import FastAPI, Response

# Configuration
BOT_TOKEN = "7376249732:AAGmXms19BSqHmQBRmaow_D2V6reM2jEm8k"  # Replace with environment variable in production
CHAT_IDS = ["-1002537379800"]
API_URL = "https://api.joshlei.com/v2/growagarden/stock"
KEYWORDS = {"godly", "master", "mythical", "bug egg", "prismatic"}

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI and Telegram Bot
app = FastAPI()
bot = Bot(BOT_TOKEN)
last_payload = ""
last_msg_id = {cid: None for cid in CHAT_IDS}

def fmt_section(title, items):
    live = [i for i in (items or []) if i.get("end_date_unix", 0) > asyncio.get_event_loop().time()]
    return f"<b>{title}</b>\n" + "\n".join(f"• {i['display_name']} – {i['quantity']}" ecommerce for i in live) if live else ""

async def build_payload(data):
    return "\n\n".join(filter(None, [
        fmt_section("🛠️ Gear", data.get("gear_stock")),
        fmt_section("🥚 Eggs", data.get("egg_stock")),
    ]))

def contains_keyword(items):
    return [i["display_name"] for i in (items or []) if any(k in i.get("display_name", "").lower() for k in KEYWORDS)]

async def tick(session):
    global last_payload, last_msg_id
    try:
        async with session.get(API_URL, timeout=15) as r:
            data = await r.json()
        payload = await build_payload(data)
        all_items = data.get("gear_stock", []) + data.get("egg_stock", [])
        alerts = contains_keyword(all_items)

        if payload and payload != last_payload:
            for cid in CHAT_IDS:
                if last_msg_id[cid]:
                    try:
                        await bot.delete_message(chat_id=cid, message_id=last_msg_id[cid])
                    except Exception as e:
                        logger.warning(f"Failed to delete message in {cid}: {e}")
                msg = await bot.send_message(chat_id=cid, text=payload, parse_mode="HTML")
                last_msg_id[cid] = msg.message_id
            last_payload = payload
            logger.info("✅ Full stock updated")
        if alerts:
            for cid in CHAT_IDS:
                await bot.send_message(
                    chat_id=cid,
                    text=f"🚨 <b>ALERT!</b>\n" + "\n".join(f"• {a}" for a in alerts) + "\n@everyone",
                    parse_mode="HTML"
                )
            logger.info("🚨 Alert sent: %s", alerts)
        return {"status": "success", "message": "Tick executed", "alerts": alerts}
    except Exception as e:
        logger.error("❌ %s", e)
        return {"status": "error", "message": str(e)}

@app.get("/tick")
async def handle_tick():
    async with aiohttp.ClientSession() as session:
        result = await tick(session)
    return result
