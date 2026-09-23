"""Production-readiness gate: the two things no other suite can see.

1. COMPUTED CONTRAST. Every other visual suite asserts geometry or presence, so
   a rule can paint severity ink the same colour as the severity FILL and every
   suite stays green while the chip is literally invisible (that is the 2026-09-23
   audit's B1: 1.00:1 night / 1.52:1 dawn). Here the browser resolves the real
   foreground and the real ground under it and applies WCAG 1.4.3.

2. HIT TARGETS. WCAG 2.5.8's 24x24 minimum, measured on the real hit area (a
   control may carry its target in a transparent pad) rather than markup (the
   audit found 18 visible controls below it).

Both are checked in BOTH shipped themes, because the theme is a re-pin layer
(tungsten.css) and a token that passes at night can fail at dawn.

Scope rule, so this stays a gate and not a wish-list: it asserts on text whose
colour resolves to a SEMANTIC token (severity / status / ink / accent-ink). Those
roles are the design system's contract; a page-specific literal is design debt,
reported here but fixed by the debt pass.

Run:  python tests/e2e_browser_readiness_gate.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (Checks, launch, open_dock_section_holding,  # noqa: E402
                                start_studio, studio_headers)
from playwright.sync_api import sync_playwright  # noqa: E402

# Tokens whose text role is the design system's contract. A failure here is a
# defect in a shared role, not a one-off colour choice in one panel. The
# `*-text` roles are listed alongside their fills on purpose: a site repointed
# from --sev-mid to --sev-mid-text must stay IN this gate's scope, or the gate
# would go green by losing track of the very chip it exists to protect.
TOKENS = ("--danger", "--danger-text", "--danger-on-paper", "--sev-mid",
          "--sev-mid-text", "--ok", "--text", "--text-muted", "--text-faint",
          "--accent-ink")

PROBE = """(tokens) => {
  const num = (s) => (s || "").match(/[-\\d.]+/g) || [];
  // Chrome resolves `color-mix(in oklab, ...)` — which is how most of this
  // system tints a token toward paper or ink — to a COMPUTED `oklab(L a b)`
  // string, not rgb(). Reading its components as 0-255 channels turns a mid
  // amber into near-black and invents a contrast failure that no reader sees,
  // so oklab/oklch are converted properly and anything else unrecognised
  // resolves to no ground (a NOTE) rather than a wrong number.
  const gamut = (v) => {
    const f = (x) => (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
    return [0, 1, 2].map((i) => Math.min(1, Math.max(0, f(v[i]))));
  };
  const oklabToRgb = (L, a, b) => {
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.291485548 * b;
    const [l, m, s] = [l_ ** 3, m_ ** 3, s_ ** 3];
    return gamut([
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ]);
  };
  const hex = (s) => {
    s = (s || "").trim();
    if (s.startsWith("#")) {
      const h = s.slice(1);
      const f = (a) => parseInt(a, 16) / 255;
      return h.length === 3
        ? [f(h[0] + h[0]), f(h[1] + h[1]), f(h[2] + h[2])]
        : [f(h.slice(0, 2)), f(h.slice(2, 4)), f(h.slice(4, 6))];
    }
    if (s.startsWith("oklab(")) {
      const p = num(s).map(Number);
      return p.length >= 3 ? oklabToRgb(p[0], p[1], p[2]) : null;
    }
    if (s.startsWith("oklch(")) {
      const p = num(s).map(Number);
      if (p.length < 3) return null;
      const h = (p[2] * Math.PI) / 180;
      return oklabToRgb(p[0], p[1] * Math.cos(h), p[1] * Math.sin(h));
    }
    if (!s.startsWith("rgb")) return null;  // hsl()/color()/lab(): no guess, no number
    const p = num(s).map(Number);
    return p.length >= 3 ? [p[0] / 255, p[1] / 255, p[2] / 255] : null;
  };
  const alpha = (s) => { const p = num(s).map(Number); return p.length > 3 ? p[3] : 1; };
  const lum = (c) => {
    const f = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => {
    const la = lum(a), lb = lum(b), hi = Math.max(la, lb), lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  };
  const blend = (fg, bg, a) => [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a));
  const cs = (n) => getComputedStyle(n);
  // An element at `opacity: .45` does not render its text at .45 — it renders
  // it mixed 55% toward whatever sits behind it, so an "addressed" note is
  // really a 2:1 note. Chrome reports `color` pre-composite, so the effective
  // alpha is walked up the tree and folded into the foreground.
  const effAlpha = (el) => {
    let a = 1;
    for (let n = el; n; n = n.parentElement) {
      const o = parseFloat(cs(n).opacity);
      if (Number.isFinite(o)) a *= o;
      if (n === document.documentElement) break;
    }
    return a;
  };
  // ...but a RUNNING pulse keyframe (stage-mark dips to .35 every 1.4s) is not
  // the surface a reader judges; the resting rule is. Cancelling removes the
  // animation's effect so the base value is what resolves, which also makes
  // every sweep deterministic instead of phase-dependent.
  (document.getAnimations ? document.getAnimations() : []).forEach((a) => a.cancel());
  const visible = (n) => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const path = (el) => {
    const one = (n) => n.tagName.toLowerCase() + (n.id ? "#" + n.id : "") +
      (n.className && typeof n.className === "string"
        ? "." + n.className.trim().split(/\\s+/).slice(0, 3).join(".") : "");
    return el.className && typeof el.className === "string" && el.className.trim()
      ? one(el) : one(el) + " < " + one(el.parentElement || el);
  };

  // The real ground under an element, resolved the way the compositor does.
  // A colour layer is one ground. A gradient layer is ALTERNATIVE grounds —
  // the pixel under a glyph is one of its stops — so it multiplies the
  // candidate set and the caller takes the worst: a chip painted
  // linear-gradient(#a, #b) is legible only if the text clears AA against the
  // stop that fights it hardest. Stops composite over what sits UNDER them,
  // translucent ones included: a 0.9-alpha pill on the void is a resolvable
  // ground, and skipping it made the walk report the void itself and read a
  // 6:1 chip as 1:1.
  function groundsOf(el) {
    // Topmost paint first. Within one element the image sits on top of the
    // background colour, so the colour goes in first.
    const layers = [];
    let n = el;
    while (n) {
      const st = cs(n);
      const c = hex(st.backgroundColor);
      if (!c) return null;
      const a = alpha(st.backgroundColor);
      if (a > 0) layers.push({ c, a });
      const img = st.backgroundImage;
      if (img && img !== "none" && /gradient\\(/.test(img)) {
        const stops = (img.match(/#[0-9a-f]{3,8}\\b|rgba?\\([^)]*\\)/g) || [])
          .map((t) => [hex(t), alpha(t)]).filter(([c]) => c)
          // `transparent` and the 0.04 radial breaths are not paints; only a
          // stop that could plausibly sit under a glyph becomes a candidate.
          .filter(([, a]) => a >= 0.5);
        if (stops.length) layers.push({ stops });
      }
      if (layers.some((L) => L.c && L.a >= 0.999)) break;
      n = n.parentElement;
    }
    if (!layers.length) return null;
    // Composite from the deepest layer up; with no opaque layer anywhere the
    // deepest colour stands in as the page's own ground.
    let base = null;
    let i = layers.length - 1;
    for (; i >= 0; i--) {
      const L = layers[i];
      if (L.c && L.a >= 0.999) { base = L.c; i--; break; }
    }
    if (base === null) {
      const j = layers.findIndex((L) => L.c);
      if (j === -1) return null;
      base = layers[j].c;
      i = j - 1;
    }
    let cands = [base];
    for (; i >= 0; i--) {
      const L = layers[i];
      if (L.c) { cands = cands.map((g) => blend(L.c, g, L.a)); continue; }
      const out = [];
      for (const g of cands) for (const [sc, sa] of L.stops) out.push(blend(sc, g, sa));
      cands = out;
    }
    return cands;
  }

  const tokenColors = {};
  const missingTokens = [];
  for (const t of tokens) {
    const v = cs(document.body).getPropertyValue(t);
    const c = hex(v);
    if (c) tokenColors[t] = c; else missingTokens.push(t);
  }

  const text = [];
  const other = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    if (!el || !node.nodeValue || !node.nodeValue.trim()) continue;
    if (!visible(el)) continue;
    const st = cs(el);
    const fg = hex(st.color);
    if (!fg) continue;
    // `opacity: 0` paints nothing at all. The hover-revealed row ✕ and the
    // proximity-faded project bar are ABSENT chrome until revealed (both are
    // pointer-events:none while faded), so measuring them as text would invent
    // a 1:1 failure the reader never sees — the same category as the
    // parked-off-screen control the target walk below already exempts.
    const ea = effAlpha(el);
    if (ea <= 0.01) continue;
    const size = parseFloat(st.fontSize) || 16;
    const bold = parseInt(st.fontWeight, 10) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
    const grounds = groundsOf(el);
    let worst = null, worstR = null;
    for (const g of (grounds || [])) {
      const r = ratio(ea < 0.999 ? blend(fg, g, ea) : fg, g);
      if (worstR === null || r < worstR) { worstR = r; worst = g; }
    }
    const own = Object.entries(tokenColors).find(([, c]) =>
      c.every((v, i) => Math.abs(v - fg[i]) < 0.004));
    const rec = {
      sel: path(el),
      text: node.nodeValue.trim().slice(0, 28),
      size: Math.round(size * 10) / 10, need,
      // The two numbers a reader needs to fix this: what it was painted with,
      // and the ground it was measured on. Without them a failure is a ratio
      // and nothing else to act on.
      fg: st.color, ground: worst ? "rgb(" + worst.map((v) => Math.round(v * 255)).join(",") + ")" : null,
      opacity: ea < 0.999 ? Math.round(ea * 100) / 100 : null,
      ratio: worstR === null ? null : Math.round(worstR * 100) / 100,
      token: own ? own[0] : null,
    };
    if (rec.ratio === null) { other.push({ ...rec, why: "no resolvable ground" }); continue; }
    if (rec.token) text.push(rec);
    if (rec.ratio < rec.need) other.push({ ...rec, why: rec.token ? "token " + rec.token : "sub-AA" });
  }

  const boxes = [];
  // The hit area, not the painted box: a control may carry its target in a
  // transparent ::before pad (the ruler ticks are 6px scale marks). A pad is
  // identified by insets that hang OUTSIDE the box on all four sides; resolved
  // `auto` insets are used-value offsets and must not be mistaken for one.
  const hit = (el) => {
    const r = el.getBoundingClientRect();
    const pb = getComputedStyle(el, "::before");
    const pad = ["top", "right", "bottom", "left"].map((s) => parseFloat(pb[s]));
    if (pb.content && pb.content !== "none" && pb.position === "absolute"
        && pad.every((v) => Number.isFinite(v) && v < 0)) {
      const [t, rr, b, l] = pad;
      return { w: r.width - l - rr, h: r.height - t - b };
    }
    return { w: r.width, h: r.height };
  };
  document.querySelectorAll("button, a[href], [role=button], [role=tab], input[type=checkbox]").forEach((el) => {
    if (!visible(el)) return;
    const rect = el.getBoundingClientRect();
    // parked off-screen (a skip link until focus, a row action until hover) is
    // not a small target — it is no target yet
    if (rect.right <= 0 || rect.bottom <= 0 || rect.left >= innerWidth
        || rect.top >= innerHeight) return;
    const st = hit(el);
    // Inline links inside a sentence are exempt from 2.5.8; a control that has
    // its own line is not.
    if (el.tagName === "A" && el.closest("p, li, .prose")) return;
    if (st.w < 24 || st.h < 24) {
      boxes.push({
        sel: path(el),
        label: (el.getAttribute("aria-label") || el.title || el.textContent || "").trim().slice(0, 28),
        w: Math.round(st.w), h: Math.round(st.h),
      });
    }
  });

  return { tokenText: text, failing: other, smallTargets: boxes,
           missingTokens: missingTokens };
}"""


def sweep(checks, page, tag):
    page.wait_for_timeout(250)
    res = page.evaluate(PROBE, list(TOKENS))
    # An unresolvable token would drop its sites out of scope silently, which is
    # how this gate nearly went green by looking away.
    checks.ok(f"{tag}: every contract token resolves",
              not res["missingTokens"], "undefined: " + ", ".join(res["missingTokens"]))
    worst = sorted((r for r in res["tokenText"]), key=lambda r: r["ratio"])
    bad = [r for r in worst if r["ratio"] < r["need"]]
    checks.ok(
        f"{tag}: every semantic-token text clears WCAG AA",
        not bad,
        "; ".join(f"{r['token']} {r['ratio']}:1 on {r['sel']}"
                  + (f" (@opacity {r['opacity']})" if r["opacity"] else "")
                  + f" {r['text']!r}" for r in bad[:6]),
    )
    tiny = res["smallTargets"]
    checks.ok(
        f"{tag}: no visible control below the 24x24 minimum",
        not tiny,
        "; ".join(f"{r['sel']} {r['w']}x{r['h']} {r['label']!r}" for r in tiny[:6]),
    )
    # The token sweep only sees text that *references* a contract token. Text
    # painted with a literal (`color: #241a10` on a lamp-gold CTA) is invisible
    # to it, and until now it was only ever printed — a NOTE line no reader
    # watches. Measured sub-AA is measured sub-AA wherever the color came from,
    # so it fails here. Rows with no resolvable ground stay a NOTE: a gradient
    # or a translucent stack is not a computed number, and pretending otherwise
    # would train us to ignore the check that matters.
    hard = [r for r in res["failing"] if r["why"] != "no resolvable ground"]
    checks.ok(
        f"{tag}: no measured text below AA, token-fed or literal",
        not hard,
        "; ".join(f"{r['ratio']}:1 (needs {r['need']}) {r['why']} {r['sel']} "
                  f"{r['fg']} on {r['ground']}"
                  + (f" @opacity {r['opacity']}" if r['opacity'] else "")
                  + f" {r['text']!r}" for r in hard[:6]),
    )
    by_shape = {}
    for r in tiny:
        e = by_shape.setdefault(r["sel"], [0, r["w"], r["h"]])
        e[0] += 1
        e[1] = min(e[1], r["w"])
        e[2] = min(e[2], r["h"])
    print(f"  NOTE  {tag}: {len(worst)} token-text runs measured, "
          f"worst {worst[0]['ratio'] if worst else 'n/a'}:1, "
          f"{len(res['failing'])} other sub-AA/inferred, "
          f"{len(tiny)} small targets in {len(by_shape)} shapes")
    for sel, (n, w, h) in sorted(by_shape.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"        {n}x {sel} smallest {w}x{h}")
    for r in res["failing"][:10]:
        print(f"        {r['ratio']}:1 (needs {r['need']}) {r['why']} {r['sel']} {r['text']!r}")


def run(base, name):
    checks = Checks()
    with sync_playwright() as pw:
        for theme in ("night", "dawn"):
            browser, page, errors = launch(pw)
            page.set_viewport_size({"width": 1280, "height": 900})
            page.goto(base)
            page.wait_for_load_state("networkidle")
            if theme == "dawn":
                # the footer toggle lives in the room drawer; the product's own
                # applier is the honest entry point for a theme sweep
                page.evaluate("() => applyDawn(true)")
            checks.ok(f"{theme}: the theme really applied",
                      page.evaluate("() => document.body.classList.contains('dawn')")
                      is (theme == "dawn"))
            # the landing screen is its own world: that is where the primary call
            # to action lives, so a desk-only sweep could never see it
            checks.ok(f"{theme}: landing offers the new-project CTA",
                      page.locator("#new-project-btn:visible").count() > 0)
            sweep(checks, page, f"{theme} landing")

            # The two deliberately-dark rooms. Both paint with their own palette
            # instead of the desk ramp, so neither was ever measured: a sweep
            # that stops at the landing and the desk cannot see them.
            page.locator("#new-idea-btn").click()
            page.wait_for_timeout(900)
            checks.ok(f"{theme}: the idea room is open",
                      page.evaluate("() => document.body.classList.contains('idea-mode')"))
            checks.ok(f"{theme}: the idea room offers its two calls to action",
                      page.locator("#idea-sam-pill:visible, #idea-graduate-btn:visible").count() == 2)
            sweep(checks, page, f"{theme} idea room")
            # The save state is the room's one live status label, and it is only
            # on screen while the autosave runs — a sweep of the empty page
            # would never see it. Drive it the way a writer does.
            page.locator("#idea-content").click()
            page.locator("#idea-content").type("A courier story about regret.", delay=12)
            page.wait_for_timeout(150)
            page.wait_for_selector("#idea-save-state:not(:empty)", timeout=4000)
            sweep(checks, page, f"{theme} idea room, saving")
            page.wait_for_function(
                "() => { const e = document.getElementById('idea-save-state');"
                " return e && /saved/.test(e.textContent); }", timeout=8000)
            sweep(checks, page, f"{theme} idea room, saved")

            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_function("() => !!(state.report && state.report.findings)",
                                   timeout=30000)
            page.evaluate("() => openDock('evidence')")
            page.wait_for_selector("#context-dock.open", timeout=5000)
            open_dock_section_holding(page, ".sev-badge")
            page.wait_for_timeout(400)
            checks.ok(f"{theme}: the desk is still on that theme",
                      page.evaluate("() => document.body.classList.contains('dawn')")
                      is (theme == "dawn"))
            checks.ok(f"{theme}: severity chips are on screen",
                      page.locator(".sev-badge:visible").count() > 0)
            sweep(checks, page, f"{theme} desk")

            # ②b The dispositions the desk sweep could not reach. Every settled
            # row is dimmed with `opacity`, which composites against whatever
            # surface is underneath it — so a sweep of the untouched report
            # measures paper these rows never get. Two real writer calls, taken
            # through the cards' own buttons: "next pass" parks a finding (it
            # stays on screen, muted, once the Next-pass chip shows it) and
            # "addressed" leaves the ledger but not the Fix-queue row.
            def click(page, selector):
                return page.evaluate("""(sel) => {
                  const b = document.querySelector(sel);
                  if (!b) return false;
                  b.click(); return true;
                }""", selector)

            parked = click(page, '.finding-note .intent-btn[title^="Park"]')
            page.wait_for_timeout(700)
            called = click(page, '.finding-note .intent-btn[title^="My call"]')
            page.wait_for_timeout(900)
            chip = page.locator('.dock-filter-row .fchip', has_text="Next pass")
            checks.ok(f"{theme}: the desk offers both writer intents and the chip",
                      parked and called and chip.count() > 0)
            chip.first.click()
            page.wait_for_timeout(700)
            dims = page.evaluate("""() => {
              const visible = (sel) => [...document.querySelectorAll(sel)]
                  .filter((n) => n.offsetParent).length;
              return {deferred: visible('.finding-note.deferred'),
                      done: visible('.fix-row.done'),
                      marks: JSON.stringify(state.findingMarks || {})};
            }""")
            checks.ok(f"{theme}: a parked finding and a done queue row are on screen",
                      dims["deferred"] and dims["done"], str(dims))
            # The recede has to live in a colour, not in an alpha. Asserting the
            # parked card reads dimmer than an open one AND carries no alpha is
            # what stops `opacity` from coming back on a settled row wearing a
            # contrast the sweep would otherwise pass.
            cue = page.evaluate("""() => {
              const one = (sel) => [...document.querySelectorAll(sel)]
                  .find((n) => n.offsetParent);
              const parked = one('.finding-note.deferred');
              const open = one('.finding-note:not(.deferred):not(.addressed):not(.ghosted)');
              const body = (n) => n && getComputedStyle(n.querySelector('.finding-note-text')).color;
              return { parked: body(parked), open: body(open),
                       alpha: parked && getComputedStyle(parked).opacity };
            }""")
            checks.ok(f"{theme}: a parked card recedes by colour, not by alpha",
                      bool(cue["parked"] and cue["open"])
                      and cue["parked"] != cue["open"]
                      and float(cue["alpha"]) == 1.0, str(cue))
            sweep(checks, page, f"{theme} desk, dispositions taken")

            # ③ river read — the same manuscript re-painted on dark glass. Its
            # handler is #flow-btn's, which is parked in the overflow menu, so
            # the product's own click is invoked directly (a JS click fires on
            # a hidden element).
            page.evaluate("() => document.getElementById('flow-btn').click()")
            page.wait_for_timeout(700)
            checks.ok(f"{theme}: river read is on",
                      page.evaluate("() => document.body.classList.contains('river-read')"))
            checks.ok(f"{theme}: the manuscript is on the river surface",
                      page.locator("#manuscript-container .scene-page:visible").count() > 0)
            sweep(checks, page, f"{theme} river read")
            page.evaluate("() => document.getElementById('flow-btn').click()")
            browser.close()
    checks.finish()


if __name__ == "__main__":
    import json
    import tempfile
    import urllib.request

    def post(base, hdr, path):
        req = urllib.request.Request(base + path, data=b"{}",
                                     headers={"Content-Type": "application/json", **hdr},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode() or "{}")

    def force_every_severity(projects_dir, name):
        """The demo model's findings are not HIGH, and the HIGH chip is one of
        the two collision sites. Rewrite the seeded report so every severity
        tier reaches the real renderer — data in, DOM out, no injected markup.
        """
        p = os.path.join(projects_dir, name, "report.findings.json")
        with open(p, encoding="utf-8") as f:
            report = json.load(f)
        for i, finding in enumerate(report.get("findings") or []):
            finding["severity"] = ("high", "medium", "low")[i % 3]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f)

    with start_studio(projects_dir=tempfile.mkdtemp(prefix="readiness_")) as studio:
        proj = post(studio.base_url, studio_headers(studio.base_url), "/api/sample").get("project")
        post(studio.base_url, studio_headers(studio.base_url),
             f"/api/projects/{proj}/analyze")
        force_every_severity(studio.projects_dir, proj)
        run(studio.base_url, proj)
