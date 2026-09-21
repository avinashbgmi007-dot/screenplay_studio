"""The second `rmtree` site — and the retry policy that applies to both.

Two unbounded `shutil.rmtree` calls existed, in two different modules, and the
audit item named only one of them (`delete_project`). The other is
`IdeaStore.delete`, reachable from `DELETE /api/ideas/<id>`: same race, same
partial-delete harm. This file covers it, so the fix is not one call site wide.

The retry is `jsonio.retry_permission` — the project's ONE bounded retry for this
race, already used by the store paths and already tested there. These tests pin
the WIRING, not the policy.

Note the signature they use: a `PermissionError` with **no winerror**. That is
deliberate. The real-world holder is an antivirus scanner or indexer, and the
2026-09-20 decision recorded in `jsonio.py` exists precisely because such a
denial arrives with no winerror at all — "a signature the winerror-only filter
read as a genuine denial and (correctly) refused to retry, leaving the suite
red". A test written against `winerror=32` would pass under that rejected filter
and prove nothing.
"""
import shutil

import pytest

from screenplay_studio import jsonio
from screenplay_studio.ideas import IdeaStore


def _av_style_denial():
    """A PermissionError with NO winerror — the antivirus/indexer signature."""
    return PermissionError(13, "Access is denied")


@pytest.fixture
def store(tmp_path):
    s = IdeaStore(str(tmp_path / "ideas"))
    (tmp_path / "ideas" / "abc12345").mkdir(parents=True)
    (tmp_path / "ideas" / "abc12345" / "idea.json").write_text("{}")
    return s


def test_a_transient_denial_is_retried_and_the_idea_goes(store, tmp_path, monkeypatch):
    real, calls = shutil.rmtree, []

    def flaky(path, *args, **kwargs):
        calls.append(path)
        if len(calls) == 1:
            raise _av_style_denial()
        return real(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", flaky)
    store.delete("abc12345")

    assert len(calls) == 2, "IdeaStore.delete must retry like the project shelf"
    assert not (tmp_path / "ideas" / "abc12345").exists()


def test_a_denial_that_never_clears_still_raises_after_the_budget(store, monkeypatch):
    """Bounded, and not swallowed: a genuinely stuck delete must still fail —
    it is just not fail-fast (the accepted trade in jsonio's docstring)."""
    calls = []

    def always_denied(path, *args, **kwargs):
        calls.append(path)
        raise _av_style_denial()

    monkeypatch.setattr(shutil, "rmtree", always_denied)
    with pytest.raises(PermissionError):
        store.delete("abc12345")

    assert len(calls) == jsonio.retry_permission.__defaults__[0], (
        "it should have used the whole retry budget before giving up")
