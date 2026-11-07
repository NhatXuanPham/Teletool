import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID_RAW = os.getenv('TELEGRAM_API_ID', '').strip()
API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
SESSION_NAME = os.getenv('SESSION_NAME', 'session_userbot').strip() or 'session_userbot'

if not API_ID_RAW or not API_HASH:
    print("[!] Vui lòng điền TELEGRAM_API_ID và TELEGRAM_API_HASH vào file .env!")
    exit(1)

API_ID = int(API_ID_RAW)
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def main():
    print("\n" + "="*55)
    print(" DANH SÁCH CÁC NHÓM / KÊNH TELEGRAM CỦA BẠN ")
    print("="*55)
    print(f"{'CHAT ID':<20} | {'TÊN NHÓM / KÊNH'}")
    print("-" * 55)

    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"{dialog.id:<20} | {dialog.title}")

    print("="*55)
    print(">> Sao chép ID nhóm cần nghe (có cả dấu trừ '-') dán vào TARGET_CHAT_ID trong .env\n")

with client:
    client.loop.run_until_complete(main())

