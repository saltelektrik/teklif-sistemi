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

# ✅ Fonksiyon: JSON’dan veriyi yükle
def load_requests():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ✅ Fonksiyon: JSON’a kaydet
def save_requests():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(requests_data, f, ensure_ascii=False, indent=2)

# Başlangıçta veriyi yükle
requests_data = load_requests()

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
    req = {
        "id": len(requests_data) + 1,
        "name": user["name"],
        "email": user["email"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": [
            {"sender": "müşteri", "sender_name": user["name"], "text": message, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        ],
        "status": "new",
        "products": [{"desc": d, "code": c, "brand": b, "qty": q} for d, c, b, q in zip(desc, code, brand, qty)],
    }
    requests_data.append(req)
    save_requests()
    flash("Talebiniz başarıyla gönderildi.")
    return redirect(url_for("dashboard"))

# 💬 Müşteri mesajlaşma
@app.route("/status/<int:req_id>", methods=["GET", "POST"])
@login_required
def status(req_id):
    user = get_current_user()  # ✅ eklendi (bazı eski sürümlerde eksikti)
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        text = request.form.get("message", "").strip()
        file = request.files.get("file")
        file_path = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_path = f"/static/uploads/{filename}"

        if text or file_path:
            req["messages"].append({
                "sender": "müşteri",
                "sender_name": user["name"],
                "text": text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path
            })
            save_requests()
        return redirect(url_for("status", req_id=req_id))

    # 👇 burada user'ı da template'e gönderiyoruz
    return render_template("client/status.html", req=req, user=user)


# ⚙️ Yönetici Paneli
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    user = get_current_user()
    return render_template("admin/dashboard.html", requests=requests_data, user=user, users=users)

@app.route("/admin/assign/<int:req_id>", methods=["POST"])
@admin_required
def assign_admin(req_id):
    admin_name = request.form.get("admin_name")
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if req:
        req["assigned_admin"] = admin_name
        save_requests()  # ✅ kalıcı kaydet
    return ("", 204)

@app.route("/admin/request/<int:req_id>")
@admin_required
def admin_request_detail(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if not req:
        flash("Talep bulunamadı.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/request_detail.html", req=req, user=user)

@app.route("/admin/message/<int:req_id>", methods=["POST"])
@admin_required
def admin_message(req_id):
    user = get_current_user()
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if req:
        msg_text = request.form.get("message", "").strip()
        file = request.files.get("file")
        file_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            file_path = f"/static/uploads/{filename}"
        if msg_text or file_path:
            req["messages"].append({
                "sender": "yönetici",
                "sender_name": user["name"],
                "text": msg_text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file": file_path
            })
            req["status"] = "replied"
            save_requests()
    return redirect(url_for("admin_request_detail", req_id=req_id))

@app.route("/admin/close/<int:req_id>")
@admin_required
def admin_close(req_id):
    req = next((r for r in requests_data if r["id"] == req_id), None)
    if req:
        req["status"] = "closed"
        flash("Talep kapatıldı.")
        save_requests()
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

if __name__ == "__main__":
    app.run(debug=True)
