from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from dotenv import load_dotenv
from groq import Groq
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import os
import uuid
import json
import random
import string
from datetime import datetime
import pytz
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = "chatbot-secret-key-123"

# ── Mail Configuration ──
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_EMAIL")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_EMAIL")
app.config["MAIL_TIMEOUT"] = 30

mail = Mail(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── IST Timezone ──
def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%d %b %Y %I:%M %p IST")

# ── File Storage ──
USERS_FILE = "users.json"
CHATS_FILE = "chats.json"
OTP_FILE = "otps.json"

# ── Admin Credentials ──
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_chats(chats):
    with open(CHATS_FILE, "w") as f:
        json.dump(chats, f, indent=2)

def load_otps():
    if os.path.exists(OTP_FILE):
        with open(OTP_FILE, "r") as f:
            return json.load(f)
    return {}

def save_otps(otps):
    with open(OTP_FILE, "w") as f:
        json.dump(otps, f, indent=2)

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ─── USER AUTH ROUTES ──────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        users = load_users()

        if email not in users:
            return jsonify({"error": "Email not found! Please register."}), 401
        if not check_password_hash(users[email]["password"], password):
            return jsonify({"error": "Wrong password!"}), 401

        session["user_id"] = email
        session["username"] = users[email]["name"]
        users[email]["last_login"] = get_ist_time()
        save_users(users)

        return jsonify({"success": True})
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.json
        name = data.get("name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not name or not email or not password:
            return jsonify({"error": "Please fill all fields!"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be 6+ characters!"}), 400

        users = load_users()
        if email in users:
            return jsonify({"error": "Email already registered!"}), 400

        users[email] = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "joined": get_ist_time(),
            "last_login": get_ist_time()
        }
        save_users(users)

        chats = load_chats()
        chats[email] = {}
        save_chats(chats)

        session["user_id"] = email
        session["username"] = name
        return jsonify({"success": True})

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("login"))

# ─── FORGOT PASSWORD ROUTES ────────────

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        data = request.json
        email = data.get("email", "").strip().lower()
        users = load_users()

        if email not in users:
            return jsonify({"error": "Email not found! Please register first."}), 404

        # Generate 6-digit OTP
        otp = generate_otp()

        # Save OTP with timestamp
        otps = load_otps()
        otps[email] = {
            "otp": otp,
            "created_at": get_ist_time(),
            "expires_at": get_ist_time()
        }
        save_otps(otps)

        # Send OTP email
        try:
            msg = Message(
                subject="🔐 Your Password Reset OTP - AI Chatbot",
                recipients=[email]
            )
            msg.html = f"""
            <div style="font-family: Arial, sans-serif;
                max-width: 500px; margin: 0 auto;
                background: #1a1a2e; color: white;
                padding: 30px; border-radius: 12px;">

                <h2 style="color: #6c47ff; text-align: center;">
                    🤖 AI Chatbot
                </h2>

                <h3 style="text-align: center; color: white;">
                    Password Reset OTP
                </h3>

                <p style="color: #aaa; text-align: center;">
                    You requested to reset your password.
                    Use the OTP below:
                </p>

                <div style="background: #16213e;
                    border: 2px solid #6c47ff;
                    border-radius: 12px;
                    padding: 20px;
                    text-align: center;
                    margin: 20px 0;">
                    <p style="color: #aaa; font-size: 14px;
                        margin-bottom: 8px;">
                        Your OTP Code
                    </p>
                    <h1 style="color: #6c47ff;
                        font-size: 42px;
                        letter-spacing: 8px;
                        margin: 0;">
                        {otp}
                    </h1>
                </div>

                <p style="color: #ff4757;
                    text-align: center;
                    font-size: 13px;">
                    ⚠️ This OTP is valid for 10 minutes only.
                </p>

                <p style="color: #555;
                    text-align: center;
                    font-size: 12px;
                    margin-top: 20px;">
                    If you didn't request this,
                    please ignore this email.
                </p>

                <p style="color: #555;
                    text-align: center;
                    font-size: 11px;">
                    Sent at {get_ist_time()}
                </p>
            </div>
            """
            mail.send(msg)
            return jsonify({"success": True})

        except Exception as e:
            print("Mail Error:", str(e))
            return jsonify({
                "error": "Failed to send email. Check mail settings."
            }), 500

    return render_template("forgot_password.html")

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        data = request.json
        email = data.get("email", "").strip().lower()
        entered_otp = data.get("otp", "").strip()

        otps = load_otps()

        if email not in otps:
            return jsonify({"error": "OTP expired or not found!"}), 400

        if otps[email]["otp"] != entered_otp:
            return jsonify({"error": "Wrong OTP! Please try again."}), 400

        # OTP is correct
        session["reset_email"] = email
        return jsonify({"success": True})

    email = request.args.get("email", "")
    return render_template("verify_otp.html", email=email)

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        data = request.json
        new_password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")

        if "reset_email" not in session:
            return jsonify({
                "error": "Session expired! Please start again."
            }), 400

        if len(new_password) < 6:
            return jsonify({
                "error": "Password must be at least 6 characters!"
            }), 400

        if new_password != confirm_password:
            return jsonify({"error": "Passwords do not match!"}), 400

        email = session["reset_email"]
        users = load_users()

        if email not in users:
            return jsonify({"error": "User not found!"}), 404

        # Update password
        users[email]["password"] = generate_password_hash(new_password)
        users[email]["last_password_reset"] = get_ist_time()
        save_users(users)

        # Clear OTP and session
        otps = load_otps()
        if email in otps:
            del otps[email]
            save_otps(otps)

        session.pop("reset_email", None)

        return jsonify({"success": True})

    return render_template("reset_password.html")

# ─── CHAT ROUTES ───────────────────────

@app.route("/chat-page")
@login_required
def home():
    return render_template("index.html",
        username=session.get("username"))

@app.route("/new-chat", methods=["POST"])
@login_required
def new_chat():
    user_id = session["user_id"]
    chat_id = str(uuid.uuid4())[:8]
    chats = load_chats()

    if user_id not in chats:
        chats[user_id] = {}

    chats[user_id][chat_id] = {
        "id": chat_id,
        "title": "New Chat",
        "messages": [],
        "created_at": get_ist_time()
    }
    save_chats(chats)
    return jsonify({"chat_id": chat_id})

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    try:
        user_id = session["user_id"]
        data = request.json
        user_message = data.get("message")
        chat_id = data.get("chat_id")

        if not user_message or not chat_id:
            return jsonify({"error": "Missing data"}), 400

        chats = load_chats()
        if user_id not in chats:
            chats[user_id] = {}
        if chat_id not in chats[user_id]:
            chats[user_id][chat_id] = {
                "id": chat_id,
                "title": "New Chat",
                "messages": [],
                "created_at": get_ist_time()
            }

        chats[user_id][chat_id]["messages"].append({
            "role": "user",
            "content": user_message,
            "time": get_ist_time()
        })

        if chats[user_id][chat_id]["title"] == "New Chat":
            chats[user_id][chat_id]["title"] = (
                user_message[:30] + "..."
                if len(user_message) > 30
                else user_message
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system",
                 "content": "You are a helpful friendly AI assistant."}
            ] + [
                {"role": m["role"], "content": m["content"]}
                for m in chats[user_id][chat_id]["messages"]
            ],
            max_tokens=1024
        )

        assistant_message = response.choices[0].message.content

        chats[user_id][chat_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "time": get_ist_time()
        })
        save_chats(chats)

        return jsonify({
            "reply": assistant_message,
            "chat_id": chat_id,
            "title": chats[user_id][chat_id]["title"],
            "time": get_ist_time()
        })

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": "Error: " + str(e)}), 500

