"""
Gap 31: another project's details entered a current project's prompt.

Filed: with a synthetic shelf, the real library digest put another project's
TITLE and CHARACTER NAME into a captured fake-client prompt. The digest can also
carry theme findings, and it "can be shed under prompt pressure" — meaning the
inclusion was not even guaranteed, so it was a best-effort leak.

The entry's own words are the design constraint: **"a prompt instruction not to
confuse projects is not a privacy boundary."** `LIBRARY_GROUNDING_GUARD` is an
instruction. The boundary has to be that the digest is never BUILT unless one of
two things is true:

  * the model is on this machine, so nothing leaves the writer's computer — the
    same promise the desk already makes about the script itself; or
  * the writer opted in for THIS project, knowing what goes where.

Default is off. These tests pin the default, both permitted routes, and the fact
that the desk says what it is asking for.
"""

import json
import os

import pytest

from screenplay_cowriter.writer_library import (library_digest_text,
                                                shelf_context_allowed,
                                                shelf_disclosure_text)


class TestTheConsentRule:

    def test_a_remote_model_with_no_opt_in_is_refused(self):
        assert shelf_context_allowed(shared_opt_in=False, model_is_local=False) is False

    def test_a_local_model_still_requires_project_opt_in(self):
        # Locality is useful disclosure, not consent. The writer may not want
        # scripts mixed even when no bytes leave this machine.
        assert shelf_context_allowed(shared_opt_in=False, model_is_local=True) is False
        assert shelf_context_allowed(shared_opt_in=True, model_is_local=True) is True

    def test_an_explicit_opt_in_allows_a_remote_model(self):
        assert shelf_context_allowed(shared_opt_in=True, model_is_local=False) is True

    def test_the_default_arguments_are_deny(self):
        # A caller that forgets to pass anything must get NO, not YES. This is
        # the one signature mistake that would silently restore the defect.
        assert shelf_context_allowed() is False

    def test_the_disclosure_names_the_risk_and_the_remedy(self):
        text = shelf_disclosure_text()
        assert "OTHER scripts" in text
        assert "remote" in text.lower()
        assert "off" in text.lower()

    def test_the_digest_itself_still_does_what_it_does(self):
        # The gate is about WHEN it is built, not about the digest being wrong:
        # it is accurate and useful, which is why it must be reachable.
        text = library_digest_text([{"title": "Pain", "characters": ["RAHUL"],
                                     "scene_count": 4, "source_format": "pdf",
                                     "themes": ["grief"]}])
        assert "Pain" in text and "RAHUL" in text


class TestTheProjectFlagDefaultsOffAndPersists:

    def _manifest(self, tmp_path, sample_fountain):
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest.create(str(tmp_path / "p"), sample_fountain)
        m.save()
        return m

    def test_a_new_project_does_not_share_its_shelf(self, tmp_path, sample_fountain):
        m = self._manifest(tmp_path, sample_fountain)
        assert m.share_shelf_context is False, (
            "a new project shared the writer's other scripts by default")

    def test_the_choice_survives_a_save_and_load(self, tmp_path, sample_fountain):
        from screenplay_studio.manifest import ProjectManifest
        m = self._manifest(tmp_path, sample_fountain)
        m.share_shelf_context = True
        m.save()
        back = ProjectManifest.load(m.project_dir)
        assert back.share_shelf_context is True

    def test_an_old_manifest_without_the_field_reads_as_off(self, tmp_path, sample_fountain):
        # Every project created before this change must not inherit permission.
        from screenplay_studio.manifest import ProjectManifest
        m = self._manifest(tmp_path, sample_fountain)
        m.share_shelf_context = True
        m.save()
        path = m.manifest_path
        data = json.load(open(path, encoding="utf-8"))
        data.pop("share_shelf_context", None)
        json.dump(data, open(path, "w", encoding="utf-8"))
        back = ProjectManifest.load(m.project_dir)
        assert back.share_shelf_context is False


