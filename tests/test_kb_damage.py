"""Gaps 119 and 123 — a damaged knowledge base must not lie, and must not kill.

Measured before this fix, with a corrupt `rules/*.json` cold:

* `POST /api/projects/<n>/analyze` → **502** carrying the JSON parser's own
  sentence ("Expecting property name enclosed in double quotes: line 1 column 2")
  and **no reading at all** — even though every deterministic pass and every
  model call would have worked without grounding;
* `GET /api/rules/<id>` → **400** with the same parser text, where a *missing*
  KB gets a designed 503. A 400 reads as "your request was bad" about a file the
  app failed to read;
* `GET /api/health` → **200 `status: ok`**, so the desk could not tell that every
  finding was about to lose its grounding.

And with an EMPTY rules directory (the silent case): the analysis warned on
stderr and put the message in `errors`, which the desk does not render, so the
writer saw a normal report.
"""
import io
import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from knowledge_base import KnowledgeBase, KnowledgeBaseDamaged
from screenplay_analyzer import rules_context as rules_context_mod

SAMPLE = b"""Title: KB Test

INT. STUDY - NIGHT

MARA opens the drawer and finds nothing at all.
"""

RULE_ID = "action_hero_competence"  # ships with the package; asserted real below


@pytest.fixture
def client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    # The caches are never cleared by the app, so a test that damages the KB must
    # start cold and leave the process cold — otherwise it would poison every
    # later test in the same process (which is exactly the staleness bug fixed).
    # Uses the stdlib hooks directly, NOT the app's own helper: a fixture that
    # needs a function introduced by the fix could not run against the pre-fix
    # code, and a test that cannot run pre-fix is not evidence (see critique §31).
    _cold()
    yield webapp_server.app.test_client()
    _cold()


def _cold():
    """Forget any cached KB without depending on post-fix helpers."""
    webapp_server._knowledge_base.cache_clear()
    webapp_server._kb_rule_ids.cache_clear()


def _rules_dir_with(tmp_path, name, content):
    path = tmp_path / name
    path.mkdir()
    (path / "broken.json").write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def damaged_kb(tmp_path, monkeypatch):
    """Point every KB load at a directory holding a corrupt rule file."""
    rules = _rules_dir_with(tmp_path, "rules-damaged", '{"not": "a list"')

    real_init = KnowledgeBase.__init__

    def _init(self, rules_dir=None):
        real_init(self, rules)

    monkeypatch.setattr(KnowledgeBase, "__init__", _init)
    _cold()
    return rules


@pytest.fixture
def empty_kb(tmp_path, monkeypatch):
    """A directory that exists and holds no rules — the silent case."""
    rules = tmp_path / "rules-empty"
    rules.mkdir()

    real_init = KnowledgeBase.__init__

    def _init(self, rules_dir=None):
        real_init(self, str(rules))

    monkeypatch.setattr(KnowledgeBase, "__init__", _init)
    _cold()
    return str(rules)


def _project(client):
    resp = client.post("/api/projects",
                       data={"file": (io.BytesIO(SAMPLE), "kb.fountain"), "title": "KB"},
                       content_type="multipart/form-data")
    return resp.get_json()["project"]


class TestDamageIsReportedNotGuessed:
    def test_the_error_is_typed_and_names_the_directory(self, tmp_path):
        rules = _rules_dir_with(tmp_path, "r", "{oops")
        with pytest.raises(KnowledgeBaseDamaged) as excinfo:
            KnowledgeBase(rules)
        assert excinfo.value.rules_dir == rules
        assert "could not be read" in str(excinfo.value)
        assert "broken.json" in str(excinfo.value), (
            "the message must say WHICH file, or the operator cannot fix it")

    def test_a_valid_directory_still_loads(self):
        kb = KnowledgeBase()
        assert len(kb.all()) > 0, "the shipped KB must load for this test to mean anything"
        assert kb.get(RULE_ID) is not None, (
            f"'{RULE_ID}' must be a real shipped rule id for the route test")


