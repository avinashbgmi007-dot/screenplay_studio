"""Gap 19 — the Stash must never cut a passage in silence.

Measured before the fix: `add_to_stash(project_dir, "A"*4000 + "TAIL")` saved
exactly 4,000 characters — tail gone — returned an ordinary entry, and the route
answered **201** so the UI said "Stashed ✓". The success record had no field
that could express "this was cut", so no surface could tell the writer. The text
was then the only copy, because the writer had already cleared their selection.

The property these tests pin is not "the bound changed" — the bound is fine and
stays. It is: **nothing is lost without the writer being told.** Text over the
bound is refused with a sentence naming both lengths, and the refusal reaches
the writer through the route rather than being swallowed.
"""
import io
import os

import pytest

from screenplay_studio.stash_store import (
    MAX_TEXT_CHARS,
    add_to_stash,
    entry_truncated,
    load_stash,
)


def _mk_project(client, name):
    r = client.post("/api/projects", content_type="multipart/form-data", data={
        "file": (io.BytesIO(b"Title: t\n\nINT. ROOM - DAY\n\nAction.\n\nANA\nLine.\n"),
                 f"{name}.fountain"),
        "title": name,
    })
    assert r.status_code == 201, r.get_data(as_text=True)[:200]
    return name


@pytest.fixture
def http_client(tmp_path, mock_server):
    from screenplay_studio import webapp_server

    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


# ---------------------------------------------------------------------------
# Store: refuse, never slice
# ---------------------------------------------------------------------------

def test_a_passage_over_the_bound_is_refused_not_cut(tmp_path):
    """The measured defect, exactly: 4,004 characters used to save 4,000."""
    d = str(tmp_path)
    text = "A" * MAX_TEXT_CHARS + "TAIL"

    with pytest.raises(ValueError) as exc:
        add_to_stash(d, text)

    msg = str(exc.value)
    assert "4,004" in msg, f"the refusal must name the actual length: {msg}"
    assert "4,000" in msg, f"the refusal must name the bound: {msg}"
    assert "Nothing was saved and nothing was cut" in msg


def test_a_refused_passage_writes_nothing_at_all(tmp_path):
    """A refusal that still wrote a partial entry would be the same loss with an
    exception attached."""
    d = str(tmp_path)
    with pytest.raises(ValueError):
        add_to_stash(d, "B" * (MAX_TEXT_CHARS + 1))
    assert load_stash(d) == []
    assert not os.path.exists(os.path.join(d, "stash.json")), (
        "a refused entry must not create the store file")


def test_a_passage_exactly_at_the_bound_is_saved_whole(tmp_path):
    """The boundary itself is allowed and must not lose its last character —
    an off-by-one here is a silent trim of one character."""
    d = str(tmp_path)
    text = "C" * (MAX_TEXT_CHARS - 1) + "Z"
    entry = add_to_stash(d, text)
    assert len(entry["text"]) == MAX_TEXT_CHARS
    assert entry["text"].endswith("Z")
    assert load_stash(d)[0]["text"] == text


def test_unicode_is_measured_in_characters_at_the_bound(tmp_path):
    """A multi-byte script must be refused by character count, not bytes, and a
    passage under the bound must survive intact (no re-encoding, no slicing of a
    code point)."""
    d = str(tmp_path)
    ok = "ഹ" * (MAX_TEXT_CHARS - 6) + "അവസാനം"
    assert len(ok) == MAX_TEXT_CHARS
    entry = add_to_stash(d, ok)
    assert entry["text"].endswith("അവസാനം"), "the last glyphs were lost"

    with pytest.raises(ValueError):
        add_to_stash(d, "ഹ" * (MAX_TEXT_CHARS + 1))