@app.route("/get-chats")
@login_required
def get_chats():
    user_id = session["user_id"]
    chats = load_chats()
    user_chats = chats.get(user_id, {})
    chat_list = [
        {"id": c["id"], "title": c["title"],
         "created_at": c["created_at"]}
        for c in user_chats.values()
    ]
    return jsonify({"chats": chat_list[::-1]})

@app.route("/get-messages/<chat_id>")
@login_required
def get_messages(chat_id):
    user_id = session["user_id"]
    chats = load_chats()
    user_chats = chats.get(user_id, {})
    if chat_id in user_chats:
        return jsonify({
            "messages": user_chats[chat_id]["messages"]
        })
    return jsonify({"messages": []})

@app.route("/delete-chat/<chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    user_id = session["user_id"]
    chats = load_chats()
    if user_id in chats and chat_id in chats[user_id]:
        del chats[user_id][chat_id]
        save_chats(chats)
    return jsonify({"success": True})

# ─── ADMIN ROUTES ──────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        data = request.json
        username = data.get("username", "")
        password = data.get("password", "")
        if username == ADMIN_USERNAME and \
           password == ADMIN_PASSWORD:
            session["admin"] = True
            return jsonify({"success": True})
        return jsonify({
            "error": "Wrong admin credentials!"
        }), 401
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    users = load_users()
    chats = load_chats()

    total_users = len(users)
    total_chats = sum(len(v) for v in chats.values())
    total_messages = sum(
        len(chat["messages"])
        for user_chats in chats.values()
        for chat in user_chats.values()
    )

    user_list = []
    for email, user in users.items():
        user_chats = chats.get(email, {})
        user_msg_count = sum(
            len(c["messages"])
            for c in user_chats.values()
        )
        user_list.append({
            "name": user["name"],
            "email": email,
            "joined": user.get("joined", "N/A"),
            "last_login": user.get("last_login", "N/A"),
            "total_chats": len(user_chats),
            "total_messages": user_msg_count
        })

    return render_template("admin_dashboard.html",
        total_users=total_users,
        total_chats=total_chats,
        total_messages=total_messages,
        users=user_list,
        current_time=get_ist_time()
    )

@app.route("/admin/delete-user/<email>",
           methods=["DELETE"])
@admin_required
def admin_delete_user(email):
    users = load_users()
    chats = load_chats()
    if email in users:
        del users[email]
        save_users(users)
    if email in chats:
        del chats[email]
        save_chats(chats)
    return jsonify({"success": True})

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )