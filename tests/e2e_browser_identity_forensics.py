"""Forensic probe: the SHIPPED app's actual identity, as computed in the
browser — palette tokens, ambient tints, font-family chain on key surfaces,
compared live against the two design docs' claims (midnight-desk-preview
amber/steel vs DESIGN.md Nocta violet/cyan)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

CHECKS = Checks()


def main():
    # Dual-mode, like export_flush: talk to a running studio when E2E_BASE is
    # set (the shared-sweep convention), otherwise boot a private demo studio —
    # so the suite participates in the ordinary sweep instead of hard-failing
    # with a KeyError on an env var most runs never set.
    external = os.environ.get("E2E_BASE")
    if not external:
        from e2e_browser_common import open_studio
        with open_studio() as base:
            return _run(base.rstrip("/"))
    _run(external.rstrip("/"))


def _run(base):
    with sync_playwright() as pw:
        from e2e_browser_common import launch
        browser, page, errors = launch(pw)
        page.goto(base + "/", wait_until="networkidle")
        page.wait_for_timeout(800)

        # ---- 1. the token truth ------------------------------------------
        tokens = page.evaluate(
            """() => {
              const root = getComputedStyle(document.documentElement);
              const body = getComputedStyle(document.body);
              const g = (n) => (root.getPropertyValue(n) ||
                                body.getPropertyValue(n)).trim();
              return {
                ink950: g('--ink-950'), ink900: g('--ink-900'),
                ink800: g('--ink-800'), line: g('--line'),
                paper: g('--paper'), paperInk: g('--paper-ink'),
                lamp: g('--lamp'), lampDeep: g('--lamp-deep'),
                consult: g('--consult'), sevMid: g('--sev-mid'),
                accent: g('--accent'), danger: g('--danger'),
                fontUi: g('--font-ui'), fontScript: g('--font-script'),
                fontTypewriter: g('--font-typewriter'),
                fontSerif: g('--font-serif'), fontHand: g('--font-hand'),
              };
            }"""
        )
        print("=== shipped token truth (computed) ===")
        for k, v in tokens.items():
            print(f"  --{k}: {v}")
        CHECKS.ok("token truth dumped", True)

        # ---- 2. surface census: what each key surface actually wears -----
        surfaces = page.evaluate(
            """() => {
              const probe = (sel, pseudo) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const cs = getComputedStyle(el, pseudo || null);
                return {bg: cs.backgroundColor, bgImage: (cs.backgroundImage || 'none').slice(0, 90),
                        color: cs.color, font: cs.fontFamily.slice(0, 70),
                        border: cs.borderColor || ''};
              };
              return {
                body: probe('body'),
                sidebar: probe('#sidebar'),
                welcomeCard: probe('.welcome-card'),
                dashCard: probe('.dash-card') || probe('#dash-grid .dash-card'),
                dropzone: probe('#dropzone'),
                ideaBtn: probe('#idea-btn'),
                statusStrip: probe('#status-strip'),
                shelf: probe('#shelf-section'),
                homeBtn: probe('#home-btn'),
              };
            }"""
        )
        print("=== surface census (welcome view) ===")
        for name, s in (surfaces or {}).items():
            if s:
                print(f"  {name:12s} bg={s['bg']:24s} color={s['color']:22s} "
                      f"font={s['font']}")
        CHECKS.ok("surface census dumped", True)

        # ---- 3. which fonts ACTUALLY render (loaded AND used) -----------
        usage = page.evaluate(
            """() => {
              const fams = {};
              const add = (label, sel) => {
                const el = document.querySelector(sel);
                if (!el) return;
                fams[label] = getComputedStyle(el).fontFamily.split(',')[0]
                  .replace(/["']/g, '');
              };
              add('body-text', 'body');
              add('welcome-h1', '#welcome-view h1');
              add('greeting', '#welcome-greeting');
              add('dash-title', '.dash-title');
              add('btn-paper', '#idea-btn');
              add('status', '#status-strip');
              return fams;
            }"""
        )
        print("=== first-family in computed chains ===")
        for k, v in usage.items():
            print(f"  {k}: {v}")
        CHECKS.ok("font chain dumped", True)

        # ---- 4. warm-vs-cool verdict on the furniture --------------------
        # sample the actual rendered bg colors: is the shell warm-brown
        # (Midnight Desk) or cool void (Spark Wall/Nocta)?
        verdict = page.evaluate(
            """() => {
              const rgb = (str) => {
                const m = str.match(/\\d+(\\.\\d+)?/g);
                return m ? m.slice(0, 3).map(Number) : null;
              };
              const classify = (c) => {
                if (!c) return 'n/a';
                const [r, g, b] = c;
                const warm = r - b;  // >0 warm-brown, <0 cool-blue
                return warm > 8 ? `WARM brown (${r},${g},${b})`
                     : warm < -8 ? `COOL void (${r},${g},${b})`
                     : `neutral (${r},${g},${b})`;
              };
              const gcs = (sel) => {
                const el = document.querySelector(sel);
                return el ? getComputedStyle(el).backgroundColor : null;
              };
              return {
                body: classify(rgb(gcs('body'))),
                sidebar: classify(rgb(gcs('#sidebar'))),
                welcomeCard: classify(rgb(gcs('.welcome-card'))),
                statusStrip: classify(rgb(gcs('#status-strip'))),
              };
            }"""
        )
        print("=== furniture temperature ===")
        for k, v in verdict.items():
            print(f"  {k}: {v}")
        CHECKS.ok("temperature dumped", True)

        # ---- 5. accent hue used on the primary CTA right now -------------
        cta = page.evaluate(
            """() => {
              const el = document.querySelector('#idea-btn')
                      || document.querySelector('.btn-paper');
              if (!el) return null;
              const cs = getComputedStyle(el);
              return {color: cs.color, bg: cs.backgroundColor,
                      border: cs.borderColor};
            }"""
        )
        print("=== primary CTA (#idea-btn) ===", cta)
        CHECKS.ok("cta dumped", True)

        CHECKS.ok("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        CHECKS.finish()


if __name__ == "__main__":
    main()
