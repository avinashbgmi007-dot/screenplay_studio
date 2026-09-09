"""Humanization v2 — persona bibles, deterministic mood, doctor case file,
register guard, and prompt routing.

- Sameer and Dr. Sushruta get full bibles with contrasting stances, quirk
  budgets, cross-character friction, and honest-memory rules.
- Mood = facts from real project data (never model-improvised), injected via
  build_system_prompt(mood_text=...).
- The doctor's case file = cross-project PATTERNS only, routed to
  script_consultant turns ONLY. Sameer never sees it.
- Register guard: the doctor never emits "!", whatever the model feels like.
- Demo model replies are persona-distinct (Sameer vs Sushruta templates).
"""

import io
import json
import os

import pytest

from screenplay_analyzer.report import save_report
from screenplay_cowriter.context import ReportContext, ScriptContext, build_system_prompt
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.reply_transforms import persona_register as _persona_register
from screenplay_parser import parse_screenplay
from screenplay_parser.models import Scene, ScriptDocument
from screenplay_studio.manifest import ProjectManifest

import screenplay_studio.webapp_server as webapp_server


# ---------------------------------------------------------------- bibles

def test_sameer_bible_has_bio_stance_and_quirk_budget():
    p = __import__("screenplay_cowriter.personas", fromlist=["PERSONAS"]).PERSONAS["writing_partner"]
    assert "defense attorney" in p                       # the stance
    assert "sold one scene" in p or "one sold scene" in p  # the biography
    assert "ONE dry aside" in p                          # sarcasm budget
    assert "Sushruta" in p                               # cross-character friction
    assert "fabrication" in p                            # honest-memory rule
    assert "worry about the SCRIPT" in p                 # anxiety = professional stakes


def test_doctor_bible_contrasts_and_register_rule():
    p = __import__("screenplay_cowriter.personas", fromlist=["PERSONAS"]).PERSONAS["script_consultant"]
    assert "guilty until proven innocent" in p           # contrasting stance
    assert "four thousand scripts" in p                  # the biography
    assert "no exclamation marks" in p                   # register rule
    assert "Sameer" in p                                 # friction — he knows his rival exists
    assert "Diagnosis is your job; prescribing rewrites is Sameer's" in p
    assert "fabricated citation" in p                    # honest-memory rule


def test_example_dialogue_carries_the_friction():
    personas = __import__("screenplay_cowriter.personas", fromlist=["PERSONAS"]).PERSONAS
    assert "his cardio" in personas["writing_partner_examples"]      # Sameer needling the doctor
    assert "Sameer defends everything" in personas["script_consultant_examples"]


def test_bible_extensions_keep_pinned_anchors():
    """The v1 anchors other tests rely on must survive the v2 rewrite."""
    personas = __import__("screenplay_cowriter.personas", fromlist=["PERSONAS"]).PERSONAS
    assert "Never invent the pages" in personas["writing_partner"]
    assert "dry wit" in personas["script_consultant"]
    assert "How Sameer talks" in personas["writing_partner_examples"]
    assert "How Dr. Sushruta talks" in personas["script_consultant_examples"]


# ---------------------------------------------------------------- register guard

def test_doctor_never_emits_exclamation_marks():
    assert _persona_register("This works! Really!", "script_consultant") == "This works. Really."


def test_sameer_keeps_his_natural_register():
    assert _persona_register("Bold call! I like it.", "writing_partner") == "Bold call! I like it."


def _engine(client, persona="writing_partner"):
    from screenplay_cowriter.models import Session

    class _Branch:
        active_persona = persona
        active_mode = "peer"
        messages = []
        awaiting_probe = False

    engine = CoWriterEngine(client, ScriptContext(None), ReportContext(None))
    session = Session.new(title="t")
    session.branches[session.current_branch].active_persona = persona
    return engine, session


class _EchoClient:
    def chat(self, messages, **kw):
        return "Unearned ending!"

    def chat_stream(self, messages, on_token=None, **kw):
        return self.chat(messages)


def test_engine_enforces_doctor_register_on_stored_reply():
    engine, session = _engine(_EchoClient(), persona="script_consultant")
    reply = engine.send_message(session, "thoughts?")
    assert "!" not in reply


# ------------------------------------------------- prompt routing

def test_case_file_rides_consultant_turns_only():
    doc = ScriptDocument(title="T", author=None, source_format="fountain", source_filename="x")
    ctx = ScriptContext(None)
    rep = ReportContext(None)
    case = "CASE FILE — patterns"
    mood = "Room state: last visit today."

    sameer = build_system_prompt(ctx, rep, "writing_partner", "peer",
                                 mood_text=mood, doctor_case_text=case)
    doctor = build_system_prompt(ctx, rep, "script_consultant", "evidence_discussion",
                                 mood_text=mood, doctor_case_text=case)
    assert case not in sameer          # Sameer never sees the doctor's lens
    assert case in doctor
    assert mood in sameer and mood in doctor   # both feel the room


