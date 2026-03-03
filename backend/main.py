import os
import json
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from api import test_connection
from agent import run_agent

app = Flask(__name__)
CORS(app)

sessions = {}

@app.route("/")
def index():
    # Read and serve index.html manually — no static folder dependency
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content, mimetype="text/html")
    except FileNotFoundError:
        return Response(f"index.html not found. Looked at: {html_path}", status=404)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/status")
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
    try:
        answer, updated_history, traces = run_agent(user_message, sessions[session_id])
        sessions[session_id] = updated_history
        return jsonify({"answer": answer, "trace": traces, "session_id": session_id})
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
