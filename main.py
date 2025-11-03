from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from functools import wraps
import os, json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super-secret-key-12345"

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

    # 🔹 En güncel talepleri JSON dosyasından yeniden yükle
    try:
        with open("data/requests.json", "r", encoding="utf-8") as f:
            requests_data = json.load(f)
                # 🧩 Eski statüleri normalize et
        for r in requests_data:
            if r.get("status") == "Revize Edildi":
                r["status"] = "Cevaplandı"
            elif r.get("status") == "new":
                r["status"] = "Yeni"


        # Eski veri formatlarını yeni anahtarlara dönüştür (mail + portal uyumu)
        for r in requests_data:
            if "messages" in r and "request_messages" not in r:
                r["request_messages"] = r["messages"]

        print(f"🗂️ Dashboard için {len(requests_data)} kayıt yüklendi.")

    except Exception as e:
        print("⚠️ Dashboard veri yükleme hatası:", e)
        requests_data = []

    user = get_current_user()

    # 🟢 Statü sıralama mantığı (status sayfasıyla uyumlu)
    # Önce "Yeni", sonra "Teklif Hazır", sonra "Cevaplandı", en altta "Kapalı"
    status_order = {
        "Yeni": 0,
        "new": 0,
        "Teklif Hazır": 1,
        "Revize Talebi": 2,
        "Cevaplandı": 3,
        "Kapalı": 4
    }

    # 🔄 Talepleri önce duruma, sonra tarihe göre sırala (yeni olanlar üstte)
    requests_data = sorted(
        requests_data,
        key=lambda r: (
            status_order.get(r.get("status"), 99),
            r.get("timestamp", "")
        ),
        reverse=False  # “Yeni” olanlar en üstte
    )

    # 📊 En güncel tarihli kayıtları da üstte göstermek istiyorsan:
    # requests_data = sorted(requests_data, key=lambda r: r.get("timestamp", ""), reverse=True)

    return render_template("admin/dashboard.html", requests=requests_data, user=user, users=users)

from flask import jsonify, request

@app.route("/admin/assign/<int:req_id>", methods=["POST"])
def admin_assign(req_id):
    data = request.get_json()
    selected_admin = data.get("admin")

    try:
        with open("data/requests.json", "r+", encoding="utf-8") as f:
            requests_data = json.load(f)
            for req in requests_data:
                if req["id"] == req_id:
                    req["assigned_admin"] = selected_admin
                    break
            f.seek(0)
            json.dump(requests_data, f, ensure_ascii=False, indent=4)
            f.truncate()

        print(f"👤 Talep {req_id} için yönetici atandı: {selected_admin}")
        return jsonify({"success": True}), 200

    except Exception as e:
        print("⚠️ Yönetici atama hatası:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/request/<int:req_id>", methods=["GET", "POST"])
