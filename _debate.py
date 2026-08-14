"""Live debate: Sam (co-writer) vs the Premise Doctor (development executive).

Drives a real conversation through the local model using the ACTUAL personas
from personas.py — no special "debate" prompt, just the two rooms talking,
alternating. Neither knows it's an AI (the personas never break the fiction).

Two hard-won lessons from earlier runs with this reasoning-distill model:
1. Feeding the full labeled transcript back each round makes the model echo
   its own earlier phrases ("coffee cools beside me", "what catches?") into
   a cross-turn loop. Each round gets only the immediately-preceding exchange
   plus a relay directive — lean context, less self-echo.
2. The model sometimes spirals into synonym cascades / stuck phrases. Every
   reply is scored (garbage-phrase blacklist + trigram repetition ratio) and
   bad replies are retried with fresh sampling before the next round runs.
"""
import io
import os
import re
import sys
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from screenplay_cowriter.llm_client import LlamaServerClient
from screenplay_cowriter.context import ScriptContext, ReportContext, build_system_prompt
from screenplay_cowriter.language_meta import (
    strip_language_meta, strip_json_wrap, strip_repetition_lines, strip_repeated_blocks,
)

BASE_URL = "http://localhost:8080"
MODEL = "Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-MTP-I-Compact_2.gguf"

client = LlamaServerClient(base_url=BASE_URL, model=MODEL, fallback_to_loaded=True)

# Bare premise card: the idea starts as nothing but Sam's pitch and the card
# is the shared, growing material the whole debate works from.
PREMISE = {"title": "", "logline": "", "premise": "", "questions": ""}

# Phrases this model gets stuck on across long generations — a hit is a
# strong signal the reply is looped garbage, not a genuine take. Also catches
# fiction breaks ("last email", "your editor") — nobody at the desk is writing
# emails.
GARBAGE = [
    "what catches", "feels thin", "coffee cools", "coffee cooling", "end credits roll",
    "theater walls", "projection booth", "balcony seats", "ceiling rafters", "window seat",
    "alive and breathing", "beginning moment zero", "between your hands", "five pitches",
    "half-formed", "wasting another week", "furniture nobody lives", "sitting upstairs",
    "pushing harder", "someone who knows better", "last email", "your editor", "the editor",
    "credits stop rolling", "first thing morning", "having feelings on screen", "pick one",
    "atmosphere and mood", "tomorrow afternoon",
]


def clean(raw: str) -> str:
    t = strip_language_meta(strip_repeated_blocks(strip_repetition_lines(strip_json_wrap(raw or ""))))
    # The loaded model is a reasoning distill: drop leftover thinking traces.
    t = re.sub(r"<\s*?(thinking|reasoning)\s*?>.*?</\s*?(thinking|reasoning)\s*?>", " ", t, flags=re.S)
    t = re.sub(r"^\s*(Thought|Reasoning):.*?(?=\n\n|\Z)", " ", t, flags=re.S)
    t = re.sub(r"\\boxed\{(.*?)\}", r"\1", t, flags=re.S)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def sam_system() -> str:
    return build_system_prompt(ScriptContext(None), ReportContext(None), "writing_partner", "peer", premise=PREMISE)


def doctor_system() -> str:
    return build_system_prompt(ScriptContext(None), ReportContext(None), "premise_doctor", "concept_validation", premise=PREMISE)


def repetition_ratio(text: str) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) < 40:
        return 0.0
    trigrams = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    seen, dups = set(), 0
    for t in trigrams:
        if t in seen:
            dups += 1
        seen.add(t)
    return dups / len(trigrams)


VERDICT_KEYWORDS = ("verdict", "my honest take", "my read", "my take", "recommend",
                    "the one thing", "next step", "commit", "buy", "sold")


def score_reply(text: str, needs_verdict: bool = False) -> float:
    low = text.lower()
    s = 2.0  # positive bias: a clean, focused reply passes unless it's penalized
    for g in GARBAGE:
        if g in low:
            s -= 2.0
    if len(text) < 60:
        s -= 1.5
    if len(text) > 1400:
        s -= 1.5
    s -= repetition_ratio(text) * 3.0
    if needs_verdict and not any(k in low for k in VERDICT_KEYWORDS):
        s -= 2.0
    return s


