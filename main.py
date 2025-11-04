from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from functools import wraps
import os, json, smtplib, ssl
from email.message import EmailMessage
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "default-key")

# 📁 Upload klasörü
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "xlsx", "xls", "docx", "doc", "txt"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 📄 JSON dosyası (kalıcı veri)
DATA_FILE = "data/requests.json"
os.makedirs("data", exist_ok=True)

# ✅ JSON yükleme / kaydetme
def load_requests():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_requests():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(requests_data, f, ensure_ascii=False, indent=2)

requests_data = load_requests()
# ✅ Eksik alanları tamamla (eski kayıtlar için güvenlik)
for r in requests_data:
    if "messages" not in r:
        r["messages"] = []
    if "offer_messages" not in r:
        r["offer_messages"] = []

# 👥 Kullanıcılar
users = [
    {"email": "admin1@saltelektrik.com", "password": "admin123", "name": "Mehmet", "role": "admin"},
    {"email": "admin2@saltelektrik.com", "password": "admin123", "name": "Abdurrahman", "role": "admin"},
    {"email": "admin3@saltelektrik.com", "password": "admin123", "name": "Abdulselam", "role": "admin"},
    {"email": "client@saltelektrik.com", "password": "client123", "name": "Müşteri", "role": "client"},
]

@app.context_processor
def inject_datetime():
    return {"datetime": datetime}

