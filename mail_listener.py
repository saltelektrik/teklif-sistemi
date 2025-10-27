import imaplib
import email
from email.header import decode_header
from datetime import datetime
import time
import ssl

# --- Natro Kurumsal Eposta Bilgileri ---
EMAIL = "teklif@e-saltelektrik.com"
PASSWORD = "KampanyaXmail0217"  # mail hesabının parolasını gir
IMAP_SERVER = "mail.kurumsaleposta.com"
IMAP_PORT = 993


def check_emails(requests_data):
    """Kurumsal Eposta kutusunu kontrol eder ve yeni mailleri requests_data listesine ekler."""
    try:
        # Güvenli ama eski SSL sürümleriyle uyumlu context oluştur
        context = ssl.create_default_context()
        context.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        # Tüm mailleri kontrol et (test aşamasında)
        status, messages = mail.search(None, "ALL")
        mail_ids = messages[0].split()

        for num in mail_ids[-3:]:  # sadece son 3 maili kontrol et (fazla yüklenmesin)
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            # Konu
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8", errors="ignore")
            sender = msg.get("From")

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
            requests_data.append({
                "id": len(requests_data),
                "user_id": 0,
                "name": sender,
                "email": sender,
                "messages": [{
                    "sender": "müşteri",
                    "text": f"📧 Yeni e-posta teklifi: {subject}\n\n{body}",
                    "image": None,
                    "time": timestamp
                }],
                "status": "new",
                "timestamp": timestamp
            })

            print(f"\033[92m[✓ YENİ TEKLİF]\033[0m {sender} → {subject}")

        mail.logout()

    except ssl.SSLError as e:
        print(f"⚠️ SSL hatası: {e}")
    except imaplib.IMAP4.error as e:
        print(f"⚠️ IMAP hatası: {e}")
    except Exception as e:
        print(f"⚠️ Mail okuma hatası: {e}")


# Test çalıştırması (isteğe bağlı)
if __name__ == "__main__":
    requests_data = []
    print("📬 Mail dinleme başlatıldı (Kurumsal Eposta)...")
    while True:
        check_emails(requests_data)
        time.sleep(60)