def test_the_bound_is_a_named_constant_not_a_buried_slice(tmp_path):
    """The number is shared by the store, the route and the UI. If it goes back
    to being a bare slice in a dict literal, this fails."""
    from screenplay_studio import stash_store
    assert isinstance(stash_store.MAX_TEXT_CHARS, int)
    assert stash_store.MAX_TEXT_CHARS >= 1000, "the bound must be usable for a passage"


# ---------------------------------------------------------------------------
# Legacy entries: reported, never rewritten
# ---------------------------------------------------------------------------

def test_a_legacy_cut_entry_is_reported_as_possibly_incomplete():
    entry = {"text": "x" * MAX_TEXT_CHARS}
    note = entry_truncated(entry)
    assert note is not None
    assert note["length"] == MAX_TEXT_CHARS
    assert note["dropped"] is None, (
        "the old store never recorded the original length — claiming a count "
        "would be a second invention")
    assert "may be missing" in note["note"]


def test_a_normal_entry_is_not_flagged():
    assert entry_truncated({"text": "a short keeper"}) is None


def test_the_route_serves_the_bound_and_flags_a_legacy_entry(http_client):
    """The UI needs the bound to refuse a long selection BEFORE sending it, and
    needs to know when an existing entry was cut by the old code."""
    import json

    name = _mk_project(http_client, "stash_legacy")
    from screenplay_studio import webapp_server
    from screenplay_studio.manifest import ProjectManifest

    m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, name))
    webapp_server.atomic_write_json(
        os.path.join(m.project_dir, "stash.json"),
        [{"id": "old1", "text": "y" * MAX_TEXT_CHARS, "title": "", "scene_number": None,
          "created_at": 1.0},
         {"id": "new1", "text": "short line", "title": "", "scene_number": None,
          "created_at": 2.0}],
    )

    data = http_client.get(f"/api/projects/{name}/stash").get_json()
    assert data["max_text_chars"] == MAX_TEXT_CHARS
    by_id = {e["id"]: e for e in data["stash"]}
    assert "truncated" in by_id["old1"], "a legacy cut entry must be marked"
    assert "truncated" not in by_id["new1"], "a normal entry must not be"
    # The legacy text is served as-is: rewriting it destroys what survived.
    assert by_id["old1"]["text"] == "y" * MAX_TEXT_CHARS


# ---------------------------------------------------------------------------
# Route: the refusal reaches the writer
# ---------------------------------------------------------------------------

def test_the_route_refuses_a_long_passage_with_400_and_a_sentence(http_client):
    """A 201 here was the whole bug: the writer's only signal was "Stashed ✓"."""
    name = _mk_project(http_client, "stash_refuse")
    r = http_client.post(f"/api/projects/{name}/stash",
                         json={"text": "A" * (MAX_TEXT_CHARS + 4)})

    assert r.status_code == 400, r.get_data(as_text=True)[:300]
    err = r.get_json()["error"]
    assert "4,004" in err and "4,000" in err
    assert "Nothing was saved" in err

    # And nothing was written.
    listing = http_client.get(f"/api/projects/{name}/stash").get_json()
    assert listing["stash"] == []


def test_the_route_still_accepts_a_passage_at_the_bound(http_client):
    name = _mk_project(http_client, "stash_ok")
    r = http_client.post(f"/api/projects/{name}/stash", json={"text": "z" * MAX_TEXT_CHARS})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    assert len(r.get_json()["text"]) == MAX_TEXT_CHARS


def test_a_proposal_rewrite_longer_than_the_bound_is_refused_too(http_client):
    """The Stash this route serves is not only the selection float: the rewrite
    panel stashes a proposed replacement, which is model-generated text of
    unknown length. It reaches the same bound — and the same honest refusal."""
    name = _mk_project(http_client, "stash_proposal")
    r = http_client.post(f"/api/projects/{name}/stash", json={
        "text": "rewritten line. " * 400,       # ~6,400 chars
        "title": "Proposed rewrite — scene 2",
        "scene_number": 2,
    })
    assert r.status_code == 400
    assert "Nothing was saved" in r.get_json()["error"]
