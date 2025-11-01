import imaplib
import email
from email.header import decode_header
from datetime import datetime
import time
import ssl
import json
import os
import re

# 📁 Klasör yapısı
os.makedirs("data", exist_ok=True)
os.makedirs("static/uploads/mail_attachments", exist_ok=True)
DATA_FILE = "data/requests.json"

EMAIL = "teklif@e-saltelektrik.com"
PASSWORD = "KampanyaXmail0217"
IMAP_SERVER = "mail.kurumsaleposta.com"
IMAP_PORT = 993


def _decode_str(s):
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(p)
    return "".join(out)


def _extract_plain_text(msg):
    """Mesaj gövdesini sade metin olarak çıkar."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    pass
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    html = re.sub(r"<br\s*/?>", "\n", html)
                    return re.sub(r"<[^>]+>", "", html)
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def _extract_attachments(msg):
    """E-posta içindeki ekleri 'static/uploads/mail_attachments' klasörüne kaydeder."""
    saved_files = []
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        if "attachment" in disp:
            filename = part.get_filename()
            if filename:
                filename = _decode_str(filename)
                safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
                file_path = os.path.join("static/uploads/mail_attachments", safe_name)
                try:
                    with open(file_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    saved_files.append(f"/static/uploads/mail_attachments/{safe_name}")
                    print(f"📎 Ek kaydedildi: {file_path}")
                except Exception as e:
                    print(f"⚠️ Ek kaydedilemedi ({filename}): {e}")
    return saved_files


def check_emails(requests_data):
    try:
        context = ssl.create_default_context()
        context.options |= 0x4
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        mail.login(EMAIL, PASSWORD)
        print("✅ IMAP bağlantısı başarılı:", EMAIL)
        mail.select("INBOX")

        status, messages = mail.search(None, "UNSEEN")
        mail_ids = messages[0].split()
        print("📥 Yeni mail sayısı:", len(mail_ids))

        for num in mail_ids:
            try:
                uid = num.decode()
                res, msg_data = mail.fetch(num, "(RFC822)")
                if res != "OK" or not msg_data or not msg_data[0]:
                    print(f"⚠️ UID {uid}: Mail verisi alınamadı.")
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                mail.store(num, "+FLAGS", "\\Seen")

                subject = _decode_str(msg.get("Subject"))
                raw_from = _decode_str(msg.get("From") or "")
                msg_id = msg.get("Message-ID") or f"uid-{uid}"
                print(f"📨 Mail alındı: {subject}")

                body = _extract_plain_text(msg).strip()
                attachments = _extract_attachments(msg)

                # Aynı UID veya Message-ID zaten varsa atla
                if any(r.get("uid") == uid or r.get("msg_id") == msg_id for r in requests_data):
                    print(f"⏭️ {subject} zaten mevcut, atlandı.")
                    continue

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_request = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "uid": uid,
                    "msg_id": msg_id,
                    "name": raw_from or "Bilinmeyen Gönderen",
                    "email": raw_from or "bilinmiyor@e-posta.com",
                    "timestamp": timestamp,
                    "products": [],
                    "status": "new",
                    "request_messages": [
                        {
                            "sender": "müşteri",
                            "sender_name": raw_from or "E-posta Gönderen",
                            "text": f"📧 E-posta konusu: {subject}\n\n{body or '(Mesaj içeriği yok)'}",
                            "file": attachments[0] if attachments else None,
                            "attachments": attachments,
                            "time": timestamp,
                        }
                    ],
                    "offer_messages": [],
                }

                requests_data.append(new_request)
                print(f"💾 Kaydedildi: {subject} ({new_request['id']})")

                # JSON güncelle
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "r+", encoding="utf-8") as f:
                        try:
                            existing = json.load(f)
                        except Exception:
                            existing = []
                        existing.append(new_request)
                        f.seek(0)
                        json.dump(existing, f, ensure_ascii=False, indent=4)
                        f.truncate()
                else:
                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump([new_request], f, ensure_ascii=False, indent=4)

            except Exception as e:
                print(f"❌ Mail işleme hatası (UID {num}):", e)
                continue

        mail.logout()

    except Exception as e:
        print("❌ Mail okuma hatası:", e)


requests_data = []


def start_listener():
    global requests_data
    print("📬 Mail dinleme başlatıldı...")
    while True:
        try:
            check_emails(requests_data)
        except Exception as e:
            print("⚠️ Listener hata verdi:", e)
            time.sleep(10)
        time.sleep(60)