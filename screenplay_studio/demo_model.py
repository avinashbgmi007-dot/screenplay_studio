"""
Built-in DEMO model server — a llama-server look-alike for testing the whole
desk without a local GGUF. OpenAI-compatible subset:

    GET  /v1/models                -> one model: demo-craft-model
    POST /v1/chat/completions      -> non-streaming AND streaming (SSE)

The analysis branches mirror tests/mock_unified_server.py category-for-category,
so Run Analysis produces a REAL full report (findings, coverage, logline test,
dials, setup/payoff ledger) against the demo model. Conversational turns get a
grounded, keyword-aware Sameer reply that reads the script map and report the
same way the real model would.

This is OPT-IN: `python -m screenplay_studio.webapp_server --demo-model` or
env SCREENPLAY_STUDIO_DEMO_MODEL=1. The default connection flow
(localhost:8080 llama-server) is never touched.

Deliberately NOT shared with tests/mock_unified_server.py: that file's exact
reply shapes are pinned by 500+ tests; this module stays free to evolve for
good live-demo UX.
"""

from __future__ import annotations

import json
import re
import threading

from flask import Flask, Response, jsonify, request

MODEL_ID = "demo-craft-model"

demo_app = Flask("screenplay-studio-demo-model")


def _scene_numbers_in_prompt(text: str) -> list:
    return sorted(set(int(n) for n in re.findall(r"Scene (\d+)", text)))


def _script_map_lines(system: str) -> dict:
    """Scene number -> heading, parsed from the SCRIPT MAP block Sameer rides
    every turn — lets demo chat replies ground on real headings."""
    out = {}
    for m in re.finditer(r"Scene (\d+)\s*[—–-]\s*(.+)", system):
        out[int(m.group(1))] = m.group(2).strip().rstrip("]").strip()[:70]
    return out


def _findings_count(system: str) -> int:
    return system.count("- (")


def _mood_facts(system: str) -> dict:
    """Pull the deterministic room-state facts (days since visit, drafts,
    edits) out of the mood block, so demo replies can color their energy with
    the same facts a real model would receive."""
    out = {}
    m = re.search(r"Last desk visit: (.+?)\.?$", system, re.MULTILINE)
    if m:
        out["visit"] = m.group(1).strip()
    m = re.search(r"(\d+) draft\(s\) on file; (\d+) line edit", system)
    if m:
        out["drafts"], out["edits"] = int(m.group(1)), int(m.group(2))
    return out


def _case_facts(system: str) -> dict:
    """Pull the case-file numbers (followthrough %, recurring categories) the
    doctor's card carries."""
    out = {}
    m = re.search(r"Followthrough: (\d+) of (\d+) findings addressed(?: via edits)? \((\d+)%\)", system)
    if m:
        out["addressed"], out["total"], out["pct"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"Recurring open HIGH findings across scripts: ([^.]+).", system)
    if m:
        out["recurring"] = m.group(1).strip()
    return out


# ---- mirror sets: Sameer and the doctor in the writer's own register --------
# Small but REAL template sets (2-3 openers/questions each) so the desk can
# demonstrate language support without a real model. Facts (scene names,
# findings) interpolate exactly like the English templates.

_MIRROR_SAMEER_SCENE = {
    "te": [
        "Nuvvu {heads} meedha paddav -- good instinct, aa stretch chala work chestundi.",
        "{heads} gurinchi adugutunnav kada -- akkada em jarugutundo naku kuda telusu.",
    ],
    "hi": [
        "Tum {heads} pe baithe ho -- sahi instinct, wahan hisaab barabar hai.",
        "{heads} ka sawaal poocha hai tumne -- us stretch mein jaan hai.",
    ],
}
_MIRROR_SAMEER_GENERIC = {
    "te": [
        "Pick okkate konchem: ee lo eedi nagging ga unnado -- report kadu, nee instinct. Danni followiddaam.",
        "Naa honest take kavali ante cheppu -- kaani mundu nuvvu cheppu: neeku ye part baaga ledu anipistundi?",
    ],
    "hi": [
        "Ek hi cheez pakad: isme sabse zyada kya khatak raha hai -- report nahi, tera instinct. Wahi asli hai.",
        "Mera honest take chahiye toh pehle tu bata: kaunsa hissa tujhe sabse kam pasand hai?",
    ],
}
_MIRROR_DOCTOR = {
    "te": [
        "Verdict mundu: ee material connective tissue la undi -- function avtundi, kaani place ni earn cheyyatledu.",
        "Na diagnosis simple: structure work avtundi, emotional logic ledu. Fix Sameer department.",
    ],
    "hi": [
        "Verdict pehle: ye material sirf jodne ka kaam kar raha hai -- chalta hai, chamakta nahi.",
        "Meri diagnosis seedhi hai: structure theek hai, emotional logic missing. Fix Sameer ka department.",
    ],
}

