"""Shared helpers for the 2026-09-30 audit evidence scripts."""
import json
import os
import time


def shot(page, shots_dir, name):
    """Screenshot named evidence into shots_dir; returns the relative name."""
    path = os.path.join(shots_dir, f"{name}.png")
    try:
        page.screenshot(path=path, full_page=False)
        return os.path.basename(path)
    except Exception as e:
        return f"screenshot-failed: {e!r}"


def save_console_capture(ev_dir, name, console_msgs, page_errors, failed_net):
    """Console + page-error + failed-network capture as JSON evidence."""
    with open(os.path.join(ev_dir, name), "w", encoding="utf-8") as f:
        json.dump({
            "console": console_msgs,
            "page_errors": page_errors,
            "failed_network": failed_net,
        }, f, indent=2)


def reveal_chrome(page, sel, timeout=8000):
    """Auto-hiding chrome (#desk-toolbar/#project-bar: opacity 0 +
    pointer-events none while idle) needs a mousemove with clientY < 120 to
    come back for ~4s. Adopted from tests/e2e_browser_phase8_lifecycle.py:
    move where a writer's mouse would be, then poll the REAL hit test until
    the control is genuinely the hit target. Returns True/False, never raises."""
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
        page.wait_for_timeout(150)
        page.mouse.move(700, 8)
    return False
