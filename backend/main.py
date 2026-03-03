import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from api import test_connection
from agent import run_agent

# __file__ is /app/main.py so this gives us /app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# In-memory session store
sessions = {}

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/status", methods=["GET"])
def status():
    conn = test_connection()
    return jsonify({
        "monday_connected": conn["ok"],
        "monday_user": conn.get("name", ""),
        "deals_board_id": os.getenv("DEALS_BOARD_ID"),
        "work_orders_board_id": os.getenv("WORK_ORDERS_BOARD_ID"),
        "error": conn.get("error")
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json()
    if not body or "message" not in body:
        return jsonify({"error": "Missing 'message' field"}), 400

    user_message = body["message"].strip()
    session_id = body.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    if session_id not in sessions:
        sessions[session_id] = []

    history = sessions[session_id]

    try:
        answer, updated_history, traces = run_agent(user_message, history)
        sessions[session_id] = updated_history
        return jsonify({
            "answer": answer,
            "trace": traces,
            "session_id": session_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reset", methods=["POST"])
def reset():
    body = request.get_json() or {}
    session_id = body.get("session_id", "default")
    sessions[session_id] = []
    return jsonify({"status": "reset", "session_id": session_id})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