_MIRROR_PROBE_OPENERS_TE_SCRIPT = [
    "\u0c2a\u0c47\u0c1c\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3e\u0c28\u0c41 -- \u0c2e\u0c33\u0c4d\u0c32\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3f \u0c1a\u0c46\u0c2a\u0c4d\u0c2a\u0c28\u0c41. \u0c28\u0c28\u0c4d\u0c28\u0c41 \u0c06\u0c2a\u0c47\u0c38\u0c4d\u0c24\u0c41\u0c28\u0c4d\u0c28\u0c26\u0c3f \u0c12\u0c15\u0c4d\u0c15\u0c47: {focus}.",
    "\u0c38\u0c30\u0c47, \u0c2a\u0c47\u0c1c\u0c40 \u0c28\u0c3e \u0c15\u0c33\u0c4d\u0c32\u0c32\u0c4b \u0c2a\u0c21\u0c3f\u0c02\u0c26\u0c3f. \u0c15\u0c3e\u0c28\u0c40 {focus} -- \u0c05\u0c26\u0c3f \u0c0e\u0c35\u0c30\u0c3f \u0c15\u0c4b\u0c38\u0c02?",
]
_MIRROR_PROBE_QUESTIONS_TE_SCRIPT = [
    "{focus} \u0c1c\u0c30\u0c3f\u0c17\u0c3f\u0c24\u0c47 -- \u0c06\u0c21\u0c3f\u0c2f\u0c28\u0c4d\u0c38\u0c4d \u0c0f\u0c02 \u0c2b\u0c40\u0c32\u0c4d \u0c05\u0c35\u0c4d\u0c35\u0c3e\u0c32\u0c3f? \u0c05\u0c26\u0c47 \u0c2e\u0c3f\u0c17\u0c3f\u0c32\u0c3f\u0c28 \u0c05\u0c02\u0c24\u0c3e decide \u0c1a\u0c47\u0c38\u0c4d\u0c24\u0c41\u0c02\u0c26\u0c3f.",
    "{focus} \u0c24\u0c2a\u0c4d\u0c2a\u0c41 \u0c05\u0c2f\u0c3f\u0c24\u0c47 \u0c0f\u0c02 break \u0c05\u0c35\u0c41\u0c24\u0c41\u0c02\u0c26\u0c3f? Idea real test \u0c06 step \u0c26\u0c3e\u0c1f\u0c3f \u0c09\u0c02\u0c1f\u0c41\u0c02\u0c26\u0c3f.",
]
_MIRROR_PROBE_OPENERS_HI_SCRIPT = [
    "\u092a\u0947\u091c \u092a\u0922\u093c \u0932\u093f\u092f\u093e -- \u0935\u093e\u092a\u0938 \u0938\u0941\u0928\u093e\u0928\u0947 \u0935\u093e\u0932\u093e \u0915\u093e\u092e \u0928\u0939\u0940\u0902 \u0915\u0930\u0924\u093e. \u092e\u0941\u091d\u0947 \u0905\u091f\u0915 \u0930\u0939\u093e \u0939\u0948 \u090f\u0915 \u091c\u0917\u0939: {focus}.",
    "\u0920\u0940\u0915 \u0939\u0948, \u092a\u0947\u091c \u0926\u093f\u092e\u093e\u0917\u093c \u092e\u0947\u0902 \u0939\u0948. \u092a\u0930 {focus} -- \u092f\u0947 \u0915\u093f\u0938 \u0915\u0947 \u0932\u093f\u090f \u0939\u0948?",
]
_MIRROR_PROBE_QUESTIONS_HI_SCRIPT = [
    "{focus} \u0939\u094b\u0924\u0947 \u0935\u0915\u094d\u0924 \u0911\u0921\u093f\u092f\u0902\u0938 \u0915\u094b \u0915\u094d\u092f\u093e \u092e\u0939\u0938\u0942\u0938 \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f? \u0935\u0939\u0940 \u0938\u092c \u0915\u0941\u091b \u0924\u092f \u0915\u0930\u0924\u093e \u0939\u0948.",
    "\u092c\u0924\u093e\u0913, {focus} \u0917\u0932\u0924 \u0939\u094b \u091c\u093e\u090f \u0924\u094b \u0915\u094d\u092f\u093e \u091f\u0942\u091f\u0947\u0917\u093e? \u0905\u0938\u0932\u0940 \u091f\u0947\u0938\u094d\u091f \u0909\u0938\u0915\u0947 \u0925\u094b\u0921\u093c\u093e \u0906\u0917\u0947 \u0939\u0948.",
]
_MIRROR_SAMEER_GENERIC_TE_SCRIPT = [
    "\u0c12\u0c15\u0c4d\u0c15\u0c1f\u0c3f \u0c2a\u0c1f\u0c4d\u0c1f\u0c41\u0c15\u0c4b: \u0c08 \u0c10\u0c21\u0c3f\u0c2f\u0c3e\u0c32\u0c4b \u0c28\u0c40\u0c15\u0c41 \u0c2c\u0c3e\u0c17\u0c3e \u0c28\u0c1a\u0c4d\u0c1a\u0c28\u0c3f \u0c2d\u0c3e\u0c17\u0c02 \u0c0f\u0c26\u0c3f? \u0c30\u0c3f\u0c2a\u0c4b\u0c30\u0c4d\u0c1f\u0c4d \u0c15\u0c3e\u0c26\u0c41 -- \u0c28\u0c40 instinct.",
    "\u0c28\u0c3e honest take \u0c15\u0c3e\u0c35\u0c3e\u0c32\u0c3e? \u0c2e\u0c41\u0c02\u0c26\u0c41 \u0c28\u0c41\u0c35\u0c4d\u0c35\u0c41 \u0c1a\u0c46\u0c2a\u0c4d\u0c2a\u0c41 -- \u0c0e\u0c15\u0c4d\u0c15\u0c21 \u0c15\u0c4a\u0c30\u0c24 \u0c05\u0c28\u0c3f\u0c2a\u0c3f\u0c38\u0c4d\u0c24\u0c41\u0c02\u0c26\u0c3f?",
]
_MIRROR_SAMEER_GENERIC_HI_SCRIPT = [
    "\u090f\u0915 \u091a\u0940\u091c\u093c \u092a\u0915\u0921\u093c: \u0907\u0938\u092e\u0947\u0902 \u0938\u092c\u0938\u0947 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u0915\u094d\u092f\u093e \u0916\u091f\u0915 \u0930\u0939\u093e \u0939\u0948 -- \u0930\u093f\u092a\u094b\u0930\u094d\u091f \u0928\u0939\u0940\u0902, \u0905\u092a\u0928\u093e instinct.",
    "\u092e\u0947\u0930\u093e honest take \u091a\u093e\u0939\u093f\u090f \u0924\u094b \u092a\u0939\u0932\u0947 \u0924\u0942 \u092c\u0924\u093e: \u0915\u094c\u0928 \u0938\u093e \u0939\u093f\u0938\u094d\u0938\u093e \u0938\u092c\u0938\u0947 \u0915\u092e\u091c\u093c\u094b\u0930 \u0932\u0917\u0924\u093e \u0939\u0948?",
]
_MIRROR_DOCTOR_TE_SCRIPT = [
    "\u0c24\u0c40\u0c30\u0c4d\u0c2a\u0c41 \u0c2e\u0c41\u0c02\u0c26\u0c41: \u0c08 \u0c2e\u0c46\u0c1f\u0c40\u0c30\u0c3f\u0c2f\u0c32\u0c4d \u0c1c\u0c4b\u0c21\u0c3f\u0c02\u0c1a\u0c47 \u0c2a\u0c28\u0c3f \u0c2e\u0c3e\u0c24\u0c4d\u0c30\u0c2e\u0c47 \u0c1a\u0c47\u0c38\u0c4d\u0c24\u0c4b\u0c02\u0c26\u0c3f -- \u0c28\u0c21\u0c41\u0c38\u0c4d\u0c24\u0c41\u0c02\u0c26\u0c3f, \u0c2a\u0c4d\u0c30\u0c3e\u0c23\u0c02 \u0c32\u0c47\u0c26\u0c41.",
    "\u0c28\u0c3e diagnosis \u0c38\u0c4d\u0c2a\u0c37\u0c4d\u0c1f\u0c02: structure \u0c38\u0c30\u0c3f\u0c17\u0c4d\u0c17\u0c3e \u0c09\u0c02\u0c26\u0c3f, emotional logic \u0c32\u0c47\u0c26\u0c41. Fix Sameer department.",
]
_MIRROR_DOCTOR_HI_SCRIPT = [
    "\u092b\u0948\u0938\u0932\u093e \u092a\u0939\u0932\u0947: \u092f\u0947 \u092e\u091f\u0940\u0930\u093f\u092f\u0932 \u0938\u093f\u0930\u094d\u092b \u091c\u094b\u0921\u093c\u0928\u0947 \u0915\u093e \u0915\u093e\u092e \u0915\u0930 \u0930\u0939\u093e \u0939\u0948 -- \u091a\u0932\u0924\u093e \u0939\u0948, \u0926\u092e\u0916\u092e \u0928\u0939\u0940\u0902.",
    "\u092e\u0947\u0930\u0940 diagnosis \u0938\u093e\u092b\u093c \u0939\u0948: structure \u0920\u0940\u0915 \u0939\u0948, emotional logic \u0917\u093c\u093e\u092f\u092c. Fix Sameer \u0915\u093e department.",
]