def test_prompt_byte_identical_without_new_params():
    doc = ScriptDocument(title="T", author=None, source_format="fountain", source_filename="x")
    ctx, rep = ScriptContext(None), ReportContext(None)
    a = build_system_prompt(ctx, rep, "writing_partner", "peer")
    b = build_system_prompt(ctx, rep, "writing_partner", "peer", mood_text=None, doctor_case_text=None)
    assert a == b


# ------------------------------------------------- webapp: mood + case file

def _make_project(root, name, findings, addressed_quotes_gone=False):
    src = os.path.join(root, f"{name}.fountain")
    with open(src, "w", encoding="utf-8") as f:
        f.write(f"Title: {name}\n\nINT. ROOM - NIGHT\n\nAction.\n\nX\nLine one.\n")
    m = ProjectManifest.create(os.path.join(root, name), src, title=name)
    doc = parse_screenplay(src)
    doc.save(m.parsed_path)
    m.mark_complete("parse", {})
    result_path = m.report_findings_path
    save_report(
        _fake_result(doc, findings),
        m.report_md_path, result_path,
    )
    m.mark_complete("analyze", {"report_findings": result_path})
    return m


def _fake_result(doc, findings):
    from screenplay_analyzer.pipeline import AnalysisResult
    r = AnalysisResult(doc=doc)
    r.findings = [
        {"category": c, "issue": iss, "why_it_matters": "why", "severity": sev,
         "scene_refs": [1], "evidence_quote": quote, "verification": {"status": "no_quote"}}
        for (c, sev, iss, quote) in findings
    ]
    return r


def test_mood_fragment_reports_real_facts(tmp_path):
    src = tmp_path / "s.fountain"
    src.write_text("Title: T\n\nINT. R - NIGHT\n\nAct.\n", encoding="utf-8")
    m = ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")
    m.updated_at -= 3 * 86400  # visited three days ago
    frag = webapp_server._mood_fragment(m)
    assert "3 day(s) ago" in frag
    assert "0 draft(s) on file" in frag
    assert "No analysis has been run yet." in frag


def test_case_file_patterns_across_scripts(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "shelf")
    os.makedirs(webapp_server.PROJECTS_DIR)

    _make_project(webapp_server.PROJECTS_DIR, "Alpha", [
        ("structure", "high", "Sags badly", "Line one."),
        ("dialogue", "low", "Flat line", None),
    ])
    _make_project(webapp_server.PROJECTS_DIR, "Beta", [
        ("structure", "high", "No escalation", "Line one."),
    ])

    case = webapp_server._doctor_case_file()
    assert case and "Scripts analyzed on the shelf: 2" in case
    assert "structure (2 scripts)" in case       # recurring HIGH across scripts
    assert "\u201cAlpha\u201d" in case            # per-script numbers present


def test_case_file_excludes_current_project_and_empty_shelf(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "shelf2")
    os.makedirs(webapp_server.PROJECTS_DIR)
    assert webapp_server._doctor_case_file() is None  # empty shelf -> silent

    _make_project(webapp_server.PROJECTS_DIR, "Gamma", [("theme", "low", "Thin", None)])
    assert webapp_server._doctor_case_file(exclude="Gamma") is None  # excluded -> nothing left


# ------------------------------------------------- demo model personas

def test_demo_replies_are_persona_distinct():
    from screenplay_studio.demo_model import demo_app
    c = demo_app.test_client()
    system = (
        "SCRIPT MAP\nScene 1 - INT. STUDY - NIGHT\nScene 2 - INT. KITCHEN - DAY\n"
        "Room state (facts...):\n- Last desk visit: 4 day(s) ago.\n- 1 draft(s) on file; 2 line edit(s) applied this revision.\n"
        "CASE FILE - notes:\n- Followthrough: 3 of 9 findings addressed (33%).\n"
        "- Recurring open HIGH findings across scripts: structure (2 scripts)."
    )
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": "what about scene 2?"}]

    sameer = c.post("/v1/chat/completions", json={
        "messages": msgs + [{"role": "system", "content": "You are Sameer, co-writing partner"}]}).get_json()
    doctor = c.post("/v1/chat/completions", json={
        "messages": [{"role": "system", "content": system + "\nYou are Dr. Sushruta, an experienced script doctor."},
                     {"role": "user", "content": "what about scene 2?"}]}).get_json()

    s_txt = sameer["choices"][0]["message"]["content"]
    d_txt = doctor["choices"][0]["message"]["content"]
    # no pipeline tags — the writer talks to a person, not a demo label
    assert "demo craft model" not in s_txt and "demo craft model" not in d_txt
    assert "speaking)" not in s_txt and "speaking)" not in d_txt
    assert "4 day(s)" in s_txt                      # Sameer colors energy with the mood fact
    assert "structure (2 scripts)" in d_txt          # the doctor cites his case file
    assert "!" not in d_txt                          # cold register holds even in the demo
