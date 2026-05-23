"""
86 Proof — Flask Application
─────────────────────────────────────────
Main web server that ties the data layer, analyzer, and Claude
client together with HTML templates.

Architecture:
  - Browser uploads Excel file → /upload route parses and stores it
  - Browser loads dashboard → /dashboard route computes metrics and renders
  - User sends chat message → /api/chat route calls Claude and returns response

Session storage:
  Uploaded data is stored in an in-memory dict keyed by session ID.
  This is intentionally simple for v1. For production, replace with Redis
  or a database.
"""

import os
import uuid
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, session
)
from werkzeug.utils import secure_filename

import data_loader
import analyzer
import claude_client


# Load environment variables from .env file
load_dotenv()


# ── FLASK SETUP ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-prod")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"xlsx", "xlsm"}
MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
# Ensure upload folder exists (runs in both dev and production)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── IN-MEMORY DATA STORE ───────────────────────────────
# Keyed by session_id. In production, replace with Redis or a database.
data_store = {}


# ── HELPERS ────────────────────────────────────────────

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_session_id():
    """Get or create a session ID for this user."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def get_user_data():
    """Retrieve the parsed bar data for the current session."""
    session_id = get_session_id()
    return data_store.get(session_id)


# ── ROUTES ─────────────────────────────────────────────

@app.route("/")
def home():
    """
    Homepage. If user has uploaded data, redirect to dashboard.
    Otherwise, show the upload screen.
    """
    if get_user_data():
        return redirect(url_for("dashboard"))
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    """
    Handle file upload. Parses the Excel file via data_loader,
    stores the parsed data in the session, and redirects to dashboard.
    """
    if "file" not in request.files:
        return redirect(url_for("home"))

    file = request.files["file"]

    if file.filename == "":
        return redirect(url_for("home"))

    if not allowed_file(file.filename):
        return render_template(
            "upload.html",
            error="Please upload an .xlsx or .xlsm file."
        )

    # Save the file to the uploads folder
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Parse the file
    try:
        parsed_data = data_loader.load_all_data(filepath)
    except Exception as e:
        return render_template(
            "upload.html",
            error=f"Could not read file: {str(e)}"
        )

    if not parsed_data:
        return render_template(
            "upload.html",
            error="No usable data found in the file. "
                  "Make sure it's a valid 86 Proof export."
        )

    # Store the parsed data keyed by session
    session_id = get_session_id()
    data_store[session_id] = parsed_data

    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    """
    Render the dashboard with the 6 metric cards.
    Redirects to upload if no data is loaded.
    """
    data = get_user_data()
    if not data:
        return redirect(url_for("home"))

    metrics = analyzer.build_dashboard_metrics(data)

    return render_template(
        "dashboard.html",
        metrics=metrics,
        data=data,
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Handle chat messages. Receives the user's message and the
    conversation history, calls Claude, returns the response.

    Expected JSON payload:
      {
        "message": "user's question",
        "history": [{"role": "user"|"assistant", "content": "..."}, ...]
      }
    """
    data = get_user_data()
    if not data:
        return jsonify({"error": "No data loaded. Please upload a file first."}), 400

    payload = request.get_json()
    user_message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        response_text = claude_client.chat(
            user_message=user_message,
            conversation_history=history,
            bar_data=data,
        )
    except Exception as e:
        return jsonify({
            "error": f"Could not get response from Claude: {str(e)}"
        }), 500

    return jsonify({"response": response_text})


@app.route("/reset")
def reset():
    """Clear the user's uploaded data and start over."""
    session_id = get_session_id()
    if session_id in data_store:
        del data_store[session_id]
    return redirect(url_for("home"))


# ── ENTRY POINT ────────────────────────────────────────

if __name__ == "__main__":
    # Create uploads folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Run the server
    # In production (Render), use the PORT env variable
    # Locally, default to 5000
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(debug=debug, host="0.0.0.0", port=port)