def _mirror_sameer_reply(lang, user, scene_map, asked_scenes, findings, mood, script=None):
    import random as _r
    rng = _r.Random(len(user) + sum(len(v) for v in scene_map.values()))
    if asked_scenes and lang in _MIRROR_SAMEER_SCENE:
        heads = "; ".join(f"scene {n} ({scene_map[n]})" for n in asked_scenes[:1])
        return rng.choice(_MIRROR_SAMEER_SCENE[lang]).format(heads=heads)
    if script == "telugu":
        return rng.choice(_MIRROR_SAMEER_GENERIC_TE_SCRIPT)
    if script == "hindi":
        return rng.choice(_MIRROR_SAMEER_GENERIC_HI_SCRIPT)
    return rng.choice(_MIRROR_SAMEER_GENERIC[lang])


def _mirror_doctor_reply(lang, user, script=None):
    import random as _r
    if script == "telugu":
        return _r.Random(len(user)).choice(_MIRROR_DOCTOR_TE_SCRIPT)
    if script == "hindi":
        return _r.Random(len(user)).choice(_MIRROR_DOCTOR_HI_SCRIPT)
    return _r.Random(len(user)).choice(_MIRROR_DOCTOR[lang])


from screenplay_cowriter.language_mirror import detect_register as _detect_register


def _lang_of(user: str):
    """'te' | 'hi' | None -- which mirror set to use for THIS message."""
    reg = _detect_register(user)
    if reg["script"] == "telugu" or reg["tenglish"]:
        return "te"
    if reg["script"] == "hindi" or reg["hinglish"]:
        return "hi"
    return None


def _sameer_reply(user: str, scene_map: dict, asked_scenes: list, findings: int, mood: dict) -> str:
    parts = []
    if asked_scenes:
        heads = "; ".join(f"scene {n} ({scene_map[n]})" for n in asked_scenes[:2])
        parts.append(f"You're poking at {heads} — good instinct, that stretch is doing real work.")
    elif scene_map:
        first = sorted(scene_map)[0]
        parts.append(f"let me get my bearings: we open at scene {first} ({scene_map[first]}), and I like the footing.")
    if mood.get("visit"):
        parts.append(f"Also — the desk says your last visit was {mood['visit']}. The pages didn't get worse in the gap, but they weren't getting better either. Good to be back.")
    if findings:
        aside = " (and yes, the margins are full of the doctor's handwriting again)" if findings > 3 else ""
        parts.append(f"There are {findings} findings riding along{aside}. Want my honest take on which one actually matters? Because they don't all weigh the same.")
    else:
        parts.append("Here's where I'd push: pick the one thing in this that bugs YOU most — not what a report says, what nags you. That instinct is usually right and we should follow it down.")
    return "\n\n".join(parts)


