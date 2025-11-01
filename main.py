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
    {"email": "admin1@saltelektrik.com", "password": "admin123", "name": "Yönetici 1", "role": "admin"},
    {"email": "admin2@saltelektrik.com", "password": "admin123", "name": "Yönetici 2", "role": "admin"},
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
    global requests_data
    import json

    # 🔹 En güncel talepleri JSON dosyasından yeniden yükle
    # ◇ En güncel talepleri JSON dosyasından yeniden yükle
    try:
        with open("data/requests.json", "r", encoding="utf-8") as f:
            requests_data = json.load(f)

        # Eski veri formatlarını yeni anahtarlara dönüştür (mail + portal uyumu)
        for r in requests_data:
            if "messages" in r and "request_messages" not in r:
                r["request_messages"] = r["messages"]

        print(f"🗂️ Dashboard için {len(requests_data)} kayıt yüklendi.")

    except Exception as e:
        print("⚠️ Dashboard veri yükleme hatası:", e)
        requests_data = []


    user = get_current_user()
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

@app.route("/admin/request/<int:req_id>")
@admin_required
def admin_request_detail(req_id):
    global requests_data
    import json

    # 🔹 Güncel veriyi yeniden oku (sayfa tazelenirken değişiklikleri görmek için)
    try:
        with open("data/requests.json", "r", encoding="utf-8") as f:
            requests_data = json.load(f)
    except Exception as e:
        print("⚠️ Detay sayfası veri yükleme hatası:", e)
        requests_data = []

    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)

    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/request_detail.html", req=req, user=user)

# ===================== 💬 Teklif Mesajlaşma (Yeni) =====================

# 💬 Müşteri tarafı teklif mesajlaşması
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

    # 2️⃣ Dosya (isteğe bağlı)
    file = request.files.get("file")
    file_path = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        file_path = f"/static/uploads/{filename}"

    # 3️⃣ Ürün listesini yeniden oluştur (admin eklediklerini dahil et)
    products = []
    for d, c, b, q in zip(descs, codes, brands, qtys):
        if d or c or b or q:  # boş satırları alma
            products.append({
                "desc": d.strip(),
                "code": c.strip(),
                "brand": b.strip(),
                "qty": q.strip()
            })

    # Eğer admin ürünleri tamamen boşalttıysa, yine boş liste tut
    req["products"] = products if products else []

    # 4️⃣ Fiyat parse
    prices = []
    for p in raw_prices:
        try:
            prices.append(float(str(p).replace(",", ".")))
        except (ValueError, TypeError):
            prices.append(0.0)

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

    # 6️⃣ En az bir ürün fiyatı girilmeli
    if all(f == 0 for f in req_prices):
        flash("En az bir ürün fiyatı girilmelidir.")
        return redirect(url_for("admin_request_detail", req_id=req_id))

    # 7️⃣ Kalıcı kaydet
    req["prices"] = req_prices
    req["kdv_dahil"] = kdv_dahil
    req["ara_toplamlar"] = ara_toplamlar
    req["toplam"] = round(toplam, 2)
    req["offer_note"] = offer_text

    # 🔄 Durum güncelleme
    if req.get("status") in [None, "Yeni", "new"]:
        req["status"] = "Cevaplandı"
    elif req.get("status") != "Kapalı":
        req["status"] = "Teklif Hazır"

    # 💬 Mesaj geçmişine bilgi düş
    req.setdefault("offer_messages", [])
    req["offer_messages"].append({
        "sender": "yönetici",
        "sender_name": user["name"],
        "text": f"Yeni teklif hazırlandı. Toplam: {req['toplam']:.2f} ₺\n{offer_text}",
        "file": file_path,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    save_requests()
    flash("Teklif başarıyla kaydedildi.")
    return redirect(url_for("admin_request_detail", req_id=req_id))

@app.route("/admin/offer_pdf/<int:req_id>")
@admin_required
def admin_offer_pdf(req_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    import ssl
    import smtplib
    from email.message import EmailMessage
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Türkçe karakter desteği
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))

    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Teklif bulunamadı.")
        return redirect(url_for("admin_dashboard"))

    pdf_path = os.path.join("static", "uploads", f"teklif_{req_id}.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = 'DejaVuSans'
    styles["Title"].fontName = 'DejaVuSans'

    # 🔹 LOGO ve başlık
    logo_path = os.path.join("static", "uploads", "HD LOGO 4K.png")
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=4 * cm, height=4 * cm))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph("<b>ŞALT ELEKTRİK</b> - Teklif Formu", styles["Title"]))
    elements.append(Spacer(1, 0.3 * cm))

    # 🔹 Üst Bilgiler
    details = f"""
    <b>Müşteri:</b> {req.get('name', 'Bilinmiyor')}<br/>
    <b>E-posta:</b> {req.get('email', '')}<br/>
    <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>
    <b>Teklif No:</b> #{req_id}<br/>
    """
    elements.append(Paragraph(details, styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # 🔹 Ürün Tablosu
    data = [["Sıra", "Ürün Açıklaması", "Kod", "Marka", "Adet", "Birim Fiyat", "KDV Dahil", "Tutar"]]
    products = req.get("products", [])
    prices = req.get("prices", [])
    kdv = req.get("kdv_dahil", [])
    ara_toplam = req.get("ara_toplamlar", [])

    for i, prod in enumerate(products):
        desc = Paragraph(prod.get("desc", ""), styles["Normal"])
        code = Paragraph(prod.get("code", ""), styles["Normal"])
        brand = Paragraph(prod.get("brand", ""), styles["Normal"])

        data.append([
            str(i + 1),
            desc,
            code,
            brand,
            str(prod.get("qty", "")),
            f"{prices[i]:.2f} ₺" if i < len(prices) else "-",
            f"{kdv[i]:.2f} ₺" if i < len(kdv) else "-",
            f"{ara_toplam[i]:.2f} ₺" if i < len(ara_toplam) else "-"
        ])

    table = Table(
        data,
        colWidths=[1 * cm, 5 * cm, 2.5 * cm, 3 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 3 * cm]
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
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))

    # 🔹 Teklif Notu (varsa PDF'e ekle)
    offer_note = req.get("offer_note", "").strip()
    if offer_note:
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph("<b>Teklif Notu:</b>", styles["Normal"]))
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(Paragraph(offer_note.replace("\n", "<br/>"), styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))

    # 🔹 Açıklamalar
    notes = """
    <b>Açıklamalar:</b><br/>
    Ödeme vadesi: Peşin<br/>
    Teklif geçerlilik süresi: 7 gün<br/>
    Teslim süresi: Stok durumuna göre değişir.<br/>
    """
    elements.append(Paragraph(notes, styles["Normal"]))

    doc.build(elements)

    # ✅ Mail gönder
    sender_email = "teklif@e-saltelefktrik.com"
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