@admin_required
def admin_request_detail(req_id):
    global requests_data
    import json

    # Veriyi oku
    try:
        with open("data/requests.json", "r", encoding="utf-8") as f:
            requests_data = json.load(f)
    except Exception as e:
        print("⚠️ Veri yükleme hatası:", e)
        requests_data = []

    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    # 🔹 Teklif Kaydetme
    if request.method == "POST":
        for r in requests_data:
            if r["id"] == req_id:
             r["payment_term"] = request.form.get("payment_term", r.get("payment_term", "Peşin"))
             r["offer_option"] = request.form.get("offer_option", r.get("offer_option", "7 Gün"))

            # 🟢 Her ürün için teslim süresi kaydı
            delivery_times = request.form.getlist("delivery_time[]")
            for i, p in enumerate(r.get("products", [])):
                if i < len(delivery_times):
                    p["delivery_time"] = delivery_times[i]

            # 🧩 Statü Güncelleme
            if r.get("status") in [None, "", "Yeni", "new"]:
                r["status"] = "Teklif Hazır"
            elif r.get("status") not in ["Kapalı"]:
                r["status"] = "Cevaplandı"
            break

                # 🟢 Statü Güncelleme Mantığı
            if r.get("status") in [None, "", "Yeni", "new"]:
                    r["status"] = "Teklif Hazır"
            elif r.get("status") not in ["Kapalı"]:
                    r["status"] = "Cevaplandı"
                    break

        # JSON Kaydet
        try:
            with open("data/requests.json", "w", encoding="utf-8") as f:
                json.dump(requests_data, f, ensure_ascii=False, indent=2)
            print("💾 Teklif kaydedildi, durum:", r["status"])
            flash("Teklif kaydedildi ve durum güncellendi.")
        except Exception as e:
            print("❌ JSON kaydetme hatası:", e)
            flash("Kaydetme hatası!", "error")

        return redirect(url_for("admin_request_detail", req_id=req_id))

    return render_template("admin/request_detail.html", req=req, user=user)

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

    # İlgili kayıt bulunmazsa yönlendirme
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    # Seçili alanlar (varsayılanlarla birlikte)
    KDV_ORANI = 0.20
    payment_term = req.get("payment_term", "Peşin")
    delivery_time = req.get("delivery_time", "Stok durumuna göre/depo çıkış")
    offer_option = req.get("offer_option", "Tek opsiyon")

    COMPANY_INFO = {
        "name": "ŞALT ELEKTRİK",
        "tagline": "Elektrik Malzemeleri ve Çözüm Ortağınız",
        "addr": "Adres: İkitelli OSB, No: 10/3, İstanbul",
        "phone": "Telefon: (000) 000 00 00",
        "email": "info@saltelektrik.com",
        "website": "www.saltelektrik.com",
        "logo": os.path.join("static", "uploads", "HD LOGO 4K.png"),
    }

    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))

    pdf_path = os.path.join("static", "uploads", f"teklif_{req_id}.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.0 * cm,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVuSans"
    styles["Title"].fontName = "DejaVuSans-Bold"

    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=16, spaceAfter=6)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_bold = ParagraphStyle("cell_bold", parent=styles["Normal"], fontSize=9, leading=12, fontName="DejaVuSans-Bold")

    def fmt_money(val):
        try:
            return f"{float(val):.2f} ₺"
        except Exception:
            return "-"

    def draw_header_footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(1.6 * cm, A4[1] - 1.5 * cm, A4[0] - 1.6 * cm, A4[1] - 1.5 * cm)
        canvas.line(1.6 * cm, 1.8 * cm, A4[0] - 1.6 * cm, 1.8 * cm)
        footer_text = f"{COMPANY_INFO['addr']}  •  {COMPANY_INFO['phone']}  •  {COMPANY_INFO['email']}  •  {COMPANY_INFO['website']}"
        canvas.setFont("DejaVuSans", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 1.6 * cm, 1.45 * cm, footer_text)
        page_str = f"Sayfa {doc_.page}"
        canvas.drawString(1.6 * cm, 1.45 * cm, page_str)
        canvas.restoreState()

    elements = []

    # Başlık
    if os.path.exists(COMPANY_INFO["logo"]):
        logo = Image(COMPANY_INFO["logo"], width=3 * cm, height=3 * cm)
    else:
        logo = Paragraph(COMPANY_INFO["name"], h1)
    header_tbl = Table(
        [[logo, Paragraph(f"<b>{COMPANY_INFO['name']}</b><br/>{COMPANY_INFO['tagline']}", styles["Normal"])]],
        colWidths=[3.2 * cm, 12.8 * cm],
        hAlign="LEFT",
    )
    header_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements += [header_tbl, Spacer(1, 0.2 * cm), Paragraph("<b>TEKLİF FORMU</b>", h1)]

    # Müşteri Bilgileri
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    customer = [
        [Paragraph("<b>Müşteri:</b>", cell_bold), Paragraph(req.get("name", "-"), cell)],
        [Paragraph("<b>E-posta:</b>", cell_bold), Paragraph(req.get("email", "-"), cell)],
        [Paragraph("<b>Talep Tarihi:</b>", cell_bold), Paragraph(req.get("timestamp", "-"), cell)],
    ]
    offer_meta = [
        [Paragraph("<b>Teklif No:</b>", cell_bold), Paragraph(f"#{req_id}", cell)],
        [Paragraph("<b>Tarih:</b>", cell_bold), Paragraph(now_str, cell)],
    ]
    top_tbl = Table(
        [[Table(customer, colWidths=[3 * cm, 7 * cm]), Table(offer_meta, colWidths=[3 * cm, 7 * cm])]],
        colWidths=[10 * cm, 10 * cm],
    )
    top_tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    elements += [top_tbl, Spacer(1, 0.4 * cm)]

    # Ürün Tablosu
    data = [["Sıra", "Ürün Açıklaması", "Kod", "Marka", "Adet", "Birim Fiyat", "KDV Dahil", "Tutar"]]
    for i, prod in enumerate(req.get("products", [])):
        prices = req.get("prices", [])
        kdv_list = req.get("kdv_dahil", [])
        ara_toplam = req.get("ara_toplamlar", [])
        data.append([
            str(i + 1),
            Paragraph(prod.get("desc", ""), cell),
            Paragraph(prod.get("code", ""), cell),
            Paragraph(prod.get("brand", ""), cell),
            str(prod.get("qty", "")),
            fmt_money(prices[i]) if i < len(prices) else "-",
            fmt_money(kdv_list[i]) if i < len(kdv_list) else "-",
            fmt_money(ara_toplam[i]) if i < len(ara_toplam) else "-",
        ])

    tbl = Table(data, colWidths=[1 * cm, 6 * cm, 2 * cm, 2.6 * cm, 1.6 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    elements += [tbl, Spacer(1, 0.5 * cm)]

    # Notlar
    offer_note = (req.get("offer_note") or "").strip()
    if offer_note:
        elements += [Paragraph("<b>Teklif Notu</b>", styles["Title"]), Paragraph(offer_note.replace("\n", "<br/>"), styles["Normal"])]

    terms = (
    f"<b>Açıklamalar / Şartlar:</b><br/>"
    f"• Ödeme: {payment_term}<br/>"
    f"• Teklif Geçerlilik Süresi: {offer_option}<br/>"
    f"• Teslim: {delivery_time}<br/>"
    f"• Fiyatlara kargo/kurulum dahil değildir.<br/>"
)

    elements += [Spacer(1, 0.3 * cm), Paragraph(terms, styles["Normal"]), Spacer(1, 0.5 * cm)]

    # İmza
    sign_tbl = Table(
        [[Paragraph("<b>Hazırlayan</b><br/><br/>İsim/İmza", styles["Normal"]), Paragraph("<b>Onaylayan</b><br/><br/>İsim/İmza", styles["Normal"])]],
        colWidths=[9.8 * cm, 9.8 * cm],
    )
    sign_tbl.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey)]))
    elements.append(sign_tbl)

    # PDF oluştur
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    flash("PDF başarıyla oluşturuldu.")
    return redirect(url_for("static", filename=f"uploads/teklif_{req_id}.pdf"))