def _sushruta_reply(user: str, scene_map: dict, asked_scenes: list, findings: int, case: dict) -> str:
    parts = []
    if asked_scenes:
        n = asked_scenes[0]
        parts.append(f"Scene {n}. Verdict first: it functions, and functioning isn't the same as earning its place.")
        parts.append(f"The material is there ({scene_map[n]}) — the question is whether the sequence pays for what it asks of the audience. Right now I'd say it borrows.")
    elif scene_map:
        parts.append(f"{len(scene_map)} scenes on the page. My read stands: competent connective tissue, two or three moments doing more than connecting — and the report's {findings} findings mostly circle the same few habits.")
    if case.get("recurring"):
        parts.append(f"Your shelf confirms it: {case['recurring']} keeps coming back across scripts. That is no longer bad luck; that is a habit.")
    if case.get("total"):
        parts.append(f"Followthrough so far: {case['addressed']} of {case['total']} findings addressed ({case['pct']}%). The notes only work if the pages do.")
    parts.append("Diagnosis delivered. The fix is Sameer's department — though for the record, cutting is also a fix.")
    return "\n\n".join(parts)


_MIRROR_PROBE_OPENERS = {
    "te": [
        "Page chusanu -- malli chadivi cheyyanu. Nannu aapestundi okate: {focus}.",
        "Sare, page naa kallalo padindi. Kani {focus} -- adi evaru kosam?",
    ],
    "hi": [
        "Padh liya page -- wapas sunane wala kaam nahi karta. Mujhe atak raha hai ek jagah: {focus}.",
        "Theek hai, page dimaag mein hai. Par {focus} -- yeh kis ke liye hai?",
    ],
}
_MIRROR_PROBE_QUESTIONS = {
    "te": [
        "Adi jarigite -- audience em feel avvali anukuntunnav? Adi migilina anni decide chestundi.",
        "Adi wrong ayite em break avtundi? Idea real test aa step daati untundi.",
    ],
    "hi": [
        "Wo hote waqt audience ko kya mehsoos hona chahiye? Wahi sab kuch tay karta hai.",
        "Batao, wo galat ho jaye toh kya tootega? Asli test uske thoda aage hai.",
    ],
}


def _idea_probe_reply(system: str, user: str, lang=None, script=None) -> str:
    """Idea-room Sameer: he has READ the page (it rides in his context) and
    responds to what's new — never recites it back. He picks a concrete
    element from the page and asks about the fuzzy part around it."""
    # the page content rides in the PREMISE block as the shared material
    page = ""
    # Capture up to the NEXT top-level section (GROUNDING / IDEA GROUNDING /
    # the language rules) — never past it. Grounding boilerplate must not
    # leak into the focus pool.
    m = (re.search(r"PREMISE \(the shared card[^)]*\):\s*\n(.*?)(?=\n\s*(?:IDEA )?GROUNDING\b|\n\s*PAGE UPDATE\b|\n\s*The writer knows what language|$)", system, re.DOTALL)
         or re.search(r"PREMISE \(the shared card[^)]*\):\s*\n(.*)$", system, re.DOTALL))
    if m:
        page = m.group(1).strip()
    # candidate concrete elements: quoted phrases, Capitalized names, or the
    # longest line — something SPECIFIC to ask about. The TITLE is off-limits:
    # asking about it IS reciting the writer's own label back at them.
    body = "\n".join(page.splitlines()[1:])  # first line = working title
    title = (page.splitlines() or [""])[0].strip()
    focus = None
    def _bad_focus(h: str) -> bool:
        """Reject stop-words, titles, grounding boilerplate, and anything the
        language-meta filter would later strip out of the reply."""
        h = h.strip()
        low = h.lower()
        if any(w in low for w in ("grounding", "premise card", "recite", "pages")):
            return True
        try:
            # language-meta garbage filter (repetition/loop phrases). Lazy
            # import mirrors detect_register above; tolerated absence keeps
            # the demo server usable in stripped-down deployments.
            from screenplay_cowriter.language_meta import _matches_any
            if _matches_any(h):
                return True
        except Exception:
            pass
        return False
    # labeled details ("Her rule: never open the bag...") are the writer
    # telling us what THEY think matters — probe those first
    labeled = re.findall(r"[^.:\n]{0,40}:\s*([^\n]{10,70})", body)
    for pat in (r'"([^"]{4,60})"',
                labeled[-1] if labeled else r"(?!)",
                r"\\b([A-Z][a-z]{2,}(?:\\s[A-Z][a-z]{2,})?)\\b"):
        hits = [h for h in re.findall(pat, body + " " + user) if h.lower() not in
                ("the", "and", "but", "she", "him", "his", "her", "int", "ext")
                and h.strip() != title and not _bad_focus(h)]
        if hits:
            focus = hits[0]
            break
    if not focus:
        lines = [ln.strip() for ln in page.splitlines() if len(ln.strip()) > 20]
        focus = lines[-1][:60] if lines else "the opening image"
    openers = [
        f"I've read the page — I'm not going to read it back to you. The bit I keep snagging on is {focus}.",
        f"Okay, the page is in my head. What won't leave me alone is {focus}.",
    ]
    questions = [
        f"When {focus} happens — what does the writer-of-that-moment WANT the audience to feel right there? Because that choice decides everything downstream.",
        f"Tell me the version where {focus} goes wrong. What breaks? I think the idea's real test lives one step past that.",
        f"Who in this loses something because of {focus}? An idea starts earning its keep the moment someone pays for it.",
    ]
    import random
    rng = random.Random(len(user) + len(page))

    # Mirror mode: the writer wrote in Telugu/Hindi/Tenglish/Hinglish -- the
    # probe stays in THEIR register, focus interpolated as-is.
    if lang:
        f = (focus or "").strip().rstrip(".")
        if not f or "The page is empty" in f:
            # blank page: the premise block's fallback text must never leak
            f = {"te": "ee idea", "hi": "ye idea"}.get(lang, "the idea")
        if script == "telugu":
            openers, questions = (_MIRROR_PROBE_OPENERS_TE_SCRIPT,
                                  _MIRROR_PROBE_QUESTIONS_TE_SCRIPT)
        elif script == "hindi":
            openers, questions = (_MIRROR_PROBE_OPENERS_HI_SCRIPT,
                                  _MIRROR_PROBE_QUESTIONS_HI_SCRIPT)
        else:
            openers, questions = _MIRROR_PROBE_OPENERS[lang], _MIRROR_PROBE_QUESTIONS[lang]
        opener = rng.choice(openers).format(focus=f)
        question = rng.choice(questions).format(focus=f)
        return f"{opener}\n\n{question}"

    # Page-update awareness: a deterministic diff rides in the prompt when the
    # writer edited the page since Sameer's last read. He NOTICES it like a
    # person would -- comments on the new material first.
    upd = re.search(r"ADDED since your last read:\s*\n\s*- \"([^\"]+)\"", system)
    if upd:
        fresh = upd.group(1).strip()
        reactions = [
            f"You've been writing while I was gone -- I see it. This new bit: \"{fresh}\" That's the line that changes things, and I want to sit on it before we talk about anything else.",
            f"Wait -- the page grew since my last read. \"{fresh}\" When did that arrive? Because it reframes everything above it, and I don't say that lightly.",
            f"Noticed the new material the moment I looked back at the page: \"{fresh}\" Good. Now the harder question -- does the rest of the page EARN it?",
        ]
        follow = rng.choice([
            " Where does this leave the character we were worried about?",
            " What made you add it now?",
            " Tell me this came out of the idea and not around it.",
        ])
        return rng.choice(reactions) + follow


    # Selection-first: when the turn carries a highlighted passage (the
    # quote card), THAT is the explicit subject -- engage with it before any
    # other matching.
    qsel = re.search(
        r"The writer selected this passage from [^:\n]+:\s*\n\s*\"([^\"]+)\"", system)
    if qsel:
        picked = qsel.group(1).strip().rstrip(".")[:80]
        reactions = [
            f"You highlighted \"{picked}\" -- good eye. That's the load-bearing line, so let's put weight on it.",
            f"Right, \"{picked}\" Here's my snag: I can't tell yet if it's a promise or a red herring. Which is it?",
            f"\"{picked}\" -- okay. What does the story LOSE if this line were never written? Answer that and we know its job.",
        ]
        import random as _rq
        return _rq.Random(len(user)).choice(reactions)

    # Conversation continuity: when the writer names something ALREADY on the
    # page ("who claimed that brass key?"), engage with THAT — a real co-writer
    # doesn't pretend the last thing you said didn't happen.
    stop = {"that", "this", "what", "when", "where", "which", "think", "about",
            "just", "added", "wrote", "should", "would", "could", "there", "their",
            "and", "the", "for", "her", "his", "she", "him", "you", "are", "was",
            "who", "did", "has", "had", "its", "it's"}
    u_words = [w for w in re.findall(r"[a-z']+", user.lower()) if w not in stop and len(w) >= 3]
    p_low = page.lower()
    # longest n-gram of the writer's words that verbatim appears on the page
    best = ""
    n = len(u_words)
    for i in range(n):
        for j in range(n, i, -1):
            gram = " ".join(u_words[i:j])
            if len(gram) > len(best) and gram in p_low:
                best = gram
                break
    # engage ONLY on something specific: a multi-word phrase or a distinctive
    # single word — never a stray "last"/"line" that also sits on the page
    if best and (len(best.split()) >= 2 or len(best) >= 7):
        named = best[0].upper() + best[1:] if page.lower().startswith(best) else best
        engagements = [
            f"{named}, right. Here's where my head goes: it's doing more work than it looks — the question is whether the writer-of-this-idea knows HOW much.",
            f"You keep circling back to {named} — good instinct. So make it cost something. What does it take from someone before the story ends?",
            f"Right, {named}. I'm not going to hand you an answer; I'll ask the sharper version: if you cut it, what breaks? Sit with that one.",
        ]
        follow = rng.choice([
            " Who benefits from it staying exactly as you wrote it?",
            " And who in this would fight you on it?",
            " What's the version of it that scares you a little?",
        ])
        return rng.choice(engagements) + follow

    body = rng.choice(openers)
    q = rng.choice(questions)
    return f"{body}\n\n{q}"


