from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from dotenv import load_dotenv
from groq import Groq
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
from datetime import datetime
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = "chatbot-secret-key-123"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Simple in-memory storage
users = {}
all_chats = {}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ───────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        email = data.get("email")
        password = data.get("password")

        user = users.get(email)
        if not user:
            return jsonify({"error": "Email not found!"}), 401
        if not check_password_hash(user["password"], password):
            return jsonify({"error": "Wrong password!"}), 401

        session["user_id"] = email
        session["username"] = user["name"]
        return jsonify({"success": True})

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.json
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if email in users:
            return jsonify({"error": "Email already exists!"}), 400

        users[email] = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password)
        }
        all_chats[email] = {}

        session["user_id"] = email
        session["username"] = name
        return jsonify({"success": True})

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── CHAT ROUTES ───────────────────────────

@app.route("/chat-page")
@login_required
def home():
    return render_template("index.html", username=session.get("username"))

@app.route("/new-chat", methods=["POST"])
@login_required
def new_chat():
    user_id = session["user_id"]
    chat_id = str(uuid.uuid4())[:8]

    if user_id not in all_chats:
        all_chats[user_id] = {}

    all_chats[user_id][chat_id] = {
        "id": chat_id,
        "title": "New Chat",
        "messages": [],
        "created_at": datetime.now().strftime("%d %b %Y")
    }
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

        if user_id not in all_chats:
            all_chats[user_id] = {}

        if chat_id not in all_chats[user_id]:
            all_chats[user_id][chat_id] = {
                "id": chat_id,
                "title": "New Chat",
                "messages": [],
                "created_at": datetime.now().strftime("%d %b %Y")
            }

        all_chats[user_id][chat_id]["messages"].append({
            "role": "user",
            "content": user_message
        })

        if all_chats[user_id][chat_id]["title"] == "New Chat":
            all_chats[user_id][chat_id]["title"] = user_message[:30] + "..." if len(user_message) > 30 else user_message

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful friendly AI assistant."}
            ] + all_chats[user_id][chat_id]["messages"],
            max_tokens=1024
        )

        assistant_message = response.choices[0].message.content

        all_chats[user_id][chat_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message
        })

        return jsonify({
            "reply": assistant_message,
            "chat_id": chat_id,
            "title": all_chats[user_id][chat_id]["title"]
        })

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": "Error: " + str(e)}), 500

@app.route("/get-chats", methods=["GET"])
@login_required
def get_chats():
    user_id = session["user_id"]
    user_chats = all_chats.get(user_id, {})
    chat_list = [
        {"id": c["id"], "title": c["title"], "created_at": c["created_at"]}
        for c in user_chats.values()
    ]
    return jsonify({"chats": chat_list[::-1]})

@app.route("/get-messages/<chat_id>", methods=["GET"])
@login_required
def get_messages(chat_id):
    user_id = session["user_id"]
    user_chats = all_chats.get(user_id, {})
    if chat_id in user_chats:
        return jsonify({"messages": user_chats[chat_id]["messages"]})
    return jsonify({"messages": []})

@app.route("/delete-chat/<chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    user_id = session["user_id"]
    if user_id in all_chats and chat_id in all_chats[user_id]:
        del all_chats[user_id][chat_id]
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)