# ---------------------------------------------------------------- end to end
# The filed probe: a synthetic shelf, the REAL library provider, the REAL engine,
# and a fake client that captures the prompt. The assertion is the defect's own
# sentence — another project's title and character name must not be in it.



@pytest.fixture
def shelf(tmp_path, monkeypatch):
    """Two projects on a shelf: the one being chatted with, and 'Pain'."""
    import screenplay_studio.webapp_server as W
    from screenplay_studio.manifest import ProjectManifest

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(W, "PROJECTS_DIR", str(root))
    W.app.config["TESTING"] = True

    def make(name, body):
        src = root / f"{name}.fountain"
        src.write_text(body, encoding="utf-8")
        m = ProjectManifest.create(str(root / name), str(src))
        m.save()
        return m

    mine = make("mine", "INT. ROOM - DAY\n\nMARA\nHello.\n")
    mine_name = os.path.basename(mine.project_dir)
    other = make("pain", "INT. HALL - DAY\n\nRAHUL\nLight banchey!\n")
    # the other project's parse is what the shelf reads for title/cast
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(other.source_path)
    doc.title = "Pain"
    doc.save(other.parsed_path)
    other.mark_complete("parse", {"parsed": other.parsed_path})
    other.save()
    mine.project_label = mine_name
    return mine, other


def _remote(monkeypatch, W):
    """A model that is NOT on this machine.

    `CONFIG` refuses a remote URL outright unless the writer launched with
    `--allow-remote-server` (gap 57's rule), so this is the only state in which a
    remote model exists at all -- and therefore the only state where consent can
    be missing. Patching the flag is what makes that state reachable in a test.
    """
    monkeypatch.setattr(W, "_ALLOW_REMOTE_SERVER", True)
    W.CONFIG["server_url"] = "https://models.example.com/v1"


def _local(monkeypatch, W):
    W.CONFIG["server_url"] = "http://127.0.0.1:8080"


def _library_text_for(mine):
    import screenplay_studio.webapp_server as W
    lib, _case = W._shelf_providers(mine.project_label)
    return lib()


