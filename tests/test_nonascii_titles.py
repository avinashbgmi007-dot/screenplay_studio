"""H2 — non-ASCII project titles must create projects, not 400.

create_project builds the dir name with `str.isalnum()` (Unicode-aware), so a
Telugu/Hindi title survives intact into `safe_name` — but `check_safe_id` is
ASCII-only and 400s. This is the product's core Indian-language audience. Fix:
fold the title to ASCII for the directory name (unicodedata NFKD, keep ASCII
alnum/-/_), and when nothing ASCII survives, fall back to a stable short hash —
the display title (kept in the manifest) is never touched.
"""
from __future__ import annotations

import io

import pytest

SAMPLE = ("Title: T\n\nINT. ROOM - DAY\n\nMARA crosses.\n\nMARA\nWe leave at dawn.\n")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path / "proj"))
    ws.app.config["TESTING"] = True
    return ws.app.test_client()


def _create(client, title):
    return client.post("/api/projects",
                       data={"file": (io.BytesIO(SAMPLE.encode()), "s.fountain"), "title": title},
                       content_type="multipart/form-data")


def test_telugu_title_creates_project(client):
    r = _create(client, "రాత్రి")
    assert r.status_code == 201, r.get_json()


def test_hindi_title_creates_project(client):
    r = _create(client, "रात")
    assert r.status_code == 201, r.get_json()


def test_mixed_tenglish_title_keeps_ascii(client):
    r = _create(client, "Raatri రాత్రి 1")
    assert r.status_code == 201, r.get_json()
    # the ascii part survives into the dir name
    assert "Raatri" in r.get_json()["project"]


def test_two_identical_telugu_titles_get_distinct_dirs(client):
    r1 = _create(client, "రాత్రి")
    r2 = _create(client, "రాత్రి")
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.get_json()["project"] != r2.get_json()["project"]
