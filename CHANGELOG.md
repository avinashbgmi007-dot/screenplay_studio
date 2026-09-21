# Changelog

Notable changes to Script Doctor Studio. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project has no
release tags yet, so entries are dated rather than versioned.

The full engineering record — including the reproduced evidence behind each
fix — lives in `docs/audit/` (`FIX_TRACKER.md` is the live status table).

## [Unreleased]

### Security

- **Stored XSS in the SPA is closed.** Every interpolating `innerHTML` sink now
  routes through one canonical `escapeHtml()`, the five inline `onclick`
  handlers became delegated `data-*` listeners, and the SPA is served under a
  CSP with no `unsafe-inline` and no `eval`. Previously a script could be
  planted in project data and steal the capability token.
- **The server URL is now loopback-only.** A remote `server_url` used to make
  the app post a writer's script to any host on the network. Six entry points
  validate it; remote hosts require a process-level opt-in that cannot be
  granted over HTTP.

### Fixed

- **Cross-process write tearing.** `atomic_write_json` was atomic against
  readers but not against other writers: the lock was a process-local
  `RLock`, so two processes could interleave. It now takes an OS byte-range
  lock, writes to a unique temp name, and `fsync`s before the rename.
  Reproduced before the fix with 358 of 508 edits lost.
- **A damaged store no longer reads as an empty one.** `edits.json`,
  `edits.redo.json`, and the other writer-owned stores distinguish *missing*
  from *present-but-unreadable*; the latter answers `503 {"unreadable": true}`
  instead of telling the writer "Nothing to redo." and then overwriting the
  only recoverable copy.
- **A transient read error is no longer reported as permanent damage.**
- **Finding ids agree across the boundary.** The browser and the server hashed
  by UTF-16 code unit and by code point respectively, so ids diverged on
  non-BMP characters and dismissals failed to match.
- **Asset cache-busting is derived, not hand-maintained.** Every `?v=` token in
  the served document is rewritten to that asset's content hash, so editing a
  file invalidates its URL with no build step and no human step.

### Changed

- **Dependencies are pinned.** `requirements.lock.txt` records exact versions
  for the whole declared dependency closure and CI installs with it as a
  constraints file, so a green build means the same versions everywhere.
- **CI pins its linter** (`ruff==0.16.8`) instead of installing whatever is
  latest, so a new ruff release cannot fail a green build.
- **Every CI job declares a timeout.** An unbounded job inherits the platform
  default of 360 minutes.
- **Route coverage is a gate.** `tests/route_coverage.py` requires every route
  in `app.url_map` to be exercised or explicitly declared, replacing a manual
  sweep. It found seven blind spots on its first run, including a health
  endpoint nothing called.
- **The wheel ships its data files.** `[tool.setuptools.package-data]` and
  `MANIFEST.in` carry the 263 craft rules and the SPA; without them the wheel
  installed a silently empty knowledge base and a 404 frontend.

### Added

- A proprietary `LICENSE`. This project is private and not open source; see the
  file for the terms.
