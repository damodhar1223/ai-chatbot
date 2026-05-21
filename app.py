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

# ── File paths for permanent storage ──
USERS_FILE = "users.json"
CHATS_FILE = "chats.json"

# ── Load data from files ──
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

# ── Login required decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ───────────────────────

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
            return jsonify({"error": "Email not found! Please register first."}), 401

        if not check_password_hash(users[email]["password"], password):
            return jsonify({"error": "Wrong password! Try again."}), 401

        session["user_id"] = email
        session["username"] = users[email]["name"]
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
            return jsonify({"error": "Password must be at least 6 characters!"}), 400

        users = load_users()

        if email in users:
            return jsonify({"error": "Email already registered! Please login."}), 400

        users[email] = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "created_at": datetime.now().strftime("%d %b %Y")
        }
        save_users(users)

        # Create empty chat space for user
        chats = load_chats()
        chats[email] = {}
        save_chats(chats)

        session["user_id"] = email
        session["username"] = name
        return jsonify({"success": True})

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
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
                {
                    "role": "system",
                    "content": "You are a helpful friendly AI assistant."
                }
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

@app.route("/get-chats", methods=["GET"])
@login_required
def get_chats():
    user_id = session["user_id"]
    chats = load_chats()
    user_chats = chats.get(user_id, {})
    chat_list = [
        {
            "id": c["id"],
            "title": c["title"],
            "created_at": c["created_at"]
        }
        for c in user_chats.values()
    ]
    return jsonify({"chats": chat_list[::-1]})

@app.route("/get-messages/<chat_id>", methods=["GET"])
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

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )