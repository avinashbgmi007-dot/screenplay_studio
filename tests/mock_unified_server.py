"""
Unified mock llama-server for end-to-end orchestrator testing. Piece 2 and
Piece 3 each have their own focused mocks for their own unit tests — this
one exists because a real end-to-end run hits the SAME server for both
analysis and chat, and we need one mock that handles both request shapes
to genuinely test the full pipeline rather than just each piece in
isolation again.

Routing logic is intentionally similar to each piece's own mock (same
category-detection keywords for Piece 2, same persona/mode echo pattern
for Piece 3) so behavior stays consistent with what's already
unit-tested — this file doesn't invent new mock behavior, it combines
what's already proven to work.
"""

import json
import re

from flask import Flask, request, jsonify

app = Flask(__name__)
MODEL_ID = "mock-e2e-model.gguf"


def _scene_numbers_in_prompt(text: str) -> list:
    return sorted(set(int(n) for n in re.findall(r"Scene (\d+)", text)))


@app.route("/v1/models", methods=["GET"])
def models():
    return jsonify({"data": [{"id": MODEL_ID}], "models": [{"name": MODEL_ID}]})


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json()
    messages = body["messages"]
    system_texts = [m["content"] for m in messages if m["role"] == "system"]
    system = "\n".join(system_texts)
    user = messages[-1]["content"] if messages else ""
    scene_nums = _scene_numbers_in_prompt(user)

    # ---- Writer relationship memory refresh (Piece 3 v2) ----
    if "RELATIONSHIP MEMORY REFRESH" in user:
        return _reply(json.dumps({
            "detail_level": {"value": "deep", "confidence": 0.8},
            "directness": {"value": "direct", "confidence": 0.7},
            "probe_appetite": {"value": "no_evidence", "confidence": 0.0},
            "pushback_appetite": {"value": "no_evidence", "confidence": 0.0},
            "observations": [{"text": "The writer likes to explore character motives at length.",
                              "dimension": "topic_gravity"}],
        }))

    # ---- Revision loop (Piece 2.5) request shape ----
    if "script doctor proposing a targeted revision" in system.lower():
        block = user.split("SCENE TEXT:", 1)[1] if "SCENE TEXT:" in user else user
        lines = [ln.strip() for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("[Scene")]
        target = "I'll tell you everything when this is over." if any("tell you everything" in ln for ln in lines) else (lines[0] if lines else "")
        if target:
            return _reply(json.dumps({
                "replacements": [{"old": target, "new": "[fixed] The character says something entirely different instead."}],
                "note": "Mock rewrite: replaced the first dialogue line.",
            }))
        return _reply(json.dumps({"replacements": [], "note": "Nothing to rewrite."}))

    # ---- Piece 2 (analyzer) request shapes ----
    if "Summarize each" in system:
        return _reply(json.dumps({"summaries": [
            {"scene_number": n, "summary": f"Scene {n} advances the plot."} for n in scene_nums
        ]}))
    if "on-the-nose dialogue" in system.lower():
        findings = []
        if scene_nums:
            quote = "I'll tell you everything when this is over." if "tell you everything" in user else None
            findings.append({
                "category": "dialogue", "issue": "Sample dialogue finding.",
                "why_it_matters": "Test reasoning.", "severity": "low",
                "scene_refs": [scene_nums[0]], "evidence_quote": quote, "rule_id": None,
            })
        return _reply(json.dumps({"findings": findings}))
    if "applying a specific, named dramatic-economy" in system.lower():
        upper = user.upper()
        if "REVOLVER" in upper or "GUN" in upper:
            return _reply(json.dumps({
                "significant": True, "paid_off": False,
                "reasoning": "Given deliberate visual emphasis, never resolved.",
            }))
        return _reply(json.dumps({
            "significant": False, "paid_off": False,
            "reasoning": "Ordinary continuity.",
        }))
    if "theme and subtext" in system.lower():
        refs = scene_nums[:1] if scene_nums else []
        return _reply(json.dumps({"findings": [{
            "category": "theme", "issue": "Sample theme finding.",
            "why_it_matters": "Test reasoning.", "severity": "low",
            "scene_refs": refs, "evidence_quote": None, "rule_id": None,
        }] if refs else []}))
    if "character arcs" in system.lower():
        refs = scene_nums[-1:] if scene_nums else []
        return _reply(json.dumps({"findings": [{
            "category": "character", "issue": "Sample character finding.",
            "why_it_matters": "Test reasoning.", "severity": "low",
            "scene_refs": refs, "evidence_quote": None, "rule_id": None,
        }] if refs else []}))
    if "structure and pacing" in system.lower():
        return _reply(json.dumps({"findings": []}))
    if "earns its place" in system.lower():
        return _reply(json.dumps({"findings": []}))
    if "genre specialist checking whether" in system.lower():
        return _reply(json.dumps({"findings": [{
            "category": "genre", "issue": "Sample genre finding.",
            "why_it_matters": "Test reasoning.", "severity": "low",
            "scene_refs": [], "evidence_quote": None, "rule_id": None,
        }]}))
    if "professional script coverage" in system.lower():
        return _reply(json.dumps({
            "logline": "A test logline.", "genre": "Drama", "tone": "Serious",
            "one_page_synopsis": "A test synopsis.", "strengths": ["Clear structure"],
            "weaknesses": ["Needs more conflict"], "comparable_films": ["Example Film"],
            "recommendation": "consider",
        }))
    if "logline's job is to land" in system.lower():
        return _reply(json.dumps({
            "logline": "A test logline.", "signal": "workable",
            "what_works": "Specific protagonist.", "what_muddles": "Stakes are vague.",
            "missing": "Clear stakes.", "tightened": "A test logline, tightened.",
        }))
    if "impartial first-time reader" in system.lower():
        refs = scene_nums[:1] if scene_nums else []
        return _reply(json.dumps({"reads": [{
            "character": "MARA", "how_reads": "Resolute and guarded.",
            "apparent_intent": "Resolute and guarded.", "gap": "Minimal.",
            "scene_refs": refs, "evidence_quote": None,
        }]}))

    # ---- Piece 3 (co-writer) request shape: none of the above matched,
    # so this is a conversational turn. Echo context markers, same as
    # Piece 3's own mock, so grounding can still be verified end-to-end. ----
    persona_markers = {
        "film producer": "producer", "development executive": "dev_exec",
        "screenwriting teacher": "teacher", "general moviegoer": "audience",
        "genre specialist": "genre_specialist", "script consultant": "script_consultant",
        "co-writing partner": "writing_partner",
    }
    detected_persona = "unknown"
    for marker, name in persona_markers.items():
        if marker in system.lower():
            detected_persona = name
            break
    findings_count = system.count("- (")
    injected_scenes = re.findall(r"\[Scene (\d+)", system)
    reply = (
        f"[mock chat reply] persona={detected_persona} findings_seen={findings_count} "
        f"injected_scenes={sorted(set(injected_scenes))} | re: {user[:60]}"
    )
    return _reply(reply)


def _reply(content: str):
    return jsonify({
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "model": MODEL_ID,
    })


def main():
    app.run(host="127.0.0.1", port=8196, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
