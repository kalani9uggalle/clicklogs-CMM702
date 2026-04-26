"""
saveTaps backend — Python Flask
Writes to Firebase Firestore AND MongoDB Atlas.
Fixed: MongoClient created per-request (fork-safe).
"""

import json
import os
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, make_response, request
from flask_cors import CORS
from pymongo import MongoClient

# ── Firebase init ─────────────────────────────────────────────────────────────
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

fs_db = firestore.client()

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://kalani9uggalle_db_user:CYEdoMO5j3LtQOSr@cluster0.truaou2.mongodb.net/?appName=Cluster0&tls=true&tlsAllowInvalidCertificates=true"
)

app = Flask(__name__)
CORS(app)


def cors_resp(body, status):
    resp = make_response(body, status)
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/saveTaps", methods=["POST", "OPTIONS"])
def save_taps():

    if request.method == "OPTIONS":
        return cors_resp("", 204)

    session_id = request.form.get("id",   "").strip()
    device     = request.form.get("var",  "").strip()
    taps_raw   = request.form.get("taps", "").strip()

    if not session_id or not device or not taps_raw:
        return cors_resp("Missing required fields", 400)

    try:
        taps = json.loads(taps_raw)
    except json.JSONDecodeError as e:
        return cors_resp(f"Invalid JSON: {e}", 400)

    if not isinstance(taps, list) or len(taps) == 0:
        return cors_resp("taps must be a non-empty array", 400)

    server_ts = datetime.now(timezone.utc)
    documents = []

    for tap in taps:
        start    = int(tap.get("startTimestamp", 0))
        end      = int(tap.get("endTimestamp",   0))
        duration = end - start if end >= start else 0
        documents.append({
            "session_id":         session_id,
            "device":             device,
            "tap_sequence":       int(tap.get("tapSequenceNumber",  0)),
            "start_timestamp":    start,
            "end_timestamp":      end,
            "duration":           duration,
            "interface_type":     tap.get("interface", ""),
            "interface_sequence": int(tap.get("interfaceSequence", 0)),
            "created_at":         server_ts,
        })

    # ── Write to Firestore ────────────────────────────────────────────────────
    try:
        batch   = fs_db.batch()
        col_ref = fs_db.collection("tap_logs")
        for doc in documents:
            batch.set(col_ref.document(), doc)
        batch.commit()
    except Exception as e:
        print(f"Firestore error: {e}")

    # ── Write to MongoDB (client created per-request — fork safe) ─────────────
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        col    = client["clicklogs"]["tap_logs"]
        col.insert_many(documents)
        client.close()
    except Exception as e:
        print(f"MongoDB error: {e}")

    return cors_resp("Data saved successfully", 200)


@app.route("/", methods=["GET"])
def health():
    return cors_resp("saveTaps backend is running", 200)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
