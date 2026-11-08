import os
import sys
import asyncio
import base64
from collections import deque
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_PATH, override=True)

API_ID_RAW = os.getenv('TELEGRAM_API_ID', '').strip()
API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING', '').strip()
TARGET_CHAT_ID_RAW = os.getenv('TARGET_CHAT_ID', '').strip()
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook/telegram-to-threads').strip()

if os.getenv('IN_DOCKER') == 'true':
    N8N_WEBHOOK_URL = N8N_WEBHOOK_URL.replace('://localhost', '://host.docker.internal').replace('://127.0.0.1', '://host.docker.internal')

REQUIRE_PHOTO = os.getenv('REQUIRE_PHOTO', 'true').strip().lower() in ('true', '1', 'yes')
MIN_LENGTH = int(os.getenv('MIN_LENGTH', '0').strip() or '0')
QUEUE_DELAY = int(os.getenv('QUEUE_DELAY', '10').strip() or '10')
INCLUDE_KEYWORDS = [k.strip().lower() for k in os.getenv('INCLUDE_KEYWORDS', '').strip('[]').split(',') if k.strip()]
EXCLUDE_KEYWORDS = [k.strip().lower() for k in os.getenv('EXCLUDE_KEYWORDS', '').strip('[]').split(',') if k.strip()]

missing_vars = [
    name for name, val in [
        ('TELEGRAM_API_ID', API_ID_RAW),
        ('TELEGRAM_API_HASH', API_HASH),
        ('TARGET_CHAT_ID', TARGET_CHAT_ID_RAW.strip('[]').strip()),
    ] if not val
]
if missing_vars:
    print(f"[!] Missing required environment variables: {', '.join(missing_vars)}")
    exit(1)

if not SESSION_STRING:
    print("[!] Missing TELEGRAM_SESSION_STRING in .env!")
    print("    Please log in first using one of the following commands:")
    print("    1. Direct Python: python get_chat_ids.py")
    print("    2. Via Docker:    docker compose run --rm telegram-listener python get_chat_ids.py")
    sys.exit(1)

API_ID = int(API_ID_RAW)
TARGET_CHAT_IDS = [int(cid.strip()) for cid in TARGET_CHAT_ID_RAW.strip('[]').split(',') if cid.strip()]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
message_queue = asyncio.Queue()
seen_albums = deque(maxlen=500)


async def queue_worker():
    while True:
        message = await message_queue.get()
        try:
            raw_text = (message.text or "").strip()
            image_base64 = ""

            if message.photo:
                image_bytes = await message.download_media(file=bytes)
                if image_bytes:
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            payload = {
                'message_id': str(message.id),
                'original_caption': raw_text,
                'image_base64': image_base64
            }
            res = await asyncio.to_thread(
                requests.post, N8N_WEBHOOK_URL, json=payload, timeout=30
            )
            print(f"[+] Sent message {message.id} to n8n: {res.status_code} (Queue left: {message_queue.qsize()})")
        except Exception as e:
            print(f"[-] Webhook error for message {message.id}: {e}")
        finally:
            message_queue.task_done()

        if QUEUE_DELAY > 0:
            await asyncio.sleep(QUEUE_DELAY)


@client.on(events.NewMessage(chats=TARGET_CHAT_IDS))
async def handle_message(event):
    message = event.message

    if message.grouped_id:
        if message.grouped_id in seen_albums:
            return

    raw_text = (message.text or "").strip()

    if REQUIRE_PHOTO and not message.photo:
        return

    if len(raw_text) < MIN_LENGTH:
        return

    text_lower = raw_text.lower()
    if any(kw in text_lower for kw in EXCLUDE_KEYWORDS):
        return

    if INCLUDE_KEYWORDS and not any(kw in text_lower for kw in INCLUDE_KEYWORDS):
        return

    if message.grouped_id:
        seen_albums.append(message.grouped_id)

    await message_queue.put(message)
    print(f"[+] Queued message {message.id} (Queue size: {message_queue.qsize()})")


async def main():
    await client.get_dialogs()
    asyncio.create_task(queue_worker())
    print(f"Listening on chats {TARGET_CHAT_IDS} -> {N8N_WEBHOOK_URL} (Delay: {QUEUE_DELAY}s)")
    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
