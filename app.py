from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from dotenv import load_dotenv
from groq import Groq
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import json
from datetime import datetime
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = "chatbot-secret-key-123"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── File Storage ──
USERS_FILE = "users.json"
CHATS_FILE = "chats.json"

# ── Admin Credentials ──
ADMIN_USERNAME = "Damodhar Krishna Chappa"
ADMIN_PASSWORD = "Damodhar@2504"

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

        # Track last login
        users[email]["last_login"] = datetime.now().strftime("%d %b %Y %H:%M")
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
            "joined": datetime.now().strftime("%d %b %Y %H:%M"),
            "last_login": datetime.now().strftime("%d %b %Y %H:%M")
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
        "created_at": datetime.now().strftime("%d %b %Y %H:%M")
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
                "created_at": datetime.now().strftime("%d %b %Y")
            }

        chats[user_id][chat_id]["messages"].append({
            "role": "user",
            "content": user_message
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
            ] + chats[user_id][chat_id]["messages"],
            max_tokens=1024
        )

        assistant_message = response.choices[0].message.content
        chats[user_id][chat_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message
        })
        save_chats(chats)

        return jsonify({
            "reply": assistant_message,
            "chat_id": chat_id,
            "title": chats[user_id][chat_id]["title"]
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
        return jsonify({"messages": user_chats[chat_id]["messages"]})
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

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            return jsonify({"success": True})
        return jsonify({"error": "Wrong admin credentials!"}), 401

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
            len(c["messages"]) for c in user_chats.values()
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
        users=user_list
    )

@app.route("/admin/delete-user/<email>", methods=["DELETE"])
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

@app.route("/admin/user-chats/<email>")
@admin_required
def admin_user_chats(email):
    chats = load_chats()
    user_chats = chats.get(email, {})
    chat_list = [
        {"id": c["id"], "title": c["title"],
         "messages": len(c["messages"]),
         "created_at": c["created_at"]}
        for c in user_chats.values()
    ]
    return jsonify({"chats": chat_list[::-1]})

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )