"""e2e_browser_desk_controls.py — the desk's shipped controls nobody drove.

R6-E2E-5 (round 6, 2026-09-26). The audit found a class of hole the fleet could
never notice: a control with full API coverage and zero browser coverage, so the
endpoint can be fine while the button that calls it is broken. These are the ones
that matter, because three of them DESTROY state:

  * `#reparse-btn`      — re-parses the source and invalidates a finished analysis
  * `#reset-edits-btn`  — "Discard edits", throws away every applied change
  * `#draft-select`     — switching drafts is the R6-BE-3 data-loss path
  * `#export-fdx` / `#export-txt` — two of the three export formats, which no
    suite had ever fetched (only fountain was, and with a check that could not
    fail: `a and b or c or d` — R6-E2E-1)

Two things this suite deliberately does not pretend:

1. **Undo/Redo are not clickable.** `#undo-btn` / `#redo-btn` carry click
   handlers and a maintained `.disabled`, but nothing ever clears their inline
   `display:none` — measured live with an edit applied AND the overflow menu open,
   both still 0x0. That is documented intent in two places:
   `index.html:208-210` ("no visible surface on purpose — keyboard parity is the
   contract; the hidden buttons stay because the edit-state refreshers drive
   their .disabled") and `docs/UI_UX_SPECIFICATION.md` §7 ("undo/redo is
   keyboard-only"). So there is no button here to click; asserting one existed
   would be the fake coverage this round exists to remove. The fence below is
   that they STAY off the desk, so a half-reveal is a red suite rather than a
   control nobody re-checked. The keyboard round trip is driven by
   `e2e_browser_rewrite_loop.py`.
2. **`#reparse-btn` now lives on the desk toolbar** (Option A+, audit
   2026-09-30: the legacy panel header that hosted it retired). The desk
   toolbar is auto-hiding chrome — `visibility` flips on hover, and the
   toolbar's own `.revealed` class keeps it steady. The suite reveals it the
   way the product does (the same reveal contract `phase8_lifecycle` pins for
   Run Analysis), then drives the button through its own POST.

Every destructive check reads the SERVER after the click, not just the page: the
failure being hunted is a control that looks right and writes nothing (or writes
too much and reports nothing).

Run:  python tests/e2e_browser_desk_controls.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks, launch, open_studio, studio_headers, assert_no_js_errors)
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")
# A token unique to the fixture, so an export that returns ANOTHER project's
# script cannot pass by being a plausible screenplay.
TOKEN = "Siddhu"

checks = Checks()
check = checks.ok

# A second draft that is unmistakably different from the fixture, so a switch
# that silently kept the old text shows up rather than passing on the wrong page.
ALT_MARKER = "DESKSWITCHQZ7"
ALT_SCRIPT = f"""Title: Alt
{ALT_MARKER} opening

INT. WAREHOUSE - NIGHT

{ALT_MARKER}

