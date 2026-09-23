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
  const hex = (s) => {
    s = (s || "").trim();
    if (s.startsWith("#")) {
      const h = s.slice(1);
      const f = (a) => parseInt(a, 16) / 255;
      return h.length === 3
        ? [f(h[0] + h[0]), f(h[1] + h[1]), f(h[2] + h[2])]
        : [f(h.slice(0, 2)), f(h.slice(2, 4)), f(h.slice(4, 6))];
    }
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
  const visible = (n) => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const path = (el) => {
    const one = (n) => n.tagName.toLowerCase() + (n.id ? "#" + n.id : "") +
      (n.className && typeof n.className === "string"
        ? "." + n.className.trim().split(/\\s+/).slice(0, 3).join(".") : "");
    return el.className && typeof el.className === "string" && el.className.trim()
      ? one(el) : one(el) + " < " + one(el.parentElement || el);
  };

  // The real ground under an element. Opaque layers composite as usual. A
  // gradient contributes ONLY its fully opaque stops, and the caller takes the
  // worst one — a chip painted with linear-gradient(#a, #b) is legible only if
  // the text clears AA against the stop that fights it hardest. Translucent
  // stops (the rim-light glows) are not grounds; the walk keeps going under them.
  function groundsOf(el) {
    const stack = [];
    let n = el;
    while (n) {
      const st = cs(n);
      const img = st.backgroundImage;
      if (img && img !== "none" && /gradient\\(/.test(img)) {
        const raw = (img.match(/#[0-9a-f]{3,8}\\b|rgba?\\([^)]*\\)/g) || [])
          .map((t) => [hex(t), alpha(t)]).filter(([c]) => c);
        const opaque = raw.filter(([, a]) => a >= 0.999).map(([c]) => c);
        if (opaque.length) {
          let out = opaque;
          for (let i = stack.length - 1; i >= 0; i--) {
            const [c, a] = stack[i];
            out = out.map((g) => blend(c, g, a));
          }
          return out;
        }
      }
      const c = hex(st.backgroundColor);
      if (!c) return null;
      const a = alpha(st.backgroundColor);
      if (a > 0) { stack.push([c, a]); if (a >= 0.999) break; }
      n = n.parentElement;
    }
    if (!stack.length) return null;
    let base = stack[stack.length - 1][0];  // deepest = the first OPAQUE layer
    for (let i = stack.length - 2; i >= 0; i--) base = blend(stack[i][0], base, stack[i][1]);
    return [base];
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
    const size = parseFloat(st.fontSize) || 16;
    const bold = parseInt(st.fontWeight, 10) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
    const grounds = groundsOf(el);
    const own = Object.entries(tokenColors).find(([, c]) =>
      c.every((v, i) => Math.abs(v - fg[i]) < 0.004));
    const rec = {
      sel: path(el),
      text: node.nodeValue.trim().slice(0, 28),
      size: Math.round(size * 10) / 10, need,
      ratio: grounds && grounds.length
        ? Math.round(Math.min(...grounds.map((g) => ratio(fg, g))) * 100) / 100
        : null,
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
        "; ".join(f"{r['token']} {r['ratio']}:1 on {r['sel']} {r['text']!r}" for r in bad[:6]),
    )
    tiny = res["smallTargets"]
    checks.ok(
        f"{tag}: no visible control below the 24x24 minimum",
        not tiny,
        "; ".join(f"{r['sel']} {r['w']}x{r['h']} {r['label']!r}" for r in tiny[:6]),
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
