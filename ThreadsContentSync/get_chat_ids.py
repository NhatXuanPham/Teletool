import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_PATH, override=True)

API_ID_RAW = os.getenv('TELEGRAM_API_ID', '').strip()
API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING', '').strip()

if not API_ID_RAW or not API_HASH:
    print("[!] Missing required environment variables: TELEGRAM_API_ID, TELEGRAM_API_HASH")
    exit(1)

client = TelegramClient(StringSession(SESSION_STRING or None), int(API_ID_RAW), API_HASH)


async def main():
    if not SESSION_STRING:
        print(f"\n[+] Copy this line into your .env file:\nTELEGRAM_SESSION_STRING={client.session.save()}\n")
    print(f"{'CHAT ID':<20} | {'TITLE'}")
    print("-" * 50)
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"{dialog.id:<20} | {dialog.title}")


with client:
    client.loop.run_until_complete(main())
