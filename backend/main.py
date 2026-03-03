import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from api import test_connection
from agent import run_agent

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# In-memory session store (keyed by session_id)
sessions = {}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/status", methods=["GET"])
def status():
    """Check Monday.com connection status."""
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
    """
    POST body: { "message": "...", "session_id": "..." }
    Returns: { "answer": "...", "trace": [...], "session_id": "..." }
    """
    body = request.get_json()
    if not body or "message" not in body:
        return jsonify({"error": "Missing 'message' field"}), 400

    user_message = body["message"].strip()
    session_id = body.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # Load or init conversation history for this session
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
    """Reset conversation history for a session."""
    body = request.get_json() or {}
    session_id = body.get("session_id", "default")
    sessions[session_id] = []
    return jsonify({"status": "reset", "session_id": session_id})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