# 🔐 Yardımcı fonksiyonlar
def get_current_user():
    if "user_email" in session:
        return next((u for u in users if u["email"] == session["user_email"]), None)
    elif "admin_email" in session:
        return next((u for u in users if u["email"] == session["admin_email"]), None)
    return None

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            flash("Lütfen giriş yapın.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "admin":
            flash("Bu sayfaya erişim izniniz yok.")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

# 🏠 Anasayfa
@app.route("/")
def index():
    user = get_current_user()
    if user:
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# 👤 Giriş
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = next((u for u in users if u["email"] == email and u["password"] == password), None)
        if not user:
            flash("E-posta veya şifre hatalı.")
            return redirect(url_for("login"))
        session.clear()
        if user["role"] == "admin":
            session["admin_email"] = user["email"]
            flash(f"{user['name']} olarak giriş yapıldı.")
            return redirect(url_for("admin_dashboard"))
        else:
            session["user_email"] = user["email"]
            flash("Giriş başarılı.")
            return redirect(url_for("dashboard"))
    return render_template("client/login.html")

# 📝 Kayıt
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        if next((u for u in users if u["email"] == email), None):
            flash("Bu e-posta adresiyle zaten kayıt olunmuş.")
            return redirect(url_for("register"))
        users.append({"email": email, "password": password, "name": name, "role": "client"})
        flash("Kayıt başarılı! Giriş yapabilirsiniz.")
        return redirect(url_for("login"))
    return render_template("client/register.html")

# 🚪 Çıkış
@app.route("/logout")
def logout():
    session.clear()
    flash("Oturum kapatıldı.")
    return redirect(url_for("login"))

# 💼 Müşteri Paneli
@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if user["role"] != "client":
        return redirect(url_for("admin_dashboard"))
    user_requests = [r for r in requests_data if r["email"] == user["email"]]
    return render_template("client/dashboard.html", user=user, requests=user_requests)

@app.route("/submit", methods=["POST"])
@login_required
def submit_request():
    user = get_current_user()
    desc = request.form.getlist("desc[]")
    code = request.form.getlist("code[]")
    brand = request.form.getlist("brand[]")
    qty = request.form.getlist("qty[]")
    message = request.form.get("message", "")

    # 📎 Dosya yükleme kısmı
    file = request.files.get("file")
    file_path = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        file_path = f"/static/uploads/{filename}"

    # 🧾 Ürün listesi oluştur
    products = []
    for d, c, b, q in zip(desc, code, brand, qty):
        if d or c or b or q:
            products.append({
                "desc": d.strip(),
                "code": c.strip(),
                "brand": b.strip(),
                "qty": q.strip(),
            })

    # 🆕 Eğer müşteri ürün eklemediyse boş ürün alanı oluştur
    if not products:
        products = [{
            "desc": "",
            "code": "",
            "brand": "",
            "qty": ""
        }]

    # 💬 Talep verisi
    req = {
        "id": len(requests_data) + 1,
        "name": user["name"],
        "email": user["email"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "request_messages": [
            {
                "sender": "müşteri",
                "sender_name": user["name"],
                "text": message.strip(),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path,
            }
        ],
        "offer_messages": [],
        "status": "new",
        "products": products,  # 🆕 her durumda dolu
    }

    # 💾 Kaydet
    requests_data.append(req)
    save_requests()
    flash("Talebiniz başarıyla gönderildi.")
    return redirect(url_for("dashboard"))

@app.route("/edit/<int:req_id>", methods=["GET", "POST"])
@login_required
def edit_request(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id and r["email"] == user["email"]), None)

    if not req:
        flash("Talep bulunamadı veya düzenleme yetkiniz yok.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        # Yeni verileri al
        desc = request.form.getlist("desc[]")
        code = request.form.getlist("code[]")
        brand = request.form.getlist("brand[]")
        qty = request.form.getlist("qty[]")
        message = request.form.get("message", "").strip()

        # Ürünleri güncelle
        req["products"] = [
            {"desc": d, "code": c, "brand": b, "qty": q}
            for d, c, b, q in zip(desc, code, brand, qty)
        ]

        # Talep notunu güncelle
        if req["request_messages"]:
            req["request_messages"][0]["text"] = message

        save_requests()
        flash("Talep başarıyla güncellendi.")
        return redirect(url_for("status", req_id=req_id))

    # Sayfa ilk yüklendiğinde mevcut verileri gönder
    return render_template("client/edit_request.html", req=req, user=user)

# 💬 Müşteri mesajlaşma
@app.route("/status/<int:req_id>", methods=["GET", "POST"])
@login_required
def status(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("dashboard"))
    req.setdefault("payment_term", "Peşin")
    req.setdefault("delivery_time", "Stokta (hemen teslim)")
    req.setdefault("offer_option", "7 Gün")

    # Eski kayıt uyumu
    req.setdefault("request_messages", req.pop("messages", []))
    req.setdefault("offer_messages", [])

    if request.method == "POST":
        text = request.form.get("message", "").strip()
        file = request.files.get("file")
        file_path = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_path = f"/static/uploads/{filename}"

        if text or file_path:
            req["request_messages"].append({
                "sender": "müşteri",
                "sender_name": user["name"],
                "text": text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path
            })
            save_requests()
        return redirect(url_for("status", req_id=req_id))

    return render_template("client/status.html", req=req, user=user)

# ⚙️ Yönetici Paneli
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    global requests_data, users
    import json
    from datetime import datetime

    # 🔹 Filtre & Sıralama Parametreleri
    sort = request.args.get("sort", "default")          # default, newest
    status_filter = request.args.get("status", "all")   # all, Teklif Hazır, Yeni, vb.

    # 🔹 Talepleri JSON dosyasından yükle
    try:
        with open("data/requests.json", "r", encoding="utf-8") as f:
            requests_data = json.load(f)

        # 🧩 Eski statüleri normalize et
        for r in requests_data:
            if r.get("status") == "Revize Edildi":
                r["status"] = "Cevaplandı"
            elif r.get("status") == "new":
                r["status"] = "Yeni"

        # 🪄 Eski veri formatlarını dönüştür (uyumluluk için)
        for r in requests_data:
            if "messages" in r and "request_messages" not in r:
                r["request_messages"] = r["messages"]

        print(f"🗂️ Dashboard için {len(requests_data)} kayıt yüklendi.")

    except Exception as e:
        print("⚠️ Dashboard veri yükleme hatası:", e)
        requests_data = []

    user = get_current_user()

    # 🟢 Statü sıralama mantığı
    status_order = {
        "Yeni": 0,
        "new": 0,
        "Teklif Hazır": 1,
        "Revize Talebi": 2,
        "Cevaplandı": 3,
        "Kapalı": 4
    }

    # 🔄 Filtreleme
    if status_filter and status_filter != "all":
        requests_data = [r for r in requests_data if r.get("status") == status_filter]

    # 🔄 Sıralama Fonksiyonu
    def parse_date_safe(ts):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                continue
        return datetime.min

    # 🔄 Sıralama Uygulama
    if sort == "newest":
        requests_data = sorted(
            requests_data,
            key=lambda r: parse_date_safe(r.get("timestamp", "")),
            reverse=True
        )
    else:
        requests_data = sorted(
            requests_data,
            key=lambda r: (
                status_order.get(r.get("status"), 99),
                r.get("timestamp", "")
            ),
            reverse=False
        )

    # 📅 Cevaplanma Süresi Hesaplama
    def _parse(ts):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                pass
        return None

    for r in requests_data:
        r["response_minutes"] = None
        ts = r.get("timestamp")
        ot = r.get("offer_created_at")
        if ts and ot:
            t1 = _parse(ts)
            t2 = _parse(ot)
            if t1 and t2:
                diff_min = int(max(0, (t2 - t1).total_seconds() // 60))
                r["response_minutes"] = diff_min

    # 🔚 Render Dashboard
    return render_template("admin/dashboard.html", requests=requests_data, user=user, users=users)

@app.route("/admin/assign/<int:req_id>", methods=["POST"])
@admin_required
def admin_assign(req_id):
    data = request.get_json()
    selected_admin = data.get("admin")

    try:
        # JSON'u güvenli oku → güncelle → atomik yaz
        with open("data/requests.json", "r", encoding="utf-8") as f:
            current = json.load(f)

        for req in current:
            if req["id"] == req_id:
                req["assigned_admin"] = selected_admin
                break

        tmp = "data/requests.tmp.json"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        os.replace(tmp, "data/requests.json")

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/request/<int:req_id>", methods=["GET", "POST"])
@admin_required
def admin_request_detail(req_id):
    if request.method == "POST":
        for r in requests_data:
            if r["id"] == req_id:
                r["payment_term"] = request.form.get("payment_term", r.get("payment_term", "Peşin"))
                r["offer_option"] = request.form.get("offer_option", r.get("offer_option", "7 Gün"))

                # Ürün teslim süreleri
                delivery_times = request.form.getlist("delivery_time[]")
                for i, p in enumerate(r.get("products", [])):
                    if i < len(delivery_times):
                        p["delivery_time"] = delivery_times[i]

                # Statü güncelleme (TEK yerde)
                if r.get("status") in [None, "", "Yeni", "new"]:
                    r["status"] = "Teklif Hazır"
                elif r.get("status") != "Kapalı":
                    r["status"] = "Cevaplandı"
                break

        try:
            with open("data/requests.json", "w", encoding="utf-8") as f:
                json.dump(requests_data, f, ensure_ascii=False, indent=2)
            flash("Teklif kaydedildi ve durum güncellendi.")
        except Exception as e:
            flash("Kaydetme hatası!", "error")

        # 🔹 Bu satır fonksiyonun içinde, POST bloğunun sonunda olmalı:
        return redirect(url_for("admin_request_detail", req_id=req_id))

    # GET isteği burada:
    for r in requests_data:
        if r["id"] == req_id:
            return render_template("admin/request_detail.html", req=r)


@app.route("/offer_chat/<int:req_id>", methods=["GET", "POST"])
@login_required
def offer_chat(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("dashboard"))

    # 🔹 Mesaj gönderme
    if request.method == "POST":
        text = request.form.get("message", "").strip()
        file = request.files.get("file")
        file_path = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_path = f"/static/uploads/{filename}"

        if text or file_path:
            req.setdefault("offer_messages", [])
            req["offer_messages"].append({
                "sender": "müşteri",
                "sender_name": user["name"],
                "text": text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path
            })
            save_requests()

        # JavaScript sayfayı yenilemeden POST yapıyor, o yüzden boş dönüyoruz
        return ("", 204)

    # 🔹 GET isteği → mesajları yenilemek için JSON veya HTML döner
    # AJAX yenileme için minimal HTML dönüyoruz
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # sadece mesaj alanını döndürelim
        return render_template("client/_chat_messages.html", messages=req["offer_messages"])

    # Normal sayfa yükleme
    return render_template("client/offer_chat.html", req=req, user=user)

# 💬 Admin tarafı teklif mesajlaşması
@app.route("/admin/offer_chat/<int:req_id>", methods=["GET", "POST"])
@admin_required
def admin_offer_chat(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        text = request.form.get("message", "").strip()
        file = request.files.get("file")
        file_path = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_path = f"/static/uploads/{filename}"

        if text or file_path:
            if "offer_messages" not in req:
                req["offer_messages"] = []
            req["offer_messages"].append({
                "sender": "yönetici",
                "sender_name": user["name"],
                "text": text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path
            })
            save_requests()

        return redirect(url_for("admin_offer_chat", req_id=req_id))

    return render_template("admin/offer_chat.html", req=req, user=user)

# 🔒 Talep kapatma
@app.route("/admin/close/<int:req_id>")
@admin_required
def admin_close(req_id):
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if req:
        req["status"] = "Kapalı"
        save_requests()
        flash("Talep kapatıldı.")
    return redirect(url_for("admin_dashboard"))

# 👤 Hesap sayfaları
@app.route("/account")
@login_required
def account():
    user = get_current_user()
    if user["role"] != "client":
        return redirect(url_for("admin_account"))
    return render_template("client/account.html", user=user)

@app.route("/admin/account")
@admin_required
def admin_account():
    user = get_current_user()
    return render_template("admin/account.html", user=user)

# 🔑 Admin giriş
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = next((u for u in users if u["email"] == email and u["password"] == password and u["role"] == "admin"), None)
        if not user:
            flash("Admin e-posta veya şifre hatalı.")
            return redirect(url_for("admin_login"))
        session.clear()
        session["admin_email"] = user["email"]
        flash(f"{user['name']} olarak giriş yapıldı.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")

# 💾 Teklif kaydetme (admin) — Geliştirilmiş sürüm
@app.route("/admin/save_offer/<int:req_id>", methods=["POST"])
@admin_required
def admin_save_offer(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    # 1️⃣ Form verileri
    raw_prices = request.form.getlist("price[]")
    offer_text = request.form.get("offer_text", "").strip()

    # 🧾 Ürün verilerini de al (admin yeni eklediyse)
    descs = request.form.getlist("desc[]")
    codes = request.form.getlist("code[]")
    brands = request.form.getlist("brand[]")
    qtys = request.form.getlist("qty[]")
    delivery_times = request.form.getlist("delivery_time[]")  # ✅ yeni alan

    # 2️⃣ Dosya (isteğe bağlı)
    file = request.files.get("file")
    file_path = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        file_path = f"/static/uploads/{filename}"

    # 3️⃣ Ürün listesini yeniden oluştur (admin eklediklerini dahil et)
    products = []
    for i, (d, c, b, q) in enumerate(zip(descs, codes, brands, qtys)):
        if d or c or b or q:  # boş satırları alma
            delivery = delivery_times[i] if i < len(delivery_times) else ""  # ✅ her ürünün teslim süresi
            products.append({
                "desc": d.strip(),
                "code": c.strip(),
                "brand": b.strip(),
                "qty": q.strip(),
                "delivery_time": delivery.strip()  # ✅ JSON’a kaydet
            })

    req["products"] = products if products else []

    # 4️⃣ Fiyat parse
    prices = []
    for p in raw_prices:
        try:
            prices.append(float(str(p).replace(",", ".")))
        except (ValueError, TypeError):
            prices.append(0.0)

    # 🔹 Genel bilgiler
    req["payment_term"] = request.form.get("payment_term", req.get("payment_term", "Peşin"))
    req["offer_option"] = request.form.get("offer_option", req.get("offer_option", "7 Gün"))

    # 5️⃣ Hesaplamalar
    kdv_orani = 0.20
    req_prices, kdv_dahil, ara_toplamlar = [], [], []
    toplam = 0.0

    for i, prod in enumerate(req["products"]):
        fiyat = prices[i] if i < len(prices) else 0.0
        try:
            adet = float(str(prod.get("qty", "0")).replace(",", ".")) or 0.0
        except (ValueError, TypeError):
            adet = 0.0

        fiyat_kdv = round(fiyat * (1 + kdv_orani), 2)
        satir_toplam = round(fiyat_kdv * adet, 2)

        req_prices.append(fiyat)
        kdv_dahil.append(fiyat_kdv)
        ara_toplamlar.append(satir_toplam)
        toplam += satir_toplam

    if all(f == 0 for f in req_prices):
        flash("En az bir ürün fiyatı girilmelidir.")
        return redirect(url_for("admin_request_detail", req_id=req_id))

    # 6️⃣ Kaydet
    req["prices"] = req_prices
    req["kdv_dahil"] = kdv_dahil
    req["ara_toplamlar"] = ara_toplamlar
    req["toplam"] = round(toplam, 2)
    req["offer_note"] = offer_text

    # 🔄 Durum güncelleme
    if req.get("status") in [None, "", "Yeni", "new"]:
        req["status"] = "Teklif Hazır"
    if not req.get("offer_created_at"):
        req["offer_created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif req.get("status") != "Kapalı":
        req["status"] = "Cevaplandı"

    # 💬 Mesaj geçmişine bilgi düş
    req.setdefault("offer_messages", [])
    status_text = "Yeni teklif hazırlandı." if req["status"] == "Teklif Hazır" else "Teklif revize edildi."
    req["offer_messages"].append({
        "sender": "yönetici",
        "sender_name": user["name"],
        "text": f"{status_text} Toplam: {req['toplam']:.2f} ₺\n{offer_text}",
        "file": file_path,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    save_requests()
    flash("Teklif başarıyla kaydedildi.")
    return redirect(url_for("admin_request_detail", req_id=req_id))

@app.route("/admin/offer_pdf_only/<int:req_id>")
@admin_required
def admin_offer_pdf_only(req_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from datetime import datetime
    import os

    # --------- DATA ----------
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    KDV_ORANI = 0.20
    payment_term = req.get("payment_term", "Peşin")
    delivery_time_global = req.get("delivery_time", "Stok durumuna göre/depo çıkış")
    offer_option = req.get("offer_option", "7 Gün")

    COMPANY = {
        "name": "ŞALT ELEKTRİK",
        "tag": "Elektrik Malzemeleri ve Çözüm Ortağınız",
        "addr": "Adana OSB Çanakkale Cad, No: 3, Adana",
        "phone": "(554) 547 72 20",
        "email": "info@saltelektrik.com",
        "web": "www.saltelektrik.com",
        "logo": os.path.join("static", "uploads", "HD LOGO 4K.png"),
    }

    # --------- FONTS / DOC ----------
    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))
    os.makedirs(os.path.join("static", "uploads"), exist_ok=True)
    pdf_path = os.path.join("static", "uploads", f"teklif_{req_id}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2.0*cm, bottomMargin=2.0*cm,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVuSans"
    styles["Title"].fontName = "DejaVuSans-Bold"

    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=16, alignment=1, spaceAfter=8)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_left = ParagraphStyle("cell_left", parent=cell, alignment=0)
    cell_bold = ParagraphStyle("cell_bold", parent=styles["Normal"], fontSize=9, leading=12, fontName="DejaVuSans-Bold")
    amt_right = ParagraphStyle("amt_right", parent=styles["Normal"], fontSize=9, alignment=2)

    def fmt_money(v):
        try:
            return f"{float(v):.2f} ₺"
        except Exception:
            return "-"

    def draw_header_footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(1.5*cm, A4[1]-1.4*cm, A4[0]-1.5*cm, A4[1]-1.4*cm)
        canvas.line(1.5*cm, 1.9*cm, A4[0]-1.5*cm, 1.9*cm)
        canvas.setFont("DejaVuSans", 8)
        canvas.setFillColor(colors.grey)
        footer = f"{COMPANY['addr']}  •  {COMPANY['phone']}  •  {COMPANY['email']}  •  {COMPANY['web']}"
        canvas.drawRightString(A4[0]-1.5*cm, 1.55*cm, footer)
        canvas.drawString(1.5*cm, 1.55*cm, f"Sayfa {doc_.page}")
        canvas.restoreState()

    elements = []

    # --------- HEADER ----------
    if os.path.exists(COMPANY["logo"]):
        left = Image(COMPANY["logo"], width=3.0*cm, height=3.0*cm)
    else:
        left = Paragraph(COMPANY["name"], styles["Title"])
    right = Paragraph(f"<b>{COMPANY['name']}</b><br/><font size=9>{COMPANY['tag']}</font>", styles["Normal"])
    header = Table([[left, right]], colWidths=[3.2*cm, 12.8*cm])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    elements += [header, Spacer(1, 0.25*cm), Paragraph("TEKLİF FORMU", h1)]

    # --------- META ----------
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    left_info = [
        [Paragraph("<b>Müşteri:</b>", cell_bold), Paragraph(req.get("name", "-"), cell_left)],
        [Paragraph("<b>E-posta:</b>", cell_bold), Paragraph(req.get("email", "-"), cell_left)],
        [Paragraph("<b>Talep Tarihi:</b>", cell_bold), Paragraph(req.get("timestamp", "-"), cell_left)],
    ]
    right_info = [
        [Paragraph("<b>Teklif No:</b>", cell_bold), Paragraph(f"#{req_id}", cell_left)],
        [Paragraph("<b>Tarih:</b>", cell_bold), Paragraph(now_str, cell_left)],
    ]
    meta = Table([[Table(left_info, colWidths=[3.2*cm, 7.2*cm]),
                   Table(right_info, colWidths=[3.2*cm, 7.2*cm])]],
                 colWidths=[10.4*cm, 10.4*cm])
    meta.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#e5e5e5")),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#e5e5e5")),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
    ]))
    elements += [meta, Spacer(1, 0.35*cm)]

    # --------- PRODUCTS ----------
    headers = ["Sıra", "Ürün Açıklaması", "Kod", "Marka", "Adet", "Teslim Süresi", "Birim Fiyat", "KDV Dahil", "Tutar"]
    data = [headers]

    products = req.get("products", [])
    prices = req.get("prices", [])
    kdv_list = req.get("kdv_dahil", [])
    ara_toplam = req.get("ara_toplamlar", [])

    subtotal = 0.0

    for i, prod in enumerate(products):
        qty = float(str(prod.get("qty", "0")).replace(",", ".") or 0)
        unit = float(prices[i]) if i < len(prices) else 0.0
        total_excl = qty * unit
        subtotal += total_excl

        data.append([
            str(i + 1),
            Paragraph(prod.get("desc", ""), ParagraphStyle("desc", alignment=0, fontName="DejaVuSans", fontSize=9)),
            Paragraph(prod.get("code", ""), ParagraphStyle("code", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(prod.get("brand", ""), ParagraphStyle("brand", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(str(prod.get("qty", "")), ParagraphStyle("qty", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(prod.get("delivery_time", delivery_time_global), ParagraphStyle("delivery", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(fmt_money(unit), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(fmt_money(unit * (1 + KDV_ORANI)), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
            Paragraph(fmt_money(total_excl * (1 + KDV_ORANI)), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
        ])

    table = Table(
        data,
        colWidths=[0.9*cm, 4.5*cm, 2.0*cm, 2.2*cm, 1.4*cm, 2.8*cm, 2.4*cm, 2.2*cm, 2.4*cm],
        hAlign="CENTER"
    )
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]))
    elements += [table, Spacer(1, 0.4 * cm)]

    # --------- TOTALS ----------
    kdv_tutar = subtotal * KDV_ORANI
    genel_toplam = subtotal + kdv_tutar

    totals = Table([
        [Paragraph("Ara Toplam (KDV Hariç):", cell_bold), Paragraph(fmt_money(subtotal), amt_right)],
        [Paragraph(f"KDV (%{int(KDV_ORANI*100)}):", cell_bold), Paragraph(fmt_money(kdv_tutar), amt_right)],
        [Paragraph("Genel Toplam:", cell_bold), Paragraph(fmt_money(genel_toplam), amt_right)],
    ], colWidths=[8.0*cm, 4.0*cm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "RIGHT"),
        ("LINEABOVE", (0,2), (-1,2), 0.8, colors.black),
        ("FONTNAME", (0,2), (-1,2), "DejaVuSans-Bold"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    elements += [totals, Spacer(1, 0.45*cm)]

    # --------- TERMS ----------
    terms = (
        "<b>Açıklamalar / Şartlar:</b><br/>"
        f"• Ödeme: {payment_term}<br/>"
        f"• Teklif Geçerlilik Süresi: {offer_option}<br/>"
        f"• Teslim: {delivery_time_global}<br/>"
        "• Fiyatlara kargo/kurulum dahil değildir.<br/>"
    )
    elements += [Paragraph(terms, styles["Normal"]), Spacer(1, 0.5*cm)]

    # --------- SIGN ----------
    sign = Table(
        [[Paragraph("<b>Hazırlayan</b><br/><br/>İsim/İmza", styles["Normal"]),
          Paragraph("<b>Onaylayan</b><br/><br/>İsim/İmza", styles["Normal"])]],
        colWidths=[9.8*cm, 9.8*cm],
    )
    sign.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(sign)

    # İlk teklif zamanı (sadece bir kez yaz)
    if not req.get("offer_created_at"):
        req["offer_created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # dosyaya yaz
    with open("data/requests.json", "w", encoding="utf-8") as f:
        json.dump(requests_data, f, ensure_ascii=False, indent=2)

    # --------- BUILD PDF ----------
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    flash("PDF başarıyla oluşturuldu.")
    return redirect(url_for("static", filename=f"uploads/teklif_{req_id}.pdf"))

@app.route("/admin/offer_pdf/<int:req_id>")
@admin_required
def admin_offer_pdf(req_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from datetime import datetime
    from email.message import EmailMessage
    import smtplib, os

    # --------- DATA ----------
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    KDV_ORANI = 0.20
    payment_term = req.get("payment_term", "Peşin")
    delivery_time_global = req.get("delivery_time", "Stok durumuna göre/depo çıkış")
    offer_option = req.get("offer_option", "7 Gün")

    COMPANY = {
        "name": "ŞALT ELEKTRİK",
        "tag": "Elektrik Malzemeleri ve Çözüm Ortağınız",
        "addr": "Adana OSB Çanakkale Cad, No: 3, Adana",
        "phone": "(554) 547 72 20",
        "email": "info@saltelektrik.com",
        "web": "www.saltelektrik.com",
        "logo": os.path.join("static", "uploads", "HD LOGO 4K.png"),
    }

    # --------- FONTS / DOC ----------
    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))
    os.makedirs(os.path.join("static", "uploads"), exist_ok=True)
    pdf_path = os.path.join("static", "uploads", f"teklif_{req_id}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2.0*cm, bottomMargin=2.0*cm,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVuSans"
    styles["Title"].fontName = "DejaVuSans-Bold"

    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=16, alignment=1, spaceAfter=8)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_left = ParagraphStyle("cell_left", parent=cell, alignment=0)
    cell_bold = ParagraphStyle("cell_bold", parent=styles["Normal"], fontSize=9, leading=12, fontName="DejaVuSans-Bold")
    amt_right = ParagraphStyle("amt_right", parent=styles["Normal"], fontSize=9, alignment=2)

    def fmt_money(v):
        try:
            return f"{float(v):.2f} ₺"
        except Exception:
            return "-"

    def draw_header_footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(1.5*cm, A4[1]-1.4*cm, A4[0]-1.5*cm, A4[1]-1.4*cm)
        canvas.line(1.5*cm, 1.9*cm, A4[0]-1.5*cm, 1.9*cm)
        canvas.setFont("DejaVuSans", 8)
        canvas.setFillColor(colors.grey)
        footer = f"{COMPANY['addr']}  •  {COMPANY['phone']}  •  {COMPANY['email']}  •  {COMPANY['web']}"
        canvas.drawRightString(A4[0]-1.5*cm, 1.55*cm, footer)
        canvas.drawString(1.5*cm, 1.55*cm, f"Sayfa {doc_.page}")
        canvas.restoreState()

    elements = []

    # --------- HEADER ----------
    if os.path.exists(COMPANY["logo"]):
        left = Image(COMPANY["logo"], width=3.0*cm, height=3.0*cm)
    else:
        left = Paragraph(COMPANY["name"], styles["Title"])
    right = Paragraph(f"<b>{COMPANY['name']}</b><br/><font size=9>{COMPANY['tag']}</font>", styles["Normal"])
    header = Table([[left, right]], colWidths=[3.2*cm, 12.8*cm])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    elements += [header, Spacer(1, 0.25*cm), Paragraph("TEKLİF FORMU", h1)]

    # --------- META ----------
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    left_info = [
        [Paragraph("<b>Müşteri:</b>", cell_bold), Paragraph(req.get("name", "-"), cell_left)],
        [Paragraph("<b>E-posta:</b>", cell_bold), Paragraph(req.get("email", "-"), cell_left)],
        [Paragraph("<b>Talep Tarihi:</b>", cell_bold), Paragraph(req.get("timestamp", "-"), cell_left)],
    ]
    right_info = [
        [Paragraph("<b>Teklif No:</b>", cell_bold), Paragraph(f"#{req_id}", cell_left)],
        [Paragraph("<b>Tarih:</b>", cell_bold), Paragraph(now_str, cell_left)],
    ]
    meta = Table([[Table(left_info, colWidths=[3.2*cm, 7.2*cm]),
                   Table(right_info, colWidths=[3.2*cm, 7.2*cm])]],
                 colWidths=[10.4*cm, 10.4*cm])
    meta.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#e5e5e5")),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#e5e5e5")),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
    ]))
    elements += [meta, Spacer(1, 0.35*cm)]

    # --------- PRODUCTS ----------
    headers = ["Sıra", "Ürün Açıklaması", "Kod", "Marka", "Adet", "Teslim Süresi", "Birim Fiyat", "KDV Dahil", "Tutar"]
    data = [headers]

    products = req.get("products", [])
    prices = req.get("prices", [])
    kdv_list = req.get("kdv_dahil", [])
    ara_toplam = req.get("ara_toplamlar", [])

    subtotal = 0.0

    for i, prod in enumerate(products):
        qty = float(str(prod.get("qty", "0")).replace(",", ".") or 0)
    unit = float(prices[i]) if i < len(prices) else 0.0
    total_excl = qty * unit
    subtotal += total_excl

    data.append([
        str(i + 1),
        Paragraph(prod.get("desc", ""), ParagraphStyle("desc", alignment=0, fontName="DejaVuSans", fontSize=9)),
        Paragraph(prod.get("code", ""), ParagraphStyle("code", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(prod.get("brand", ""), ParagraphStyle("brand", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(str(prod.get("qty", "")), ParagraphStyle("qty", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(prod.get("delivery_time", delivery_time_global), ParagraphStyle("delivery", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(fmt_money(unit), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(fmt_money(unit * (1 + KDV_ORANI)), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
        Paragraph(fmt_money(total_excl * (1 + KDV_ORANI)), ParagraphStyle("money", alignment=1, fontName="DejaVuSans", fontSize=9)),
    ])

# --- TABLO AYARLARI ---
    table = Table(
    data,
    colWidths=[0.9*cm, 4.5*cm, 2.0*cm, 2.2*cm, 1.4*cm, 2.8*cm, 2.4*cm, 2.2*cm, 2.4*cm],
    hAlign="CENTER"
)
    table.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("ALIGN", (1, 1), (1, -1), "LEFT"),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
    ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ("TOPPADDING", (0, 1), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
]))
    elements += [table, Spacer(1, 0.4 * cm)]


    # --------- TOTALS ----------
    kdv_tutar = subtotal * KDV_ORANI
    genel_toplam = subtotal + kdv_tutar

    totals = Table([
        [Paragraph("Ara Toplam (KDV Hariç):", cell_bold), Paragraph(fmt_money(subtotal), amt_right)],
        [Paragraph(f"KDV (%{int(KDV_ORANI*100)}):", cell_bold), Paragraph(fmt_money(kdv_tutar), amt_right)],
        [Paragraph("Genel Toplam:", cell_bold), Paragraph(fmt_money(genel_toplam), amt_right)],
    ], colWidths=[8.0*cm, 4.0*cm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "RIGHT"),
        ("LINEABOVE", (0,2), (-1,2), 0.8, colors.black),  # sadece son satır üstü çizgi
        ("FONTNAME", (0,2), (-1,2), "DejaVuSans-Bold"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    elements += [totals, Spacer(1, 0.45*cm)]

    # --------- TERMS ----------
    terms = (
        "<b>Açıklamalar / Şartlar:</b><br/>"
        f"• Ödeme: {payment_term}<br/>"
        f"• Teklif Geçerlilik Süresi: {offer_option}<br/>"
        f"• Teslim: {delivery_time_global}<br/>"
        "• Fiyatlara kargo/kurulum dahil değildir.<br/>"
    )
    elements += [Paragraph(terms, styles["Normal"]), Spacer(1, 0.5*cm)]

    # --------- SIGN ----------
    sign = Table(
        [[Paragraph("<b>Hazırlayan</b><br/><br/>İsim/İmza", styles["Normal"]),
          Paragraph("<b>Onaylayan</b><br/><br/>İsim/İmza", styles["Normal"])]],
        colWidths=[9.8*cm, 9.8*cm],
    )
    sign.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(sign)

    # İlk teklif zamanı (sadece bir kez yaz)
    if not req.get("offer_created_at"):
        req["offer_created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # dosyaya yaz
    with open("data/requests.json", "w", encoding="utf-8") as f:
        json.dump(requests_data, f, ensure_ascii=False, indent=2)

    # --------- BUILD PDF ----------
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    # --------- SEND MAIL ----------
    smtp_host = os.getenv("SMTP_HOST", "mail.kurumsaleposta.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SMTP_USER")
    sender_password = os.getenv("SMTP_PASS")
    to_email = req.get("email")

    if not all([smtp_host, smtp_port, sender_email, sender_password]):
        flash("⚠️ SMTP ayarları eksik (.env dosyasını kontrol edin)", "error")
        return redirect(url_for("admin_dashboard"))

    msg = EmailMessage()
    msg["Subject"] = f"Yeni Teklifiniz - {COMPANY['name']}"
    msg["From"] = sender_email
    msg["To"] = to_email
    msg.set_content(
        "Merhaba,\n\nYeni teklifiniz ekte yer almaktadır.\nİyi çalışmalar dileriz.\n\nŞalt Elektrik"
    )

    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
            print(f"✅ Mail gönderildi: {to_email}")
    except Exception as e:
        print("❌ Mail gönderim hatası:", e)

    flash("Teklif PDF oluşturuldu ve mail gönderildi.")
    return redirect(url_for("static", filename=f"uploads/teklif_{req_id}.pdf"))


# 📬 Mail listener başlatıcı fonksiyon
import threading
from mail_listener import start_listener

def run_mail_listener():
    try:
        threading.Thread(target=start_listener, daemon=True).start()
        print("📬 Mail listener başlatıldı.")
    except Exception as e:
        print("❌ Mail listener başlatılamadı:", e)

# Arka planda mail listener’ı başlat
run_mail_listener()
@app.route("/search_stock", methods=["POST"])
def search_stock():
    data = request.get_json()
    query = data.get("query", "").strip().lower()

    if not query:
        return jsonify({"error": "Ürün adı gerekli"}), 400

    stock_file = "data/stock.json"
    if not os.path.exists(stock_file):
        return jsonify({"error": "Stok dosyası bulunamadı"}), 500

    with open(stock_file, "r", encoding="utf-8") as f:
        stock_data = json.load(f)

    # Eğer stock.json bir listeyse:
    matches = [item for item in stock_data if query in item["name"].lower()]

    return jsonify({"results": matches})

# Flask uygulamasını başlat
if __name__ == "__main__":
    app.run(debug=True)

