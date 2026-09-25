"""One log file per desk — the support channel a no-telemetry product needs.

This app sends nothing anywhere. That is the point, and it also means the only
evidence of a failure is what the writer can hand over. Before this module there
was none: a search for `logging.basicConfig` / `getLogger` across all four shipped
packages returned exactly one incidental hit, so a failed analysis left
werkzeug's stderr — which is not captured at all when the app is launched from a
desktop shortcut — and nothing else. BE-3, audit 2026-09-24.

Two deliberate choices:

* **The log sits BESIDE the projects directory, not inside it.** `PROJECTS_DIR`
  is enumerated to build the shelf, and the listing code already has to skip
  `writer_profile.json` and every `<store>.lock` sidecar; a log file in there
  would be a third thing it must know to ignore.
* **Failing to open the log is not fatal.** A desk installed read-only must still
  analyse scripts, so `configure()` returns None instead of raising and the
  startup path reports that in words.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILENAME = "screenplay_studio.log"

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUPS = 3

# The single handler this module owns. Tracked so repeated `main()` calls (which
# happen in tests) cannot leak a handler per call — a leak would mean every later
# log record being written once per call, and one open file handle per tmp dir.
_our_handler: RotatingFileHandler | None = None


def log_path(projects_dir: str) -> str:
    """Where this desk's log lives, given the projects directory it was launched
    with. A sibling of that directory, never a child."""
    return os.path.join(os.path.dirname(os.path.abspath(projects_dir)), LOG_FILENAME)


def configure(projects_dir: str, level: int = logging.INFO) -> str | None:
    """Start logging to a rotating file beside `projects_dir`.

    Returns the path it opened, or None when it could not (a read-only install
    directory, a missing parent). Other handlers already on the root logger are
    left alone — this app is not the only thing that may be logging in the
    process (the test runner, for one).
    """
    global _our_handler
    path = log_path(projects_dir)
    root = logging.getLogger()
    root.setLevel(level)

    if _our_handler is not None:
        current = os.path.abspath(getattr(_our_handler, "baseFilename", "") or "")
        if current == os.path.abspath(path):
            return path
        # Re-pointed at a different desk: drop ours before adding the new one.
        root.removeHandler(_our_handler)
        _our_handler.close()
        _our_handler = None

    try:
        handler = RotatingFileHandler(path, maxBytes=_MAX_BYTES,
                                      backupCount=_BACKUPS, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    _our_handler = handler
    return path


def reset_for_tests() -> None:
    """Detach and close the handler this module owns. Test-only: it keeps one
    test's log file from being held open (and written to) by the next."""
    global _our_handler
    if _our_handler is not None:
        logging.getLogger().removeHandler(_our_handler)
        _our_handler.close()
        _our_handler = None
