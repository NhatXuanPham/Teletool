import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID_RAW = os.getenv('TELEGRAM_API_ID', '').strip()
API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
SESSION_NAME = os.getenv('SESSION_NAME', 'session_userbot').strip() or 'session_userbot'

if not API_ID_RAW or not API_HASH:
    print("[!] Missing required environment variables: TELEGRAM_API_ID, TELEGRAM_API_HASH")
    exit(1)

client = TelegramClient(SESSION_NAME, int(API_ID_RAW), API_HASH)


async def main():
    print(f"{'CHAT ID':<20} | {'TITLE'}")
    print("-" * 50)
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"{dialog.id:<20} | {dialog.title}")


with client:
    client.loop.run_until_complete(main())