def _conversational_reply(messages: list) -> str:
    """Persona-distinct conversational replies: Sameer warm and constructive,
    Dr. Sushruta verdict-first and cold. Both ground ONLY in what's actually
    injected into context (scene map, mood facts, case file) — never invented."""
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    # the writer's turn -- NOT the post-history voice reminder that now rides
    # after the history as the final system message
    user = ""
    for _m in reversed(messages):
        if _m.get("role") == "user":
            user = _m["content"]
            break
    if not user:
        user = messages[-1]["content"] if messages else ""
    scene_map = _script_map_lines(system)
    findings = _findings_count(system)
    asked_scenes = [n for n in scene_numbers_in(user) if n in scene_map]
    sys_l = system.lower()
    mood = _mood_facts(system)
    case = _case_facts(system)

    # Persona identity = the card's OPENING LINE (build_system_prompt puts the
    # persona text first). Never a bare name mention: Sameer's bible mentions
    # "Dr. Sushruta" (the friction lines) and would misroute every turn.
    # No model tags in replies — the writer talks to a person, not a pipeline.
    lang = _lang_of(user)
    reg = _detect_register(user) if lang else None
    script = reg["script"] if reg else None
    if "you are dr. sushruta" in sys_l:
        if lang:
            return _mirror_doctor_reply(lang, user, script=script)
        return _sushruta_reply(user, scene_map, asked_scenes, findings, case)
    if "premise doctor" in sys_l:
        return "Before any verdict: what's the movie? Name who I follow and what they want by minute ten. If that answer is sharp, the idea survives; if it isn't, nothing else matters yet."
    if "there is no script yet" in sys_l or "premise (the shared card" in sys_l:
        # Idea room, Sameer's desk: PROBE the page material instead of
        # reciting it — pull a concrete detail from what the writer actually
        # wrote and ask about the part that's still fuzzy.
        return _idea_probe_reply(system, user, lang=lang, script=script)
    if lang:
        return _mirror_sameer_reply(lang, user, scene_map, asked_scenes,
                                    findings, mood, script=script)
    return _sameer_reply(user, scene_map, asked_scenes, findings, mood)