def turn(system: str, last_exchange: str | None, directive: str, attempt: int = 0) -> str:
    if last_exchange:
        context = f"This is the conversation so far (the last exchange):\n\n{last_exchange}\n\n"
    else:
        context = ""
    extra = (
        "\n\nTry again, from scratch: write it fresh and SHORTER. Do not reuse any phrase "
        "or idea from the text above. ~150 words."
        if attempt > 0 else ""
    )
    user = (
        f"{context}{directive}\n\n"
        "You are talking with the writer in person — a real conversation, not a document. "
        "Reply now, in your own voice, directly to them. Keep it under ~250 words. Write it "
        "fresh — do not repeat, echo, or reuse phrases or imagery from anything above, "
        "including your own earlier replies. Never comment on the format of this "
        "conversation, never refer to it as a debate, and never use email or document "
        "metaphors."
        f"{extra}"
    )
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return clean(client.chat(msgs, max_tokens=700, repeat_penalty=1.4,
                             presence_penalty=0.6, frequency_penalty=0.2,
                             temperature=0.7 + 0.2 * attempt))


thread = []


def exchange(who: str, system: str, directive: str, header: str, needs_verdict: bool = False):
    print(f"\n{'=' * 72}\n{header}\n{'=' * 72}", flush=True)
    last_exchange = None
    if thread:
        prev_who, prev_text = thread[-1]
        last_exchange = f"{prev_who}: {prev_text}"
    reply, best, best_score = None, None, -1e9
    for attempt in range(5):
        reply = turn(system, last_exchange, directive, attempt)
        s = score_reply(reply, needs_verdict=needs_verdict)
        print(f"  [round {len(thread) + 1} attempt {attempt + 1}: score {s:.1f}]", flush=True)
        if s > best_score:
            best, best_score = reply, s
        if s >= 1.0:
            break
    reply = best
    print("\n" + reply, flush=True)
    thread.append((who, reply))


exchange(
    "Sam", sam_system(),
    "You're at the desk with your writer, who has nothing in the hopper and wants to build "
    "something new. They said: \"I've got a scene-shaped hole in my week. Pitch me something "
    "— an idea we can actually build.\" Pitch them ONE genuinely interesting idea, concrete "
    "enough to see, and end by asking what lands for them.",
    "ROUND 1 — Sam pitches the idea",
)

exchange(
    "Premise Doctor", doctor_system(),
    "Sam — the co-writer — just pitched that idea to the writer. The writer brings it to you "
    "for your honest read: what's the hook, is this actually a movie, and where is it thin "
    "right now? End with the one question that matters most.",
    "ROUND 2 — The Premise Doctor's first read",
)

exchange(
    "Sam", sam_system(),
    "The writer took your idea to a script doctor for a read, and that's the note above. Give "
    "the writer YOUR OWN read of the doctor's note — in your own words, your own position, "
    "your own reaction. Do not quote the doctor or re-argue their exact sentences; say what "
    "you actually think is right and wrong about their take, and where you'd strengthen the "
    "idea in response.",
    "ROUND 3 — Sam pushes back",
)

exchange(
    "Premise Doctor", doctor_system(),
    "Sam has responded to your read, above. Where does that leave the idea? Push on whatever "
    "still worries you, and say so plainly if Sam has actually answered it. Then give your "
    "verdict in one tight paragraph: verdict first, the one thing that would fully win you "
    "over, and the one next step for the writer.",
    "ROUND 4 — The Premise Doctor's verdict",
    needs_verdict=True,
)

out_dir = "docs/debates"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"sam-vs-premise-doctor-{date.today().isoformat()}.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"# Sam vs. the Premise Doctor — a live debate\n\n")
    f.write(f"_Generated {date.today().isoformat()} on the local model, "
            f"through the app's real personas. Neither speaker knows it's an AI._\n\n")
    for who, reply in thread:
        f.write(f"\n### {who}\n\n{reply}\n")
print(f"\n\nTranscript saved to {out_path}")
