"""
saveTaps backend — Python Flask + Firebase Firestore
Replaces the missing saveTaps.php from the clicklogs project.

Receives POST data from index.html and writes each tap record
into the Firebase Firestore 'tap_logs' collection.

POST params received:
  id   — session identifier (timestamp + random suffix)
  var  — device platform (android / pc)
  taps — JSON array string of tap objects

Each tap object from the frontend:
  { tapSequenceNumber, startTimestamp, endTimestamp,
    interfaceSequence, interface }
"""

import json
import os
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request
from flask_cors import CORS

# ── Firebase initialisation ───────────────────────────────────────────────────
# On Render: set the environment variable GOOGLE_APPLICATION_CREDENTIALS
# to point to your Firebase service account JSON key file path,
# OR paste the JSON content into an env var called FIREBASE_CREDENTIALS_JSON.

if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        # Credentials provided as a JSON string in env var (recommended for Render)
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback: path to service account key file
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from GitHub Pages


@app.route("/saveTaps", methods=["POST", "OPTIONS"])
def save_taps():
    """
    Receive tap data from the frontend and store each tap
    as a separate document in the Firestore 'tap_logs' collection.
    """

    # Handle CORS preflight
    if request.method == "OPTIONS":
        return _cors_response("", 204)

    # ── Parse POST fields ─────────────────────────────────────────────────────
    session_id = request.form.get("id", "").strip()
    device     = request.form.get("var", "").strip()
    taps_raw   = request.form.get("taps", "").strip()

    # Basic validation
    if not session_id or not device or not taps_raw:
        return _cors_response("Missing required fields: id, var, taps", 400)

    # ── Parse taps JSON array ─────────────────────────────────────────────────
    try:
        taps = json.loads(taps_raw)
    except json.JSONDecodeError as e:
        return _cors_response(f"Invalid taps JSON: {e}", 400)

    if not isinstance(taps, list) or len(taps) == 0:
        return _cors_response("taps must be a non-empty JSON array", 400)

    # ── Write to Firestore in a batch ─────────────────────────────────────────
    # Using a batch write for efficiency — all tap documents committed atomically.
    batch     = db.batch()
    col_ref   = db.collection("tap_logs")
    server_ts = datetime.now(timezone.utc)

    for tap in taps:
        doc_ref = col_ref.document()  # auto-generated document ID

        start = int(tap.get("startTimestamp", 0))
        end   = int(tap.get("endTimestamp",   0))

        # Compute duration here and store it.
        # Firestore cannot compute derived fields during queries,
        # so storing duration avoids fetching all documents to the client
        # for aggregation queries.
        duration = end - start if end >= start else 0

        batch.set(doc_ref, {
            # ── Session-level fields (same for all taps in this session) ──
            "session_id":         session_id,
            "device":             device,          # "android" or "pc"

            # ── Tap-level fields ──────────────────────────────────────────
            "tap_sequence":       int(tap.get("tapSequenceNumber", 0)),
            "start_timestamp":    start,           # Unix ms
            "end_timestamp":      end,             # Unix ms
            "duration":           duration,        # ms — stored for fast aggregation
            "interface_type":     tap.get("interface", ""),        # feedbackshown | nofeedback
            "interface_sequence": int(tap.get("interfaceSequence", 0)),  # 1 or 2

            # ── Server metadata ───────────────────────────────────────────
            "created_at":         server_ts,
        })

    batch.commit()

    # index.html checks for exactly this string
    return _cors_response("Data saved successfully", 200)


@app.route("/", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return _cors_response("saveTaps backend is running", 200)


def _cors_response(body, status):
    """Helper — attach CORS headers to every response."""
    from flask import make_response
    resp = make_response(body, status)
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


if __name__ == "__main__":
    # Local development: python app.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
