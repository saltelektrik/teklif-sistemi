import imaplib
import email
from email.header import decode_header
from datetime import datetime
import time
import ssl
import json
import os

# 📂 JSON dosyası — main.py ile aynı veri kaynağı
os.makedirs("data", exist_ok=True)
DATA_FILE = "data/requests.json"

# --- Natro Kurumsal Eposta Bilgileri ---
EMAIL = "teklif@e-saltelektrik.com"
PASSWORD = "KampanyaXmail0217"  # mail hesabının parolasını gir
IMAP_SERVER = "mail.kurumsaleposta.com"
IMAP_PORT = 993


def check_emails(requests_data):
    """Kurumsal e-posta kutusunu kontrol eder ve yeni mailleri requests_data listesine ekler."""
    try:
        context = ssl.create_default_context()
        context.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        mail.login(EMAIL, PASSWORD)
        print("✅ IMAP bağlantısı başarılı:", EMAIL)
        mail.select("INBOX")

        status, messages = mail.search(None, "UNSEEN")
        mail_ids = messages[0].split()
        print("📥 Mail kutusu içeriği:", len(mail_ids), "adet mail bulundu.")

        for num in mail_ids[-3:]:
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            mail.store(num, '+FLAGS', '\\Seen')

            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8", errors="ignore")
            sender = msg.get("From")
            print("📨 Yeni mail kontrol ediliyor:", subject)

            # İçerik çözümleme
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition"))
                    if ctype == "text/plain" and "attachment" not in disp:
                        body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            # Eğer mail zaten eklenmişse tekrar ekleme
            if any(subject in r["messages"][0]["text"] for r in requests_data if r["messages"]):
                continue

            # Yeni talep kaydı oluştur
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_request = {
                "id": len(requests_data) + 1,
                "user_id": 0,
                "name": sender,
                "email": sender,
                "messages": [{
                    "sender": "müşteri",
                    "text": f"📧 Yeni e-posta teklifi: {subject}\n\n{body}",
                    "image": None,
                    "time": timestamp
                }],
                "status": "Yeni Talep",
                "timestamp": timestamp
            }

            requests_data.append(new_request)

            # JSON dosyasına kaydet (birikmeli - eskiler silinmez)
            try:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "r+", encoding="utf-8") as f:
                        try:
                            existing_data = json.load(f)
                        except:
                            existing_data = []

                        existing_data.append(new_request)
                        f.seek(0)
                        json.dump(existing_data, f, ensure_ascii=False, indent=4)
                        f.truncate()
                        print("💾 Yeni talep eklendi:", subject)
                else:
                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump([new_request], f, ensure_ascii=False, indent=4)
                        print("💾 Yeni dosya oluşturuldu:", subject)

            except Exception as e:
                print("⚠️ JSON kaydetme hatası:", e)

        mail.logout()

    except Exception as e:
        print("❌ Mail okuma hatası:", e)


# 🟢 Global değişken tanımla
requests_data = []


def start_listener():
    global requests_data
    print("📬 Mail dinleme başlatıldı (Kurumsal Eposta)...")
    while True:
        check_emails(requests_data)
        time.sleep(20)
