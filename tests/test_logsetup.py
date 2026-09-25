"""BE-3 (audit 2026-09-24) — the desk must leave a durable record.

The product ships no telemetry, deliberately. That makes the local log the only
support channel there is: before this, a failed analysis left werkzeug's stderr —
which is not captured at all when the app is launched from a desktop shortcut —
and nothing else. A search for `logging.basicConfig` / `getLogger` across all four
shipped packages returned exactly one incidental hit.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

import pytest

from screenplay_studio import logsetup


@pytest.fixture(autouse=True)
def _clean_handlers():
    """Never let one test's log file stay open into the next one — on Windows an
    open handle also blocks the tmp dir from being removed."""
    yield
    logsetup.reset_for_tests()


class TestWhereTheLogGoes:
    def test_it_is_a_sibling_of_the_projects_directory(self, tmp_path):
        """Not a child: PROJECTS_DIR is enumerated to build the shelf, and the
        listing code already has to skip `writer_profile.json` and every
        `<store>.lock` sidecar. A log in there would be a third exception."""
        path = logsetup.log_path(str(tmp_path / "studio_projects"))
        assert os.path.dirname(path) == str(tmp_path)
        assert os.path.basename(path) == "screenplay_studio.log"

    def test_it_follows_the_projects_directory_it_was_launched_with(self, tmp_path):
        a = logsetup.log_path(str(tmp_path / "one" / "proj"))
        b = logsetup.log_path(str(tmp_path / "two" / "proj"))
        assert a != b
        assert os.path.dirname(a) == str(tmp_path / "one")


class TestConfigure:
    def test_it_opens_the_file_and_records_what_is_logged(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        path = logsetup.configure(str(proj))
        assert path == logsetup.log_path(str(proj))
        logging.getLogger("screenplay_studio.webapp").info("a-recorded-marker")
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert "a-recorded-marker" in open(path, encoding="utf-8").read()

    def test_it_does_not_leak_a_handler_per_call(self, tmp_path):
        """`main()` is called repeatedly in tests. A handler per call would mean
        every later record written once per call, and one open handle per tmp
        directory — which on Windows also blocks that directory's removal."""
        for name in ("a", "b", "c"):
            (tmp_path / name).mkdir()
            logsetup.configure(str(tmp_path / name / "proj"))
        ours = [h for h in logging.getLogger().handlers
                if isinstance(h, RotatingFileHandler)]
        assert len(ours) == 1, f"{len(ours)} rotating handlers attached — leaked"
        assert logsetup.log_path(str(tmp_path / "c" / "proj")) in ours[0].baseFilename

    def test_re_configuring_the_same_desk_is_a_no_op(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        first = logsetup.configure(str(proj))
        handler = logsetup._our_handler
        assert logsetup.configure(str(proj)) == first
        assert logsetup._our_handler is handler

    def test_an_unwritable_location_returns_none_instead_of_raising(self, tmp_path):
        """A desk installed read-only must still analyse scripts."""
        assert logsetup.configure(str(tmp_path / "does-not-exist" / "proj")) is None


class TestTheErrorHandlerRecordsIt:
    def test_an_unhandled_error_lands_in_the_log(self, tmp_path):
        import screenplay_studio.webapp_server as ws

        proj = tmp_path / "proj"
        proj.mkdir()
        path = logsetup.configure(str(proj))
        with ws.app.test_request_context("/api/boom", method="GET"):
            body, status = ws._unhandled(RuntimeError("kaboom-marker"))
        assert status == 500
        assert body.get_json()["error"].endswith("kaboom-marker")
        for handler in logging.getLogger().handlers:
            handler.flush()
        recorded = open(path, encoding="utf-8").read()
        assert "kaboom-marker" in recorded, "the failure left no durable record"
        assert "/api/boom" in recorded, "the record does not say which route failed"

    def test_an_http_exception_is_not_logged_as_an_error(self, tmp_path):
        """404/405 are part of the API's contract, not failures — logging them
        would bury the real ones."""
        from werkzeug.exceptions import NotFound
        import screenplay_studio.webapp_server as ws

        proj = tmp_path / "proj"
        proj.mkdir()
        path = logsetup.configure(str(proj))
        with ws.app.test_request_context("/nope", method="GET"):
            assert ws._unhandled(NotFound()) is not None
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert "NotFound" not in open(path, encoding="utf-8").read()