class TestTheRulesRouteAnswersHonestly:
    def test_a_damaged_kb_is_a_503_not_a_400(self, client, damaged_kb):
        resp = client.get(f"/api/rules/{RULE_ID}")
        assert resp.status_code == 503, (
            "a broken install is not the caller's bad request")
        error = resp.get_json()["error"]
        assert "could not be read" in error
        assert "Expecting property name" not in error.split("(")[0], (
            "the parser's raw sentence must be framed, not served as the answer")

    def test_a_missing_rule_is_still_a_404(self, client):
        resp = client.get("/api/rules/no_such_rule_at_all")
        assert resp.status_code == 404

    def test_a_real_rule_still_resolves(self, client):
        resp = client.get(f"/api/rules/{RULE_ID}")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == RULE_ID


class TestHealthDoesNotClaimHealthItCannotVerify:
    def test_health_reports_a_damaged_kb(self, client, damaged_kb):
        body = client.get("/api/health").get_json()
        assert body["status"] == "degraded"
        assert body["knowledge_base"]["state"] == "damaged"
        assert "could not be read" in body["knowledge_base"]["reason"]

    def test_health_is_ok_with_a_healthy_kb(self, client):
        body = client.get("/api/health").get_json()
        assert body["status"] == "ok"
        assert "knowledge_base" not in body


class TestAnalysisSurvivesADamagedKb:
    def test_the_analysis_still_produces_a_reading(self, client, damaged_kb):
        project = _project(client)
        resp = client.post(f"/api/projects/{project}/analyze", json={})
        assert resp.status_code == 200, (
            "a grounding fault must not cost the writer their reading")
        report = client.get(f"/api/projects/{project}/report")
        assert report.status_code == 200, "the report must still be servable"

    def test_the_writer_is_told_in_the_report(self, client, damaged_kb):
        project = _project(client)
        client.post(f"/api/projects/{project}/analyze", json={})
        report = client.get(f"/api/projects/{project}/report").get_json()
        notices = " | ".join(report.get("notices") or [])
        assert "could not be read" in notices, (
            "stderr is not the writer's desk — the degradation belongs in notices")

    def test_an_empty_rules_directory_is_also_announced(self, client, empty_kb):
        project = _project(client)
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200
        report = client.get(f"/api/projects/{project}/report").get_json()
        notices = " | ".join(report.get("notices") or [])
        assert "ZERO rules" in notices, (
            "an ungrounded report that looks normal is the defect, not the fix")


class TestTheCacheCannotPoisonItself:
    def test_damage_is_not_cached_after_repair(self, client, tmp_path, monkeypatch):
        """A failed KB read must not be remembered: a repaired install has to be
        re-read, or the desk serves an empty rule set until the process restarts.
        The app never cleared these caches, so this is the lock on that door."""
        rules = _rules_dir_with(tmp_path, "r", "{oops")
        real_init = KnowledgeBase.__init__

        def _broken(self, rules_dir=None):
            real_init(self, rules)

        monkeypatch.setattr(KnowledgeBase, "__init__", _broken)
        _cold()
        assert client.get(f"/api/rules/{RULE_ID}").status_code == 503

        # "repaired": the corrupt file becomes valid
        (tmp_path / "r" / "broken.json").write_text("[]", encoding="utf-8")
        monkeypatch.setattr(KnowledgeBase, "__init__", real_init)
        # The route cleared the cache on damage, so this must load the good KB.
        assert client.get(f"/api/health").get_json()["status"] == "ok"

    def test_the_rule_counter_still_answers_for_a_healthy_kb(self, client):
        """`rule_count` exists to tell 'grounding is missing' from 'cannot count',
        and the zero-rules guard reads it. It must keep working after the change.
        (A CONSTRUCTOR failure is a different matter: `RulesContext()` propagates
        `KnowledgeBaseDamaged`, and the pipeline catches it — that is the test
        above, not this one.)"""
        ctx = rules_context_mod.RulesContext()
        assert ctx.rule_count() == len(KnowledgeBase().all()) > 0
