/* _lab.js — Design Lab shared layer (v5, real data + real endpoints).
 *
 * Every preview-next world includes this AFTER a small inline config:
 *   window.LAB_IA = "report" | "chat" | "canvas" | "stream" | "inspector" | "command";
 *   window.LAB_PROJECT = "The_Late_Hour" | null (null = first shelf project);
 * then calls Lab.boot({ onReady, render }).
 *
 * What lives here (shared because it is the CONTRACT, not the IA):
 *   - data: fetch real project payload from /api/preview/data/<name>, with a
 *     static _payload.js fallback for file:// review.
 *   - panes: the tri-pane desk state machine (script center; feedback LEFT;
 *     sameer RIGHT; independent toggles + both-at-once master). Uniform
 *     data-pane-* hooks so the e2e walks every world identically.
 *   - chat: REAL Sameer turns — POST /api/preview/chat/<name> (isolated
 *     preview-lab session; the writer's own thread is never touched).
 *   - verbs: Locate (jump to the real scene), Discuss (pre-fill), Dismiss
 *     (POST to the app's real dismiss routes — persists across reloads).
 *   - switcher: real project switcher across the shelf.
 *
 * What does NOT live here: each world's information architecture — skeleton,
 * navigation, landing view, and layout are the world's own.
 */
