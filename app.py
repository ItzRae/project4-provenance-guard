import json
import re
import string
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20 per minute"],
    storage_uri="memory://",
)

LOG_PATH = "audit_log.jsonl"

def log_event(entry):
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_log(limit=20):
    try:
        with open(LOG_PATH, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    return [json.loads(line) for line in lines[-limit:]]


def llm_based_classifier(text):
    """
    First detection signal.
    Returns an AI-probability score from 0 to 1 plus reasoning.
    Placeholder until the Groq API version is added.
    """

    ai_like_phrases = [
        "in conclusion",
        "it is important to note",
        "furthermore",
        "moreover",
        "overall",
        "as a result",
        "plays a crucial role",
        "in today's world",
    ]

    lower_text = text.lower()
    matches = sum(1 for phrase in ai_like_phrases if phrase in lower_text)

    if len(text.split()) < 20:
        score = 0.5
        reasoning = "Text is short, so this signal is uncertain."
    elif matches > 0:
        score = min(0.65 + matches * 0.08, 0.95)
        reasoning = "Text contains phrasing patterns often associated with AI-generated writing."
    else:
        score = 0.4
        reasoning = "Text does not strongly match common AI-like phrasing patterns."

    return {
        "signal": "llm_classifier",
        "ai_probability": round(score, 2),
        "reasoning": reasoning,
    }
def generate_label(confidence):
    if confidence >= 0.75:
        return (
            "This content was classified as likely AI-generated with high confidence. "
            "This result is based on multiple automated detection signals and may be appealed by the creator."
        )

    if confidence <= 0.25:
        return (
            "This content appears to be human-written with high confidence. "
            "This assessment is based on multiple automated detection signals and is not a guarantee of authorship."
        )

    return (
        "The system could not confidently determine whether this content was "
        "human-written or AI-generated. Readers should treat this label as "
        "additional context rather than a final judgment."
    )

def stylometric_analyzer(text):
    """
    Second detection signal.
    Computes stylometric features and returns an AI-probability score from 0 to 1.
    """

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)

    if word_count == 0:
        return {
            "signal": "stylometric_heuristics",
            "ai_probability": 0.5,
            "features": {},
            "reasoning": "No usable words found, so this signal is uncertain.",
        }

    unique_words = len(set(words))
    type_token_ratio = unique_words / word_count

    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]

    if len(sentence_lengths) > 1:
        avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
        sentence_length_variance = sum(
            (length - avg_sentence_length) ** 2 for length in sentence_lengths
        ) / len(sentence_lengths)
    else:
        avg_sentence_length = sentence_lengths[0] if sentence_lengths else word_count
        sentence_length_variance = 0

    punctuation_count = sum(1 for char in text if char in string.punctuation)
    punctuation_density = punctuation_count / max(len(text), 1)

    score = 0.5

    if sentence_length_variance < 10:
        score += 0.10
    elif sentence_length_variance < 25:
        score += 0.05
    else:
        score -= 0.05

    if type_token_ratio < 0.45:
        score += 0.10
    elif type_token_ratio < 0.60:
        score += 0.05
    else:
        score -= 0.05

    if punctuation_density < 0.035:
        score += 0.07
    else:
        score -= 0.03

    score = max(0.0, min(score, 1.0))

    return {
        "signal": "stylometric_heuristics",
        "ai_probability": round(score, 2),
        "features": {
            "word_count": word_count,
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "sentence_length_variance": round(sentence_length_variance, 3),
            "type_token_ratio": round(type_token_ratio, 3),
            "punctuation_density": round(punctuation_density, 3),
        },
        "reasoning": (
            "Score is based on sentence length variance, vocabulary diversity, "
            "and punctuation density."
        ),
    }


def calculate_confidence(llm_score, stylometric_score):
    """
    planning.md formula:
    combined_ai_probability = (0.65 * llm_score) + (0.35 * stylometric_score)
    """
    combined_score = (0.65 * llm_score) + (0.35 * stylometric_score)
    return round(combined_score, 2)


def classify_attribution(confidence):
    """
    planning.md thresholds:
    0.00–0.25 = likely_human
    0.26–0.74 = uncertain
    0.75–1.00 = likely_ai
    """
    if confidence <= 0.25:
        return "likely_human"
    if confidence >= 0.75:
        return "likely_ai"
    return "uncertain"


@app.route("/submit", methods=["POST"])
@limiter.limit("5 per minute")
def submit():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not isinstance(text, str):
        return jsonify({"error": "Missing or invalid field: text."}), 400

    if not creator_id:
        return jsonify({"error": "Missing required field: creator_id."}), 400

    content_id = str(uuid.uuid4())

    llm_signal = llm_based_classifier(text)
    stylometric_signal = stylometric_analyzer(text)

    llm_score = llm_signal["ai_probability"]
    stylometric_score = stylometric_signal["ai_probability"]

    confidence = calculate_confidence(llm_score, stylometric_score)
    attribution = classify_attribution(confidence)
    label = generate_label(confidence)

    log_event({
        "event_type": "submission",
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "signals": {
            "llm_classifier": llm_signal,
            "stylometric_heuristics": stylometric_signal,
        },
        "status": "classified",
    })

def find_content_by_id(content_id):
    entries = get_log(limit=1000)

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("event_type") == "submission"
        ):
            return entry

    return None

@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    content_id = data.get("content_id")
    appeal_reasoning = data.get("creator_reasoning")

    if not content_id:
        return jsonify({"error": "Missing required field: content_id."}), 400

    if not appeal_reasoning or not isinstance(appeal_reasoning, str):
        return jsonify({"error": "Missing or invalid required field: creator_reasoning."}), 400

    original_decision = find_content_by_id(content_id)

    if not original_decision:
        return jsonify({"error": "No submission found for that content_id."}), 404

    appeal_id = str(uuid.uuid4())
    creator_id = original_decision.get("creator_id")

    log_event({
        "event_type": "appeal",
        "appeal_id": appeal_id,
        "content_id": content_id,
        "creator_id": creator_id,
        "appeal_reasoning": appeal_reasoning,
        "original_attribution": original_decision.get("attribution"),
        "original_confidence": original_decision.get("confidence"),
        "original_llm_score": original_decision.get("llm_score"),
        "original_stylometric_score": original_decision.get("stylometric_score"),
        "status": "under_review",
    })

    return jsonify({
        "appeal_id": appeal_id,
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal submitted for review."
    })

@app.route("/log", methods=["GET"])
def log():
    return jsonify({
        "entries": get_log()
    })

# print(generate_label(0.80))  # high-confidence AI
# print(generate_label(0.10))  # high-confidence human
# print(generate_label(0.50))  # uncertain

if __name__ == "__main__":
    app.run(debug=True)