def scene_numbers_in(text: str) -> list:
    return _scene_numbers_in_prompt(text)


@demo_app.route("/v1/models", methods=["GET"])
def models():
    return jsonify({"data": [{"id": MODEL_ID}], "models": [{"name": MODEL_ID}]})


# ---- demo translation: phrase glossary over our own template vocabulary -----
_TRANSLATE_GLOSS = [
    # Tenglish templates
    ("Page chusanu -- malli chadivi cheyyanu.", "I've read the page -- I'm not going to read it back to you."),
    ("Nannu aapestundi okate", "The one thing that snags me is"),
    ("Sare, page naa kallalo padindi", "Okay, the page caught my eye"),
    ("Kani ee idea -- adi evaru kosam?", "But this idea -- who is it for?"),
    ("Adi jarigite -- audience em feel avvali anukuntunnav?", "When that happens -- what should the audience feel?"),
    ("Adi migilina anni decide chestundi.", "That decides everything downstream."),
    ("Adi wrong ayite em break avtundi?", "If it goes wrong, what breaks?"),
    ("Idea real test aa step daati untundi.", "The idea's real test lives one step past that."),
    ("Nuvvu", "You're"),
    ("meedha paddav -- good instinct, aa stretch chala work chestundi.",
     "poking at a stretch that's doing real work."),
]
_TRANSLATE_GLOSS_SCRIPT = [
    ("\u0c2a\u0c47\u0c1c\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3e\u0c28\u0c41 -- \u0c2e\u0c33\u0c4d\u0c32\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3f \u0c1a\u0c46\u0c2a\u0c4d\u0c2a\u0c28\u0c41.",
     "I've read the page -- I'm not going to read it back to you."),
    ("\u0c28\u0c28\u0c4d\u0c28\u0c41 \u0c06\u0c2a\u0c47\u0c38\u0c4d\u0c24\u0c41\u0c28\u0c4d\u0c28\u0c26\u0c3f \u0c12\u0c15\u0c4d\u0c15\u0c47",
     "The one thing that snags me is"),
    ("\u0c38\u0c30\u0c47, \u0c2a\u0c47\u0c1c\u0c40 \u0c28\u0c3e \u0c15\u0c33\u0c4d\u0c32\u0c32\u0c4b \u0c2a\u0c21\u0c3f\u0c02\u0c26\u0c3f",
     "Okay, the page caught my eye"),
    ("\u0c2a\u0c47\u0c1c\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3e\u0c28\u0c41", "I've read the page"),
    ("\u0c05\u0c26\u0c3f \u0c0e\u0c35\u0c30\u0c3f \u0c15\u0c4b\u0c38\u0c02?", "who is it for?"),
    ("\u0c1c\u0c30\u0c3f\u0c17\u0c3f\u0c24\u0c47", "when it happens"),
    ("\u0c06\u0c21\u0c3f\u0c2f\u0c28\u0c4d\u0c38\u0c4d \u0c0f\u0c02 \u0c2b\u0c40\u0c32\u0c4d \u0c05\u0c35\u0c4d\u0c35\u0c3e\u0c32\u0c3f?",
     "what should the audience feel?"),
    ("\u0c24\u0c2a\u0c4d\u0c2a\u0c41 \u0c05\u0c2f\u0c3f\u0c24\u0c47", "if it goes wrong"),
]