MARA
If this line is on the page, the switch worked.
"""

HIT = """(s) => { const e = document.querySelector(s);
  if (!e) return { state: 'absent', chrome: document.body.className };
  const r = e.getBoundingClientRect();
  const rect = [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  if (r.width < 4) return { state: 'zero', rect, chrome: document.body.className };
  const t = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
  const ok = (t === e || e.contains(t));
  return { state: ok ? 'hit' : 'covered', rect, chrome: document.body.className,
           hit: t ? (t.tagName + '#' + t.id + '.' + String(t.className)).slice(0, 60) : null }; }"""

VIS = """(sel) => {
  const e = document.querySelector(sel);
  if (!e) return { present: false };
  const cs = getComputedStyle(e);
  const r = e.getBoundingClientRect();
  return { present: true, display: cs.display, visibility: cs.visibility,
           w: Math.round(r.width), h: Math.round(r.height),
           onScreen: r.width > 10 && r.height > 10 && cs.visibility !== 'hidden',
           disabled: !!e.disabled, href: e.getAttribute('href') || null,
           download: e.getAttribute('download') || null,
           text: (e.textContent || '').trim().slice(0, 60) };
}"""

LINE0 = "() => { const l = document.querySelector('#manuscript-container [class^=el-]');" \
        " return l ? l.textContent.trim() : null; }"
PAGE_TEXT = "() => document.querySelector('#manuscript-container').textContent"


def wait_or_false(page, js, timeout):
    """Bounded poll whose failure is a value, not a traceback.

    R6-E2E-6: the sync point here is a network round trip the product performs,
    so poll for the real condition — but the check must still be able to report
    RED rather than erroring out the suite.
    """
    try:
        page.wait_for_function(js, timeout=timeout)
        return True
    except Exception:  # noqa: BLE001 - the caller's check IS the report
        return False


def reveal_chrome(page, sel="#desk-analyze-btn", timeout=8000):
    """Move the mouse where a writer's would be, then poll until the control is
    the hit target (auto-hiding chrome: opacity 0 + pointer-events none until a
    top-edge mousemove brings it back). Returns True/False — never raises.
    Copied from phase8_lifecycle's identical helper (that suite owns it; this
    one needed the same contract for the re-homed Re-parse button)."""
    import time
    page.mouse.move(700, 8)
    deadline = time.time() + timeout / 1000
    hit = "missing"
    while time.time() < deadline:
        hit = page.evaluate(
            """(sel) => {
              const e = document.querySelector(sel);
              if (!e) return 'missing';
              const r = e.getBoundingClientRect();
              const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
              if (!t) return 'none';
              return (e === t || e.contains(t)) ? 'ok' : t.tagName + '#' + (t.id || '-');
            }""", sel)
        if hit == "ok":
            return True
        page.wait_for_timeout(100)
    return False


def api_get(base, path):
    return requests.get(base + path, timeout=120).json()


def stages(base, project):
    # `stages` lives on the project summary (webapp_server._manifest_summary);
    # /status is the analyze *progress* poller and does not carry them.
    return api_get(base, f"/api/projects/{project}")["stages"]


def reveal(page, sel, timeout=8000):
    """Hover the auto-hiding chrome until `sel` is genuinely the hit target.

    `#desk-toolbar` is `.auto-hide-chrome`: idle it carries `opacity: 0;
    pointer-events: none`, so Playwright's is_visible() ignores opacity and a
    bare .click() dies with "intercepts pointer events". Same trap phase8_lifecycle
    root-caused on 2026-09-23.
    """
    detail = {"state": "not tried"}
    end = time.time() + timeout / 1000.0
    while time.time() < end:
        page.mouse.move(700, 40)
        detail = page.evaluate(HIT, sel)
        if detail["state"] == "hit":
            return True
        page.wait_for_timeout(150)
    print(f"   reveal({sel}) gave up: {json.dumps(detail)}")
    return False


def open_overflow(page):
    assert reveal(page, "#overflow-toggle"), "#overflow-toggle never became clickable"
    page.locator("#overflow-toggle").click()
    page.wait_for_function(
        "() => getComputedStyle(document.querySelector('#overflow-dropdown')).display !== 'none'",
        timeout=5000)


def close_overflow(page):
    """The product's own outside-click close.

    Measured here, not assumed: Escape does NOT dismiss this menu (its handler
    is only `stopPropagation`), so a writer leaves it the same way they leave any
    popup — a click elsewhere. `#main` with a 4px offset is the desk's own
    padding, which no handler claims.
    """
    page.locator("#main").click(position={"x": 4, "y": 4})
    page.wait_for_function(
        "() => getComputedStyle(document.querySelector('#overflow-dropdown')).display === 'none'",
        timeout=5000)


def download_body(page, sel, tag):
    """Click an export anchor for real and return the bytes a writer receives."""
    tmp = os.path.join(os.environ.get("TEMP", "."), f"desk_dl_{tag}")
    with page.expect_download(timeout=20000) as dl:
        page.locator(sel).click()
    d = dl.value
    d.save_as(tmp)
    try:
        with open(tmp, "r", encoding="utf-8", errors="replace") as fh:
            return d, fh.read()
    finally:
        os.remove(tmp)


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw, accept_downloads=True)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            with open(FIXTURE, "rb") as f:
                r = requests.post(
                    f"{base}/api/projects", headers=studio_headers(base),
                    files={"file": ("desk.fountain", f, "text/plain")},
                    data={"title": "Desk Controls"}, timeout=60)
            assert r.status_code in (200, 201), r.text
            project = r.json()["project"]
            page.evaluate("async (n) => { await openProject(n); }", project)
            page.wait_for_selector("#manuscript-container [class^=el-]", timeout=30000)

            # ---------- 1. the two formats no suite ever fetched --------------
            open_overflow(page)
            for sel, fmt in [("#export-fdx", "fdx"), ("#export-txt", "txt"),
                             ("#export-fountain", "fountain")]:
                v = page.evaluate(VIS, sel)
                check(f"{fmt}: the overflow menu offers it on screen",
                      v.get("onScreen"), json.dumps(v))
                check(f"{fmt}: its href asks the server for that format",
                      (v["href"] or "").endswith(f"/export?format={fmt}"),
                      v["href"] or "")
                check(f"{fmt}: it downloads under the right extension",
                      (v["download"] or "").endswith(f".{fmt}"), v["download"] or "")
                try:
                    d, body = download_body(page, sel, fmt)
                    # Every clause is required — no `or` between them, which is
                    # the R6-E2E-1 shape that let a 500 page pass an export check.
                    error_page = ("Internal Server Error" in body
                                  or "404 Not Found" in body
                                  or body.lstrip().startswith("<!DOCTYPE html>"))
                    is_this_script = TOKEN in body
                    right_shape = (body.lstrip().startswith("<?xml") if fmt == "fdx"
                                   else "INT." in body or "EXT." in body)
                    named = d.suggested_filename.endswith(f".{fmt}")
                    check(f"{fmt}: the file a writer receives is that format, this script, and not an error page",
                          named and not error_page and is_this_script and right_shape,
                          f"{d.suggested_filename} / {len(body)} chars / "
                          f"error_page={error_page} this_script={is_this_script} "
                          f"shape={right_shape}")
                except Exception as e:  # noqa: BLE001 - the check IS the report
                    check(f"{fmt}: the file a writer receives is that format, this script, and not an error page",
                          False, str(e)[:90])
                page.wait_for_timeout(250)

            # ---------- 2. Discard edits: gated on there being edits ----------
            v = page.evaluate(VIS, "#reset-edits-btn")
            check("a project with no edits is not offered Discard edits",
                  v["present"] and not v["onScreen"], json.dumps(v))
            close_overflow(page)

            # Undo/Redo have no surface at all — documented, so fenced as such.
            for sel in ("#undo-btn", "#redo-btn"):
                u = page.evaluate(VIS, sel)
                check(f"{sel} stays off the desk (undo/redo is keyboard-only, spec §7)",
                      u["present"] and not u["onScreen"], json.dumps(u))

            # ---------- 3. apply a real edit, then discard it ----------------
            line = page.evaluate(LINE0)
            assert line, "no manuscript line to edit"
            scene1 = page.evaluate("() => state.script.scenes[0].scene_number")
            api = api_get(base, f"/api/projects/{project}/edits")
            check("the fixture starts with a clean edit book",
                  not api["edits"], f"{len(api['edits'])} edits")
            requests.post(f"{base}/api/projects/{project}/edits/apply",
                          headers=studio_headers(base),
                          json={"scene_number": scene1,
                                "replacements": [{"old": line, "new": line + " [DESK-PROBE]"}]},
                          timeout=60)
            page.evaluate("async () => { await afterScriptEdit(); }")
            landed = wait_or_false(
                page,
                "() => { const l = document.querySelector('#manuscript-container [class^=el-]');"
                " return !!l && l.textContent.includes('[DESK-PROBE]'); }", 20000)
            now = page.evaluate(LINE0)
            check("the applied edit reaches the page", landed, now[:80])

            open_overflow(page)
            v = page.evaluate(VIS, "#reset-edits-btn")
            check("with edits on the book, Discard edits appears on screen",
                  v["onScreen"], json.dumps(v))
            try:
                with page.expect_response(
                        lambda rr: rr.url.endswith(f"/projects/{project}/edits/reset")
                        and rr.request.method == "POST", timeout=20000):
                    page.locator("#reset-edits-btn").click()
                posted = True
            except Exception as e:  # noqa: BLE001
                posted = False
                print("   reset POST never landed:", str(e)[:80])
            page.wait_for_timeout(2000)
            after = api_get(base, f"/api/projects/{project}/edits")
            check("clicking it really discards the edit (server, not just the page)",
                  posted and not after["edits"], f"{len(after['edits'])} edits left")
            back = page.evaluate(LINE0)
            check("...and the page goes back to what the parser read",
                  "[DESK-PROBE]" not in back and back == line,
                  f"{back[:60]!r} vs {line[:60]!r}")
            close_overflow(page)

            # ---------- 4. draft switch: the R6-BE-3 path -------------------
            alt = os.path.join(os.environ.get("TEMP", "."), "desk_alt.fountain")
            with open(alt, "w", encoding="utf-8") as fh:
                fh.write(ALT_SCRIPT)
            page.set_input_files("#draft-file-input", alt)
            try:
                page.wait_for_function(
                    """() => { const s = document.getElementById('upload-draft-status');
                               return s && s.textContent.includes('Draft parsed'); }""",
                    timeout=60000)
                parsed = True
            except Exception:  # noqa: BLE001
                parsed = False
            check("the + Draft upload parses and says so on the desk",
                  parsed, page.evaluate(
                      "() => document.querySelector('#upload-draft-status').textContent")[:80])

            d = api_get(base, f"/api/projects/{project}/drafts")
            check("the new draft is registered and now the active one",
                  d["active_draft"] == "draft-1" and len(d["drafts"]) == 1, json.dumps(d))

            # uploadNewDraft() ends with loadProjects() + openProject(), so the
            # desk rebuilds itself over several round trips after the status line
            # lands. Poll the real sync point (the switcher repopulated from
            # /drafts) before asserting what the writer sees.
            settled = wait_or_false(
                page,
                "() => [...document.querySelectorAll('#draft-select option')]"
                ".map(o => o.value).join(',') === 'original,draft-1'", 30000)
            page_text = page.evaluate(PAGE_TEXT) or ""
            check("the page the writer sees is the new draft",
                  settled and ALT_MARKER in page_text,
                  f"settled={settled} / {page.evaluate(LINE0)[:60]!r}")

            opts = page.evaluate(
                "() => [...document.querySelectorAll('#draft-select option')].map(o => o.value)")
            check("the switcher lists both drafts, so the old one is still reachable",
                  "original" in opts and "draft-1" in opts, json.dumps(opts))

            # Switch BACK — the path that used to delete the writer's only copy.
            # Arm the watcher BEFORE the select: select_option fires the change
            # handler synchronously, so a watcher armed after it can miss the POST.
            # A missing POST is the product bug under test, so it becomes a red
            # check rather than a traceback.
            try:
                with page.expect_response(
                        lambda rr: f"/projects/{project}/drafts/activate" in rr.url
                        and rr.request.method == "POST", timeout=30000) as ri:
                    page.select_option("#draft-select", "original")
                activate_status = ri.value.status
            except Exception as e:  # noqa: BLE001 - the check IS the report
                activate_status = 0
                print("   activate POST never landed:", str(e)[:80])
            shown_original = wait_or_false(
                page,
                "() => { const t = document.querySelector('#manuscript-container').textContent;"
                f" return t.includes({json.dumps(TOKEN)})"
                f" && !t.includes({json.dumps(ALT_MARKER)}); }}", 30000)
            check("switching drafts posts the activate",
                  activate_status == 200, str(activate_status))
            d2 = api_get(base, f"/api/projects/{project}/drafts")
            check("the server now works on the original draft",
                  d2["active_draft"] in (None, "original"), json.dumps(d2))
            page_text2 = page.evaluate(PAGE_TEXT) or ""
            check("...and the page shows the original again",
                  shown_original and ALT_MARKER not in page_text2 and TOKEN in page_text2,
                  page.evaluate(LINE0)[:60])
            exp = requests.get(f"{base}/api/projects/{project}/export?format=fountain",
                               timeout=60)
            check("the round trip lost no text — the original still exports whole",
                  exp.status_code == 200 and TOKEN in exp.text,
                  f"{exp.status_code} / {len(exp.text)} chars / token={TOKEN in exp.text}")
            alt_left = api_get(base, f"/api/projects/{project}/drafts")["drafts"]
            check("...and the draft the writer uploaded was not destroyed by switching away",
                  len(alt_left) == 1 and alt_left[0]["name"] == "draft-1", json.dumps(alt_left))
            os.remove(alt)

            # ---------- 5. Re-parse: destroys a finished analysis -------------
            # Option A+: the button is on the desk toolbar now (auto-hiding
            # chrome). Reveal it the way the writer's mouse does, then reach in.
            check("the desk toolbar offers Re-parse on screen",
                  reveal_chrome(page, "#reparse-btn"))
            v = page.evaluate(VIS, "#reparse-btn")
            check("Re-parse is genuinely the hit target once revealed",
                  v["present"] and v["onScreen"], json.dumps(v))

            if stages(base, project).get("analyze") != "complete":
                requests.post(f"{base}/api/projects/{project}/analyze",
                              headers=studio_headers(base), json={}, timeout=600)
            s_before = stages(base, project)
            check("a finished analysis is on the book before the destructive click",
                  s_before.get("analyze") == "complete", json.dumps(s_before))
            # Write an edit too: re-parse must not be a way to lose the writer's
            # own work while resetting the doctor's.
            requests.post(f"{base}/api/projects/{project}/edits/apply",
                          headers=studio_headers(base),
                          json={"scene_number": scene1,
                                "replacements": [{"old": line, "new": line + " [KEEPME]"}]},
                          timeout=60)

            try:
                with page.expect_response(
                        lambda rr: rr.url.endswith(f"/projects/{project}/reparse")
                        and rr.request.method == "POST", timeout=60000):
                    page.locator("#reparse-btn").click()
                rp_posted = True
            except Exception as e:  # noqa: BLE001
                rp_posted = False
                print("   reparse POST never landed:", str(e)[:80])
            page.wait_for_timeout(3000)
            after_rp = stages(base, project)
            check("clicking Re-parse re-ran the parse",
                  rp_posted and after_rp.get("parse") == "complete", json.dumps(after_rp))
            check("...and invalidated the stale analysis rather than serving it on",
                  after_rp.get("analyze") != "complete",
                  f"analyze is {after_rp.get('analyze')}")
            rep = requests.get(f"{base}/api/projects/{project}/report", timeout=30)
            check("the desk no longer serves a report built from the superseded parse",
                  rep.status_code == 400, str(rep.status_code))
            check("the script itself survived the re-parse",
                  wait_or_false(page,
                                "() => document.querySelectorAll('#manuscript-container .scene-page').length > 0",
                                30000),
                  "no scene page rendered after the re-parse")
            keep = api_get(base, f"/api/projects/{project}/edits")
            check("and the writer's own edit was NOT swept up with the analysis",
                  len(keep["edits"]) == 1 and "KEEPME" in json.dumps(keep["edits"]),
                  f"{len(keep['edits'])} edits")
            # Phase 8: the desk button is the lifecycle's home (the legacy
            # #analyze-btn retired with the panel). After a re-parse the desk
            # re-arms so the writer is not stuck.
            check("the desk re-arms Run Analysis so the writer is not stuck",
                  reveal_chrome(page, "#desk-analyze-btn"))
            desk = page.evaluate(VIS, "#desk-analyze-btn")
            check("...and the re-armed button is genuinely clickable",
                  desk.get("present") and desk["onScreen"] and not desk["disabled"], json.dumps(desk))
            label = page.evaluate("() => document.querySelector('#desk-analyze-btn').textContent.trim()")
            check("...and it reads Run Analysis, not Re-run, since there is nothing to re-run",
                  "Run Analysis" in label, label[:40])

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
