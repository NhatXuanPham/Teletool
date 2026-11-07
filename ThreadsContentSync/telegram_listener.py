import os
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

# Lấy cấu hình từ file .env hoặc biến môi trường
API_ID_RAW = os.getenv('TELEGRAM_API_ID', '').strip()
API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
TARGET_CHAT_ID_RAW = os.getenv('TARGET_CHAT_ID', '').strip()
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://n8n.your-domain.com/webhook/telegram-to-threads').strip()
SESSION_NAME = os.getenv('SESSION_NAME', 'session_userbot').strip() or 'session_userbot'

# Cấu hình bộ lọc (Filters)
REQUIRE_PHOTO = os.getenv('REQUIRE_PHOTO', 'true').strip().lower() in ('true', '1', 'yes')
MIN_LENGTH = int(os.getenv('MIN_LENGTH', '0').strip() or '0')

# Danh sách từ khóa (phân cách bằng dấu phẩy)
INCLUDE_KEYWORDS = [
    k.strip().lower() for k in os.getenv('INCLUDE_KEYWORDS', '').split(',') if k.strip()
]
EXCLUDE_KEYWORDS = [
    k.strip().lower() for k in os.getenv('EXCLUDE_KEYWORDS', '').split(',') if k.strip()
]

if not API_ID_RAW or not API_HASH:
    print("\n[!] LỖI CẤU HÌNH: Bạn chưa điền API credentials trong file .env")
    print("    - TELEGRAM_API_ID: Lấy tại https://my.telegram.org")
    print("    - TELEGRAM_API_HASH: Lấy tại https://my.telegram.org")
    print("Vui lòng mở file .env và điền các giá trị trên trước khi chạy script.\n")
    exit(1)

if not TARGET_CHAT_ID_RAW:
    print("\n[!] LỖI CẤU HÌNH: TARGET_CHAT_ID chưa được điền trong file .env")
    print("    - TARGET_CHAT_ID: ID nhóm hoặc kênh cần theo dõi (ví dụ: -1001234567890)\n")
    exit(1)

API_ID = int(API_ID_RAW)
TARGET_CHAT_ID = int(TARGET_CHAT_ID_RAW)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

@client.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def handle_message(event):
    message = event.message
    raw_text = message.text or ""
    
    # 1. BỘ LỌC ĐIỀU KIỆN
    # Lọc 1: Bắt buộc có ảnh
    if REQUIRE_PHOTO and not message.photo:
        print(f"[-] Bỏ qua message {message.id}: Không có ảnh đính kèm.")
        return

    # Lọc 2: Độ dài tối thiểu của text
    if len(raw_text.strip()) < MIN_LENGTH:
        print(f"[-] Bỏ qua message {message.id}: Độ dài text ({len(raw_text.strip())}) nhỏ hơn MIN_LENGTH ({MIN_LENGTH}).")
        return

    # Lọc 3: Từ khóa loại trừ (Exclude)
    if any(kw in raw_text.lower() for kw in EXCLUDE_KEYWORDS):
        matched_kw = [kw for kw in EXCLUDE_KEYWORDS if kw in raw_text.lower()]
        print(f"[-] Bỏ qua message {message.id}: Chứa từ khóa loại trừ {matched_kw}.")
        return

    # Lọc 4: Từ khóa bắt buộc (Include) - nếu có định nghĩa thì phải chứa ít nhất 1 từ
    if INCLUDE_KEYWORDS and not any(kw in raw_text.lower() for kw in INCLUDE_KEYWORDS):
        print(f"[-] Bỏ qua message {message.id}: Không chứa từ khóa yêu cầu trong INCLUDE_KEYWORDS.")
        return

    print(f"\n[+] Bắt được message hợp lệ: ID {message.id}")
    if raw_text:
        preview = (raw_text[:60] + "...") if len(raw_text) > 60 else raw_text
        print(f"    Preview: {preview}")

    # 2. Xử lý tải ảnh và gửi Webhook
    file_path = None
    files = {}
    if message.photo:
        os.makedirs("temp_images", exist_ok=True)
        file_path = await message.download_media(file="temp_images/")
        if not file_path:
            print(f"[-] Không tải được file ảnh của tin nhắn: {message.id}")
            return

    try:
        data = {
            'message_id': message.id,
            'caption_goc': raw_text
        }
        
        if file_path:
            with open(file_path, 'rb') as f:
                files = {'photo': (os.path.basename(file_path), f, 'image/jpeg')}
                res = requests.post(N8N_WEBHOOK_URL, data=data, files=files, timeout=30)
        else:
            res = requests.post(N8N_WEBHOOK_URL, json=data, timeout=30)

        print(f"[+] Pushed sang n8n thành công: Status {res.status_code}")
    except Exception as e:
        print(f"[-] Lỗi gửi webhook sang n8n: {e}")
    finally:
        # Dọn dẹp file tạm
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

with client:
    print("\n" + "="*50)
    print("Userbot đang lắng nghe tin nhắn...")
    print(f"- Target Chat ID : {TARGET_CHAT_ID}")
    print(f"- Yêu cầu có ảnh : {'BẬT (True)' if REQUIRE_PHOTO else 'TẮT (False)'}")
    print(f"- Độ dài text min: {MIN_LENGTH} ký tự")
    print(f"- Từ khóa cần có : {INCLUDE_KEYWORDS if INCLUDE_KEYWORDS else 'Tất cả (không lọc)'}")
    print(f"- Từ khóa loại trừ: {EXCLUDE_KEYWORDS if EXCLUDE_KEYWORDS else 'Không có'}")
    print("="*50 + "\n")
    client.run_until_disconnected()