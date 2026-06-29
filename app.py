"""Provenance Guard — Flask API.

Endpoints:
  POST /submit  -> classify text with 2 signals, return label + confidence
  POST /appeal  -> contest a classification, set status to under_review
  GET  /log     -> recent structured audit-log entries
"""
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import audit
import scoring
from labels import make_label
from signals import llm_signal, style_signal

load_dotenv()

app = Flask(__name__)

# Rate limiting. Limits chosen for a writing platform (see README): a real
# creator submits a handful of pieces; the cap stops a script from flooding.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/")
def home():
    return "Provenance Guard is running."


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    creator_id = body.get("creator_id")
    if not text or not creator_id:
        return jsonify({"error": "text and creator_id are required"}), 400

    # Two independent signals: semantic (LLM) + structural (stylometrics).
    signal1 = llm_signal(text)
    signal2 = style_signal(text)
    llm_score = signal1["llm_score"]
    style_score = signal2["style_score"]

    # Combined confidence -> attribution band -> transparency label.
    confidence = scoring.combine(llm_score, style_score)
    attribution = scoring.classify(confidence)
    label = make_label(confidence, attribution)

    content_id = str(uuid.uuid4())
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": audit.now_iso(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "style_score": style_score,
        "label": label,
        "status": "classified",
        "appeal": None,
    }
    audit.add_entry(entry)

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": label,
        }
    )


@app.route("/appeal", methods=["POST"])
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id")
    reasoning = (body.get("creator_reasoning") or "").strip()
    if not content_id or not reasoning:
        return (
            jsonify({"error": "content_id and creator_reasoning are required"}),
            400,
        )

    original = audit.find_entry(content_id)
    if original is None:
        return jsonify({"error": "content_id not found"}), 404

    # Flip status and attach the appeal alongside the original decision.
    updated = audit.update_entry(
        content_id,
        {
            "status": "under_review",
            "appeal": {
                "creator_reasoning": reasoning,
                "appealed_at": audit.now_iso(),
            },
        },
    )

    return jsonify(
        {
            "message": "Appeal received. This content is now under review.",
            "content_id": content_id,
            "status": updated["status"],
        }
    )


@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": audit.get_log()})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