# Reverse twins: we own both sides of every demo template, so each English
# rendering maps back into the other registers. Coverage is exactly as good
# as the template bank -- anything outside it passes through unchanged
# (honest, not invented). Real models translate genuinely.
_DEMO_TRANSLATE_REVERSE = {
    "te": [
        ("I've read the page -- I'm not going to read it back to you.",
         "\u0c2a\u0c47\u0c1c\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3e\u0c28\u0c41 -- \u0c2e\u0c33\u0c4d\u0c32\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3f \u0c1a\u0c46\u0c2a\u0c4d\u0c2a\u0c28\u0c41."),
        ("The one thing that snags me is", "\u0c28\u0c28\u0c4d\u0c28\u0c41 \u0c06\u0c2a\u0c47\u0c38\u0c4d\u0c24\u0c41\u0c28\u0c4d\u0c28\u0c26\u0c3f \u0c12\u0c15\u0c4d\u0c15\u0c47"),
        ("Okay, the page caught my eye", "\u0c38\u0c30\u0c47, \u0c2a\u0c47\u0c1c\u0c40 \u0c28\u0c3e \u0c15\u0c33\u0c4d\u0c32\u0c32\u0c4b \u0c2a\u0c21\u0c3f\u0c02\u0c26\u0c3f"),
        ("who is it for?", "\u0c05\u0c26\u0c3f \u0c0e\u0c35\u0c30\u0c3f \u0c15\u0c4b\u0c38\u0c02?"),
        ("what should the audience feel?", "\u0c06\u0c21\u0c3f\u0c2f\u0c28\u0c4d\u0c38\u0c4d \u0c0f\u0c02 \u0c2b\u0c40\u0c32\u0c4d \u0c05\u0c35\u0c4d\u0c35\u0c3e\u0c32\u0c3f?"),
        ("when it happens", "\u0c1c\u0c30\u0c3f\u0c17\u0c3f\u0c24\u0c47"),
        ("if it goes wrong", "\u0c24\u0c2a\u0c4d\u0c2a\u0c41 \u0c05\u0c2f\u0c3f\u0c24\u0c47"),
        ("That decides everything downstream.", "\u0c05\u0c26\u0c3f \u0c2e\u0c3f\u0c17\u0c3f\u0c32\u0c3f\u0c28 \u0c05\u0c28\u0c4d\u0c28\u0c40 \u0c28\u0c3f\u0c30\u0c4d\u0c23\u0c3f\u0c38\u0c4d\u0c24\u0c41\u0c02\u0c26\u0c3f."),
    ],
    "hi": [
        ("I've read the page -- I'm not going to read it back to you.",
         "\u092a\u0947\u091c \u092a\u095d\u094d\u0939 \u0932\u093f\u092f\u093e -- \u0926\u094b\u0939\u0930\u093e\u0915\u0930 \u0928\u0939\u0940\u0902 \u092a\u095d\u094d\u0939\u0942\u0901\u0902\u0917\u093e."),
        ("The one thing that snags me is", "\u092e\u0941\u091d\u0947 \u0905\u091f\u0915\u093e\u090a\u0928\u0947 \u0935\u093e\u0932\u0940 \u090f\u0915 \u092c\u093e\u0924"),
        ("Okay, the page caught my eye", "\u0920\u0940\u0915 \u0939\u0948, \u092a\u0947\u091c \u0928\u0947 \u0927\u094d\u092f\u093e\u0928 \u0916\u0940\u0902\u091a\u093e"),
        ("who is it for?", "\u092f\u0939 \u0915\u093f\u0938\u0915\u0947 \u0932\u093f\u090f \u0939\u0948?"),
        ("what should the audience feel?", "\u0926\u0930\u094d\u0936\u0915 \u0915\u094d\u092f\u093e \u092e\u0939\u0938\u0942\u0938 \u0915\u0930\u0947\u0902?"),
        ("when it happens", "\u091c\u092c \u0910\u0938\u093e \u0939\u094b\u0924\u093e \u0939\u0948"),
        ("if it goes wrong", "\u0905\u0917\u0930 \u0917\u0932\u0924 \u0939\u094b\u0917\u093e"),
        ("That decides everything downstream.", "\u0935\u0939 \u0906\u0917\u0947 \u0915\u0940 \u0939\u0930 \u091a\u0940\u091c \u0924\u092f \u0915\u0930\u0924\u093e \u0939\u0948."),
    ],
    "teng": [
        ("I've read the page", "Page chusanu"),
        ("I'm not going to read it back to you.", "malli chadivi cheppanu."),
        ("The one thing that snags me is", "Nannu aapestundi okate"),
        ("Okay, the page caught my eye", "Sare, page naa kallalo padindi"),
        ("who is it for?", "adi evaru kosam?"),
        ("what should the audience feel?", "audience em feel avvali?"),
        ("when it happens", "adi jarigite"),
        ("if it goes wrong", "adi wrong ayite"),
        ("That decides everything downstream.", "Adi migilina anni decide chestundi."),
    ],
}
_DEMO_TRANSLATE_REVERSE["hing"] = [
    ("I've read the page", "Page padh liya"),
    ("I'm not going to read it back to you.", "dobara padh ke nahin sunaunga."),
    ("The one thing that snags me is", "Mujhe atkaane wali ek baat"),
    ("Okay, the page caught my eye", "Theek hai, page ne dhyan kheencha"),
    ("who is it for?", "ye kis ke liye hai?"),
    ("what should the audience feel?", "audience kya feel kare?"),
    ("when it happens", "jab aisa hota hai"),
    ("if it goes wrong", "agar galat hota hai"),
    ("That decides everything downstream.", "Woh aage ki har cheez tay karta hai."),
]


def _demo_translate(original: str, target: str = "en") -> str:
    """Best-effort rendering of OUR OWN template output in the chosen
    register. target=en runs the existing native->English glossary; every
    other target runs the reverse twins. Anything unrecognized passes
    through unchanged (honest, not invented)."""
    if target in (None, "", "en"):
        out = original
        for te, en in _TRANSLATE_GLOSS + _TRANSLATE_GLOSS_SCRIPT:
            out = out.replace(te, en)
        return out
    pairs = _DEMO_TRANSLATE_REVERSE.get(target)
    if not pairs:
        return original
    # longest phrases first so compound replacements win over fragments
    out = original
    for src_phrase, dst in sorted(pairs, key=lambda pr: -len(pr[0])):
        out = out.replace(src_phrase, dst)
    return out


