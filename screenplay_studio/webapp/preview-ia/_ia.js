/* _ia.js — renderer for the post-analysis IA wireframe (preview-ia/index.html).
 *
 * GRAYSCALE, STRUCTURE ONLY. This page exists to review information
 * architecture before any visual direction is decided (the Nocta vs Midnight
 * Desk fork stays parked — REDESIGN_MASTER_PLAN §4/§10). It reads the studio's
 * real Design Lab feed (/api/preview/data/<name>, the same endpoint the six
 * preview-next worlds use); it never writes and never opens a chat.
 *
 * Source of truth: docs/superpowers/specs/2026-10-02-post-analysis-ia-design.md
 *
 * Default project prefers gun_pen_2 > Pain_3_updated_FULL > gun_pen, then any
 * analyzed project. gun_pen's on-disk copy is currently a demo re-analysis, so
 * the wireframe shows the real production run (Pain_3_updated_FULL) until the
 * real gun_pen project is back on the shelf. ?project=<name> overrides.
 */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var SEV_ORDER = { high: 0, medium: 1, low: 2 };
  var PREFERRED = ["gun_pen_2", "Pain_3_updated_FULL", "gun_pen"];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }

  // The studio mints a capability token on /; reads are fine without it, but
  // every lab call follows the same reader (H1 convention).
  function studioToken() {
    var m = document.cookie.match(/(?:^|;\s*)studio_token=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  async function fetchJSON(url) {
    var headers = {};
    var tok = studioToken();
    if (tok) headers["X-Studio-Token"] = tok;
    var r = await fetch(url, { headers: headers });
    var body = await r.json().catch(function () { return {}; });
    if (!r.ok) throw new Error(body.error || r.statusText);
    return body;
  }

  /* ---------- payload -> wireframe model ---------- */
  function normalize(data) {
    var rep = data.report || {};
    var cov = rep.coverage || {};
    var items = (data.fixqueue && data.fixqueue.items) || [];
    var statusByIdx = new Map();
    items.forEach(function (it) { statusByIdx.set(it.index, it); });

    var findings = (rep.findings || []).map(function (f, i) {
      var it = statusByIdx.get(i) || {};
      var ver = (f.verification || {}).status || "";
      return {
        i: i,
        sev: f.severity || "low",
        cat: f.category || "",
        issue: f.issue || "",
        why: f.why_it_matters || "",
        scenes: f.scene_refs || [],
        heading: it.scene_heading || null,
        actName: it.act_name || "Script-level",
        status: it.status || "unknown",
        dismissed: !!it.dismissed,
        quote: f.evidence_quote || f.quote || "",
        ver: ver,
      };
    }).filter(function (f) { return !f.dismissed; });
    findings.sort(function (a, b) {
      return (SEV_ORDER[a.sev] - SEV_ORDER[b.sev]) || (a.i - b.i);
    });

    var scenes = ((data.parsed || {}).scenes || []).map(function (s) {
      return { n: s.scene_number, head: s.heading_raw || "" };
    });

    // Assign each finding to its first scene ref; the rail and the loop walk
    // scene by scene in script order.
    var byScene = new Map();
    findings.forEach(function (f) {
      if (f.scenes.length == null || f.scenes[0] == null) return;
      var n = f.scenes[0];
      if (!byScene.has(n)) byScene.set(n, []);
      byScene.get(n).push(f);
    });

    var mech = Array.isArray(rep.formatting_findings) ? rep.formatting_findings : [];
    var threads = Array.isArray(rep.setup_payoff) ? rep.setup_payoff : [];
    var strengths = cov.strengths || [];

    return {
      name: data.name,
      title: data.title || data.name,
      model: rep.model_used || "",
      recommendation: cov.recommendation || "",
      findings: findings,
      scenes: scenes,
      byScene: byScene,
      mech: mech,
      threads: threads,
      strengths: strengths,
      counts: {
        open: findings.length,
        high: findings.filter(function (f) { return f.sev === "high"; }).length,
        med: findings.filter(function (f) { return f.sev === "medium"; }).length,
        low: findings.filter(function (f) { return f.sev === "low"; }).length,
        mech: mech.length,
        threads: threads.length,
        cleared: findings.filter(function (f) { return f.status === "addressed"; }).length,
      },
    };
  }

  /* ---------- shared bits ---------- */
  function sevChip(s) { return el("span", "sev " + (s || "low"), (s || "low").toUpperCase()); }
  function verTag(f) {
    if (f.ver === "verified") return el("span", "tag ok", "verified");
    if (f.ver === "not_found") return el("span", "tag flag", "quote not found");
    if (f.ver === "no_quote") return el("span", "tag flag", "no quote — flagged");
    if (f.ver === "scene_not_found") return el("span", "tag flag", "scene not found");
    return null;
  }
  function sceneText(f) {
    return f.cat + (f.scenes.length ? " · scene " + f.scenes.join(", ") : " · script-level");
  }

  function gistRow(f, chev) {
    var r = el("div", "row");
    r.appendChild(sevChip(f.sev));
    var mid = el("div", "row-mid");
    var head = el("div", "row-head");
    head.appendChild(el("span", "cat", sceneText(f)));
    var t = verTag(f); if (t) head.appendChild(t);
    mid.appendChild(head);
    mid.appendChild(el("div", "row-issue", f.issue));
    r.appendChild(mid);
    if (chev) {
      var cv = el("span", "chev", "›");
      cv.setAttribute("aria-hidden", "true");
      r.appendChild(cv);
    }
    return r;
  }

  function l2Card(f) {
    var c = el("div", "card");
    var head = el("div", "card-head");
    head.appendChild(sevChip(f.sev));
    head.appendChild(el("span", "cat", sceneText(f)));
    var t = verTag(f); if (t) head.appendChild(t);
    if (f.actName) head.appendChild(el("span", "tag mut", f.actName));
    c.appendChild(head);
    c.appendChild(el("div", "card-issue", f.issue));
    if (f.why) c.appendChild(el("div", "card-why", "Why it matters: " + f.why));
    c.appendChild(el("div", "quote" + (f.quote ? "" : " missing"),
      f.quote ? "“" + f.quote + "”" : "No quote to verify — the finding stays visible, flagged."));
    var verbs = el("div", "verbs");
    ["Locate", "Discuss with Sushruta", "Park for the next pass", "My call: addressed"].forEach(function (v) {
      var b = el("button", "vbtn", v);
      b.type = "button";
      b.title = "wireframe sketch — not wired";
      verbs.appendChild(b);
    });
    c.appendChild(verbs);
    return c;
  }

  function railRow(sc, list, current) {
    var r = el("div", "rail-row" + (current ? " current" : ""));
    r.setAttribute("role", "listitem");
    r.appendChild(el("span", "rail-n", String(sc.n)));
    r.appendChild(el("span", "rail-head", sc.head));
    var right = el("span", "rail-marks");
    if (!list || !list.length) {
      right.appendChild(el("span", "tick", "✓"));
    } else {
      ["high", "medium", "low"].forEach(function (s) {
        if (list.some(function (f) { return f.sev === s; })) right.appendChild(el("span", "dot " + s));
      });
      right.appendChild(el("span", "rail-count", String(list.length)));
    }
    right.setAttribute("aria-hidden", "true");
    r.appendChild(right);
    r.setAttribute("aria-label", "Scene " + sc.n + " — " +
      (list && list.length ? list.length + " live findings" : "clean"));
    return r;
  }

  function foldBar(label, count, kind) {
    var b = el("div", "fold");
    b.appendChild(el("span", "tier " + kind, kind === "mech" ? "MECH" : kind === "struct" ? "STRUCT" : "JUDG"));
    b.appendChild(el("span", "fold-title", label));
    b.appendChild(el("span", "count", String(count)));
    var fb = el("span", "chev", "›");
    fb.setAttribute("aria-hidden", "true");
    b.appendChild(fb);
    b.setAttribute("aria-label", label + " — " + count + " folded, counted");
    return b;
  }

  /* ---------- frames ---------- */
  function renderArrival(m) {
    var c = m.counts;
    var line = $("#arr-line");
    clear(line);
    var halo = el("span", "halo");
    halo.setAttribute("aria-hidden", "true");
    line.appendChild(halo);
    line.appendChild(el("span", "arrive-text",
      "Analysis ready · " + c.high + " high · "));
    var cta = el("button", "cta-btn", "Start the fix loop");
    cta.type = "button";
    cta.title = "wireframe sketch — not wired";
    line.appendChild(cta);
    $("#arr-tierline").textContent =
      c.open + " open findings · " + c.mech + " mechanical checks · " + c.threads +
      " structural reads · every count from one predicate (findingDisposition)";
    $("#arr-return").textContent =
      c.high + " high still live · line only, no halo once seen · resume from where you left";
  }

  function renderLoop(m) {
    var c = m.counts;
    var paid = m.threads.filter(function (t) { return t.status === "paid"; }).length;
    var unpaid = m.threads.length - paid;
    var strip = $("#loop-threads");
    clear(strip);
    strip.appendChild(el("span", "tier struct", "STRUCT"));
    strip.appendChild(el("span", "fold-title",
      "Whole script · " + c.threads + " setup/payoff threads (" + paid + " paid · " + unpaid +
      " open) · coverage · " + c.mech + " mechanical checks as one checklist"));
    var scv = el("span", "chev", "›");
    scv.setAttribute("aria-hidden", "true");
    strip.appendChild(scv);
    $("#loop-mech-note").textContent =
      "One checklist, read once. In the doc this batch is per scene where checks are scene-anchored; " +
      "here it is the whole-script stop so nothing is implied that the data cannot back.";

    // scene rail
    var rail = $("#loop-rail");
    clear(rail);
    var firstHigh = m.findings.filter(function (f) { return f.sev === "high" && f.scenes.length; })[0];
    var loopN = firstHigh ? firstHigh.scenes[0] : (m.scenes[0] ? m.scenes[0].n : null);
    m.scenes.forEach(function (sc) {
      rail.appendChild(railRow(sc, m.byScene.get(sc.n), sc.n === loopN));
    });

    // the current scene's card stack
    var sc = m.scenes.filter(function (s) { return s.n === loopN; })[0] || { n: loopN, head: "" };
    $("#loop-scene-kick").textContent = "Scene " + sc.n + " of " + m.scenes.length + " · declared depth: just the highs";
    $("#loop-scene").textContent = sc.head || "(scene " + sc.n + ")";
    var rows = $("#loop-rows");
    clear(rows);
    var list = (m.byScene.get(sc.n) || []);
    if (!list.length) {
      rows.appendChild(el("div", "row empty", "No live findings in this scene — it gets the ✓ and the loop moves on."));
    } else {
      list.forEach(function (f, idx) { rows.appendChild(gistRow(f, idx > 0)); });
    }
    var cardWrap = $("#loop-card");
    clear(cardWrap);
    cardWrap.appendChild(l2Card(list[0] || m.findings[0] || {
      sev: "low", cat: "—", issue: "No findings to show.", why: "", scenes: [], ver: "", actName: "",
    }));
    var clearedHigh = m.findings.filter(function (f) {
      return f.sev === "high" && f.status === "addressed";
    }).length;
    $("#loop-progress").textContent =
      "Progress: " + clearedHigh + " of " + c.high + " highs cleared · scene " + sc.n +
      " · Esc exits; the arrival line resumes you here";
  }

  function renderLedger(m) {
    var c = m.counts;
    $("#led-totals").textContent =
      c.open + " open · " + c.high + " high · " + c.med + " medium · " + c.low + " low";

    var cats = new Map();
    m.findings.forEach(function (f) { cats.set(f.cat, (cats.get(f.cat) || 0) + 1); });
    var facets = $("#led-facets");
    clear(facets);
    Array.from(cats.entries()).sort(function (a, b) { return b[1] - a[1]; }).forEach(function (pair) {
      var chip = el("span", "chip", pair[0] + " " + pair[1]);
      chip.title = "category facet — filter, counted, and never silent about what it hides";
      facets.appendChild(chip);
    });

    var list = $("#led-list");
    clear(list);
    m.findings.slice(0, 6).forEach(function (f) { list.appendChild(gistRow(f, true)); });

    var mech = $("#led-mech");
    clear(mech);
    mech.appendChild(foldBar("Formatting & continuity checks — labeled checks, not judgment", c.mech, "mech"));

    var threads = $("#led-threads");
    clear(threads);
    threads.appendChild(foldBar("Setup/payoff ledger", c.threads, "struct"));
    m.threads.slice(0, 2).forEach(function (t) {
      var row = el("div", "thread");
      row.appendChild(el("span", "thread-name", t.setup || "—"));
      row.appendChild(el("span", "tag mut", t.status || ""));
      threads.appendChild(row);
    });

    var work = $("#led-working");
    clear(work);
    work.appendChild(foldBar("What’s working — leads the ledger", m.strengths.length, "judg"));
    m.strengths.forEach(function (s) { work.appendChild(el("div", "strength", s)); });

    var cardWrap = $("#led-card");
    clear(cardWrap);
    var cardF = m.findings.filter(function (f) { return f.sev === "high" && f.quote; })[0] ||
                m.findings.filter(function (f) { return f.sev === "high"; })[0] ||
                m.findings[0];
    if (cardF) cardWrap.appendChild(l2Card(cardF));
  }

  function renderRegisters(m) {
    var c = m.counts;
    $("#reg-counts").textContent = c.high + " high · " + c.open + " open · counted once, shown twice";
    var pin = m.findings.filter(function (f) { return f.sev === "high" && f.quote; })[0] ||
              m.findings.filter(function (f) { return f.sev === "high"; })[0] || m.findings[0];
    var wrap = $("#reg-pin");
    clear(wrap);
    if (!pin) { wrap.appendChild(el("div", "row empty", "No finding to pin.")); return; }
    wrap.appendChild(el("div", "pin-kick", "Discussing a finding — the pin survives every switch"));
    wrap.appendChild(el("div", "pin-body", pin.quote ? "“" + pin.quote + "”" : pin.issue));
    wrap.appendChild(el("div", "pin-meta", "scene " + (pin.scenes[0] || "—") + " · " + pin.cat + " · " + pin.sev));
  }

  /* ---------- boot ---------- */
  function showLoadError(err) {
    var box = $("#loadError");
    box.hidden = false;
    clear(box);
    box.appendChild(el("div", "err-kick", "No live data — open this page through the studio"));
    box.appendChild(el("div", "err-body",
      "Start the studio (python -m screenplay_studio.webapp --port 8500 --projects studio_projects), " +
      "open an analyzed project once, then visit /preview-ia/index.html. The wireframe reads the same " +
      "Design Lab feed the preview-next worlds use. (" + String(err && err.message || err) + ")"));
  }

  function fillSwitcher(shelf, current) {
    var sel = $("#projectSel");
    clear(sel);
    shelf.forEach(function (p) {
      var o = el("option", null, p.title + "  ·  " + p.name + (p.has_findings ? "" : " (no analysis yet)"));
      o.value = p.name;
      if (p.name === current) o.selected = true;
      sel.appendChild(o);
    });
    sel.disabled = shelf.length === 0;
    sel.addEventListener("change", function () {
      location.search = "?project=" + encodeURIComponent(sel.value);
    });
  }

  async function boot() {
    var qp = new URLSearchParams(location.search).get("project");
    var shelf = [];
    try {
      shelf = (await fetchJSON("/api/preview/projects")).projects || [];
    } catch (e) {
      showLoadError(e);
      return;
    }
    var usable = shelf.filter(function (p) { return p.has_findings; });
    var pick = (qp && usable.some(function (p) { return p.name === qp; })) ? qp : null;
    if (!pick) {
      for (var i = 0; i < PREFERRED.length; i++) {
        if (usable.some(function (p) { return p.name === PREFERRED[i]; })) { pick = PREFERRED[i]; break; }
      }
    }
    if (!pick && usable.length) pick = usable[0].name;
    if (!pick) { showLoadError(new Error("no analyzed project on the shelf")); return; }

    var data;
    try {
      data = await fetchJSON("/api/preview/data/" + encodeURIComponent(pick));
    } catch (e) {
      showLoadError(e);
      return;
    }
    if (!data.report) {
      showLoadError(new Error("project has no analysis report"));
      return;
    }

    var m = normalize(data);
    $("#srcBadge").className = "badge live";
    $("#srcBadge").textContent = "LIVE — real studio payload";
    $("#srcLine").textContent = m.title + (m.model ? "  ·  analyzed with " + m.model : "");
    document.title = "IA Wireframe — " + m.title;
    $("#pickNote").textContent =
      "Default prefers gun_pen_2 → Pain_3_updated_FULL → gun_pen. Pick any analyzed project above; " +
      "?project=<name> in the URL works too.";
    fillSwitcher(shelf, pick);

    renderArrival(m);
    renderLoop(m);
    renderLedger(m);
    renderRegisters(m);
    document.body.dataset.loaded = "true";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