(function () {
  "use strict";

  const $  = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  const IA = window.LAB_IA || "report";
  let PROJECT = window.LAB_PROJECT || null;
  let DATA = null;
  let STATE = { left: true, right: true, feedback: "auto" }; // feedback: auto|empty|running|complete

  async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || r.statusText), { status: r.status, body });
    return body;
  }

  /* ---------- data (real, with static fallback) ---------- */
  async function loadData() {
    try {
      DATA = await fetchJSON(`/api/preview/data/${encodeURIComponent(PROJECT)}`);
      DATA.live = true;
    } catch (e) {
      // static fallback (file:// review) — shape mirrors the endpoint
      const P = window.PAYLOAD;
      DATA = P ? {
        name: P.project.title.replace(/\s+/g, "_"), title: P.project.title,
        format: P.project.format, live: false,
        stages: { parse: "complete", analyze: P.project.analyzed ? "complete" : "pending", chat: "pending" },
        parsed: {
          scenes: P.script.map(sc => ({
            scene_number: sc.n, heading_raw: sc.slug,
            elements: sc.elements.map(([t, a, b]) =>
              t === "dialogue" ? { type: "character", text: a }
              : t === "parenthetical" ? { type: "parenthetical", text: a }
              : t === "transition" ? { type: "transition", text: a }
              : { type: t === "action" ? "action" : "general", text: a }),
          })),
        },
        report: P.project.analyzed ? {
          logline: P.coverage.logline, genre: P.coverage.genre,
          synopsis: P.coverage.synopsis, recommendation: P.coverage.recommendation,
          findings: P.findings.map(f => ({
            index: f.id - 1, category: f.category, severity: f.severity,
            issue: f.note, why_it_matters: "", scene_refs: [f.scene],
            verified: f.verified, quote: f.quote,
          })),
          pacing: P.pacing.map(p => ({ scene_number: p.scene, pace: p.pace, drag: p.drag, density: p.density, action_share: p.action_share })),
          character_dials: P.dials.map(d => ({ character: d.character, poles: d.poles, scene_numbers: d.scenes })),
          setup_payoff: P.ledger.map(l => ({ setup: l.setup, kind: l.kind, setup_scene: l.setup_scene, status: l.status, note: l.note })),
          character_reads: P.reads.map(r => ({ character: r.character, read: r.read })),
        } : null,
        fixqueue: P.project.analyzed ? {
          items: P.findings.map((f, i) => ({
            index: i, category: f.category, severity: f.severity, issue: f.note,
            scene_refs: [f.scene], verified: f.verified, quote: f.quote,
            status: "unknown", dismissed: false, act_name: "Script-level",
          })),
          dismissed_keys: [],
        } : null,
        shelf: [{ name: DATA0_NAME(), title: P.project.title, format: P.project.format,
                  stage_parse: "complete", stage_analyze: P.project.analyzed ? "complete" : "pending",
                  has_findings: !!P.project.analyzed }],
      } : { error: "No data", shelf: [] };
    }
  }
  function DATA0_NAME() { return (window.PAYLOAD && window.PAYLOAD.project.title.replace(/\s+/g, "_")) || "Fallback"; }

  /* ---------- derived views over the REAL report ---------- */
  function findings() {
    return (DATA.report && DATA.report.findings) || [];
  }
  function fixItems() {
    if (DATA.fixqueue && DATA.fixqueue.items) return DATA.fixqueue.items;
    return findings().map((f, i) => ({
      index: i, category: f.category, severity: f.severity, issue: f.issue,
      why_it_matters: f.why_it_matters, scene_refs: f.scene_refs || [],
      verified: f.verified !== false, quote: f.quote,
      status: "unknown", dismissed: false, act_name: "Script-level",
    }));
  }
  function sceneByNumber(n) {
    return ((DATA.parsed || {}).scenes || []).find(s => s.scene_number === n) || null;
  }
  function stages() {
    return DATA.stages || { parse: "pending", analyze: "pending", chat: "pending" };
  }
  const STAGE_NAMES = ["Formatting & stats", "Voice & subtext", "Continuity", "Scene summaries",
    "Dialogue analysis", "Script categories", "Principles engine", "Setup/payoff ledger",
    "Character dials", "Verification", "Coverage", "Logline & genre"];

  /* ---------- panes: the tri-pane state machine (uniform contract) ---------- */
  function deskState() {
    if (STATE.left && STATE.right) return "both-open";
    if (STATE.left) return "left-only";
    if (STATE.right) return "right-only";
    return "none-open";
  }
  function renderPanes() {
    const d = $("[data-desk]");
    if (!d) return;
    d.dataset.deskState = deskState();
    d.classList.toggle("left-closed", !STATE.left);
    d.classList.toggle("right-closed", !STATE.right);
    $$("[data-pane-left-toggle]").forEach(b => b.setAttribute("aria-pressed", String(STATE.left)));
    $$("[data-pane-right-toggle]").forEach(b => b.setAttribute("aria-pressed", String(STATE.right)));
  }
  function toggleLeft() { STATE.left = !STATE.left; renderPanes(); }
  function toggleRight() { STATE.right = !STATE.right; renderPanes(); }
  function toggleMaster() {
    if (STATE.left || STATE.right) { STATE.left = false; STATE.right = false; }
    else { STATE.left = true; STATE.right = true; }
    renderPanes();
  }
  function wirePaneControls() {
    $$("[data-pane-left-toggle]").forEach(b => b.addEventListener("click", toggleLeft));
    $$("[data-pane-right-toggle]").forEach(b => b.addEventListener("click", toggleRight));
    $$("[data-panes-master]").forEach(b => b.addEventListener("click", toggleMaster));
  }

  /* ---------- feedback lifecycle (real stage states) ---------- */
  function feedbackMode() {
    if (STATE.feedback !== "auto") return STATE.feedback;
    return stages().analyze === "complete" ? "complete" : "empty";
  }
  function renderFeedback() {
    $$("[data-state]").forEach(el => el.style.display = "none");
    const el = $(`[data-state="${feedbackMode()}"]`);
    if (el) el.style.display = "";
  }
  function wireFeedbackToggle() {
    $$("[data-fb]").forEach(b => b.addEventListener("click", () => {
      STATE.feedback = b.dataset.fb; renderFeedback();
      $$("[data-fb]").forEach(x => x.classList.toggle("on", x === b));
    }));
  }

  /* ---------- real chat (isolated preview-lab session) ---------- */
  async function chatHistory() {
    return fetchJSON(`/api/preview/chat/${encodeURIComponent(PROJECT)}`);
  }
  async function chatSend(message, quote) {
    return fetchJSON(`/api/preview/chat/${encodeURIComponent(PROJECT)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, quote: quote || null }),
    });
  }
  async function chatClear() {
    return fetchJSON(`/api/preview/chat/${encodeURIComponent(PROJECT)}`, { method: "DELETE" });
  }
  function renderThread(container, messages) {
    if (!container) return;
    container.innerHTML = messages.map(m => `
      <div class="lab-msg ${m.role === "user" ? "lab-me" : "lab-sam"}">
        <div class="lab-msg-who">${m.role === "user" ? "You" : "Sameer"}</div>
        <div class="lab-msg-bubble">${esc(m.content).replace(/\n/g, "<br>")}</div>
      </div>`).join("");
    container.scrollTop = container.scrollHeight;
  }
  function wireComposer(textareaSel, sendBtnSel, threadSel, quoteHolder) {
    const ta = $(textareaSel), btn = $(sendBtnSel), thread = $(threadSel);
    if (!ta || !btn) return;
    const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 200) + "px"; };
    ta.addEventListener("input", grow);
    async function send() {
      const text = ta.value.trim();
      if (!text) return;
      ta.value = ""; grow();
      const quote = (quoteHolder && quoteHolder.quote) || null;
      if (thread) thread.insertAdjacentHTML("beforeend",
        `<div class="lab-msg lab-me"><div class="lab-msg-who">You</div>
         <div class="lab-msg-bubble">${esc(text).replace(/\n/g, "<br>")}</div></div>`);
      if (thread) thread.scrollTop = thread.scrollHeight;
      btn.disabled = true;
      try {
        const res = await chatSend(text, quote);
        renderThread(thread, res.messages);
        if (quoteHolder) clearQuote();
      } catch (e) {
        if (thread) thread.insertAdjacentHTML("beforeend",
          `<div class="lab-msg lab-sam"><div class="lab-msg-who">Sameer</div>
           <div class="lab-msg-bubble lab-err">${esc(e.message || "The model server could not be reached.")}</div></div>`);
      } finally {
        btn.disabled = false;
      }
    }
    btn.addEventListener("click", send);
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }
  let _quote = null;
  function setQuote(quote) { _quote = quote; }
  function getQuote() { return _quote; }
  function clearQuote() {
    _quote = null;
    $$("[data-lab-quote]").forEach(el => { el.hidden = true; });
  }
  function fillQuoteUI(quote, srcText) {
    _quote = quote;
    $$("[data-lab-quote]").forEach(el => {
      el.hidden = false;
      const t = $("[data-lab-quote-text]", el), s = $("[data-lab-quote-src]", el);
      if (t) t.textContent = "\u201C" + quote.text + "\u201D";
      if (s) s.textContent = srcText;
    });
  }

  /* ---------- verbs: Locate / Discuss / Dismiss (real endpoints) ---------- */
  function locateFinding(f) {
    const n = (f.scene_refs && f.scene_refs[0]) || null;
    const pane = $(`[data-scene="${n}"]`);
    Lab.onLocate && Lab.onLocate(f, pane);
    if (pane) {
      $$(".lab-flash").forEach(e => e.classList.remove("lab-flash"));
      pane.classList.add("lab-flash");
      pane.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      setTimeout(() => pane.classList.remove("lab-flash"), 1800);
    }
  }
  function discussFinding(f) {
    Lab.onDiscuss && Lab.onDiscuss(f);
    fillQuoteUI({ scene_number: (f.scene_refs || [])[0] || null, text: f.quote || f.issue || "" },
      `Finding — ${f.category} · severity ${f.severity}`);
    $$("[data-lab-composer-focus]").forEach(el => el.focus());
  }
  async function dismissFinding(f) {
    if (!DATA.live) { f._localDismiss = true; return; }
    await fetchJSON(`/api/projects/${encodeURIComponent(PROJECT)}/findings/${f.index}/dismiss`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue: f.issue || "" }),
    });
  }
  async function undismissFinding(f) {
    if (!DATA.live) { f._localDismiss = false; return; }
    await fetchJSON(`/api/projects/${encodeURIComponent(PROJECT)}/findings/${f.index}/undismiss`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
  }
  function wireFindingVerbs(containerSel, reRender) {
    $(containerSel).addEventListener("click", async e => {
      const b = e.target.closest("[data-verb]");
      if (!b) return;
      const idx = +b.closest("[data-finding]").dataset.finding;
      const f = fixItems().find(x => x.index === idx);
      if (!f) return;
      if (b.dataset.verb === "locate") locateFinding(f);
      if (b.dataset.verb === "discuss") discussFinding(f);
      if (b.dataset.verb === "dismiss") { await dismissFinding(f); f.dismissed = true; reRender && reRender(); }
      if (b.dataset.verb === "undismiss") { await undismissFinding(f); f.dismissed = false; reRender && reRender(); }
    });
  }

  /* ---------- project switcher (real shelf) ---------- */
  async function loadShelf() {
    if (DATA.live) {
      try {
        const body = await fetchJSON("/api/preview/projects");
        DATA.shelf = body.projects;
      } catch (e) { /* keep endpoint-provided shelf */ }
    }
  }
  function renderShelf(sel) {
    const el = $(sel);
    if (!el || !DATA.shelf) return;
    el.innerHTML = DATA.shelf.map(p =>
      `<option value="${esc(p.name)}" ${p.name === PROJECT ? "selected" : ""}>${esc(p.title)}${p.has_findings ? "" : " (not analyzed)"}</option>`).join("");
  }
  function wireShelf(sel, onChange) {
    const el = $(sel);
    if (!el) return;
    el.addEventListener("change", () => {
      PROJECT = el.value;
      const u = new URL(location.href);
      u.searchParams.set("project", PROJECT);
      history.replaceState(null, "", u);
      location.reload();
      onChange && onChange(PROJECT);
    });
  }

  /* ---------- shared chrome: top bar + review bar + tri-pane desk ----------
   * The IA contract pieces (switcher, live badge, title, pane toggles,
   * findings pane, script pages, Sameer thread, composer, quote card) are
   * injected identically into every world — what differs per world is only
   * the landing view and how it links into the desk. */

  const DESK_HTML = `
    <aside class="pane pane-left" aria-label="Feedback">
      <div class="pane-head"><h3>Feedback</h3></div>
      <div class="lab-thread" id="lab-desk-findings" style="padding:14px 16px"></div>
    </aside>
    <div class="lab-scroll lab-pages" aria-label="Script" id="lab-desk-pages"></div>
    <aside class="pane pane-right" aria-label="Sameer">
      <div class="pane-head"><h3>Sameer</h3></div>
      <div class="lab-thread" data-lab-thread id="lab-thread"></div>
      <div class="lab-quote" data-lab-quote hidden>
        <span data-lab-quote-text></span>
        <span class="qsrc" data-lab-quote-src></span>
      </div>
      <div class="lab-composer">
        <textarea data-lab-composer-input rows="1" placeholder="Reply to Sameer — a real turn on the real script…"></textarea>
        <button class="send" data-lab-composer-send aria-label="Send">↑</button>
      </div>
    </aside>`;

  const TOP_HTML = `
    <header class="lab-top">
      <span class="mark">${IA}-first</span>
      <span class="who" data-lab-title></span>
      <span class="live" data-lab-live></span>
      <span class="switcher">project
        <select data-lab-switcher aria-label="Project"></select>
      </span>
      <a class="home" href="index.html">Lab</a>
    </header>`;

  const PV_HTML = `
    <div id="pv">
      <b>REVIEW</b>
      <button data-lab-home>Home</button>
      <span class="sep"></span>
      <button data-fb="empty">Empty</button>
      <button data-fb="running">Running</button>
      <button data-fb="complete" class="on">Complete</button>
      <span class="sep"></span>
      <a href="index.html">Gallery</a>
      <button id="pv-close" aria-label="Dismiss review bar">✕</button>
    </div>`;

  function mountChrome() {
    document.body.insertAdjacentHTML("afterbegin", TOP_HTML + PV_HTML);
    $("#pv-close").addEventListener("click", () => $("#pv").remove());
    $$("[data-lab-home]").forEach(b => b.addEventListener("click", () => { showDesk(false); if (Lab.onHome) Lab.onHome(); }));
  }

  function mountDesk(hiddenOnLoad) {
    document.body.insertAdjacentHTML("beforeend", `<div data-desk="both-open" style="${hiddenOnLoad ? "display:none" : ""}">${DESK_HTML}</div>
      <div class="desk-ctl" style="display:none">
        <button data-pane-left-toggle title="Fold/unfold feedback (left)">left</button>
        <button data-panes-master>fold both / open both</button>
        <button data-pane-right-toggle title="Fold/unfold Sameer (right)">right</button>
      </div>`);
    renderPanes();
    wirePaneControls();
    wireFeedbackToggle();
    wireComposer("[data-lab-composer-input]", "[data-lab-composer-send]", "[data-lab-thread]");
  }

  function showDesk(show) {
    const d = $("[data-desk]"), ctl = $(".desk-ctl");
    if (!d) return;
    if (d.style.display === "none" || d.style.display === "") d.style.display = show ? "grid" : "none";
    else d.style.display = show ? "grid" : "none";
    if (ctl) ctl.style.display = show ? "flex" : "none";
  }
  function deskVisible() {
    const d = $("[data-desk]");
    return d && d.style.display !== "none";
  }

  function renderDeskFromData() {
    // script pages
    const scenes = (DATA.parsed || {}).scenes || [];
    const pages = $("#lab-desk-pages");
    if (pages) pages.innerHTML = scenes.map(sc => `
      <article class="lab-page" data-scene="${sc.scene_number}">
        <div class="slug">SCENE ${sc.scene_number} — ${esc(sc.heading_raw || "")}</div>
        ${(sc.elements || []).map(el => {
          const t = el.type || "general";
          if (t === "character") return `<div class="lab-el character">${esc(el.text)}</div>`;
          if (t === "dialogue") return `<div class="lab-el dialogue">${esc(el.text)}</div>`;
          if (t === "parenthetical") return `<div class="lab-el parenthetical">${esc(el.text)}</div>`;
          if (t === "transition") return `<div class="lab-el transition">${esc(el.text)}</div>`;
          return `<div class="lab-el action">${esc(el.text)}</div>`;
        }).join("")}
      </article>`).join("");
    // findings pane
    const df = $("#lab-desk-findings");
    if (df) {
      df.innerHTML = fixItems().map(f => `
        <div class="lab-finding ${f.dismissed ? "dismissed" : ""}" data-finding="${f.index}">
          <div class="fhead">
            <span class="lab-sev sev-${f.severity}">${f.severity || "?"}</span>
            <span class="fcat">s${(f.scene_refs || [])[0] || "—"}</span>
          </div>
          <div style="font-size:13.5px">${esc((f.issue || "").split(". ")[0])}.</div>
          <div class="fverbs">
            <button data-verb="locate">locate</button>
            <button data-verb="discuss">discuss</button>
            <button data-verb="${f.dismissed ? "undismiss" : "dismiss"}">${f.dismissed ? "restore" : "dismiss"}</button>
          </div>
        </div>`).join("") || '<div class="lab-empty-note">No findings yet.</div>';
    }
  }

  function renderFindingsInto(sel) {
    const box = $(sel);
    if (!box) return;
    box.innerHTML = fixItems().map(f => `
      <div class="lab-finding ${f.dismissed ? "dismissed" : ""}" data-finding="${f.index}">
        <div class="fhead">
          <span class="lab-sev sev-${f.severity}">${f.severity || "?"}</span>
          <span class="fcat">${esc(f.category || "")} · scene ${(f.scene_refs || [])[0] || "—"}</span>
          ${f.verified === false ? '<span class="vtag">unverified</span>' : ""}
        </div>
        <div style="font-size:14.5px">${esc(f.issue || "")}</div>
        ${f.quote ? `<div class="fquote ${f.verified === false ? "unverified" : ""}">“${esc(f.quote)}”</div>` : ""}
        <div class="fverbs">
          <button data-verb="locate">📍 Locate</button>
          <button data-verb="discuss">💬 Discuss</button>
          <button data-verb="${f.dismissed ? "undismiss" : "dismiss"}">${f.dismissed ? "Restore" : "Dismiss"}</button>
        </div>
      </div>`).join("") || '<div class="lab-empty-note">No findings yet — Run Analysis from the studio.</div>';
  }

  /* ---------- boot ---------- */
  async function boot(opts) {
    opts = opts || {};
    if (!PROJECT) {
      try { PROJECT = new URL(location.href).searchParams.get("project"); } catch (e) { /* file:// */ }
    }
    if (!PROJECT) {
      try { PROJECT = (JSON.parse(localStorage.getItem("labProject") || "null")); } catch (e) { /* ignore */ }
    }
    // no project chosen yet: ask the shelf (live) so first paint is real data
    if (!PROJECT) {
      try {
        const shelfBody = await fetchJSON("/api/preview/projects");
        if (shelfBody.projects && shelfBody.projects.length) PROJECT = shelfBody.projects[0].name;
      } catch (e) { /* file:// — static fallback below */ }
    }
    await loadData();
    if (!PROJECT && DATA.shelf && DATA.shelf.length) PROJECT = DATA.shelf[0].name;
    if (PROJECT) { try { localStorage.setItem("labProject", JSON.stringify(PROJECT)); } catch (e) {} }
    await loadShelf();
    renderDeskFromData();
    renderPanes();
    renderFeedback();
    wirePaneControls();
    wireFeedbackToggle();
    wireShelf("[data-lab-switcher]");
    renderShelf("[data-lab-switcher]");
    $$("[data-lab-title]").forEach(el => { el.textContent = DATA.title || PROJECT || ""; });
    $$("[data-lab-live]").forEach(el => { el.textContent = DATA.live ? "live data" : "static fallback"; });
    if (opts.render) opts.render();
    Lab.ready = true;
    document.dispatchEvent(new CustomEvent("lab:ready", { detail: { data: DATA } }));
  }

  const Lab = {
    IA, get project() { return PROJECT; }, get data() { return DATA; },
    $, $$, esc, boot, loadData, loadShelf, renderShelf,
    findings, fixItems, sceneByNumber, stages, STAGE_NAMES,
    deskState, renderPanes, toggleLeft, toggleRight, toggleMaster, wirePaneControls,
    feedbackMode, renderFeedback, wireFeedbackToggle,
    chatHistory, chatSend, chatClear, renderThread, wireComposer,
    setQuote, getQuote, clearQuote, fillQuoteUI,
    locateFinding, discussFinding, dismissFinding, undismissFinding, wireFindingVerbs,
    mountChrome, mountDesk, showDesk, deskVisible, renderDeskFromData, renderFindingsInto,
    ready: false, onLocate: null, onDiscuss: null, onHome: null,
  };
  window.Lab = Lab;
})();
