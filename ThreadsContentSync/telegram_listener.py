import os
import re
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

if not API_ID_RAW or not API_HASH or not TARGET_CHAT_ID_RAW:
    print("[!] Missing required environment variables: TELEGRAM_API_ID, TELEGRAM_API_HASH, TARGET_CHAT_ID")
    exit(1)

if os.getenv('IN_DOCKER') == 'true' and not SESSION_STRING:
    print("[!] Chưa có TELEGRAM_SESSION_STRING trong file .env!")
    print("    Hãy đăng nhập lần đầu bằng 1 trong 2 lệnh sau (hệ thống sẽ tự lưu session vào .env):")
    print("    1. Chạy trực tiếp: python get_chat_ids.py")
    print("    2. Chạy qua Docker: docker compose run --rm telegram-listener python get_chat_ids.py")
    sys.exit(1)

API_ID = int(API_ID_RAW)
TARGET_CHAT_IDS = [int(cid.strip()) for cid in TARGET_CHAT_ID_RAW.strip('[]').split(',') if cid.strip()]

client = TelegramClient(StringSession(SESSION_STRING or None), API_ID, API_HASH)
message_queue = asyncio.Queue()
seen_albums = deque(maxlen=500)


def save_session_to_env(new_session_str: str):
    if not new_session_str or not os.path.exists(ENV_PATH):
        return
    try:
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        if re.search(r'^TELEGRAM_SESSION_STRING=.*$', content, flags=re.MULTILINE):
            content = re.sub(
                r'^TELEGRAM_SESSION_STRING=.*$',
                f'TELEGRAM_SESSION_STRING={new_session_str}',
                content,
                flags=re.MULTILINE
            )
        else:
            content = content.rstrip() + f'\nTELEGRAM_SESSION_STRING={new_session_str}\n'
        with open(ENV_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print("[+] Saved TELEGRAM_SESSION_STRING to .env")
    except Exception as e:
        print(f"[!] Could not save TELEGRAM_SESSION_STRING to .env: {e}")


async def env_watcher():
    last_mtime = os.path.getmtime(ENV_PATH) if os.path.exists(ENV_PATH) else None
    while True:
        await asyncio.sleep(2)
        if os.path.exists(ENV_PATH):
            current_mtime = os.path.getmtime(ENV_PATH)
            if last_mtime is not None and current_mtime != last_mtime:
                print("[*] Detected .env change! Reloading...")
                await client.disconnect()
                os._exit(0)
            last_mtime = current_mtime


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
    if not SESSION_STRING:
        save_session_to_env(client.session.save())
    await client.get_dialogs()
    asyncio.create_task(env_watcher())
    asyncio.create_task(queue_worker())
    print(f"Listening on chats {TARGET_CHAT_IDS} -> {N8N_WEBHOOK_URL} (Delay: {QUEUE_DELAY}s)")
    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