@app.route("/admin/offer_pdf/<int:req_id>")
@admin_required
def admin_offer_pdf(req_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER
    from datetime import datetime
    import ssl, smtplib, os
    from email.message import EmailMessage

    TA_LEFT = 0
    TA_RIGHT = 2

    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    KDV_ORANI   = 0.20
    payment_term = req.get("payment_term", "Peşin")
    delivery_time = req.get("delivery_time", "Stok durumuna göre/depo çıkış")
    offer_option = req.get("offer_option", "Tek opsiyon")

    COMPANY_NAME = "ŞALT ELEKTRİK"
    COMPANY_TAGLINE = "Elektrik Malzemeleri ve Çözüm Ortağınız"
    COMPANY_ADDR = "Adres: İkitelli OSB, No: 10/3, İstanbul"
    COMPANY_PHONE = "Telefon: (000) 000 00 00"
    COMPANY_EMAIL = "info@saltelektrik.com"
    COMPANY_WEBSITE = "www.saltelektrik.com"
    LOGO_PATH = os.path.join("static", "uploads", "HD LOGO 4K.png")

    # --- Fontlar (Türkçe desteği) ---
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))

    # --- Veriyi bul ---
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    # -------------------- PDF Yol/Ayar --------------------
    pdf_path = os.path.join("static", "uploads", f"teklif_{req_id}.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.0 * cm,
    )

    # -------------------- Stil Tanımları --------------------
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = 'DejaVuSans'
    styles["Title"].fontName = 'DejaVuSans-Bold'

    h1 = ParagraphStyle(
        "h1", parent=styles["Title"], fontSize=16, alignment=TA_LEFT, spaceAfter=6
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Title"], fontSize=12, alignment=TA_LEFT, spaceAfter=4
    )
    tiny = ParagraphStyle(
        "tiny", parent=styles["Normal"], fontSize=8, textColor=colors.grey, alignment=TA_RIGHT
    )
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_bold = ParagraphStyle("cell_bold", parent=styles["Normal"], fontSize=9, leading=12)
    cell_bold.fontName = 'DejaVuSans-Bold'

    def fmt_money(val):
        try:
            return f"{float(val):.2f} ₺"
        except Exception:
            return "-"

    # -------------------- Header/Footer (tüm sayfalar) --------------------
    def draw_header_footer(canvas, doc_):
        canvas.saveState()
        # Header çizgisi
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(1.6 * cm, A4[1] - 1.5 * cm, A4[0] - 1.6 * cm, A4[1] - 1.5 * cm)
        # Footer çizgisi
        canvas.line(1.6 * cm, 1.8 * cm, A4[0] - 1.6 * cm, 1.8 * cm)

        # Footer metni
        footer_text = f"{COMPANY_ADDR}  •  {COMPANY_PHONE}  •  {COMPANY_EMAIL}  •  {COMPANY_WEBSITE}"
        canvas.setFont("DejaVuSans", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 1.6 * cm, 1.45 * cm, footer_text)

        # Sayfa no
        page_str = f"Sayfa {doc_.page}"
        canvas.drawString(1.6 * cm, 1.45 * cm, page_str)
        canvas.restoreState()

    elements = []

    # -------------------- Üst Bilgiler (Logo + Başlık) --------------------
    header_row = []
    if os.path.exists(LOGO_PATH):
        header_row.append(Image(LOGO_PATH, width=3.0 * cm, height=3.0 * cm))
    else:
        header_row.append(Paragraph(COMPANY_NAME, h1))

    header_right = Paragraph(
        f"<b>{COMPANY_NAME}</b><br/>{COMPANY_TAGLINE}",
        styles["Normal"],
    )
    header_tbl = Table(
        [[header_row[0], header_right]],
        colWidths=[3.2 * cm, 12.8 * cm],
        hAlign="LEFT",
    )
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph("<b>TEKLİF FORMU</b>", h1))

    # -------------------- Müşteri & Teklif Üst Özeti --------------------
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    customer = [
        [Paragraph("<b>Müşteri:</b>", cell_bold), Paragraph(req.get("name", "-"), cell)],
        [Paragraph("<b>E-posta:</b>", cell_bold), Paragraph(req.get("email", "-"), cell)],
        [Paragraph("<b>Talep Tarihi:</b>", cell_bold), Paragraph(req.get("timestamp", "-"), cell)],
    ]
    offer_meta = [
        [Paragraph("<b>Teklif No:</b>", cell_bold), Paragraph(f"#{req_id}", cell)],
        [Paragraph("<b>Tarih:</b>", cell_bold), Paragraph(now_str, cell)],
    ]
    top_tbl = Table(
        [
            [Table(customer, colWidths=[3.0 * cm, 7.0 * cm]),
             Table(offer_meta, colWidths=[3.0 * cm, 7.0 * cm])]
        ],
        colWidths=[10.0 * cm, 10.0 * cm],
    )
    top_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(top_tbl)
    elements.append(Spacer(1, 0.4 * cm))

    # -------------------- Ürün Tablosu --------------------
    data = [["Sıra", "Ürün Açıklaması", "Kod", "Marka", "Adet", "Birim Fiyat", "KDV Dahil", "Tutar"]]
    products = req.get("products", [])
    prices = req.get("prices", [])
    kdv_list = req.get("kdv_dahil", [])
    ara_toplam = req.get("ara_toplamlar", [])

    for i, prod in enumerate(products):
        desc = Paragraph(prod.get("desc", ""), cell)
        code = Paragraph(prod.get("code", ""), cell)
        brand = Paragraph(prod.get("brand", ""), cell)
        adet = str(prod.get("qty", ""))
        data.append([
            str(i + 1),
            desc,
            code,
            brand,
            adet,
            fmt_money(prices[i]) if i < len(prices) else "-",
            fmt_money(kdv_list[i]) if i < len(kdv_list) else "-",
            fmt_money(ara_toplam[i]) if i < len(ara_toplam) else "-"
        ])

    table = Table(
        data,
        colWidths=[1.0 * cm, 6.0 * cm, 2.0 * cm, 2.6 * cm, 1.6 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm]
    )
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('WORDWRAP', (0, 0), (-1, -1), True),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))

    # -------------------- Hesap Özetleri --------------------
    # Varsa req.toplam'ı kullan; yoksa yeniden hesapla
    try:
        # KDV hariç ara toplamı güvenli hesapla
        subtotal_excl = 0.0
        for i, prod in enumerate(products):
            qty = float(str(prod.get("qty", "0")).replace(",", ".") or 0)
            unit_price = float(prices[i]) if i < len(prices) else 0.0
            subtotal_excl += qty * unit_price
        kdv_total = round(subtotal_excl * KDV_ORANI, 2)
        grand_total = round(subtotal_excl + kdv_total, 2)
    except Exception:
        subtotal_excl = 0.0
        kdv_total = 0.0
        grand_total = float(req.get("toplam", 0.0) or 0.0)

    # Eğer req["toplam"] varsa onu baz alalım
    if isinstance(req.get("toplam"), (int, float)):
        grand_total = float(req["toplam"])

    totals_tbl = Table(
        [
            ["Ara Toplam (KDV Hariç):", fmt_money(subtotal_excl)],
            [f"KDV (%{int(KDV_ORANI*100)}):", fmt_money(kdv_total)],
            ["Genel Toplam:", fmt_money(grand_total)],
        ],
        colWidths=[7.2 * cm, 4.0 * cm],
        hAlign="RIGHT",
    )
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -2), 'DejaVuSans'),
        ("FONTNAME", (0, -1), (-1, -1), 'DejaVuSans-Bold'),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_tbl)
    elements.append(Spacer(1, 0.4 * cm))

        # Teklif notu (varsa)
    offer_note = (req.get("offer_note") or "").strip()
    if offer_note:
        elements.append(Paragraph("<b>Teklif Notu</b>", styles["Title"]))
        elements.append(Paragraph(offer_note.replace("\n", "<br/>"), styles["Normal"]))
        elements.append(Spacer(1, 0.3 * cm))

    # Açıklamalar / Şartlar (BURASI if dışında olmalı!)
    terms = (
    f"<b>Açıklamalar / Şartlar:</b><br/>"
    f"• Ödeme: {payment_term}<br/>"
    f"• Teklif Geçerlilik Süresi: {offer_option}<br/>"
    f"• Teslim: {delivery_time}<br/>"
    f"• Fiyatlara kargo/kurulum dahil değildir.<br/>"
)

    elements.append(Paragraph(terms, styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))


    sign_tbl = Table(
        [
            [Paragraph("<b>Hazırlayan</b><br/><br/>İsim/İmza", styles["Normal"]),
             Paragraph("<b>Onaylayan</b><br/><br/>İsim/İmza", styles["Normal"])]
        ],
        colWidths=[9.8 * cm, 9.8 * cm],
    )
    sign_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(sign_tbl)

    # -------------------- PDF Oluştur --------------------
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    # -------------------- Mail Gönderim (mevcut davranış korunur) --------------------
    sender_email = "teklif@e-saltelektrik.com"
    sender_password = "KampanyaXmail0217"
    to_email = req.get("email")

    msg = EmailMessage()
    msg["Subject"] = "Yeni Teklifiniz Hazır"
    msg["From"] = sender_email
    msg["To"] = to_email
    msg.set_content("Merhaba,\n\nYeni teklifiniz ekte yer almaktadır.\nİyi çalışmalar dileriz.\n\nSalt Elektrik")

    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    try:
        context = ssl._create_unverified_context()
        with smtplib.SMTP("mail.kurumsaleposta.com", 587) as smtp:
            smtp.starttls(context=context)
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
            print(f"✅ Mail gönderildi: {to_email}")
    except Exception as e:
        print("❌ Mail gönderim hatası:", e)

    flash("Teklif PDF oluşturuldu ve mail gönderildi.")
    return redirect(url_for('static', filename=f"uploads/teklif_{req_id}.pdf"))


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

# Flask uygulamasını başlat
if __name__ == "__main__":
    app.run(debug=True)