class TestAnotherProjectDoesNotEnterThePromptByDefault:

    def test_the_provider_builds_nothing_for_a_remote_model(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        mine.share_shelf_context = False
        mine.save()
        assert _library_text_for(mine) is None, (
            "another project's digest was built for a remote model with no consent")

    def test_a_local_model_still_requires_opt_in(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _local(monkeypatch, W)
        mine.share_shelf_context = False
        mine.save()
        assert _library_text_for(mine) is None
        mine.share_shelf_context = True
        mine.save()
        assert "PAST WORK" in (_library_text_for(mine) or "")

    def test_consent_is_what_puts_the_other_title_in(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        mine.share_shelf_context = True
        mine.save()
        text = _library_text_for(mine) or ""
        assert "Pain" in text, "an explicit opt-in did not grant the shelf"

    def test_an_unreadable_manifest_is_not_consent(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        monkeypatch.setattr(W, "_load_manifest",
                            lambda name: (_ for _ in ()).throw(OSError("gone")))
        assert _library_text_for(mine) is None


class TestTheBoundaryHoldsWhereItIsUsed:
    """The doctor's case file is the SAME cross-project block shape, and the two
    must never disagree — a disagreement is how one of them becomes the leak."""

    def test_the_case_file_is_gated_by_the_same_predicate(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        mine.share_shelf_context = False
        mine.save()
        built = []
        monkeypatch.setattr(W, "_build_doctor_case_file", lambda exclude: built.append(exclude) or "aggregate")
        _lib, case = W._shelf_providers(mine.project_label)
        assert case() is None, (
            "the doctor still aggregated other projects for a remote model with "
            "no consent")
        assert built == [], "the doctor aggregated other projects before checking consent"

    def test_the_case_file_appears_under_consent(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        mine.share_shelf_context = True
        mine.save()
        built = []
        monkeypatch.setattr(W, "_build_doctor_case_file", lambda exclude: built.append(exclude) or "aggregate")
        _lib, case = W._shelf_providers(mine.project_label)
        assert case() == "aggregate"
        assert built == [mine.project_label]


class TestTheConsentSettingRoute:
    """The API persists a typed boolean, never truthy strings or implicit consent."""

    def test_the_route_saves_and_returns_the_choice(self, shelf):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        client = W.app.test_client()
        name = mine.project_label
        response = client.post(f"/api/projects/{name}/shelf-sharing", json={"enabled": True})
        assert response.status_code == 200
        assert response.get_json()["share_shelf_context"] is True
        assert W._load_manifest(name).share_shelf_context is True

    def test_the_route_rejects_a_truthy_string(self, shelf):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        response = W.app.test_client().post(
            f"/api/projects/{mine.project_label}/shelf-sharing", json={"enabled": "yes"})
        assert response.status_code == 400
        assert W._load_manifest(mine.project_label).share_shelf_context is False

    def test_the_local_preview_shows_exact_project_scope_before_opt_in(self, shelf):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        response = W.app.test_client().get(
            f"/api/projects/{mine.project_label}?shelf_preview=1")
        assert response.status_code == 200
        entries = response.get_json()["shelf_preview"]
        assert any(row["title"] == "Pain" for row in entries)
        row = next(row for row in entries if row["title"] == "Pain")
        assert "RAHUL" in row["characters"]


class TestRevocationTakesEffectOnTheNextPrompt:

    def test_an_already_loaded_session_does_not_keep_old_consent(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _remote(monkeypatch, W)
        mine.share_shelf_context = True
        mine.save()
        library, case = W._shelf_providers(mine.project_label)
        # Simulate the writer revoking after the session/engine was loaded but
        # before its next prompt build. Deferred providers must re-read consent.
        mine.share_shelf_context = False
        mine.save()
        assert library() is None
        assert case() is None


class TestTheActualEnginePromptBoundary:
    """The filed defect was prompt inclusion. Exercise the actual engine, not
    merely the provider: the unsafe title/cast must be absent unless consented."""

    class Client:
        def __init__(self):
            self.messages = None

        def chat(self, messages, **kwargs):
            self.messages = messages
            return "Noted."

        def chat_stream(self, messages, on_token=None, **kwargs):
            if on_token:
                on_token("Noted.")
            self.messages = messages
            return "Noted."

    def _send(self, mine):
        from screenplay_cowriter.context import ReportContext, ScriptContext
        from screenplay_cowriter.engine import CoWriterEngine
        from screenplay_cowriter.models import Session
        import screenplay_studio.webapp_server as W

        library, case = W._shelf_providers(mine.project_label)
        client = self.Client()
        engine = CoWriterEngine(client, ScriptContext(None), ReportContext(None),
                                writer_library_text=library, doctor_case_text=case)
        engine.send_message(Session.new(title="t"), "hello")
        return "\n".join(m["content"] for m in client.messages)

    def test_the_other_project_is_absent_from_a_real_prompt_without_opt_in(
            self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _local(monkeypatch, W)
        mine.share_shelf_context = False
        mine.save()
        prompt = self._send(mine)
        assert "Pain" not in prompt and "RAHUL" not in prompt

    def test_the_other_project_is_present_only_after_opt_in(self, shelf, monkeypatch):
        import screenplay_studio.webapp_server as W
        mine, _other = shelf
        _local(monkeypatch, W)
        mine.share_shelf_context = True
        mine.save()
        from screenplay_studio.webapp_server import _shelf_providers
        direct = _shelf_providers(mine.project_label)[0]()
        prompt = self._send(mine)
        assert "Pain" in prompt and "RAHUL" in prompt, ("direct=" + repr(direct) + "\n" + prompt[:5000])
