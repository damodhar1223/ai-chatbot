from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

conversation_history = []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat_route():
    try:
        user_message = request.json.get("message")

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a funny assistant who replies with humor."
                }
            ] + conversation_history,
            max_tokens=1024
        )

        assistant_message = response.choices[0].message.content

        conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return jsonify({"reply": assistant_message})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": "Error: " + str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)