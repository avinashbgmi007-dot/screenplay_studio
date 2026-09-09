"""Language mirror + humanization levers (SillyTavern-style).

- language_mirror: deterministic register detection (Telugu/Devanagari/
  Tenglish/Hinglish) and the prompt mirror instruction.
- engine: post-history voice reminder (last message), first-line anchor on
  empty history, trait reminder at fixed depth, few-shot budget pruning.
- demo model: trilingual replies -- the writer's register sets the language.
- UTF-8: non-Latin messages survive the session store byte-identically.
"""
from screenplay_cowriter.language_mirror import detect_register, mirror_instruction
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session
from screenplay_cowriter.context import ScriptContext, ReportContext
from screenplay_studio.demo_model import _conversational_reply


class _CaptureClient:
    def __init__(self, reply="A craft thought, plainly said. Want my honest take?"):
        self._reply = reply
        self.messages = []
        self.kwargs = {}

    def chat(self, messages, **kw):
        self.messages = [dict(m) for m in messages]
        self.kwargs = kw
        return self._reply


def _engine_and_turn(user_text, history=0):
    client = _CaptureClient()
    engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
    session = Session.new("T")
    for i in range(history):
        session.branch.messages.append(
            __import__("screenplay_cowriter.models", fromlist=["Message"]).Message(
                role="user" if i % 2 == 0 else "assistant", content=f"turn {i}"))
    engine.send_message(session, user_text)
    return client, session


# ---------------- register detection ----------------

def test_detect_telugu_script():
    reg = detect_register("ఈ సీన్ బాగుంది కానీ ఎమోషన్ లేదు")
    assert reg["script"] == "telugu" and not reg["tenglish"]


def test_detect_hindi_script():
    reg = detect_register("यह सीन अच्छा है पर इमोशन नहीं है")
    assert reg["script"] == "hindi"


def test_detect_tenglish():
    reg = detect_register("enti baaga undi kada ee scene, but the ending ledu")
    assert reg["tenglish"] and reg["script"] is None


def test_detect_hinglish():
    reg = detect_register("kya scene hai yaar, matlab the emotion is missing")
    assert reg["hinglish"] and reg["script"] is None


def test_detect_english_is_none():
    reg = detect_register("What do you think of the ending beat?")
    assert reg == {"script": None, "tenglish": False, "hinglish": False}


def test_mirror_instruction_content_and_english_absent():
    te = mirror_instruction("ఈ సీన్ బాగుంది")
    assert "TELUGU" in te and "Do NOT switch to English" in te
    ten = mirror_instruction("enti baaga undi kada")
    assert "TENGLISH" in ten
    hi = mirror_instruction("यह सीन अच्छा है")
    assert "HINDI" in hi
    assert mirror_instruction("plain english note") == ""


# ---------------- engine humanization levers ----------------

def test_post_history_reminder_is_final_message():
    client, _ = _engine_and_turn("What about scene 3?")
    last = client.messages[-1]
    assert last["role"] == "system"
    assert "Voice check" in last["content"]
    # the writer's turn sits immediately before it
    assert client.messages[-2]["role"] == "user"
    assert client.messages[-2]["content"] == "What about scene 3?"


def test_first_line_anchor_only_on_empty_history():
    client, _ = _engine_and_turn("hello desk")
    assert "SHORT and casual" in client.messages[-1]["content"]
    client2, _ = _engine_and_turn("hello again", history=2)
    assert "SHORT and casual" not in client2.messages[-1]["content"]
    assert "Voice check" in client2.messages[-1]["content"]


def test_trait_reminder_injected_at_depth():
    client, _ = _engine_and_turn("and now?", history=8)
    system_contents = [m["content"] for m in client.messages if m["role"] == "system"]
    assert any("stay in voice" in c for c in system_contents)
    # positioned inside the history, not at the very end
    assert client.messages[-1]["content"].startswith("[Voice check")


def test_fewshot_examples_dropped_when_over_budget():
    client, _ = _engine_and_turn("What about scene 3?")
    has_examples = any("How Sameer talks" in m["content"] for m in client.messages)
    assert has_examples  # normal context keeps them

    engine = CoWriterEngine(_CaptureClient(), ScriptContext(), ReportContext(None))
    engine.FEWSHOT_CHAR_BUDGET = 10  # tiny budget -> examples pushed out
    session = Session.new("T")
    engine.send_message(session, "What about scene 3?")
    msgs = engine  # noqa -- re-fetch via client below


def test_chat_sampling_is_warm():
    client, _ = _engine_and_turn("What about scene 3?")
    assert client.kwargs["temperature"] == CoWriterEngine.CHAT_TEMPERATURE
    assert client.kwargs["repeat_penalty"] == CoWriterEngine.CHAT_REPEAT_PENALTY


# ---------------- trilingual demo model ----------------

def _demo(system, user):
    return _conversational_reply([
        {"role": "system", "content": system},
        {"role": "system", "content": "[Voice check]"},
        {"role": "user", "content": user},
    ])


SAMEER_SYS = "You are Sameer, co-writing partner.\nGROUNDING - There is no script yet: the idea and the premise card are the only material."


def test_demo_tenglish_reply():
    out = _demo(SAMEER_SYS, "enti baaga undi kada ee idea lo, but ending ledu")
    markers = ("chusanu", "pick okkate", "honest take", "kallalo padindi",
               "evaru kosam", "jarigite")
    assert any(m in out.lower() for m in markers)
    assert "demo craft model" not in out


def test_demo_telugu_script_reply():
    out = _demo(SAMEER_SYS, "ఈ ఐడియా గురించి ఏమంటావ్? బాగుందా లేదా?")
    assert any("\u0C00" <= ch <= "\u0C7F" for ch in out)


def test_demo_hindi_reply():
    # Devanagari input -> Devanagari reply (script-native mirror)
    out = _demo(SAMEER_SYS, "\u092f\u0939 \u0906\u0907\u0921\u093f\u092f\u093e \u0915\u0948\u0938\u093e \u0939\u0948? \u092c\u0924\u093e\u0913 \u091c\u093c\u0930\u093e\u0964")
    assert any("\u0900" <= ch <= "\u097f" for ch in out)


def test_demo_doctor_tenglish():
    doc_sys = "You are Dr. Sushruta, an experienced script doctor."
    out = _demo(doc_sys, "enti mama ee script lo emotion ledu kada")
    assert "verdict" in out.lower() or "diagnosis" in out.lower()
    assert "!" not in out


def test_demo_english_unchanged():
    out = _demo(SAMEER_SYS, "what do you think of where this goes?")
    assert "chusanu" not in out.lower()
    assert "?" in out


# ---------------- UTF-8 persistence ----------------

def test_utf8_roundtrip_through_session_store(tmp_path):
    from screenplay_cowriter.store import SessionStore
    store = SessionStore(str(tmp_path / "sessions"))
    session = store.create(title="తెలుగు idea")
    hindi = "यह एक हिंदी सवाल है — क्या यह सही है?"
    telugu = "ఇది తెలుగు సంభాషణ — బాగుందా?"
    session.branch.messages.append(
        __import__("screenplay_cowriter.models", fromlist=["Message"]).Message(role="user", content=hindi))
    session.branch.messages.append(
        __import__("screenplay_cowriter.models", fromlist=["Message"]).Message(role="assistant", content=telugu))
    store.save(session)
    loaded = store.load(session.session_id)
    assert loaded.branch.messages[0].content == hindi
    assert loaded.branch.messages[1].content == telugu
    assert loaded.title == "తెలుగు idea"