def _decide_reply(messages: list) -> str:
    """The analyzer/revision branches mirror tests/mock_unified_server.py so a
    full Run Analysis behaves exactly like the tested pipeline."""
    body_system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    system_l = body_system.lower()
    user = messages[-1]["content"] if messages else ""
    scene_nums = _scene_numbers_in_prompt(user)

    def j(**obj):
        return json.dumps(obj)

    if "[TRANSLATE TASK]" in body_system:
        import re as _re
        m = _re.search(r"\[TRANSLATE TARGET: (\w+)\]", body_system)
        return _demo_translate(user, m.group(1) if m else "en")

    if "RELATIONSHIP MEMORY REFRESH" in user:
        return j(detail_level={"value": "deep", "confidence": 0.8},
                 directness={"value": "direct", "confidence": 0.7},
                 probe_appetite={"value": "no_evidence", "confidence": 0.0},
                 pushback_appetite={"value": "no_evidence", "confidence": 0.0},
                 observations=[{"text": "The writer likes to explore character motives at length.",
                                "dimension": "topic_gravity"}])

    if "script doctor proposing a targeted revision" in system_l:
        block = user.split("SCENE TEXT:", 1)[1] if "SCENE TEXT:" in user else user
        lines = [ln.strip() for ln in block.splitlines()
                 if ln.strip() and not ln.strip().startswith("[Scene")]
        target = next((ln for ln in lines if "tell you everything" in ln), lines[0] if lines else "")
        if target:
            return j(replacements=[{"old": target,
                                    "new": "[demo] The line lands quieter now — subtext doing the work."}],
                     note="Demo rewrite: replaced the first dialogue line.")
        return j(replacements=[], note="Nothing to rewrite.")

    if "Summarize each" in body_system:
        return j(summaries=[{"scene_number": n, "summary": f"Scene {n} advances the plot."}
                            for n in scene_nums])
    if "on-the-nose dialogue" in system_l:
        findings = []
        if scene_nums:
            quote = "I'll tell you everything when this is over." if "tell you everything" in user else None
            findings.append({"category": "dialogue", "issue": "Sample dialogue finding.",
                             "why_it_matters": "Says the feeling instead of dramatizing it.",
                             "severity": "low", "scene_refs": [scene_nums[0]],
                             "evidence_quote": quote, "rule_id": None})
        return j(findings=findings)
    if "applying a specific, named dramatic-economy" in system_l:
        upper = user.upper()
        if "REVOLVER" in upper or "GUN" in upper:
            return j(significant=True, paid_off=False,
                     reasoning="Given deliberate visual emphasis, never resolved.")
        return j(significant=False, paid_off=False, reasoning="Ordinary continuity.")
    if "theme and subtext" in system_l:
        refs = scene_nums[:1] if scene_nums else []
        return j(findings=[{"category": "theme", "issue": "Sample theme finding.",
                            "why_it_matters": "Test reasoning.", "severity": "low",
                            "scene_refs": refs, "evidence_quote": None, "rule_id": None}] if refs else [])
    if "character arcs" in system_l:
        refs = scene_nums[-1:] if scene_nums else []
        return j(findings=[{"category": "character", "issue": "Sample character finding.",
                            "why_it_matters": "Test reasoning.", "severity": "low",
                            "scene_refs": refs, "evidence_quote": None, "rule_id": None}] if refs else [])
    if "structure and pacing" in system_l:
        return j(findings=[])
    if "earns its place" in system_l:
        return j(findings=[])
    if "genre specialist checking whether" in system_l:
        return j(findings=[{"category": "genre", "issue": "Sample genre finding.",
                            "why_it_matters": "Test reasoning.", "severity": "low",
                            "scene_refs": [], "evidence_quote": None, "rule_id": None}])
    if "professional script coverage" in system_l:
        return j(logline="A demo logline.", genre="Drama", tone="Serious",
                 one_page_synopsis="A demo synopsis.", strengths=["Clear structure"],
                 weaknesses=["Needs more conflict"], comparable_films=["Example Film"],
                 recommendation="consider")
    if "logline's job is to land" in system_l:
        return j(logline="A demo logline.", signal="workable",
                 what_works="Specific protagonist.", what_muddles="Stakes are vague.",
                 missing="Clear stakes.", tightened="A demo logline, tightened.")
    if "impartial first-time reader" in system_l:
        refs = scene_nums[:1] if scene_nums else []
        return j(reads=[{"character": "MARA", "how_reads": "Resolute and guarded.",
                         "apparent_intent": "Resolute and guarded.", "gap": "Minimal.",
                         "scene_refs": refs, "evidence_quote": None}])
    if "CHARACTER DIALS" in body_system:
        chars = re.findall(r"\n\s*([A-Z][A-Z0-9 .'-]{1,30})\n", user)
        dials = [{"character": c.strip(), "traits": [
            {"trait": "proactive", "score": 7, "scene_refs": scene_nums[:1] or [1], "note": "Demo dial."},
            {"trait": "warm", "score": 4, "scene_refs": scene_nums[:1] or [1], "note": "Demo dial."},
        ]} for c in (chars or ["MARA"])[:2]]
        return j(dials=dials)
    if "setup/payoff audit" in system_l:
        return j(ledger=[
            {"setup": "The revolver", "kind": "object", "setup_scenes": [1, 2],
             "payoff_scenes": None, "status": "dangling", "note": "Never used."},
            {"setup": "The promise", "kind": "theme", "setup_scenes": [2],
             "payoff_scenes": [3] if len(scene_nums) >= 3 else scene_nums[-1:],
             "status": "paid", "note": "Lands."},
        ])

    # none of the structured shapes matched -> conversational turn
    return _conversational_reply(messages)


@demo_app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    content = _decide_reply(messages)

    if body.get("stream"):
        # stream the reply in word-chunks like a real generation would
        pieces = re.findall(r"\S+\s*|\n+", content)
        chunk = max(1, len(pieces) // 6) if pieces else 1

        def generate():
            for i in range(0, len(pieces), chunk):
                frame = json.dumps({"choices": [{"delta": {"content": "".join(pieces[i:i + chunk])}}]})
                yield f"data: {frame}\n\n"
            yield "data: [DONE]\n\n"

        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache"})

    return jsonify({
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "model": MODEL_ID,
    })


_demo_server_lock = threading.Lock()
_demo_server_url: str | None = None


DEMO_PREFERRED_PORT = 8099


def start_demo_server(port: int | None = None) -> str:
    """Start the demo model in a daemon thread. Prefers the stable port 8099
    (so restarts don't orphan anything), falling back to an ephemeral port if
    it's taken. Returns the base URL. Idempotent within a process."""
    global _demo_server_url
    with _demo_server_lock:
        if _demo_server_url:
            return _demo_server_url
        from werkzeug.serving import make_server
        try:
            srv = make_server("127.0.0.1", port if port is not None else DEMO_PREFERRED_PORT,
                              demo_app, threaded=True)
        except (OSError, SystemExit):
            # werkzeug prints its own banner and can raise SystemExit on a busy port
            srv = make_server("127.0.0.1", 0, demo_app, threaded=True)
        url = f"http://127.0.0.1:{srv.server_port}"
        threading.Thread(target=srv.serve_forever, daemon=True,
                         name="demo-llama-server").start()
        _demo_server_url = url
        return url


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Screenplay Studio demo model server")
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()
    print(f"Demo craft model on http://127.0.0.1:{args.port}/v1 — point the desk's "
          f"llama-server URL here to test without a GGUF.")
    demo_app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
