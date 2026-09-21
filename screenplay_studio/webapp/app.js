// Script Doctor Studio — frontend logic (vanilla JS, no build step)

const API = "/api";

const state = {
  projects: [],
  ideas: [],              // idea room: scriptless development sessions
  library: [],            // writer's library: digest of past projects
  stash: [],              // the Stash: saved snippets for the current project
  currentProject: null,   // project name (string)
  currentIdea: null,      // { id, title, card } — the desk is in idea mode when set
  currentIdeaSession: null,
  inIdea: false,          // true when the premise card (not pages) is on the desk
  currentSession: null,   // session id
  branches: {},           // { branchName: { messages, active_persona, active_mode, parent_branch } }
  currentBranch: "main",
  config: { server_url: "http://localhost:8080", model: null, timeout: 600 },
  view: "chat",          // "chat" | "script"
  script: null,           // working-copy ScriptDocument JSON (script view)
  findings: [],           // findings from report.findings.json
  findingStatus: {},      // finding id (or legacy index) -> addressed / still_present / unknown
  findingIds: [],         // index -> content-hash finding id (computeFindingId)
  findingDefer: {},       // finding id -> "deferred" (client intent, Phase D) — forward-compat
  ghostedIds: new Set(),  // finding ids the writer saw as stale (Phase E diff) — forward-compat
  // ONE filter: drives ink, board, loop, fix queue, counts (R5-b + GAP-1).
  // Default = ALL severities (2026-09-20 UI audit, defect #1): the dock's mass
  // strip counts every finding, so a highs-only default made the room read
  // "6 open of 6 findings" over "0 shown / 6 total" — a self-contradiction that
  // destroyed trust in every number. Show the ledger whole; the writer narrows
  // with the chips. Page ink stays naturally sparse because a finding can only
  // ink when it carries a quote (most findings are no_quote).
  findingFilter: { severities: ["high", "medium", "low"], showDeferred: false, category: null },
  findingMarks: {},       // finding id -> "addressed" | "deferred" (writer intent, server-persisted)
  lastPass: null,         // arrival scorekeeping from the server (R4 diff) — null = first pass
  lastPassKey: null,      // computed_at of the last seen pass (arrival detection)
  editsData: null,        // { edits, findings_status } from /edits
  drafts: null,           // { active_draft, drafts } from /drafts
  fixQueue: null,         // { items, acts, dismissed_flags } from /fixqueue
  reportStats: null,      // stats from report.findings.json
  premise: null,          // premise card carried into a graduated project
  notes: [],              // the writer's own margin notes
  charTracks: [],         // per-character track layer from /characters
};

// ---------- utilities ----------

function $(sel) { return document.querySelector(sel); }
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function getManuscriptContainer() {
  // Phase 13: manuscript-container is the only scroll surface — the legacy
  // #script-scenes container (renderScriptView's home) is gone.
  return document.getElementById('manuscript-container');
}

// H1: echo the capability token the server set as a cookie on `/` so mutating
// requests prove they come from the served SPA, not a foreign blind write.
function _studioToken() {
  const m = document.cookie.match(/(?:^|;\s*)studio_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : "";
}

async function api(path, options = {}) {
  const headers = Object.assign(
    {},
    options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    options.headers || {}
  );
  const tok = _studioToken();
  if (tok) headers["X-Studio-Token"] = tok;
  const resp = await fetch(API + path, { ...options, headers });
  let data = null;
  try { data = await resp.json(); } catch (_) { /* no body */ }
  if (!resp.ok) {
    const message = (data && data.error) || `Request failed (${resp.status})`;
    const err = new Error(message);
    // Status + watchdog flag ride on the error so callers can offer a
    // "keep waiting?" retry on 408 instead of treating a slow model turn
    // like a dead server.
    err.status = resp.status;
    err.stillWorking = !!(data && data.still_working);
    throw err;
  }
  return data;
}

// ---- streaming chat turn (SSE) ----
// Raw tokens stream into the pending bubble AS the model writes them — the
// perceived-latency win for slow local models. The final SSE event carries
// the CLEANED, stored reply + full history, so what lands in state is
// exactly what the server persisted (streaming never changes what is kept).
// Falls back to the blocking endpoint when the stream route is missing.
async function streamChatTurn(base, text, quote, bubble, scrollContainer) {
  const body = JSON.stringify(quote ? { text, quote } : { text });
  const _h = { "Content-Type": "application/json" };
  const _tok = _studioToken();
  if (_tok) _h["X-Studio-Token"] = _tok;
  const resp = await fetch(API + base + "/messages/stream", {
    method: "POST",
    headers: _h,
    body,
  });
  if (resp.status === 404 || !resp.body) {
    return api(`${base}/messages`, { method: "POST", body });
  }
  if (!resp.ok) {
    let data = null;
    try { data = await resp.json(); } catch (_) { /* no body */ }
    const err = new Error((data && data.error) || `Request failed (${resp.status})`);
    err.status = resp.status;
    err.stillWorking = !!(data && data.still_working);
    throw err;
  }
  // swap the typing dots for a live stream sink; keep the .elapsed span the
  // ticker updates so it doesn't get recreated after streamed text each tick
  const dotsEl = bubble.querySelector(".typing-dots");
  if (dotsEl) dotsEl.remove();
  let sink = bubble.querySelector(".stream-text");
  if (!sink) {
    sink = el("span", "stream-text");
    bubble.insertBefore(sink, bubble.querySelector(".elapsed"));
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "", final = null, sseError = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let evt;
      try { evt = JSON.parse(line.slice(5).trim()); } catch (_) { continue; }
      if (evt.token) {
        sink.textContent += evt.token;
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      } else if (evt.done) final = evt;
      else if (evt.error) sseError = evt;
    }
  }
  if (sseError) {
    const err = new Error(sseError.error);
    err.stillWorking = !!sseError.still_working;
    throw err;
  }
  if (!final) throw new Error("The stream ended before the reply completed.");
  return final;
}

// ---- finding triage: reload just the fix queue ----
async function reloadFixQueue() {
  try {
    state.fixQueue = await api(`/projects/${encodeURIComponent(state.currentProject)}/fixqueue${state.fixQueueShowDismissed ? "?include_dismissed=1" : ""}`);
  } catch (_) { /* keep whatever we had */ }
  updateDawnMeter();
}

// ---- the dawn meter (Spark Wall / First Light) ----
// The share of findings you've resolved IS the dawn: the whole room warms as
// the number climbs. Quiet, ambient, honest — derived only from fix-queue state.
function updateDawnMeter() {
  const items = (state.fixQueue && state.fixQueue.items) || [];
  const open = items.filter((i) => i.status !== "addressed" && !i.dismissed).length;
  const done = items.filter((i) => i.status === "addressed").length;
  const total = open + done;
  const pct = total ? Math.round((done / total) * 100) : 0;
  document.documentElement.style.setProperty("--spark-dawn", String(pct / 100));
  document.querySelectorAll(".dawn-fill").forEach((f) => { f.style.width = pct + "%"; });
  document.querySelectorAll(".dawn-pct").forEach((p) => { p.textContent = pct + "%"; });
}

// ---- retry only the failed analysis categories (partial-report recovery) ----
async function retryFailedCategories() {
  const btn = $("#retry-failed-btn");
  const deskBtn = $("#desk-retry-failed-btn"); // Phase 8: same action from the desk
  const btns = [btn, deskBtn].filter(Boolean);
  if (!btns.length || btns.every((b) => b.disabled)) return;
  btns.forEach((b) => { b.disabled = true; b.textContent = "Retrying…"; });
  const label = "⚠ Retry failed";
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/analyze/retry-failed`, {
      method: "POST", body: JSON.stringify({}),
    });
    appendSystemNote("Failed categories re-run — the report has been merged and updated.");
    await loadProjects();
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    loadFeedbackPanels();
    refreshMetrics();
  } catch (e) {
    showError("Retry failed: " + e.message, true);
  } finally {
    const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
    const still = ((projSummary && projSummary.failed_categories) || []).length;
    btns.forEach((b) => {
      b.disabled = false;
      b.textContent = still ? `⚠ Retry failed (${still})` : label;
      b.style.display = still ? "inline-block" : "none";
    });
    refreshDeskToolbar(); // the desk's status line reflects the merged report
  }
}

// ---- inline editing: double-click a line on the page, type, done ----
// Rides the EXISTING apply/undo path underneath (one {old, new} replacement
// through /edits/apply), so undo, change-stars, finding re-verification and
// exports all see it — no parallel edit machinery.
function wireInlineEdit(lineEl, sceneNumber, originalText) {
  lineEl.title = "Double-click to edit this line in place";
  lineEl.addEventListener("dblclick", (ev) => {
    ev.preventDefault();
    if (lineEl.isContentEditable && lineEl.contentEditable === "true") return;
    const cancelled = { value: false };
    lineEl.contentEditable = "true";
    lineEl.classList.add("inline-editing");
    lineEl.focus();
    // caret at end, like continuing a thought
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(lineEl);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
    let busy = false;
    const finish = async (save) => {
      if (busy) return;
      busy = true;
      lineEl.contentEditable = "false";
      lineEl.classList.remove("inline-editing");
      const newText = (lineEl.textContent || "").trim();
      const oldText = originalText.trim();
      if (!save || cancelled.value || !newText || newText === oldText) {
        renderManuscript(document.getElementById('manuscript-container'));
        return;
      }
      try {
        await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/apply`, {
          method: "POST",
          body: JSON.stringify({ scene_number: sceneNumber, replacements: [{ old: originalText, new: newText }] }),
        });
        appendSystemNote("Line edited on the page — ↶ Undo takes it back.");
      } catch (err) {
        showError("Inline edit failed: " + err.message);
      }
      await loadScriptData();
      renderManuscript(document.getElementById('manuscript-container'));
      refreshMetrics();
    };
    lineEl.addEventListener("blur", () => finish(true), { once: true });
    lineEl.addEventListener("keydown", (kev) => {
      if (kev.key === "Enter" && !kev.shiftKey) { kev.preventDefault(); lineEl.blur(); }
      if (kev.key === "Escape") { kev.preventDefault(); cancelled.value = true; lineEl.blur(); }
    });
  });
}

/** Starts a live "Xm Ys elapsed" ticker inside a target element, prefixed
 * with a fixed label. Returns a stop function. Exists specifically so long
 * local-model waits (which are normal, not broken) read as "working", not
 * "frozen". */
function startElapsedTicker(targetEl, label) {
  const startedAt = Date.now();
  const tick = () => {
    const elapsed = (Date.now() - startedAt) / 1000;
    // Update the dedicated .elapsed sink when present. If it's missing,
    // find-or-create it rather than overwriting the bubble's whole text —
    // the watchdog dialog lives in that bubble and a wholesale textContent
    // replacement would erase it one second after it appears.
    let sink = targetEl.querySelector && targetEl.querySelector(".elapsed");
    if (!sink && targetEl.appendChild) {
      sink = document.createElement("span");
      sink.className = "elapsed";
      targetEl.appendChild(sink);
    }
    if (sink) sink.textContent = `${label} — ${formatElapsed(elapsed)} elapsed`;
  };
  tick();
  const handle = setInterval(tick, 1000);
  return () => clearInterval(handle);
}

// ---------- global error banner ----------

let errorBannerTimeout = null;

function showError(message, persistent) {
  const banner = $("#error-banner");
  $("#error-banner-text").textContent = message;
  banner.style.display = "flex";
  if (errorBannerTimeout) clearTimeout(errorBannerTimeout);
  if (!persistent) errorBannerTimeout = setTimeout(hideError, 10000);
}

function hideError() {
  $("#error-banner").style.display = "none";
}

// ---------- config ----------

// Canonical fallbacks for the persona/mode dropdowns. The server exposes the
// real lists via /api/config; these are used only when the server doesn't
// (e.g. the co-writer package isn't installed) so the UI never renders empty.
// Mirrors screenplay_cowriter.personas — kept in sync manually; the server's
// /api/config list always wins when it answers.
const FALLBACK_PERSONAS = ["writing_partner", "premise_doctor", "script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"];
const FALLBACK_MODES = ["peer", "evidence_discussion", "concept_validation", "brainstorm", "character_interview"];
const FALLBACK_PERSONA_LABELS = {
  writing_partner: "Sameer", premise_doctor: "Premise Doctor",
  script_consultant: "Dr. Sushruta", producer: "Producer", dev_exec: "Dev Exec",
  teacher: "Teacher", audience: "Audience", genre_specialist: "Genre Specialist",
};
const FALLBACK_MODE_LABELS = {
  peer: "Peer (default)", evidence_discussion: "Grounded Discussion",
  concept_validation: "Concept Validation", brainstorm: "Brainstorm",
  character_interview: "Character Interview",
};

// ---- the settings form, filled from whatever the desk currently believes ----
// Split out of loadConfig so OPENING the modal refreshes it too. Without that,
// the form showed the state from page load: saving a token and reopening the
// dialog still said "no token saved", which reads as "my save didn't work".
function fillSettingsForm() {
  const cfg = state.config || {};
  $("#server-url-input").value = cfg.server_url || "";
  $("#timeout-input").value = cfg.timeout || 600;
  $("#model-input").value = cfg.model || "";
  $("#fast-model-input").value = cfg.fast_model || "";
  $("#turn-timeout-input").value = cfg.turn_timeout || 120;
  // The token never comes back over the wire — only whether one is set — so the
  // field stays empty and says so in the placeholder. Typing a new value
  // replaces it; leaving it empty keeps whatever is already stored.
  const keyInput = $("#api-key-input");
  keyInput.value = "";
  keyInput.placeholder = cfg.api_key_set
    ? "•••••••• (a token is saved — type a new one to replace it)"
    : "sk-… (stored on this machine, never sent anywhere else)";
  // keepUrl: the URL came from the server, so the "Local fills in the local
  // info" reset must not overwrite it (a local server on a non-default port is
  // a perfectly ordinary setup).
  setConnectionMode(cfg.connection_mode || "local", { keepUrl: true });
}

async function loadConfig() {
  try {
    state.config = await api("/config");
    fillSettingsForm();
  } catch (e) {
    console.warn("Could not load config:", e);
  }
  updateStatusStrip();
  applyDemoDisclosure();
  checkConnection();
}

// ---- the one form, two modes (local model / remote API) ----
// The mode decides which fields are filled in and which are required; the
// fields themselves are shared, so switching never loses what was typed. The
// server derives the mode from the URL it holds, so this is presentation plus
// one request-time validation, not a second source of truth.
let connectionMode = "local";
// Set only when the writer CLICKS "Local model": that is a deliberate move back
// to a local server, and it must clear any remote credential rather than leave
// it pointed at localhost. A blank field is otherwise "leave the saved token
// alone", because a local llama-server can legitimately have one.
let clearTokenOnSave = false;

function setConnectionMode(mode, opts = {}) {
  connectionMode = mode === "remote" ? "remote" : "local";
  const local = connectionMode === "local";
  document.querySelectorAll(".mode-opt").forEach((b) => {
    b.setAttribute("aria-checked", String(b.dataset.mode === connectionMode));
  });
  $("#api-key-row").style.display = "block";
  // The token field is shared by both modes and stays visible: a local
  // llama-server CAN require one (it is started with --api-key), and hiding the
  // field would make that setup unreachable from the UI while the stored token
  // silently kept being sent. Only the hint changes.
  $("#api-key-hint").innerHTML = local
    ? "A local llama-server needs no token unless you started it with " +
      "<code>--api-key</code>. Leave this blank unless yours does."
    : "Sent as <code>Authorization: Bearer …</code> to that URL only. Saved in this " +
      "studio's settings and in each project's manifest, so a resumed project can " +
      "still reach the same endpoint. It is never returned to the browser.";
  // A mode the server would refuse is not offered: the remote option is disabled
  // (with the reason in the hint below) until the studio is launched with
  // --allow-remote-server. The server refuses it too — this is the honest UI for
  // that refusal, not the enforcement of it.
  const remoteBlocked = !!(state.config && state.config.allow_remote === false);
  $("#mode-remote").disabled = remoteBlocked;
  $("#mode-remote").title = remoteBlocked
    ? "Restart the studio with --allow-remote-server to enable this"
    : "";
  $("#server-url-label").textContent = local ? "llama-server URL" : "API base URL";
  $("#server-url-input").placeholder = local
    ? "http://localhost:8080"
    : "https://api.example.com/v1";
  if (local && !opts.keepUrl) {
    // "Local" fills the local info in for you — the same reset the server does,
    // so the form never shows a remote URL while Local is selected.
    $("#server-url-input").value = "http://localhost:8080";
    $("#api-key-input").value = "";
  }
  const hint = $("#mode-hint");
  let text = "";
  if (local) {
    text = "Everything stays on this machine: your script is sent only to " +
      "localhost, and no token is needed.";
  } else {
    text = "Your script leaves this machine on every analysis and chat turn. " +
      "Use a base URL ending in /v1 for an OpenAI-compatible endpoint.";
  }
  if (remoteBlocked) {
    // The disabled Remote option needs its reason IN TEXT, not only in a
    // hover tooltip: a greyed-out control with no visible explanation is
    // indistinguishable from a broken one.
    text += " Remote API is unavailable because this studio was started without " +
      "remote access — restart it with --allow-remote-server (or set " +
      "SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1). That has to be a launch-time " +
      "decision, because an HTTP request must not be able to send your script " +
      "off this machine.";
  }
  hint.textContent = text;
}

document.querySelectorAll(".mode-opt").forEach((btn) => {
  btn.onclick = () => {
    if (btn.disabled) return;
    if (btn.dataset.mode === "local") clearTokenOnSave = true;
    setConnectionMode(btn.dataset.mode);
  };
});

async function saveConfig() {
  const server_url = $("#server-url-input").value.trim();
  const timeout = parseInt($("#timeout-input").value, 10) || 600;
  const model = $("#model-input").value.trim();
  const fast_model = $("#fast-model-input").value.trim();
  const turn_timeout = parseInt($("#turn-timeout-input").value, 10) || 120;
  const body = { connection_mode: connectionMode, server_url, timeout,
                 model, fast_model, turn_timeout };
  // A typed token always wins. A blank field means "leave the saved one alone"
  // — except after an explicit switch to Local, which clears it.
  const typed = $("#api-key-input").value.trim();
  if (typed) body.api_key = typed;
  else if (clearTokenOnSave) body.api_key = "";
  try {
    state.config = await api("/config", { method: "POST", body: JSON.stringify(body) });
    clearTokenOnSave = false;
    closeModal("#settings-modal");
    applyDemoDisclosure();
    checkConnection();
  } catch (e) {
    showError("Couldn't save settings: " + e.message);
  }
}

async function testConnection() {
  const btn = $("#test-connection-btn");
  const resultEl = $("#test-connection-result");
  const url = $("#server-url-input").value.trim();
  const typed = $("#api-key-input").value.trim();
  const body = { server_url: url };
  if (typed) body.api_key = typed;
  btn.disabled = true;
  resultEl.className = "test-connection-result";
  resultEl.textContent = "Checking…";
  try {
    const res = await api("/test-connection", { method: "POST", body: JSON.stringify(body) });
    resultEl.textContent = res.message;
    resultEl.classList.add(res.ok ? "ok" : "fail");
  } catch (e) {
    resultEl.textContent = "Couldn't check: " + e.message;
    resultEl.classList.add("fail");
  }
  btn.disabled = false;
}

// ---- loop instrumentation (IMPROVEMENT_AUDIT 1.3) ----
// Quiet metrics in the status strip: avg reply time · findings fixed,
// with analysis duration / discussed count in the hover detail.

async function refreshMetrics() {
  const el = $("#status-metrics");
  if (!el) return;
  if (!state.currentProject) { el.textContent = "⚡ —"; el.title = "Your writing loop, measured quietly on this machine"; return; }
  try {
    const m = await api(`/projects/${encodeURIComponent(state.currentProject)}/metrics`);
    const avg = m.avg_reply_seconds;
    let label = "⚡ ";
    label += avg != null ? `${avg}s` : "—";
    if (m.findings_total) label += ` · ${m.findings_fixed || 0}/${m.findings_total} fixed`;
    el.textContent = label;
    const parts = [];
    parts.push(`Average reply: ${avg != null ? avg + "s" : "no chats yet"}`);
    parts.push(`Last analysis: ${fmtDuration(m.analysis_seconds)}`);
    if (m.findings_total) parts.push(`${m.findings_fixed || 0} of ${m.findings_total} findings fixed (${m.findings_fixed_pct || 0}%)`);
    parts.push(`Passages discussed with Sameer: ${m.discussed || 0}`);
    el.title = parts.join("\n");
  } catch (_) {
    el.textContent = "⚡ —";
    el.title = "Your writing loop, measured quietly on this machine";
  }
}

async function checkConnection() {
  const dot = $("#connection-dot");
  const connEl = $("#status-conn");
  const demo = !!(state.config && state.config.demo_model);
  try {
    const res = await api("/test-connection", { method: "POST", body: JSON.stringify({}) });
    state.connState = { ok: !!res.ok, message: res.message, models: res.models || [] };
    renderDashboard();  // the dashboard's connection pill follows the strip
    if (demo) {
      // honesty first: green means YOUR model — the demo shows amber
      dot.className = "connection-dot demo";
      dot.title = "Built-in demo craft model — not your llama-server.";
      if (connEl) {
        connEl.textContent = "● demo craft model (built-in)";
        connEl.className = "status-item demo";
        connEl.title = dot.title;
      }
      // is the writer's real server back? offer the one-click switch
      try {
        const probe = await api("/real-server-check");
        state.realServer = probe.available
          ? { available: true, url: probe.url, models: probe.models || [] }
          : { available: false };
        if (probe.available && connEl) {
          // a11y (WCAG 1.4.3, caught by axe): pulsing the WHOLE line's opacity
          // dragged the text to 4.15:1 (night) and ~2.2:1 (dawn) at the trough.
          // Only the decorative ● dot pulses now; the words stay at full
          // contrast in both themes.
          connEl.innerHTML = '<span class="switch-dot" aria-hidden="true">●</span> your model is back — click to switch';
          connEl.className = "status-item switch";
          connEl.title = `Your llama-server answered at ${probe.url}` +
            (probe.models && probe.models.length ? ` — ${probe.models[0]}` : "");
        }
      } catch (_) { state.realServer = { available: false }; }
    } else {
      const mid = state.connState.models[0];
      dot.className = "connection-dot " + (res.ok ? "ok" : "fail");
      dot.title = res.message;
      if (connEl) {
        connEl.textContent = res.ok
          ? `● model ready${mid ? " — " + shortModelId(mid) : ""}`
          : "● model unreachable";
        connEl.className = "status-item " + (res.ok ? "ok" : "fail");
        connEl.title = res.message;
      }
    }
  } catch (e) {
    dot.className = "connection-dot fail";
    dot.title = "Couldn't check connection: " + e.message;
    if (connEl) {
      connEl.textContent = "● model unreachable";
      connEl.className = "status-item fail";
      connEl.title = dot.title;
    }
  }
  updateStatusStrip();
  renderConnCard();
}

// Demo mode means the "report" and the "co-writer" are a rule-based stand-in, not
// a model. The amber dot in the status strip is a status, not a label — the
// surfaces a writer actually reads have to say it themselves (§5 item 8,
// §7 item 10). One helper, so the two partner-name call sites cannot drift.
function isDemoModel() {
  return !!(state.config && state.config.demo_model);
}

function partnerLabel(base) {
  return isDemoModel()
    ? `${base} — stand-in (connect your model for the real one)`
    : base;
}

// The report's own disclosure. One attribute, several surfaces: the report lives
// in the dock for a project and in the Feedback panel for the idea room, and a
// demo studio is a stand-in for the findings AND the co-writer either way. Toggling
// them all from one place is what stops one surface drifting out of date.
function applyDemoDisclosure() {
  const demo = isDemoModel();
  document.querySelectorAll("[data-demo-banner]").forEach((el) => {
    el.hidden = !demo;
  });
}

function updateStatusStrip() {
  const label = $("#status-model-label");
  if (!label) return;
  const url = state.config && state.config.server_url;
  const demo = !!(state.config && state.config.demo_model);
  const mid = state.connState && state.connState.models && state.connState.models[0];
  let text;
  if (demo) text = "demo craft model";
  else if (mid) text = shortModelId(mid);
  else if (url) text = `llama · ${url.replace(/^https?:\/\//, "")}`;
  else text = "model server not set";
  label.textContent = text;
}

// Hover card on the bottom-left: which brain, which server, how connected.
function renderConnCard() {
  const card = $("#conn-card");
  if (!card) return;
  card.hidden = false;  // visibility itself is CSS :hover-driven
  const url = (state.config && state.config.server_url) || "—";
  const demo = !!(state.config && state.config.demo_model);
  const mid = state.connState && state.connState.models && state.connState.models[0];
  const ok = !!(state.connState && state.connState.ok);
  const stateTxt = demo ? "Demo (built-in stand-in)" : ok ? "Connected" : "Unreachable";
  const cls = demo ? "demo" : ok ? "ok" : "fail";
  card.innerHTML =
    `<div class="conn-card-row ${cls}"><b>${escapeHtml(stateTxt)}</b></div>` +
    `<div class="conn-card-row">model <b>${escapeHtml(demo ? "demo craft model" : (mid || "—"))}</b></div>` +
    `<div class="conn-card-row">server <b>${escapeHtml(url)}</b></div>` +
    (demo && state.realServer && state.realServer.available
      ? `<div class="conn-card-row switch">your model is back — click "switch" beside</div>` : "");
}

// ---------- projects ----------

async function loadProjects() {
  try {
    state.projects = await api("/projects");
    renderProjectList();
    renderDashboard();
  } catch (e) {
    showError("Couldn't load your projects: " + e.message, true);
  }
}

// ---- dashboard: every script as an intuitive card ----

function renderDashboard() {
  const grid = $("#dash-grid");
  if (!grid) return;
  grid.innerHTML = "";
  const projects = state.projects || [];

  if (!projects.length) {
    const empty = el("p", "dash-empty", "Nothing here yet — lay a manuscript on the desk above, or open the sample page.");
    grid.appendChild(empty);
  }

  for (const p of projects) {
    const card = el("div", "dash-card" + (p.project === state.currentProject ? " active" : ""));
    card.title = `Open "${p.title}" on the desk`;

    // head: title + format chip + delete
    const head = el("div", "dash-card-head");
    head.appendChild(el("span", "dash-card-title", p.title));
    if (p.unreadable) {
      head.appendChild(el("span", "idea-unreadable", "\u26A0 unreadable"));
      card.title = "Damaged on disk \u2014 can't be opened. Remove it with \u2715.";
    }
    if (p.source_format) head.appendChild(el("span", "dash-format", p.source_format.replace(".", "").toUpperCase()));
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = `Remove "${p.title}" from the shelf`;
    del.setAttribute("aria-label", `Remove ${p.title}`);
    del.addEventListener("click", (e) => { e.stopPropagation(); deleteProjectFlow(p.project, p.title); });
    head.appendChild(del);
    card.appendChild(head);

    // pipeline stepper: parse -> analyze -> chat
    const steps = el("div", "dash-steps");
    steps.innerHTML =
      _stageStep("Parse", p.stages.parse) +
      _stageStep("Analyze", p.stages.analyze) +
      _stageStep("Chat", p.stages.chat);
    card.appendChild(steps);

    // stats row
    const stats = el("div", "dash-stats");
    stats.appendChild(el("span", null, `${(p.sessions || []).length} chat${(p.sessions || []).length === 1 ? "" : "s"}`));
    stats.appendChild(el("span", null, `${p.edit_count || 0} edit${(p.edit_count || 0) === 1 ? "" : "s"}`));
    if ((p.failed_categories || []).length) {
      const warn = el("span", "dash-warn", `⚠ ${(p.failed_categories).length} failed`);
      warn.title = "Some analysis categories failed — Retry failed in the Feedback room";
      stats.appendChild(warn);
    }
    card.appendChild(stats);

    // actions
    const actions = el("div", "dash-actions");
    const openBtn = el("button", "dash-open", "Open desk →");
    openBtn.type = "button";
    openBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (p.unreadable) { showError("This project's files are damaged on disk and can't be opened."); return; }
      openProject(p.project);
    });
    const backup = el("a", "dash-backup", "⬇ Backup");
    backup.href = `/api/projects/${encodeURIComponent(p.project)}/backup`;
    backup.download = `${p.project}-backup.zip`;
    backup.title = "Download everything — source, report, chats, edits";
    backup.addEventListener("click", (e) => e.stopPropagation());
    actions.appendChild(openBtn);
    actions.appendChild(backup);
    card.appendChild(actions);

    // a11y (WCAG 2.1.1 Keyboard + axe nested-interactive): same as the
    // shelf rows — a labelled GROUP (open via Enter/Space, "Open desk →",
    // "Backup", ✕), never role="button" (would nest interactives).
    card.setAttribute("role", "group");
    card.setAttribute("aria-label", `Open project ${p.title}`);
    card.setAttribute("tabindex", "0");
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (p.unreadable) { showError("This project's files are damaged on disk and can't be opened."); return; }
        openProject(p.project);
      }
    });
    card.addEventListener("click", () => {
      if (p.unreadable) { showError("This project's files are damaged on disk and can't be opened."); return; }
      openProject(p.project);
    });
    grid.appendChild(card);
  }

  // connection pill mirrors the status strip's model state
  const conn = $("#dash-conn");
  if (conn && state.connState) {
    conn.className = "dash-conn " + (state.connState.ok ? "ok" : "fail");
    conn.textContent = state.connState.ok ? "● model connected" : "○ model offline";
  }
}

async function deleteProjectFlow(name, title) {
  if (!window.confirm(`Remove "${title}"?\n\nYour library and the shelf are one source -- this deletes the script and its analysis from this machine, and its library entry goes with it.`)) return;
  try {
    await api(`/projects/${encodeURIComponent(name)}`, { method: "DELETE" });
    if (state.currentProject === name) {
      state.currentProject = null;
      state.currentSession = null;
      state.script = null;
      state.findings = [];
      state.fixQueue = null;
      state.branches = { main: { messages: [], active_persona: "script_consultant", active_mode: "evidence_discussion" } };
      state.currentBranch = "main";
      hideAllViews();
      $("#welcome-view").style.display = "flex";
      $("#project-bar").style.display = "none";
      $("#input").value = "";
    }
    await Promise.all([loadProjects(), loadLibrary()]);   // both shelves drop the row
    saveSession();
  } catch (err) {
    showError("Couldn't remove the project: " + err.message);
  }
}

function stageLabel(p) {
  if (p.stages.analyze === "complete") return "Analyzed";
  if (p.stages.analyze === "failed") return "Analysis failed";
  if (p.stages.analyze === "running") return "Analyzing…";
  if (p.stages.parse === "complete") return "Parsed — not yet analyzed";
  return "…";
}

function renderProjectList() {
  const list = $("#project-list");
  list.innerHTML = "";
  setSectionCount("#shelf-count", state.projects.length);
  if (!state.projects.length) {
    list.appendChild(el("p", "empty-hint", "No screenplays yet — upload one to begin."));
    return;
  }
  for (const p of state.projects) {
    const item = el("div", "project-item" + (p.project === state.currentProject ? " active" : ""));
    const stage = (p.stages && p.stages.analyze) || "";
    const dotClass = stage === "complete" ? "complete" : stage === "failed" ? "failed" : "";
    const row = el("div", "project-item-row");
    row.appendChild(el("span", "stage-dot" + (dotClass ? " " + dotClass : "")));
    row.appendChild(document.createTextNode(p.title));
    if (p.unreadable) {
      row.appendChild(el("span", "idea-unreadable", "\u26A0 unreadable"));
      item.title = "This project's manifest is damaged on disk \u2014 it couldn't be opened. Remove it with \u2715 or inspect studio_projects/ by hand.";
    }
    item.appendChild(row);
    item.appendChild(el("div", "project-item-status", stageLabel(p)));
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = `Remove "${p.title}" from the shelf (deletes its files)`;
    del.setAttribute("aria-label", `Remove ${p.title} from the shelf`);
    // ONE shared delete flow (same as the dashboard card) -- this inline
    // duplicate used to skip the library refresh and leave a ghost entry in
    // Your library until a full reload.
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteProjectFlow(p.project, p.title);
    });
    item.appendChild(del);
    // a11y (WCAG 2.1.1 Keyboard + axe nested-interactive): the shelf row is
    // a GROUP of actions (open via Enter/Space, ✕ remove) — role="button"
    // on the container NESTED interactive controls (axe serious). The row
    // stays keyboard-openable (tabindex + Enter/Space) as a labelled group.
    item.setAttribute("role", "group");
    item.setAttribute("aria-label", `Open project ${p.title}`);
    item.setAttribute("tabindex", "0");
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (p.unreadable) { showError("This project's files are damaged on disk and can't be opened."); return; }
        openProject(p.project);
      }
    });
    item.addEventListener("click", () => {
      if (p.unreadable) { showError("This project's files are damaged on disk and can't be opened."); return; }
      openProject(p.project);
    });
    list.appendChild(item);
  }
}

// ---------- the Stash (saved snippets beside the script) ----------

async function loadStash() {
  if (!state.currentProject) return;
  try {
    const data = await api(`/projects/${encodeURIComponent(state.currentProject)}/stash`);
    state.stash = (data && data.stash) || [];
    renderStashList();
  } catch (_) { /* stash is optional — never break the desk */ }
}

function renderStashList() {
  const list = $("#stash-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.stash.length) {
    list.appendChild(el("p", "empty-hint", "Nothing stashed yet — select a line and press 📥 Stash this."));
    return;
  }
  state.stash.forEach((e) => {
    const item = el("div", "stash-item");
    const meta = e.scene_number ? `Scene ${e.scene_number}` : "From the desk";
    item.appendChild(el("div", "stash-item-text", e.text));
    const row = el("div", "stash-item-foot");
    row.appendChild(el("span", "stash-item-meta", meta));
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = "Remove from the Stash";
    del.addEventListener("click", async () => {
      try {
        await api(`/projects/${encodeURIComponent(state.currentProject)}/stash/${e.id}`, { method: "DELETE" });
        await loadStash();
      } catch (err) {
        showError("Couldn't remove that: " + err.message);
      }
    });
    row.appendChild(del);
    item.appendChild(row);
    list.appendChild(item);
  });
}

// ---------- Phase 0: the structural rail (scenes outline · stash · notes) ----------

function renderRailScenes() {
  const list = $("#rail-scenes");
  if (!list) return;
  list.innerHTML = "";
  const scenes = state.script && state.script.scenes;
  if (!scenes || !scenes.length) {
    list.appendChild(el("p", "empty-hint", "No scenes yet."));
    return;
  }
  scenes.forEach((scene) => {
    const item = el("div", "rail-scene");
    item.appendChild(el("span", "rail-scene-num", String(scene.scene_number)));
    item.appendChild(el("span", "rail-scene-head", scene.heading_raw || `Scene ${scene.scene_number}`));
    if (scene.page_start) item.appendChild(el("span", "rail-scene-page", `p.${scene.page_start}`));
    item.addEventListener("click", () => jumpToScene(scene.scene_number));
    list.appendChild(item);
  });
}

function renderRailNotes() {
  const list = $("#rail-notes");
  if (!list) return;
  list.innerHTML = "";
  if (!state.notes.length) {
    list.appendChild(el("p", "empty-hint", "No margin notes yet — select a line and press 📝 Note this line."));
    return;
  }
  // the rail notes panel is the notes wiki: every note, newest first,
  // click to jump to where it lives (its anchored line, else its scene)
  state.notes.forEach((n) => {
    const item = el("div", "rail-note" + (n.anchor ? " anchored" : ""));
    item.title = n.anchor ? `Pinned to: ${n.anchor.slice(0, 60)}` : "Click to jump to this scene";
    item.appendChild(el("div", "rail-note-text", (n.text || "").slice(0, 160)));
    const foot = el("div", "rail-note-foot");
    const loc = el("span", "stash-item-meta", n.scene_number ? `Scene ${n.scene_number}${n.anchor ? " · 📌" : ""}` : "Script");
    foot.appendChild(loc);
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = "Remove this note";
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        await api(`/projects/${encodeURIComponent(state.currentProject)}/notes/${n.id}`, { method: "DELETE" });
        await reloadNotesAndRender();
        renderRailNotes();
      } catch (err) {
        showError("Couldn't remove the note: " + err.message);
      }
    });
    foot.appendChild(del);
    item.appendChild(foot);
    item.addEventListener("click", () => {
      if (n.anchor) {
        const page = document.getElementById(`scene-page-${n.scene_number}`);
        if (page) {
          const q = normText(n.anchor);
          for (const line of page.querySelectorAll("[class^=el-]")) {
            const lt = normText(line.textContent);
            if (lt === q || (q.length > 4 && lt.includes(q))) {
              line.scrollIntoView({ behavior: "smooth", block: "center" });
              line.classList.add("finding-highlight");
              setTimeout(() => line.classList.remove("finding-highlight"), 2600);
              return;
            }
          }
        }
        scrollToSceneInPlace(n.scene_number);
      } else {
        scrollToSceneInPlace(n.scene_number);
      }
    });
    list.appendChild(item);
  });
}

async function loadCharacters() {
  if (!state.currentProject) return;
  try {
    const data = await api(`/projects/${encodeURIComponent(state.currentProject)}/characters`);
    state.charTracks = (data && data.characters) || [];
  } catch (_) { state.charTracks = []; /* track layer is optional */ }
  renderRailCharacters();
}

function renderRailCharacters() {
  const list = $("#rail-characters");
  if (!list) return;
  list.innerHTML = "";
  const tracks = state.charTracks || [];
  if (!tracks.length) {
    list.appendChild(el("p", "empty-hint", "Run an analysis to map who's in this script."));
    return;
  }
  const mains = tracks.filter((t) => t.importance === "main");
  const rest = tracks.filter((t) => t.importance !== "main");
  const renderRow = (t) => {
    const item = el("div", "rail-char" + (t.importance === "main" ? " main" : ""));
    const head = el("div", "rail-char-head");
    head.appendChild(el("span", "rail-char-name", t.name));
    head.appendChild(el("span", "rail-char-meta", `${t.scene_count} sc · ${t.dialogue_lines} ln`));
    item.appendChild(head);
    const body = el("div", "rail-char-body");
    body.hidden = true;
    // presence strip: scenes present as ticks, click to jump
    if (state.script && state.script.scene_count) {
      const strip = el("div", "rail-char-strip");
      const total = state.script.scene_count;
      const present = new Set(t.scenes_present || []);
      for (let n = 1; n <= total; n++) {
        const dot = el("span", "rail-char-dot" + (present.has(n) ? " on" : ""), "");
        if (present.has(n)) {
          dot.title = `Scene ${n}`;
          dot.addEventListener("click", (ev) => { ev.stopPropagation(); jumpToScene(n); });
        }
        strip.appendChild(dot);
      }
      body.appendChild(strip);
    }
    // dials (trait scores) as labelled sliders
    if (t.dials && t.dials.length) {
      const dials = el("div", "rail-char-dials");
      t.dials.forEach((d) => {
        const row = el("div", "dial-row");
        row.appendChild(el("span", "dial-label", d.trait));
        const trackEl = el("span", "dial-track");
        const fill = el("span", "dial-fill");
        fill.style.width = `${d.score * 10}%`;
        trackEl.appendChild(fill);
        row.appendChild(trackEl);
        row.appendChild(el("span", "dial-score", String(d.score)));
        if (d.note) row.title = d.note;
        dials.appendChild(row);
      });
      body.appendChild(dials);
    }
    // trait mentions from the page (age/descriptor parentheticals)
    if (t.traits && t.traits.length) {
      const tm = el("div", "rail-char-traits");
      t.traits.forEach((x) => {
        const chip = el("span", "trait-chip", x.text);
        if (x.scene) { chip.title = `Scene ${x.scene}`; chip.addEventListener("click", () => jumpToScene(x.scene)); }
        tm.appendChild(chip);
      });
      body.appendChild(tm);
    }
    // interactions: who they share scenes with
    if (t.interactions && t.interactions.length) {
      const ix = el("div", "rail-char-ix");
      ix.appendChild(el("span", "rail-char-ix-label", "On stage with:"));
      t.interactions.forEach((i) => {
        const chip = el("span", "ix-chip", `${i.name} ×${i.scenes.length}`);
        chip.title = `Scenes: ${i.scenes.join(", ")}`;
        ix.appendChild(chip);
      });
      body.appendChild(ix);
    }
    // reads (how they come across) — if the analysis produced them
    if (t.reads && (t.reads.how_reads || t.reads.apparent_intent)) {
      const rd = el("div", "rail-char-reads");
      if (t.reads.how_reads) rd.appendChild(el("p", "", `Reads: ${t.reads.how_reads}`));
      if (t.reads.apparent_intent && t.reads.apparent_intent !== t.reads.how_reads) rd.appendChild(el("p", "", `Intent: ${t.reads.apparent_intent}`));
      body.appendChild(rd);
    }
    item.appendChild(body);
    head.addEventListener("click", () => { body.hidden = !body.hidden; });
    return item;
  };
  mains.forEach((t) => list.appendChild(renderRow(t)));
  if (rest.length) {
    const toggle = el("button", "rail-char-more", `+ ${rest.length} more`);
    toggle.type = "button";
    const restWrap = el("div", "rail-char-rest");
    restWrap.hidden = true;
    rest.forEach((t) => restWrap.appendChild(renderRow(t)));
    toggle.addEventListener("click", () => { restWrap.hidden = !restWrap.hidden; toggle.textContent = restWrap.hidden ? `+ ${rest.length} more` : "− fewer"; });
    list.appendChild(toggle);
    list.appendChild(restWrap);
  }
}

function toggleRail(collapsed) {
  const rail = $("#struct-rail");
  if (!rail) return;
  const btn = $("#rail-toggle");
  rail.classList.toggle("rail-collapsed", collapsed);
  if (btn) {
    btn.textContent = collapsed ? "»" : "«";
    btn.setAttribute("aria-expanded", String(!collapsed));
  }
  savePrefs({ rail_collapsed: collapsed });
}

// collapsible left sidebar (the shelf) — same pattern as the structure rail
// persist=false: the auto-collapse the writing environment performs when a
// project/idea opens must NOT overwrite the writer's own shelf preference —
// the landing desk still opens with the shelf exactly as they left it.
function toggleSidebar(collapsed, persist = true) {
  const sidebar = $("#sidebar");
  const edgeTab = $("#sidebar-edge-tab");
  if (!sidebar) return;
  sidebar.classList.toggle("sidebar-collapsed", collapsed);
  if (edgeTab) edgeTab.classList.toggle("visible", collapsed);
  // body-level mirror for the scene rail: an OPEN shelf overlays x:0-264 and
  // would bury the 44px scene index (both sit at left:0; shelf z 590 > rail z 10).
  // The rail indents to the shelf's right edge while the shelf is open, so
  // both remain visible and the rail keeps its persistent-chrome contract
  // (design-critic P1, session 2026-09-12).
  document.body.classList.toggle("shelf-open", !collapsed);
  if (persist) savePrefs({ sidebar_collapsed: collapsed });
}

// ---------- writer's library (past work the personas can draw on) ----------

async function loadLibrary() {
  try {
    const data = await api("/writer-library");
    state.library = (data && data.projects) || [];
    renderLibraryList();
  } catch (_) { /* library is optional — never break the shelf */ }
}

function renderLibraryList() {
  const list = $("#library-list");
  if (!list) return;
  list.innerHTML = "";
  setSectionCount("#library-count", state.library.length);
  if (!state.library.length) {
    list.appendChild(el("p", "empty-hint", "Past scripts gather here — Sameer and the doctor read this shelf too."));
    return;
  }
  for (const p of state.library) {
    const item = el("div", "idea-item" + (p.project === state.currentProject ? " active" : ""));
    const row = el("div", "project-item-row");
    row.appendChild(el("span", "idea-mark", "📚"));
    row.appendChild(document.createTextNode(p.title));
    item.appendChild(row);
    const meta = `${p.scene_count || "?"} scenes · ${(p.characters || []).slice(0, 4).join(", ") || "no characters parsed"}`;
    item.appendChild(el("div", "project-item-status", meta));
    // Your library has no storage of its own -- every entry IS a shelf
    // project's parsed files. Deleting here deletes that script (same flow
    // as the shelf's X), so the two shelves can never disagree.
    const del = el("button", "project-delete", "\u2715");
    del.type = "button";
    del.title = `Remove "${p.title}" -- this deletes the script and its analysis from the machine`;
    del.setAttribute("aria-label", `Delete ${p.title} from the library`);
    del.addEventListener("click", (e) => { e.stopPropagation(); deleteProjectFlow(p.project, p.title); });
    item.appendChild(del);
    item.addEventListener("click", () => openProject(p.project));
    list.appendChild(item);
  }
}

// ---------- idea room (scriptless development) ----------

async function loadIdeas() {
  try {
    state.ideas = await api("/ideas");
    renderIdeaList();
  } catch (_) { /* ideas are optional — never break the shelf */ }
}

function renderIdeaList() {
  const list = $("#idea-list");
  list.innerHTML = "";
  setSectionCount("#idea-count", state.ideas.length);
  if (!state.ideas.length) {
    list.appendChild(el("p", "empty-hint", "No ideas yet — the desk is free for one."));
    return;
  }
  for (const idea of state.ideas) {
    const item = el("div", "idea-item" + (state.currentIdea && idea.id === state.currentIdea.id ? " active" : ""));
    const row = el("div", "project-item-row");
    row.appendChild(el("span", "idea-mark", "💡"));
    row.appendChild(document.createTextNode(idea.title || "Untitled idea"));
    if (idea.unreadable) {
      row.appendChild(el("span", "idea-unreadable", "\u26A0 unreadable"));
      item.title = "This idea's file is damaged on disk \u2014 it couldn't be opened. Delete it with \u2715 or inspect studio_projects/ideas/ by hand.";
    }
    item.appendChild(row);
    // inline rename in the shelf — the title is the writer's, always
    const ren = el("button", "idea-rename", "✎");
    ren.type = "button";
    ren.title = "Rename this idea";
    ren.setAttribute("aria-label", "Rename idea");
    ren.addEventListener("click", async (e) => {
      e.stopPropagation();
      row.innerHTML = "";
      row.appendChild(el("span", "idea-mark", "💡"));
      const inp = document.createElement("input");
      inp.type = "text";
      inp.value = idea.title || "";
      inp.className = "idea-rename-input";
      inp.maxLength = 80;
      row.appendChild(inp);
      inp.focus();
      inp.select();
      const finish = async (save) => {
        const t = inp.value.trim();
        if (save && t && t !== idea.title) {
          try {
            await api(`/ideas/${encodeURIComponent(idea.id)}/rename`, { method: "POST", body: JSON.stringify({ title: t }) });
          } catch (err) {
            showError("Couldn't rename: " + err.message);
          }
        }
        await loadIdeas();
      };
      inp.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") { ev.preventDefault(); finish(true); }
        else if (ev.key === "Escape") { ev.preventDefault(); finish(false); }
      });
      inp.addEventListener("blur", () => finish(true));
    });
    item.appendChild(ren);
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = "Throw this idea away";
    del.setAttribute("aria-label", "Delete idea");
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!window.confirm(`Throw away "${idea.title || "this idea"}"?\nThe premise card and the conversation go with it.`)) return;
      try {
        await api(`/ideas/${encodeURIComponent(idea.id)}`, { method: "DELETE" });
        if (state.currentIdea && state.currentIdea.id === idea.id) showWelcomeDesk();
        await loadIdeas();
      } catch (err) {
        showError("Couldn't delete the idea: " + err.message);
      }
    });
    item.appendChild(del);
    // a11y (WCAG 2.1.1 Keyboard + axe nested-interactive): same as the
    // project shelf row — a labelled GROUP (open via Enter/Space, ✎ rename,
    // ✕ remove), never role="button" (would nest interactives).
    item.setAttribute("role", "group");
    item.setAttribute("aria-label", `Open idea ${(idea.title || 'Untitled idea')}`);
    item.setAttribute("tabindex", "0");
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (idea.unreadable) { showError("This idea's file is damaged on disk and can't be opened."); return; }
        openIdea(idea.id);
      }
    });
    item.addEventListener("click", () => {
      if (idea.unreadable) { showError("This idea's file is damaged on disk and can't be opened."); return; }
      openIdea(idea.id);
    });
    list.appendChild(item);
  }
}

function showWelcomeDesk() {
  state.currentProject = null;
  state.currentIdea = null;
  state.currentIdeaSession = null;
  state.inIdea = false;
  document.body.classList.remove("idea-mode");
  closeRoomDrawer();
  $("#welcome-view").style.display = "flex";
  $("#project-bar").style.display = "none";
  $("#idea-canvas").style.display = "none";
  // the landing desk restores the writer's own shelf preference
  toggleSidebar(!!loadPrefs().sidebar_collapsed, false);
  const ws = document.querySelector(".workspace");
  if (ws) ws.style.display = "none";
  hideAllViews();
  const expBtn = $("#report-export-btn");
  if (expBtn) expBtn.style.display = "none";
  renderProjectList();
  renderIdeaList();
  saveSession();
}

async function createIdea() {
  try {
    const meta = await api("/ideas", { method: "POST", body: JSON.stringify({ title: "New idea" }) });
    await loadIdeas();
    await openIdea(meta.id);
  } catch (e) {
    showError("Couldn't start an idea: " + e.message);
  }
}

function populatePremiseFields(card) {
  $("#premise-title").value = card.title || "";
  $("#premise-logline").value = card.logline || "";
  $("#premise-text").value = card.premise || "";
  $("#premise-questions").value = (card.questions || []).join("\n");
}

function collectPremiseFields() {
  return {
    title: $("#premise-title").value.trim(),
    logline: $("#premise-logline").value.trim(),
    premise: $("#premise-text").value.trim(),
    questions: $("#premise-questions").value.split("\n").map((s) => s.trim()).filter(Boolean),
  };
}

async function savePremise(flash = true) {
  const card = collectPremiseFields();
  try {
    if (state.inIdea && state.currentIdea) {
      const meta = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/card`, { method: "POST", body: JSON.stringify({ card }) });
      state.currentIdea.card = meta.card;
      state.currentIdea.title = meta.title;
      $("#project-title").textContent = meta.title || "Untitled idea";
      await loadIdeas();
    } else if (state.currentProject) {
      await api(`/projects/${encodeURIComponent(state.currentProject)}/premise`, { method: "POST", body: JSON.stringify({ card }) });
    }
    if (flash) {
      const b = $("#premise-save-btn");
      const old = b.textContent;
      b.textContent = "Saved ✓";
      setTimeout(() => { b.textContent = old; }, 1400);
    }
  } catch (e) {
    showError("Couldn't save the premise card: " + e.message);
  }
}

async function openIdea(id) {
  try {
    const idea = await api(`/ideas/${encodeURIComponent(id)}`);
    state.currentIdea = idea;
    state.inIdea = true;
    state.currentProject = null;
    state.script = null;
    state.findings = [];
    state.fixQueue = null;
    state.currentIdeaSession = null; // lazy — created on the first Sameer summon
    document.body.classList.add("idea-mode"); // no doctor / scripts / shelf chrome
    renderIdeaList();

    $("#welcome-view").style.display = "none";
    $("#project-bar").style.display = "flex";
    $("#project-title").textContent = idea.title || "Untitled idea";
    $("#project-title").title = idea.title || "";

    // the blank canvas replaces the pages — and the premise form (that form
    // belongs to the script desk's premise card; ideas get a page)
    $("#premise-view").style.display = "none";
    $("#idea-canvas").style.display = "flex";
    $("#desk-toolbar").style.display = "none"; // ideas are a blank page, not a desk
    const mc = getManuscriptContainer(); if (mc) mc.style.display = "none";
    $("#draft-bar").style.display = "none";
    $("#premise-btn").style.display = "none";
    populateIdeaCanvas(idea);

    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "flex";
    // the idea canvas is a writing surface too — same rule as openProject:
    // the shelf is not permanent here either (the edge tab brings it back)
    toggleSidebar(true, false);
    setRoom("cowrite");
    closeRoomDrawer(); // Sameer stays OFF the stage until the writer summons him
    saveSession();
  } catch (e) {
    showError("Couldn't open the idea: " + e.message);
  }
}

// ---- the idea page: a blank canvas, autosaved, self-titled ----

function populateIdeaCanvas(idea) {
  $("#idea-title-input").value = idea.title || "Untitled idea";
  $("#idea-content").value = idea.content || "";
  const card = idea.card || {};
  $("#idea-logline").value = card.logline || "";
  $("#idea-questions").value = (card.questions || []).join("\n");
  updateIdeaSamPill();
}

// The summon pill is the chat's only standing address in the idea room, so it
// no longer hides on a blank page — that was exactly when a first-time writer
// had no way to discover Sameer at all (UI audit 2026-09-20, defect #7: "chat
// is not discoverable"). It always shows: an invitation on a blank page, the
// usual summon once there are words to talk about.
function updateIdeaSamPill() {
  const pill = $("#idea-sam-pill");
  if (!pill) return;
  const has = (($("#idea-content") || {}).value || "").trim().length > 0;
  pill.textContent = has ? "Sameer" : "Ask Sameer";
  pill.title = has
    ? "Talk it through with Sameer — he reads the whole page. Or just press C."
    : "Talk it through with Sameer about this idea — he reads whatever this page holds. Or just press C.";
  pill.style.display = "";
}

let ideaSaveTimer = null;
let sameerSummonTimer = null;

function handleIdeaContentInput() {
  // the /sameer command: type it ANYWHERE — its own line, the end of a line,
  // or mid-sentence — and this idea's own Sameer summons with the WHOLE page
  // in front of him. Only the command token itself is spent; the sentence it
  // sat in stays on the page, and any words right after the command become
  // his opening ask in the composer.
  //
  // The summon waits ~350ms of typing silence first: a fast-typing writer (or
  // a paste) finishes landing before he reads, so nothing gets split between
  // the page and the composer. He still feels instant — a breath, not a wait.
  const value = $("#idea-content").value;
  updateIdeaSamPill();
  if (/\/sameer(?![\w-])/.test(value)) {
    clearTimeout(sameerSummonTimer);
    sameerSummonTimer = setTimeout(() => {
      const v2 = $("#idea-content").value;
      const m2 = v2.match(/\/sameer(?![\w-])[ \t]?([^\n]*)/);
      if (!m2) return; // edited away in the meantime
      const ask = (m2[1] || "").trim();
      $("#idea-content").value =
        (v2.slice(0, m2.index) + v2.slice(m2.index + m2[0].length))
          .replace(/\n{3,}/g, "\n\n").replace(/\n+$/, "");
      updateIdeaSamPill();
      summonIdeaSam(ask);
    }, 350);
    return;
  }
  clearTimeout(sameerSummonTimer);
  scheduleIdeaSave();
}

function scheduleIdeaSave() {
  // near-instant autosave: the page is the material Sameer reads — a slow
  // debounce risks him missing the last lines before an invocation
  clearTimeout(ideaSaveTimer);
  ideaSaveTimer = setTimeout(saveIdeaContent, 300);
}

// tiny trust signal: the page saves itself, quietly -- but the writer should
// SEE that it saved ("did I lose anything?" must never be a question here)
let _ideaSaveStateTimer = null;
function setIdeaSaveState(phase) {
  const elm = $("#idea-save-state");
  if (!elm) return;
  clearTimeout(_ideaSaveStateTimer);
  if (phase === "saving") {
    elm.textContent = "saving\u2026";
    elm.classList.add("busy");
    return;
  }
  elm.classList.remove("busy");
  if (phase === "saved") {
    const t = new Date();
    elm.textContent = "saved " + t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    _ideaSaveStateTimer = setTimeout(() => { elm.textContent = ""; }, 4000);
  } else {
    elm.textContent = "";
  }
}

async function saveIdeaContent() {
  clearTimeout(ideaSaveTimer);
  if (!state.currentIdea || !state.inIdea) return;
  const content = $("#idea-content").value;
  setIdeaSaveState("saving");
  try {
    const res = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/content`, { method: "POST", body: JSON.stringify({ content }) });
    setIdeaSaveState("saved");
    state.currentIdea.content = content;
    if (res && res.auto_title) {
      state.currentIdea.title = res.title;
      $("#idea-title-input").value = res.title;
      $("#project-title").textContent = res.title;
      $("#project-title").title = res.title;
    }
    await loadIdeas(); // keep the shelf in sync (auto-title / rename)
  } catch (_) { /* autosave must never interrupt writing */ }
}

async function renameIdea(title) {
  if (!state.currentIdea) return;
  try {
    const res = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/rename`, { method: "POST", body: JSON.stringify({ title }) });
    state.currentIdea.title = res.title;
    $("#idea-title-input").value = res.title;
    $("#project-title").textContent = res.title;
    $("#project-title").title = res.title;
    await loadIdeas();
  } catch (e) {
    showError("Couldn't rename the idea: " + e.message);
  }
}

function hideIdeaQuoteFloat() {
  const btn = $("#idea-quote-float");
  if (btn) btn.hidden = true;
}

// called by the floating chip: opens Sameer with the highlighted passage as
// a pending quote card -- his next answer grounds on THOSE exact lines
function askSamAboutSelection(btn) {
  const text = (btn.dataset.text || "").trim();
  hideIdeaQuoteFloat();
  if (!text) return;
  window.getSelection().removeAllRanges();
  setPendingQuote({ scene_number: null, text });
  summonIdeaSam(`What about this part \u2014 "${text.slice(0, 80)}${text.length > 80 ? "\u2026" : ""}"?`);
}

async function summonIdeaSam(prefill) {
  if (!state.currentIdea) return;
  try {
    // flush any pending autosave BEFORE he reads: the whole point is that he
    // has everything typed up to the exact moment you called him
    await saveIdeaContent();
    if (!state.currentIdeaSession) {
      const res = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/start`, { method: "POST" });
      state.currentIdeaSession = res.session_id;
    }
    await loadIdeaSession(state.currentIdeaSession);
    openRoomDrawer();
    $("#idea-explore").style.display = "";
    const input = $("#input");
    if (prefill) { input.value = prefill; }
    input.focus();
  } catch (e) {
    showError("Couldn't start the conversation: " + e.message);
  }
}

function toggleIdeaStructure() {
  const panel = $("#idea-structure-panel");
  const open = panel.style.display === "flex";
  panel.style.display = open ? "none" : "flex";
  $("#idea-structure-btn").textContent = open ? "▸ Structure" : "▾ Structure";
}

async function saveIdeaStructure() {
  if (!state.currentIdea) return;
  const card = {
    logline: $("#idea-logline").value.trim(),
    questions: $("#idea-questions").value.split("\n").map((s) => s.trim()).filter(Boolean),
  };
  try {
    const meta = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/card`, { method: "POST", body: JSON.stringify({ card }) });
    state.currentIdea.card = meta.card;
    const b = $("#idea-structure-save");
    const old = b.textContent;
    b.textContent = "Saved ✓";
    setTimeout(() => { b.textContent = old; }, 1400);
  } catch (e) {
    showError("Couldn't save the structure: " + e.message);
  }
}

async function loadIdeaSession(sid) {
  const data = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/sessions/${sid}`);
  state.currentIdeaSession = data.session_id;
  state.branches = data.branches;
  state.currentBranch = data.current_branch;
  // Welcome-back recap: Sameer keeps a baseline of the page AS HE LAST READ
  // it. If this is a returning conversation, say so out loud (and whether the
  // page moved under him since).
  const _msgs = ((data.branches || {})[data.current_branch] || {}).messages || [];
  const _seen = (data.last_seen_content || "").trim();
  const _now = ((state.currentIdea || {}).content || "").trim();
  state.ideaRecap = _msgs.length
    ? { turns: _msgs.length, changed: !!_seen && _seen !== _now }
    : null;
  resetChatHistory();
  renderMessages();
  renderBranches();
  populateSelectors();
}

// The two lenses of the idea room: Co-write = Sameer (explore), Feedback = the
// premise doctor (validate). Same conversation, new partner — the toggle
// swaps the lens and persists it on the session.
function setIdeaLens(room) {
  const partnerName = $(".partner-name");
  const input = $("#input");
  if (room === "feedback") {
    partnerName.textContent = partnerLabel("Premise Doctor — Development Exec");
    input.placeholder = "Ask the premise doctor to test the idea…";
    document.body.dataset.room = "feedback";
  } else {
    partnerName.textContent = partnerLabel("Sameer — AI writing partner");
    input.placeholder = "Talk it through with Sameer…";
    document.body.dataset.room = "cowrite";
  }
  const chip = $("#room-chip");
  if (chip) chip.textContent = room === "feedback" ? "📋 Concept Validation" : "✍️ Idea Room";
  const cowriteBtnEl = $("#room-cowrite-btn");
  const feedbackBtnEl = $("#room-feedback-btn");
  cowriteBtnEl.classList.toggle("active", room === "cowrite");
  feedbackBtnEl.classList.toggle("active", room === "feedback");
  cowriteBtnEl.setAttribute("aria-selected", room === "cowrite" ? "true" : "false");
  feedbackBtnEl.setAttribute("aria-selected", room === "feedback" ? "true" : "false");
  setDrawerIdentity(room, true);
  syncGutter();
}

async function applyIdeaLens(room) {
  setIdeaLens(room);
  if (!state.currentIdeaSession) return;
  const persona = room === "feedback" ? "premise_doctor" : "writing_partner";
  const mode = room === "feedback" ? "concept_validation" : "peer";
  try {
    const res = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/sessions/${state.currentIdeaSession}/settings`, {
      method: "POST", body: JSON.stringify({ persona, mode }),
    });
    state.branches[state.currentBranch] = { ...currentBranchData(), active_persona: res.active_persona, active_mode: res.active_mode };
  } catch (_) { /* non-fatal — the lens still shows */ }
}

// On a graduated project the premise card lives behind a toolbar toggle.
// Phase 13: it's a full-screen view now (like the revision desk) — the old
// inline pane was display:none with .desk, so the chip was a dead end.
let premisePrevRoom = "cowrite";
function openPremiseView() {
  if (state.view === "premise") return;
  exitSpotlight();
  premisePrevRoom = state.view === "cowrite" || state.view === "feedback" ? state.view : "cowrite";
  state.view = "premise";
  hideAllViews();
  closeRoomDrawer();
  $("#premise-view").style.display = "flex";
  // the graduate path belongs to ideas — a graduated project already has
  // pages, so the upload button hides (parity with the old pane toggle)
  $("#premise-graduate-btn").style.display = state.currentProject ? "none" : "inline-block";
  populatePremiseFields(state.premise || {});
  renderExploreChips();
  saveSession();
}
function closePremiseView() {
  if (state.view !== "premise") return;
  setRoom(premisePrevRoom);
}
function togglePremisePane() {
  if (state.view === "premise") closePremiseView();
  else openPremiseView();
}

async function graduateIdea(file) {
  const btn = $("#idea-graduate-btn");
  btn.disabled = true;
  btn.textContent = "Parsing the pages…";
  const form = new FormData();
  form.append("file", file);
  form.append("title", $("#idea-title-input").value.trim() || file.name.replace(/\.[^.]+$/, ""));
  try {
    await savePremise(false);
    const project = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/graduate`, { method: "POST", body: form });
    state.inIdea = false;
    state.currentIdea = null;
    state.currentIdeaSession = null;
    await loadProjects();
    await loadIdeas();
    await openProject(project.project);
    appendSystemNote("The premise card and your conversation came with you — same desk, same Sameer.");
  } catch (e) {
    showError("Couldn't graduate the idea: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "📄 Upload the first pages";
  }
}

async function uploadFile(file) {
  const status = $("#upload-status");
  status.classList.remove("error");
  status.textContent = `Reading "${file.name}"…`;

  const form = new FormData();
  form.append("file", file);
  form.append("title", file.name.replace(/\.[^.]+$/, ""));

  try {
    const project = await api("/projects", { method: "POST", body: form });
    status.textContent = `Parsed — ${project.title}`;
    await loadProjects();
    await openProject(project.project);
  } catch (e) {
    status.classList.add("error");
    status.textContent = "Couldn't read that file: " + e.message;
  }
}

const SESSION_KEY = "screenplay_studio.session.v1";
const PREFS_KEY = "screenplay_studio.prefs.v1";

function loadPrefs() {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY) || "{}"); } catch (_) { return {}; }
}

function savePrefs(patch) {
  const prefs = { ...loadPrefs(), ...patch };
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (_) { /* private mode */ }
}

function applyDawn(dawn) {
  document.body.classList.toggle("dawn", !!dawn);
  const btn = $("#dawn-btn");
  if (btn) btn.textContent = dawn ? "🌙 Night" : "☀ Dawn";
  const statusBtn = $("#status-dawn");
  if (statusBtn) statusBtn.textContent = dawn ? "🌙 Night" : "☀ Dawn";
}

function applyReaderMode(on) {
  document.body.classList.toggle("reader-mode", !!on);
  const btn = $("#reader-btn");
  if (btn) btn.classList.toggle("active", !!on);
}

// ---- river read (Spark Wall): the draft as one continuous flow ----
// Pages become glass cards in a stream; a current nav on the right edge
// tracks your drift and jumps scenes on click. Esc leaves the river.
let flowRAF = null;

function applyFlowMode(on) {
  document.body.classList.toggle("river-read", !!on);
  const btn = $("#flow-btn");
  if (btn) btn.classList.toggle("active", !!on);
  buildRiverDots();
}

function buildRiverDots() {
  const holder = document.getElementById("river-current");
  if (!holder) return;
  holder.innerHTML = "";
  if (!document.body.classList.contains("river-read")) return;
  const container = getManuscriptContainer();
  const pages = [...(container ? container.querySelectorAll(".scene-page") : [])];
  pages.forEach((pg, i) => {
    const d = document.createElement("i");
    const headEl = pg.querySelector(".scene-page-head");
    d.title = (headEl ? headEl.textContent : `Scene ${i + 1}`).trim().slice(0, 80);
    if (i === 0) d.classList.add("on");
    d.addEventListener("click", () => {
      const c = getManuscriptContainer();
      if (c) c.scrollTo({ top: pg.offsetTop - c.offsetTop - 12, behavior: "smooth" });
    });
    holder.appendChild(d);
  });
}

function onRiverScroll() {
  if (flowRAF) return;
  flowRAF = requestAnimationFrame(() => {
    flowRAF = null;
    const holder = document.getElementById("river-current");
    const c = getManuscriptContainer();
    if (!holder || !c || !holder.children.length) return;
    const mid = c.scrollTop + c.clientHeight * 0.45;
    const pages = [...c.querySelectorAll(".scene-page")];
    let act = 0;
    pages.forEach((pg, i) => { if (pg.offsetTop - c.offsetTop <= mid) act = i; });
    // Bottom clamp: a short LAST page may never cross the 45% line (the
    // container can't scroll far enough), so reading the final scene would
    // leave the nav stuck on the scene before it. At the absolute bottom
    // the last page is, by definition, the one you're on.
    if (pages.length && c.scrollTop + c.clientHeight >= c.scrollHeight - 2) {
      act = pages.length - 1;
    }
    [...holder.children].forEach((d, i) => d.classList.toggle("on", i === act));
  });
}

// ---- explore chips: collapse to icons on first input, hover reveals ----
// The mockup contract, applied to the real drawer: expanded on open,
// .collapsed once the writer types, hover on a lone icon restores its label.
function setExploreChipsCollapsed(on) {
  document.querySelectorAll(".explore-chips").forEach((c) => c.classList.toggle("collapsed", on));
}

// ---- Focus mode: the page dims to the line you're on ----
// One ambient-mode toggle. On: chrome dims, the script's non-current scenes
// fade, and the script scrolls typewriter-style — the current scene stays
// centered and the others follow behind it.
let focusScrollRAF = null;

function applyFocusMode(on) {
  document.body.classList.toggle("focus-mode", !!on);
  const btn = $("#focus-btn");
  if (btn) {
    btn.classList.toggle("active", !!on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  if (on) {
    markCurrentScene();
    markCurrentLine();
    var _ss = getManuscriptContainer(); if (_ss) _ss.addEventListener("scroll", onFocusScroll, { passive: true });
  } else {
    var _ss2 = getManuscriptContainer(); if (_ss2) _ss2.removeEventListener("scroll", onFocusScroll);
    document.querySelectorAll(".focus-line").forEach((l) => l.classList.remove("focus-line"));
  }
}

function onFocusScroll() {
  if (focusScrollRAF) return;
  focusScrollRAF = requestAnimationFrame(() => {
    focusScrollRAF = null;
    markCurrentScene();
    markCurrentLine();
  });
}

// the scene whose spine crosses the middle of the pane — Highland-style
// "you are here" tracking (queried on the REAL script pages; earlier this
// hit the decorative night window and silently marked nothing)
function markCurrentScene() {
  const container = getManuscriptContainer();
  if (!container) return;
  const pages = [...container.querySelectorAll(".scene-page")];
  if (!pages.length) return;
  const viewportMid = container.getBoundingClientRect().top + container.clientHeight / 2;
  let current = pages[0];
  for (const p of pages) {
    const r = p.getBoundingClientRect();
    if (r.top <= viewportMid) current = p; else break;
  }
  pages.forEach((p) => p.classList.toggle("scene-current", p === current));
  updateSceneIndexHighlight();
}

// typewriter focus: within the current scene, the line nearest the pane's
// vertical center is the live line — everything else greys out (CSS)
function markCurrentLine() {
  if (!document.body.classList.contains("focus-mode")) return;
  const container = getManuscriptContainer();
  if (!container) return;
  const current = container.querySelector(".scene-page.scene-current");
  if (!current) return;
  const lines = [...current.querySelectorAll("[class^=el-]")];
  if (!lines.length) return;
  const mid = container.getBoundingClientRect().top + container.clientHeight / 2;
  let best = lines[0], bestDist = Infinity;
  for (const l of lines) {
    const d = Math.abs(l.getBoundingClientRect().top + l.offsetHeight / 2 - mid);
    if (d < bestDist) { bestDist = d; best = l; }
  }
  lines.forEach((l) => l.classList.toggle("focus-line", l === best));
}// ---- Spotlight mode: nothing but the page ----
// The "power mode" from the layout review, critically scoped: the app
// already had the palette + focus mode, so this adds only what Spotlight
// uniquely means — TOTAL chrome removal. project-bar, script toolbar, rail
// tab, gutter and drawer all vanish; the manuscript owns the screen; the
// status strip keeps only what a writer actually uses in a session (the
// sprint timer + project/room orientation). Everything else is one ⌘K or
// one key away. z toggles, Esc leaves.
function enterSpotlight() {
  if (document.body.classList.contains("spotlight-mode")) return;
  closeRoomDrawer();
  document.body.classList.add("spotlight-mode");
  const proj = $("#status-project");
  if (proj) {
    const room = state.view === "feedback" ? "Consultant" : state.inIdea ? "Idea room" : "Sameer";
    proj.textContent = `${state.currentProject || ""} · ${room} · Esc to leave`;
    proj.style.display = "inline";
  }
}

function exitSpotlight() {
  document.body.classList.remove("spotlight-mode");
  const proj = $("#status-project");
  if (proj) proj.style.display = "none";
}

function toggleSpotlight() {
  // spotlight is a manuscript-surface mode — full-screen tools (revision,
  // beat board, compare) supersede it, so it only toggles in the rooms
  if (state.view !== "cowrite" && state.view !== "feedback") return;
  if (document.body.classList.contains("spotlight-mode")) exitSpotlight();
  else enterSpotlight();
}

// ---- Sprint timer: a 25-minute writing sprint in the status strip ----
// Click to start/pause, double-click to reset. The running sprint survives a
// reload (the strip keeps counting in the background — it's a real timer,
// not a page-scoped toy).
const SPRINT_MS = 25 * 60 * 1000;
const SPRINT_KEY = "screenplay_studio.sprint.v1";
let sprintState = { running: false, remaining: SPRINT_MS, endAt: 0 };
let sprintTick = null;
let sprintFlashTimer = null;

function sprintEl() { return $("#sprint-timer"); }

function formatSprint(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(s / 60), r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function persistSprint() {
  try {
    localStorage.setItem(SPRINT_KEY, JSON.stringify({
      running: sprintState.running, remaining: sprintState.remaining, endAt: sprintState.endAt,
    }));
  } catch (_) { /* private mode */ }
}

function renderSprint() {
  const el = sprintEl();
  if (!el) return;
  const done = sprintState.remaining <= 0;
  el.textContent = done ? "⏱ done" : `⏱ ${formatSprint(sprintState.remaining)}`;
  el.classList.toggle("running", sprintState.running);
  el.classList.toggle("done", done);
  el.title = done
    ? "Sprint complete. Click for a fresh 25:00 — or double-click anywhere to reset."
    : (sprintState.running
        ? `Writing sprint — ${formatSprint(SPRINT_MS - sprintState.remaining)} in. Click to pause, double-click to reset.`
        : `Sprint paused (${formatSprint(SPRINT_MS - sprintState.remaining)} in). Click to resume, double-click to reset.`);
  persistSprint();
}

function sprintPulse() {
  if (!sprintState.running) return;
  sprintState.remaining = Math.max(0, sprintState.endAt - Date.now());
  if (sprintState.remaining <= 0) {
    sprintState.running = false;
    sprintState.remaining = 0;
    clearInterval(sprintTick);
    sprintTick = null;
    // a quiet "the sprint is over" cue — the strip flashes, nothing louder
    const el = sprintEl();
    if (el) {
      el.classList.remove("sprint-done-flash");
      void el.offsetWidth;
      el.classList.add("sprint-done-flash");
      if (sprintFlashTimer) clearTimeout(sprintFlashTimer);
      sprintFlashTimer = setTimeout(() => el.classList.remove("sprint-done-flash"), 3000);
    }
  }
  renderSprint();
}

function startSprint() {
  sprintState.running = true;
  sprintState.endAt = Date.now() + sprintState.remaining;
  if (!sprintTick) sprintTick = setInterval(sprintPulse, 1000);
  renderSprint();
}

function pauseSprint() {
  sprintState.running = false;
  sprintState.remaining = Math.max(0, sprintState.endAt - Date.now());
  if (sprintTick) { clearInterval(sprintTick); sprintTick = null; }
  renderSprint();
}

function toggleSprint() {
  if (sprintState.running) pauseSprint();
  else if (sprintState.remaining <= 0) { sprintState.remaining = SPRINT_MS; startSprint(); }
  else startSprint();
}

function resetSprint() {
  pauseSprint();
  sprintState.remaining = SPRINT_MS;
  renderSprint();
}

function wireSprint() {
  const el = sprintEl();
  if (!el) return;
  // restore a live sprint across reloads: if it was running, keep counting
  // from its endAt (it may already have finished while the tab was away)
  try {
    const saved = JSON.parse(localStorage.getItem(SPRINT_KEY) || "null");
    if (saved && typeof saved.remaining === "number") {
      sprintState.remaining = saved.remaining;
      if (saved.running && saved.endAt) {
        sprintState.endAt = saved.endAt;
        sprintState.remaining = Math.max(0, saved.endAt - Date.now());
        if (sprintState.remaining > 0) { sprintState.running = true; sprintTick = setInterval(sprintPulse, 1000); }
      }
    }
  } catch (_) { /* private mode */ }
  el.addEventListener("click", toggleSprint);
  el.addEventListener("dblclick", resetSprint);
  // a11y (WCAG 2.1.1 Keyboard): the sprint timer is role="button" + tabindex=0
  // but only had click/dblclick handlers, so it was focusable and announced as
  // a button yet did nothing from the keyboard. Enter/Space toggles; R resets.
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      toggleSprint();
    } else if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      resetSprint();
    }
  });
  renderSprint();
}

function saveSession() {
  try {
    const payload = { project: state.currentProject, view: state.view, idea: state.currentIdea ? state.currentIdea.id : null };
    if ((state.view === "cowrite" || state.view === "feedback") && state.script && state.script.scenes && state.script.scenes.length) {
      const container = getManuscriptContainer();
      const pages = container ? [...container.querySelectorAll(".scene-page")] : [];
      if (pages.length) {
        const viewportTop = container.getBoundingClientRect().top + 24;
        let idx = pages.findIndex((p) => p.getBoundingClientRect().top >= viewportTop - 8);
        if (idx === -1) idx = pages.length - 1;
        payload.scene = pages[Math.max(0, idx)].dataset.sceneNumber || null;
      }
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  } catch (_) { /* private mode — restore just won't persist */ }
}

function restoreSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
  } catch (_) {
    return null;
  }
}

// ---- Home: back to the welcome desk (shelf · library · ideas) ----
// Distinct from the room toggle and the idea room: this leaves the project
// entirely. The session is cleared so a refresh lands on the desk, not back
// inside the script.

function goHome() {

  // Hide the problem board -- it belongs to a project that's going away
  hideProblemBoard();
  state.view = "cowrite";
  state.currentProject = null;
  state.currentSession = null;
  state.currentIdea = null;
  state.currentIdeaSession = null;
  state.inIdea = false;
  state.script = null;
  state.findings = [];
  state.findingStatus = {};
  state.fixQueue = null;
  state.editsData = null;
  state.branches = { main: { messages: [], active_persona: "writing_partner", active_mode: "peer" } };
  state.currentBranch = "main";
  hideAllViews();
  $("#welcome-view").style.display = "flex";
  $("#project-bar").style.display = "none";
  // back at the landing desk: restore the shelf exactly as the writer left
  // it (the writing environment's auto-collapse is never persisted)
  toggleSidebar(!!loadPrefs().sidebar_collapsed, false);
  const input = $("#input");
  if (input) input.value = "";
  try { localStorage.removeItem(SESSION_KEY); } catch (_) {}
  refreshMetrics();
  loadProjects();
}

async function openProject(name) {
  try {
    // leaving the idea room — the pages are back on the desk
    state.inIdea = false;
    state.currentIdea = null;
    state.currentIdeaSession = null;
    document.body.classList.remove("idea-mode");
    state.currentProject = name;
    state.script = null;
    state.findings = [];
    state.findingStatus = {};
    state.fixQueue = null;
    state.reportStats = null;
    state.premise = null;
    $("#premise-view").style.display = "none";
    // leaving the idea room must put the canvas AWAY, or it stays stacked
    // above the project's pages (reported: idea page took the top half)
    $("#idea-canvas").style.display = "none";
    $("#desk-toolbar").style.display = "flex"; // Phase 13: the desk's row owns the tools now
    const mc = getManuscriptContainer(); if (mc) mc.style.display = "";
    $(".partner-name").textContent = partnerLabel("Sameer — AI writing partner");
    $("#input").placeholder = "Ask about a scene, a character, a note in the margins…";
    const project = await api(`/projects/${encodeURIComponent(name)}`);
    renderProjectList();
    renderLibraryList();
    loadStash();
    refreshMetrics();

    // an idea that graduated carries its premise card alongside the pages
    state.premise = project.premise && (project.premise.title || project.premise.logline || project.premise.premise) ? project.premise : null;
    $("#premise-btn").style.display = state.premise ? "inline-block" : "none";

    $("#welcome-view").style.display = "none";
    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "flex";
    // WIREFRAME ALIGNMENT — the writing environment has no permanent left
    // navigation: the shelf slides away so the Scene Index owns x:0-44 and
    // the 700px manuscript column can centre on the viewport. Not persisted
    // (persist=false) — the landing desk keeps the writer's shelf preference,
    // and the edge tab brings the shelf back at any time.
    toggleSidebar(true, false);
    $("#project-bar").style.display = "flex";
    $("#project-title").textContent = project.title;
    $("#project-title").title = project.title;

    $("#analyze-btn").textContent = project.stages.analyze === "complete" ? "Re-run Analysis" : "Run Analysis";
    $("#analyze-btn").disabled = project.stages.parse !== "complete";
    refreshDeskToolbar(); // Phase 8: the desk toolbar mirrors the lifecycle

    // a previous analysis may still be running (e.g. the page was reloaded
    // mid-analysis, or a background run is in flight) — resume the live
    // pipeline display without firing a second analysis
    if (project.stages.analyze === "running") {
      startAnalysisProgressUI(Date.now(), true);
    }

    // report language follows the project; defaults to English
    const langSel = $("#report-lang-select");
    if (langSel) langSel.value = project.report_language || "eng";

    if (project.stages.analyze === "failed" && project.errors && project.errors.analyze) {
      showError("Last analysis attempt failed: " + project.errors.analyze, true);
    }

    // resume existing session if one exists, otherwise start fresh on demand
    // (lazily, when the user actually sends a first message) to avoid
    // creating empty sessions just from browsing to a project.
    if (project.sessions && project.sessions.length) {
      await loadSession(project.sessions[0].session_id);
    } else {
      state.currentSession = null;
      state.branches = { main: { messages: [], active_persona: "writing_partner", active_mode: "peer" } };
      state.currentBranch = "main";
      renderMessages();
      renderBranches();
      populateSelectors();
    }

    // the script pane is always visible in both rooms — render it once
    try { await loadScriptData(); } catch (_) { /* no parse yet — pane shows its hint */ }
    renderManuscript(document.getElementById('manuscript-container'));
    maybeShowWelcome();
    // Show Problem Board if analysis exists
    if (state.findings && state.findings.length > 0) {
      showProblemBoard();
    }

    setRoom("cowrite");
    // a project opens with the manuscript center stage — the partner drawer
    // stays closed until summoned (gutter tab, room toggle, or select-to-ask)
    closeRoomDrawer();
    saveSession();
  } catch (e) {
    showError("Couldn't open that project: " + e.message);
  }
}

// ---------- rooms: Co-write (writer's desk) vs Feedback (consultant's desk) ----------
// The script pane is shared and always visible; the room toggle swaps which
// partner occupies the drawer (see body[data-room] in style.css).

// Manuscript Stage: the partner drawer + the right-edge gutter. Sameer and the
// consultant live in a drawer that slides in from the edge when summoned and
// leaves the page alone the rest of the time.
function openRoomDrawer() {
  // Phase 7: summoning the room drawer takes the conversation back from an
  // adopted dock lens — the drawer opens with its conversation in place
  dockYieldToRoom();
  const d = $("#room-drawer");
  if (d) d.classList.add("open");
  syncGutter();
  // Summoning the partner hands the keyboard to the composer: the keys typed
  // right after a summon must land in the CHAT, not wherever focus happened
  // to be sitting — on the idea page that meant text silently became canvas
  // content and re-titled the idea (UI audit 2026-09-20, defect #7). The
  // deferred focus wins the drawer's render race; the panel guard keeps the
  // project's feedback room (which has no composer) from focusing nothing.
  const composer = $("#input");
  const panel = $("#cowrite-panel");
  if (composer && panel && panel.style.display !== "none") {
    setTimeout(() => {
      if (panel.style.display !== "none") composer.focus();
    }, 0);
  }
}
function closeRoomDrawer() {
  const d = $("#room-drawer");
  if (d) d.classList.remove("open");
  syncGutter();
}
function syncGutter() {
  const sam = state.view !== "feedback";
  const gs = $("#gutter-sam"), gd = $("#gutter-doc");
  if (gs) gs.classList.toggle("on", sam);
  if (gd) gd.classList.toggle("on", !sam);
}
function setDrawerIdentity(room, idea) {
  const av = $("#drawer-av"), name = $("#drawer-name");
  if (!av || !name) return;
  if (room === "feedback") {
    av.textContent = "D";
    av.className = "drawer-avatar doc";
    name.innerHTML = idea
      ? 'Premise Doctor <small>development exec — testing the idea</small>'
      : 'Consultant <small>script doctor — reading the draft</small>';
  } else {
    av.textContent = "S";
    av.className = "drawer-avatar sam";
    name.innerHTML = idea
      ? 'Sameer <small>co-writer — exploring the idea</small>'
      : 'Sameer <small>co-writer — beside you</small>';
  }
}

function setRoom(room) {
  // Phase 7: entering a room reclaims the conversation from an adopted dock
  // lens — the room opens with its conversation in place, never empty
  dockYieldToRoom();
  state.view = room;                       // "cowrite" | "feedback"
  if (state.inIdea) {
    // idea room: both lenses share one conversation — the toggle swaps the
    // partner (Sameer <-> premise doctor), not the panel
    applyIdeaLens(room);
    $("#beatboard-view").style.display = "none";
    $("#compare-view").style.display = "none";
    $("#revision-view").style.display = "none";
    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "flex";
    saveSession();
    return;
  }
  document.body.dataset.room = room;       // drives CSS theming
  setDrawerIdentity(room, false);
  syncGutter();
  const chip = $("#room-chip");
  if (chip) chip.textContent = room === "feedback" ? "📋 Consultant's Desk" : "✍️ Writer's Desk";
  const cowriteBtnEl = $("#room-cowrite-btn");
  const feedbackBtnEl = $("#room-feedback-btn");
  cowriteBtnEl.classList.toggle("active", room === "cowrite");
  feedbackBtnEl.classList.toggle("active", room === "feedback");
  cowriteBtnEl.setAttribute("aria-selected", room === "cowrite" ? "true" : "false");
  feedbackBtnEl.setAttribute("aria-selected", room === "feedback" ? "true" : "false");
  $("#cowrite-panel").style.display = room === "cowrite" ? "flex" : "none";
  $("#feedback-panel").style.display = room === "feedback" ? "flex" : "none";
  // the composer speaks in the active partner's voice: Sameer at the writing
  // desk, the doctor at the consultant's desk
  const inputEl = $("#input");
  if (inputEl) inputEl.placeholder = room === "feedback"
    ? "Ask the consultant — he has read the whole report…"
    : "Ask about a scene, a character, a note in the margins…";
  // closing a full-screen tool returns to the active room
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  $("#revision-view").style.display = "none";
  $("#premise-view").style.display = "none";
  const ws = document.querySelector(".workspace");
  if (ws) ws.style.display = "flex";
  saveSession();
}

function openCowriteRoom() {
  if (state.view === "cowrite") { openRoomDrawer(); return; }
  setRoom("cowrite");
  renderMessages();
  maybeShowWelcome();
  openRoomDrawer();
}

function openFeedbackRoom() {
  // Phase 9: in the idea room the Feedback toggle swaps the partner lens to
  // the Premise Doctor (same conversation, per applyIdeaLens). Only after
  // the writer has summoned a session does the lens persist to the server —
  // before that the first send creates it with the right persona.
  if (state.inIdea) {
    if (state.view === "feedback") { openRoomDrawer(); return; }
    setRoom("feedback");
    renderMessages();
    openRoomDrawer();
    return;
  }
  if (state.view === "feedback") { openRoomDrawer(); return; }
  setRoom("feedback");
  if (state.inIdea) { renderMessages(); openRoomDrawer(); return; }  // unreachable — kept for safety
  if (typeof loadFeedbackPanels === "function") loadFeedbackPanels();  // defined in Task 10
  openRoomDrawer();
}

// ---------- analysis progress pipeline ----------
// Long analyses (this model + a full script can take tens of minutes) deserve
// more than a frozen spinner. The Analyze button shows live % + ETA; hovering
// the progress chip opens a pipeline map — every stage, which are done, which
// is running now, and where it's heading — plus a line on why it takes as
// long as it does.

const ANALYSIS_STAGES = [
  { key: "formatting", label: "Formatting checks", weight: 1 },
  { key: "voice", label: "Character voice fingerprints", weight: 1 },
  { key: "subtext", label: "On-the-nose scan", weight: 1 },
  { key: "idiolect", label: "Voice consistency", weight: 1 },
  { key: "continuity", label: "Continuity check", weight: 1 },
  { key: "pacing", label: "Scene pace", weight: 1 },
  { key: "summaries", label: "Scene summaries", weight: 3 },
  { key: "dialogue", label: "Dialogue & action", weight: 5 },
  { key: "theme", label: "Theme & subtext", weight: 2 },
  { key: "character", label: "Character arcs", weight: 2 },
  { key: "structure", label: "Structure & pacing", weight: 2 },
  { key: "scene_function", label: "Scene functionality", weight: 2 },
  { key: "principles", label: "Setups & payoffs", weight: 3 },
  { key: "setup_payoff", label: "Setup/payoff ledger", weight: 2 },
  { key: "char_reads", label: "Character perception", weight: 2 },
  { key: "character_dials", label: "Character dials", weight: 1 },
  { key: "verification", label: "Verifying quotes", weight: 1 },
  { key: "coverage", label: "Writing coverage", weight: 2 },
  { key: "logline_test", label: "Logline test", weight: 1 },
  { key: "genre", label: "Genre conventions", weight: 2 },
];
const ANALYSIS_TOTAL_WEIGHT = ANALYSIS_STAGES.reduce((a, s) => a + s.weight, 0);

let analysisUi = null; // { timer, poll, stop } for the running analysis display

function analysisStageIndex(key) {
  return ANALYSIS_STAGES.findIndex((s) => s.key === key);
}

function formatETA(seconds) {
  if (!isFinite(seconds) || seconds <= 0) return "time left …";
  const totalMin = Math.ceil(seconds / 60);
  if (totalMin >= 60) return `~${Math.floor(totalMin / 60)}h ${totalMin % 60}m left`;
  return `~${totalMin}m left`;
}

function renderPipelinePopover(currentKey) {
  const wrap = el("div", "analyze-pipeline");
  const idx = analysisStageIndex(currentKey);
  const head = el("div", "pipeline-head", "Analysis pipeline");
  wrap.appendChild(head);
  ANALYSIS_STAGES.forEach((s, i) => {
    const row = el("div", "pipeline-row" + (i < idx ? " done" : i === idx ? " run" : ""));
    const mark = el("span", "pipeline-mark", i < idx ? "✓" : i === idx ? "●" : "○");
    row.appendChild(mark);
    row.appendChild(el("span", "pipeline-label", s.label));
    if (i === idx) row.appendChild(el("span", "pipeline-now", "now"));
    wrap.appendChild(row);
  });
  const note = el("div", "pipeline-note");
  note.textContent =
    "Every stage calls the model on this machine — long scripts split into chunks, each taking " +
    "tens of seconds, so a bigger or slower model stretches every stage. The bar tracks stage " +
    "weight, not wall-clock, so ETA is an estimate that firms up as it goes.";
  wrap.appendChild(note);
  return wrap;
}

function startAnalysisProgressUI(startedAt, resumed = false) {
  if (analysisUi) analysisUi.stop();
  const btn = $("#analyze-btn");
  const chip = $("#analyze-progress");
  const deskBtn = $("#desk-analyze-btn");   // Phase 8: the desk toolbar runs
  const deskChip = $("#desk-analyze-progress"); // the same lifecycle in parallel
  btn.disabled = true;
  btn.classList.add("analyzing");
  chip.style.display = "flex";
  if (deskBtn) { deskBtn.disabled = true; deskBtn.classList.add("analyzing"); deskBtn.textContent = "Analyzing…"; }
  if (deskChip) deskChip.style.display = "flex";
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  let currentKey = "formatting";
  let currentLabel = "Starting";
  let renderedFor = "";
  let lastKey = null;
  let lastKeyAt = Date.now();
  let finished = false;

  const refresh = () => {
    if (finished) return;
    const elapsed = (Date.now() - startedAt) / 1000;
    const idx = analysisStageIndex(currentKey);
    if (lastKey !== currentKey) {
      lastKey = currentKey;
      lastKeyAt = Date.now();
    }
    const completedWeight =
      ANALYSIS_STAGES.slice(0, Math.max(0, idx)).reduce((a, s) => a + s.weight, 0) +
      (idx >= 0 ? ANALYSIS_STAGES[idx].weight * 0.5 : 0);
    const pct = Math.max(1, Math.min(99, Math.round((completedWeight / ANALYSIS_TOTAL_WEIGHT) * 100)));
    let eta = null;
    if (!resumed && pct > 3) {
      // we know the real elapsed time — extrapolate from overall pace
      eta = (elapsed / (pct / 100)) * (1 - pct / 100);
    } else if (idx >= 0) {
      // resumed mid-run: no known elapsed, so extrapolate from how long the
      // current stage has been running scaled by its weight
      const stageElapsed = (Date.now() - lastKeyAt) / 1000;
      const remainingWeight =
        ANALYSIS_STAGES.slice(idx + 1).reduce((a, s) => a + s.weight, 0) +
        ANALYSIS_STAGES[idx].weight * 0.5;
      if (stageElapsed > 20) eta = (stageElapsed / Math.max(1, ANALYSIS_STAGES[idx].weight)) * remainingWeight;
    }
    chip.querySelector(".ap-pct").textContent = `${pct}%`;
    chip.querySelector(".ap-eta").textContent = formatETA(eta);
    chip.querySelector(".ap-bar-fill").style.width = pct + "%";
    btn.textContent = `Analyzing — ${currentLabel} — ${pct}%`;
    // Phase 8: same numbers on the desk — one lifecycle, two surfaces
    if (deskChip && deskChip.style.display !== "none") {
      deskChip.querySelector(".ap-pct").textContent = `${pct}%`;
      deskChip.querySelector(".ap-eta").textContent = formatETA(eta);
      deskChip.querySelector(".ap-bar-fill").style.width = pct + "%";
    }
    if (deskBtn) deskBtn.textContent = `Analyzing — ${pct}%`;
    if (renderedFor !== currentKey) {
      renderedFor = currentKey;
      const old = chip.querySelector(".analyze-pipeline");
      if (old) old.remove();
      chip.appendChild(renderPipelinePopover(currentKey));
      // the desk's on-demand detail: the same popover, appended to the
      // desk chip (hover/focus reveals it there too)
      if (deskChip) {
        const oldD = deskChip.querySelector(".analyze-pipeline");
        if (oldD) oldD.remove();
        deskChip.appendChild(renderPipelinePopover(currentKey));
      }
    }
  };

  const timer = setInterval(refresh, 1000);
  const poll = setInterval(async () => {
    try {
      const p = await api(`${base}/progress`);
      if (p.stage === "done") {
        // the run finished on its own (e.g. this page resumed mid-analysis)
        clearInterval(poll);
        clearInterval(timer);
        finished = true;
        analysisUi = null;
        hideAnalysisProgressUI();
        await loadProjects();
        return;
      }
      if (p.stage === "stalled" || p.stage === "failed") {
        // the run died (crash/stall) — stop pretending and say so plainly
        clearInterval(poll);
        clearInterval(timer);
        finished = true;
        analysisUi = null;
        hideAnalysisProgressUI();
        appendSystemNote(p.stage === "stalled"
          ? "Analysis appears to have stopped mid-run — the connection to the run was lost. Re-run Analysis to start fresh."
          : "Analysis failed — see the message in the conversation for details. You can re-run it.", true);
        await loadProjects();
        return;
      }
      currentKey = p.stage || currentKey;
      currentLabel = p.detail || currentKey;
      refresh();
    } catch (_) { /* ignore transient poll failures */ }
  }, 2000);

  const ctl = {
    timer,
    poll,
    stop() {
      clearInterval(timer);
      clearInterval(poll);
      finished = true;
      if (analysisUi === ctl) analysisUi = null;
    },
  };
  analysisUi = ctl;
  refresh();
  return ctl;
}

function hideAnalysisProgressUI() {
  const chip = $("#analyze-progress");
  if (chip) chip.style.display = "none";
  const deskChip = $("#desk-analyze-progress");
  if (deskChip) deskChip.style.display = "none";
  const btn = $("#analyze-btn");
  if (btn) { btn.disabled = false; btn.classList.remove("analyzing"); }
  const deskBtn = $("#desk-analyze-btn");
  if (deskBtn) { deskBtn.disabled = false; deskBtn.classList.remove("analyzing"); }
}

// ---------- Phase 8: the desk toolbar — analysis lifecycle beside the page ----------
// The manuscript is the primary surface, so Run Analysis lives on the desk,
// not only in the feedback room header. This mirrors the SAME state the
// legacy header reads (project stages + fixqueue) — no second source, and
// the legacy buttons keep working until parity (Phase 13).

/** Sync the desk toolbar to the project's lifecycle state.
 *  unanalyzed → prominent Run Analysis + honest status line
 *  running    → progress (handled by startAnalysisProgressUI mirrors)
 *  failed     → ✓/✗ per-category outcome + Retry failed (only failed)
 *  complete   → "Re-run Analysis" + findings count */
function refreshDeskToolbar() {
  const btn = $("#desk-analyze-btn");
  const retryBtn = $("#desk-retry-failed-btn");
  const status = $("#desk-analyze-status");
  if (!btn) return;
  const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
  const stages = (projSummary && projSummary.stages) || {};
  const failedCats = (projSummary && projSummary.failed_categories) || [];

  if (!state.currentProject) {
    btn.style.display = "none";
    if (retryBtn) retryBtn.style.display = "none";
    if (status) { status.textContent = ""; status.title = ""; }
    return;
  }
  btn.style.display = "";

  if (stages.analyze === "complete") {
    btn.textContent = "Re-run Analysis";
    btn.disabled = stages.parse !== "complete";
    if (status) {
      const n = (state.findings || []).length;
      status.textContent = n
        ? `${n} finding${n === 1 ? "" : "s"} on the desk — the dock's Evidence lens has the ledger.`
        : "Analysis complete — a clean bill. The Evidence lens has the coverage.";
      status.title = status.textContent;   // titles never outlive their state
    }
  } else if (stages.analyze === "running") {
    // in-flight ONLY — "pending" means never-run (handled below): the two
    // conflated on first write and a fresh project showed a disabled
    // "Analyzing…" with no way to start
    btn.textContent = "Analyzing…";
    btn.disabled = true;
    if (status) {
      status.textContent = "The consultant is reading — the pipeline tracks below.";
      status.title = status.textContent;
    }
  } else if (stages.analyze === "failed") {
    btn.textContent = "Run Analysis";
    btn.disabled = stages.parse !== "complete";
    if (status) {
      if (failedCats.length) {
        // per-category ✓/✗ — the writer sees exactly what survived
        const ALL = ANALYSIS_STAGES.map((s) => s.key);
        const marks = ALL.map((k) => {
          const failed = failedCats.includes(k);
          return `${failed ? "✗" : "✓"}${k === "genre" ? " genre" : ""}`;
        }).join(" ");
        status.textContent = `Partial report — ${failedCats.length} categor${failedCats.length === 1 ? "y" : "ies"} failed: ${failedCats.join(", ")}. Retry re-runs only those.`;
        // the desk row is one line (Phase 13) — the sentence can ellipsize
        // there, so the hover title carries the full detail first
        status.title = `${status.textContent}  ·  ${marks}`;
      } else {
        status.textContent = "Analysis failed — re-run to try again.";
        status.title = status.textContent;
      }
    }
  } else {
    // fresh project: parse done, analysis never run
    btn.textContent = "Run Analysis";
    btn.disabled = stages.parse !== "complete";
    if (status) {
      status.textContent = stages.parse === "complete"
        ? "Unanalyzed — the manuscript is readable now; Run Analysis to summon the consultant's read."
        : "Parsing the script…";
      status.title = status.textContent;
    }
  }
  if (retryBtn) retryBtn.style.display = failedCats.length ? "inline-block" : "none";
}

async function runAnalysis() {
  if (analysisUi) return; // already running — one lifecycle at a time
  const btn = $("#analyze-btn");
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  const startedAt = Date.now();

  // fire the (blocking) analyze request, and show live stage progress in
  // parallel. force: true so "Re-run Analysis" genuinely re-runs (the
  // orchestrator would otherwise short-circuit on an already-complete stage).
  const reportLanguage = ($("#report-lang-select") || {}).value || "eng";
  const analyzePromise = api(`${base}/analyze`, { method: "POST", body: JSON.stringify({ force: true, report_language: reportLanguage }) });
  startAnalysisProgressUI(startedAt);

  try {
    await analyzePromise;
    if (analysisUi) analysisUi.stop();
    hideAnalysisProgressUI();
    btn.textContent = "Re-run Analysis";
    appendSystemNote("Analysis complete. The report is now grounding this conversation.");
    await loadProjects();  // refreshDeskToolbar rides inside the project open path
    // script pane is shared — refresh it in either room after analysis
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    if (state.view === "feedback") loadFeedbackPanels();
    refreshMetrics();
    refreshDeskToolbar(); // Phase 8: complete state on the desk
  } catch (e) {
    if (analysisUi) analysisUi.stop();
    hideAnalysisProgressUI();
    btn.textContent = "Run Analysis";
    showError("Analysis failed: " + e.message, true);
    appendSystemNote("Analysis failed: " + e.message, true);
    await loadProjects(); // stage state changed — sync the desk honestly
    refreshDeskToolbar();
  }
}

async function reparseProject() {
  // In-app re-parse: re-runs the parser on the active source file. This is
  // the fix for a mis-parsed script — formatting/classification errors show
  // up in the pane and poison the report, so re-parsing then re-running
  // analysis regenerates everything from a clean parse.
  const btn = $("#reparse-btn");
  const project = state.currentProject;
  if (!project) return;
  if (!confirm(`Re-parse "${project}" from its source file?\n\nThe script is re-parsed with the current parser and the analysis is reset — Run Analysis again to regenerate the report and fix queue.`)) return;
  btn.disabled = true;
  try {
    await api(`/projects/${encodeURIComponent(project)}/reparse`, { method: "POST" });
    appendSystemNote("Script re-parsed. The analysis was reset — Run Analysis to regenerate the report from the fresh parse.");
    await loadProjects();
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    const ab = $("#analyze-btn");
    if (ab) { ab.textContent = "Run Analysis"; ab.disabled = false; }
    if (state.view === "feedback") loadFeedbackPanels();
    refreshMetrics();
  } catch (e) {
    showError("Re-parse failed: " + e.message, true);
    appendSystemNote("Re-parse failed: " + e.message, true);
  } finally {
    btn.disabled = false;
  }
}

// ---------- sessions / chat ----------

async function ensureSession() {
  if (state.inIdea) {
    if (state.currentIdeaSession) return state.currentIdeaSession;
    const res = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/start`, { method: "POST" });
    state.currentIdeaSession = res.session_id;
    await loadIdeaSession(res.session_id);
    // Phase 9: the session was created with the default persona (Sameer).
    // If the writer entered through the Feedback lens (Premise Doctor), the
    // FIRST send must already speak as the doctor — flush the lens now,
    // before the first turn is stored.
    if (state.view === "feedback") {
      try {
        const pers = await api(`/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/sessions/${state.currentIdeaSession}/settings`, {
          method: "POST", body: JSON.stringify({ persona: "premise_doctor", mode: "concept_validation" }),
        });
        state.branches[state.currentBranch] = { ...currentBranchData(), active_persona: pers.active_persona, active_mode: pers.active_mode };
      } catch (_) { /* non-fatal — the lens still shows */ }
    }
    return res.session_id;
  }
  if (state.currentSession) return state.currentSession;
  const res = await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/start`, { method: "POST" });
  state.currentSession = res.session_id;
  await loadSession(res.session_id);
  return res.session_id;
}

async function clearChat() {
  // End-user control: erase this conversation with Sameer and start a fresh
  // page. The relationship memory is deliberately kept (backend keeps
  // writer_profile.json) so Sameer's learning about how the writer works
  // survives a cleared thread.
  // The idea room keeps its own base + session id -- reading the project ones
  // made Clear chat a silent no-op there (no project open -> early return).
  const base = state.inIdea
    ? (state.currentIdea ? `/ideas/${encodeURIComponent(state.currentIdea.id)}` : null)
    : (state.currentProject ? `/projects/${encodeURIComponent(state.currentProject)}` : null);
  if (!base) return;
  const sid = state.inIdea ? state.currentIdeaSession : state.currentSession;
  const label = sid ? "this conversation" : "the empty page";
  if (!confirm(`Erase ${label} with Sameer and start fresh?\n\nThe relationship notes are kept — only the chat history goes.`)) return;
  try {
    if (sid) {
      await api(`${base}/chat/sessions/${sid}`, { method: "DELETE" });
    }
    state.currentSession = null;
    state.currentIdeaSession = null;
    state.branches = {};
    state.currentBranch = "main";
    resetChatHistory();
    renderMessages();
    renderBranches();
    // start a brand-new session so the next message has a clean page
    await ensureSession();
    appendSystemNote("Fresh page — a new conversation. The partner still remembers what they've noticed about how you write.");
    $("#input").focus();
  } catch (e) {
    showError("Couldn't clear the chat: " + e.message);
  }
}

async function loadSession(sessionId) {
  const data = await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${sessionId}`);
  state.currentSession = data.session_id;
  state.branches = data.branches;
  state.currentBranch = data.current_branch;
  resetChatHistory();
  renderMessages();
  renderBranches();
  populateSelectors();
}

function currentBranchData() {
  return state.branches[state.currentBranch] || { messages: [], active_persona: "script_consultant", active_mode: "evidence_discussion" };
}

function renderMessages() {
  const container = $("#messages-scroll");
  container.innerHTML = "";
  if (state.inIdea && state.ideaRecap &&
      (currentBranchData().messages || []).length) {
    const r = state.ideaRecap;
    state.ideaRecap = null;   // once per visit, not per message
    container.appendChild(el("div", "idea-recap-chip",
      "\u21a9 Picked up where you left off \u2014 " + r.turns +
      (r.turns === 1 ? " message" : " messages") + " with Sameer" +
      (r.changed ? " \u00b7 your page changed since his last read" : "")));
  }
  // the context card: PROOF Sameer has the page -- word count + a peek at
  // the actual material he is reading. Deterministic UI evidence.
  if (state.inIdea && state.currentIdea) {
    const content = (state.currentIdea.content || "").trim();
    if (content) {
      const words = content.split(/\s+/).length;
      const card = el("div", "idea-context-card");
      const head = el("div", "idea-context-head");
      const label = el("span", "idea-context-label",
        "\u{1F4C4} Sameer has your idea page in front of him \u2014 " + words +
        " word" + (words === 1 ? "" : "s") + " in context. No need to repeat it.");
      const toggle = el("button", "idea-context-toggle", "show");
      toggle.type = "button";
      const snap = el("div", "idea-context-snap");
      snap.hidden = true;
      snap.textContent = content;
      toggle.addEventListener("click", () => {
        snap.hidden = !snap.hidden;
        toggle.textContent = snap.hidden ? "show" : "hide";
      });
      head.appendChild(label);
      head.appendChild(toggle);
      card.appendChild(head);
      card.appendChild(snap);
      container.appendChild(card);
    }
  }
  const msgs = currentBranchData().messages || [];
  if (!msgs.length) {
    const hint = el("div", "chat-empty-hint");
    if (state.inIdea) {
      const hasPage = state.currentIdea && (state.currentIdea.content || "").trim();
      hint.innerHTML = hasPage
        ? "He\u2019s read every word of your page \u2014 start anywhere, or ask what snagged him. Flip to <em>Feedback</em> when you want the premise doctor to stress-test it."
        : "This is the idea desk \u2014 no pages yet, and that\u2019s the point. Talk the idea through with Sameer " +
          "(he probes before he suggests), then flip to <em>Feedback</em> to have the premise doctor " +
          "stress-test it. Save the premise card as it sharpens \u2014 it rides with every turn and " +
          "carries into the script when you upload the first pages.";
    } else {
      hint.innerHTML =
        "Ask about a theme, a character, or a specific scene (e.g. <em>\"what about Scene 12?\"</em>) \u2014 " +
        "or just say hello and we\'ll take it from there. Run analysis first if you want the conversation " +
        "grounded in a full report; it works fine without one too, just more loosely.";
    }
    container.appendChild(hint);
    return;
  }
  msgs.forEach((m, i) => container.appendChild(renderMessage(m, i)));
  container.scrollTop = container.scrollHeight;
  renderMessageRail();
}

// which branch a message truly belongs to: forks deep-copy the parent's
// history, so inherited messages (before the fork point) belong to the
// parent branch, only the post-fork ones are the fork's own
function messageOriginBranch(index) {
  const branch = state.branches[state.currentBranch] || {};
  const forkedAt = branch.forked_at_index;
  if (forkedAt != null && index < forkedAt && branch.parent_branch) {
    return branch.parent_branch;
  }
  return state.currentBranch;
}

// stable, distinct color per branch name — "main" is always the neutral
// brass so the base thread reads as the home ground, forks get spread hues
const FORK_HUE_PALETTE = [45, 160, 265, 340, 15, 200, 290, 120, 225, 350, 80, 310];
function branchHue(name) {
  if (name === "main") return 35;
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return FORK_HUE_PALETTE[h % FORK_HUE_PALETTE.length];
}

// Who is answering on the chat surface: the active branch persona, labeled
// with the writer-facing name. In the feedback room that's the consultant
// (Dr. Sushruta) even when the branch data still says writing_partner.
// Phase 7: an ADOPTED dock lens IS the partner — the Sushruta lens speaks
// as the consultant regardless of the room behind it.
function _assistantRoleLabel() {
  const labels = FALLBACK_PERSONA_LABELS;
  if (dockIsOpen() && dockLens === "sushruta") {
    return labels.script_consultant || "Dr. Sushruta";
  }
  if (state.view === "feedback" || document.body.dataset.room === "feedback") {
    // Phase 9: in the idea room the Feedback lens is the Premise Doctor
    // (concept validation), not the script-desk consultant.
    if (state.inIdea) return labels.premise_doctor || "Premise Doctor";
    return labels.script_consultant || "Dr. Sushruta";
  }
  const persona = (currentBranchData() || {}).active_persona || "writing_partner";
  return labels[persona] || "Sameer";
}

function renderMessage(m, index) {
  const wrap = el("div", "msg " + (m.role === "user" ? "user" : "assistant"));
  wrap.id = `msg-${index}`;
  const head = el("div", "msg-head");
  head.appendChild(el("div", "msg-role", m.role === "user" ? "You" : _assistantRoleLabel()));
  if (m.role === "assistant") {
    // "what does that mean?" -- ephemeral rendering in ANY supported register,
    // display-only. Hovering the globe floats the language menu; picking one
    // renders inline under the bubble and is never stored.
    const tr = el("button", "translate-btn", "\u{1F310}");
    tr.type = "button";
    tr.title = "Translate this reply \u2014 hover to pick a language";
    tr.setAttribute("aria-label", "Translate this reply");
    const LANG_TARGETS = [
      ["en", "English"],
      ["te", "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41"],
      ["hi", "\u0939\u093f\u0928\u094d\u0926\u0940"],
      ["teng", "Tenglish"],
      ["hing", "Hinglish"],
    ];
    let menu = null;
    let hideMenuTimer = null;
    const closeMenu = () => { if (menu) { menu.remove(); menu = null; } };
    const openMenu = () => {
      if (menu) return;
      clearTimeout(hideMenuTimer);
      menu = el("div", "lang-menu");
      for (const [code, label] of LANG_TARGETS) {
        const opt = el("button", "lang-menu-item", label);
        opt.type = "button";
        opt.addEventListener("click", async (e) => {
          e.stopPropagation();
          closeMenu();
          let existing = wrap.querySelector(".msg-translation");
          if (existing && existing.dataset.lang === code) { existing.hidden = !existing.hidden; return; }
          if (existing) existing.remove();
          tr.textContent = "\u2026";
          try {
            const res = await api(`${state.currentIdea
              ? `/ideas/${encodeURIComponent(state.currentIdea.id)}/chat/sessions/${state.currentIdeaSession}`
              : `/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${state.currentSession}`}/translate`,
              { method: "POST", body: JSON.stringify({ index, target_lang: code }) });
            const panel = el("div", "msg-translation");
            panel.dataset.lang = code;
            const lbl = LANG_TARGETS.find((l) => l[0] === code);
            panel.appendChild(el("div", "msg-translation-label", `\u{1F310} in ${lbl ? lbl[1] : code}:`));
            panel.appendChild(el("div", "msg-translation-text", res.translation || "(nothing to translate)"));
            wrap.appendChild(panel);
          } catch (err) {
            appendSystemNote("Translation unavailable: " + err.message, true);
          } finally {
            tr.textContent = "\u{1F310}";
          }
        });
        menu.appendChild(opt);
      }
      document.querySelectorAll(".lang-menu").forEach((m) => m.remove());
      document.body.appendChild(menu);
      // Anchor AT the globe: fixed coords from the button's live rect put the
      // menu right under the hovered icon -- flipped above and clamped when
      // the message sits near a viewport edge.
      const r = tr.getBoundingClientRect();
      menu.style.position = "fixed";
      // the chat drawer itself stacks at z-index 590 -- a body child must
      // out-stack it or the bubbles paint right over the menu
      menu.style.zIndex = "600";
      LANG_MENU_TRIGGER.set(menu, tr);
      const mw = menu.offsetWidth || 130, mh = menu.offsetHeight || 150;
      let left = Math.max(8, Math.min(r.right - mw, window.innerWidth - mw - 8));
      let top = r.bottom + 4;
      if (top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 4);
      menu.style.left = left + "px";
      menu.style.top = top + "px";
      wireLangMenuDismiss();
    };
    tr.addEventListener("mouseenter", openMenu);
    tr.addEventListener("mouseleave", () => {
      hideMenuTimer = setTimeout(() => { if (!menu || !menu.matches(":hover")) closeMenu(); }, 260);
    });
    tr.addEventListener("click", (e) => { e.stopPropagation(); if (menu) closeMenu(); else openMenu(); });
    head.appendChild(tr);
  }
  const origin = messageOriginBranch(index);
  const badge = el("span", "branch-badge", origin);
  badge.style.setProperty("--badge-h", branchHue(origin));
  badge.title = `This message belongs to the “${origin}” thread`;
  head.appendChild(badge);
  wrap.appendChild(head);
  const bubble = el("div", "msg-bubble");
  if (m.role === "user") {
    if (m.quote && m.quote.text) bubble.appendChild(renderQuoteBlock(m.quote));
    bubble.appendChild(el("div", "msg-text", m.content));
  } else {
    bubble.innerHTML = formatMessageContent(m.content);
  }
  wrap.appendChild(bubble);
  return wrap;
}

function appendSystemNote(text, isError) {
  const container = $("#messages-scroll");
  if (container.querySelector(".chat-empty-hint")) container.innerHTML = "";
  const note = el("div", "msg assistant");
  note.appendChild(el("div", "msg-role", "Studio"));
  const bubble = el("div", "msg-bubble", text);
  if (isError) bubble.style.color = "var(--danger)";
  note.appendChild(bubble);
  container.appendChild(note);
  container.scrollTop = container.scrollHeight;
  updateRailPositions(container);
}

// ---------- select-to-reply ----------
// Highlight any passage in the script → a small lamp-lit button floats up →
// the passage attaches as a quote card above the composer → Sameer answers
// grounded on that exact text. Quotes in the thread are clickable: they jump
// back to the scene and flash it.

let pendingQuote = null; // { scene_number: int|null, text: string } snapshot for the next send

function setPendingQuote(quote) {
  pendingQuote = quote;
  renderQuoteCard();
}

function clearPendingQuote() {
  pendingQuote = null;
  renderQuoteCard();
}

function renderQuoteCard() {
  const card = $("#quote-card");
  if (!card) return;
  if (!pendingQuote) { card.hidden = true; card.innerHTML = ""; return; }
  card.hidden = false;
  card.innerHTML = "";
  const meta = el("span", "quote-card-meta", pendingQuote.scene_number ? `Scene ${pendingQuote.scene_number}` : "The script");
  const txt = el("span", "quote-card-text", truncate(pendingQuote.text, 220));
  const x = el("button", "quote-card-x", "✕");
  x.type = "button";
  x.title = "Remove the quote";
  x.addEventListener("click", clearPendingQuote);
  card.append(meta, txt, x);
}

function renderQuoteBlock(quote) {
  const block = el("button", "quote-block");
  block.type = "button";
  block.title = "Jump back to this passage in the script";
  const meta = el("span", "quote-block-meta", quote.scene_number ? `Scene ${quote.scene_number}` : "The script");
  const txt = el("span", "quote-block-text", truncate(quote.text || "", 260));
  block.append(meta, txt);
  block.addEventListener("click", () => jumpToScene(quote.scene_number));
  return block;
}

// LOCATE only -- every caller (rail, ruler dots, scene index, the fix loop,
// the quote block) wants to jump to a scene, never to open a room. The old
// body also called openCowriteRoom(), which covered the loop's own bar.
function jumpToScene(sceneNumber) {
  if (sceneNumber == null) return;
  let page = document.getElementById(`scene-page-${sceneNumber}`);
  if (!page || page.classList.contains("hidden")) {
    // a search filter may have hidden the scene — clear it so the jump lands
    $("#script-search").value = "";
    renderManuscript(document.getElementById('manuscript-container'));
    page = document.getElementById(`scene-page-${sceneNumber}`);
  }
  if (!page) { showError(`Scene ${sceneNumber} isn't in the working draft right now.`); return; }
  page.scrollIntoView({ behavior: "smooth", block: "start" });
  page.classList.remove("flash");
  void page.offsetWidth; // restart the animation
  page.classList.add("flash");
  setTimeout(() => page.classList.remove("flash"), 1600);
}

// ---- anchored findings (IMPROVEMENT_AUDIT 1.1) ----
// Findings and the paper are joined two ways: a finding jumps to its exact
// line (🎯 Locate), and lines the analysis quoted carry a marker that opens
// the finding. Matching is whitespace/punctuation-insensitive so a quote
// whose text got re-wrapped still lands.

function normText(t) {
  return String(t || "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

function scrollToSceneInPlace(sceneNumber) {
  if (sceneNumber == null) return;
  // close full-screen tools so the shared script pane is visible, but don't
  // yank the writer out of the Feedback room while locating
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  const ws = document.querySelector(".workspace");
  if (ws) ws.style.display = "flex";
  let page = document.getElementById(`scene-page-${sceneNumber}`);
  if (!page || page.classList.contains("hidden")) {
    // a search filter may have hidden the scene — clear it so the jump lands
    $("#script-search").value = "";
    renderManuscript(document.getElementById('manuscript-container'));
    page = document.getElementById(`scene-page-${sceneNumber}`);
  }
  if (!page) { showError(`Scene ${sceneNumber} isn't in the working draft right now.`); return; }
  page.scrollIntoView({ behavior: "smooth", block: "start" });
  page.classList.remove("flash");
  void page.offsetWidth;
  page.classList.add("flash");
  setTimeout(() => page.classList.remove("flash"), 1600);
}

function findingTargetScene(f) {
  // the verification pass corrects the scene the quote actually lives in
  if (f.verification && f.verification.status === "verified" && f.verification.matched_scene) {
    return f.verification.matched_scene;
  }
  return (f.scene_refs && f.scene_refs[0]) || null;
}

function locateFinding(f, index) {
  const scene = findingTargetScene(f);
  if (scene == null) { showError("This finding isn't tied to a specific scene."); return; }
  // in the revision view, stay inside it — jump the revision column instead
  // of yanking the writer back to the workspace
  if (state.view === "revision") {
    jumpRevisionScene(scene);
    const quote = (f.evidence_quote || "").trim();
    if (quote) {
      const q = normText(quote);
      if (q.length >= 4) {
        setTimeout(() => {
          const box = $("#revision-script");
          if (!box) return;
          for (const line of box.querySelectorAll("[class^=el-]")) {
            const lt = normText(line.textContent);
            if (lt.length >= 4 && (lt.includes(q) || q.includes(lt.slice(0, 40)))) {
              line.classList.add("finding-highlight");
              line.scrollIntoView({ behavior: "smooth", block: "center" });
              setTimeout(() => line.classList.remove("finding-highlight"), 2600);
              return;
            }
          }
        }, 140);
      }
    }
    return;
  }
  scrollToSceneInPlace(scene);
  const quote = (f.evidence_quote || "").trim();
  if (!quote) return;
  setTimeout(() => {
    const page = document.getElementById(`scene-page-${scene}`);
    if (!page) return;
    const q = normText(quote);
    if (q.length < 4) return;
    for (const line of page.querySelectorAll("[class^=el-]")) {
      const lt = normText(line.textContent);
      if (lt.length >= 4 && (lt.includes(q) || q.includes(lt.slice(0, 40)))) {
        line.classList.add("finding-highlight");
        line.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => line.classList.remove("finding-highlight"), 2600);
        return;
      }
    }
  }, 140);
}

function openFindingCard(index) {
  const card = document.querySelector(`[data-finding-index="${index}"]`);
  if (card) {
    flashCard(card);
    return true;
  }
  return false;
}

function flashCard(card) {
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.remove("finding-flash");
  void card.offsetWidth;
  card.classList.add("finding-flash");
  setTimeout(() => card.classList.remove("finding-flash"), 1800);
}

function openNoteCard(noteId) {
  const card = document.querySelector(`[data-note-id="${noteId}"]`);
  if (card) { flashCard(card); return true; }
  return false;
}

function selectionInScriptPane() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
  const range = sel.getRangeAt(0);
  const node = range.commonAncestorContainer;
  const page = node.nodeType === 1
    ? node.closest(".scene-page")
    : (node.parentElement ? node.parentElement.closest(".scene-page") : null);
  const pane = getManuscriptContainer();
  if (!page || !pane || !pane.contains(node)) return null;
  const text = sel.toString().trim().replace(/\s+/g, " ");
  if (!text || text.length < 4) return null;
  return { scene_number: parseInt(page.dataset.sceneNumber, 10) || null, text };
}

function showQuoteFloat(quote) {
  const btn = $("#quote-float");
  const stashBtn = $("#stash-float");
  const noteBtn = $("#note-float");
  // Phase 13: the floats ride on the manuscript WORKSPACE now — the legacy
  // #script-pane home was display:none in script mode, so floats positioned
  // there never rendered. The workspace wraps the manuscript and is visible
  // whenever a project is open.
  const pane = $("#manuscript-workspace") || $("#script-pane");
  if (!btn || !pane) return;
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return;
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  const paneRect = pane.getBoundingClientRect();
  btn.dataset.sceneNumber = quote.scene_number == null ? "" : String(quote.scene_number);
  btn.dataset.text = quote.text;
  btn.hidden = false;
  btn.style.left = Math.max(8, Math.min(rect.right - paneRect.left + 10, paneRect.width - 150)) + "px";
  btn.style.top = Math.max(4, rect.bottom - paneRect.top + 8) + "px";
  let row = 1;
  if (stashBtn) {
    stashBtn.dataset.sceneNumber = quote.scene_number == null ? "" : String(quote.scene_number);
    stashBtn.dataset.text = quote.text;
    stashBtn.hidden = false;
    stashBtn.style.left = btn.style.left;
    stashBtn.style.top = Math.max(4, rect.bottom - paneRect.top + 8 + 30 * row) + "px";
    row += 1;
  }
  if (noteBtn) {
    noteBtn.dataset.sceneNumber = quote.scene_number == null ? "" : String(quote.scene_number);
    noteBtn.dataset.text = quote.text;
    noteBtn.hidden = false;
    noteBtn.style.left = btn.style.left;
    noteBtn.style.top = Math.max(4, rect.bottom - paneRect.top + 8 + 30 * row) + "px";
  }
}

function hideQuoteFloat() {
  const btn = $("#quote-float");
  if (btn) btn.hidden = true;
  const stashBtn = $("#stash-float");
  if (stashBtn) stashBtn.hidden = true;
  const noteBtn = $("#note-float");
  if (noteBtn) noteBtn.hidden = true;
  clearContextPlaceholder();
}

// ---- Context-aware placeholder: the composer speaks to the selection ----
let savedPlaceholder = null;

function setContextPlaceholder() {
  const input = $("#input");
  if (!input || input.value.trim()) return;
  if (savedPlaceholder == null) savedPlaceholder = input.placeholder;
  input.classList.add("context-quote");
  input.placeholder = "Reply to the highlighted passage…";
}

function clearContextPlaceholder() {
  const input = $("#input");
  if (!input) return;
  if (savedPlaceholder != null) {
    input.placeholder = savedPlaceholder;
    savedPlaceholder = null;
  }
  input.classList.remove("context-quote");
}

function handleScriptSelection() {
  const quote = selectionInScriptPane();
  if (quote) {
    showQuoteFloat(quote);
    setContextPlaceholder();
  } else {
    hideQuoteFloat();
  }
}

// ---------- conversation overview (hover rail) ----------
// A slim strip along the chat's right edge — small horizontal lines, one per
// message. Invisible until you hover the conversation; then a compact,
// scrollable overview appears (first message → latest) with short previews.
// Click a line or an overview row to jump straight to that message.

function renderMessageRail() {
  const wrapper = $("#messages");
  const scroller = $("#messages-scroll");
  if (!wrapper || !scroller) return;
  let rail = wrapper.querySelector("#msg-rail");
  let panel = wrapper.querySelector(".rail-panel");
  if (!rail) {
    rail = el("div", "msg-rail");
    rail.id = "msg-rail";
    wrapper.appendChild(rail);
    rail.appendChild(el("div", "rail-track"));
    panel = el("div", "rail-panel");
    panel.setAttribute("role", "listbox");
    panel.setAttribute("aria-label", "Conversation overview");
    wrapper.appendChild(panel);
    // floating zone: rail and panel keep the preview open together
    const refreshHover = () => panel.classList.toggle("visible",
      rail.matches(":hover") || panel.matches(":hover"));
    rail.addEventListener("mouseenter", refreshHover);
    rail.addEventListener("mouseleave", () => setTimeout(refreshHover, 90));
    panel.addEventListener("mouseenter", refreshHover);
    panel.addEventListener("mouseleave", () => setTimeout(refreshHover, 90));
  }
  const track = rail.querySelector(".rail-track");
  track.innerHTML = "";
  panel.innerHTML = "";
  const msgs = currentBranchData().messages || [];
  if (!msgs.length) { rail.classList.add("empty"); return; }
  rail.classList.remove("empty");

  // the strip shows only the WRITER's own messages — one horizontal line per
  // question/comment, first at the top, latest at the bottom. Sameer's replies
  // stay in the conversation thread; the rail is the writer's line of intent.
  // (i = the REAL message index, so a click still jumps to the right bubble.)
  const userMsgs = msgs.map((m, i) => ({ m, i })).filter(({ m }) => m.role === "user");

  userMsgs.forEach(({ m, i }, n) => {
    const line = el("button", "rail-line user");
    line.type = "button";
    line.dataset.index = i;
    line.title = `Your message ${n + 1}: ${truncate(m.content, 80)}`;
    line.setAttribute("aria-label", `Jump to your message ${n + 1}`);
    line.addEventListener("click", () => jumpToMessage(scroller, i));
    track.appendChild(line);
  });

  // hover preview: short version of the writer's messages, scrollable first → latest
  userMsgs.forEach(({ m, i }, n) => {
    const row = el("button", "rail-row user");
    row.type = "button";
    row.dataset.index = i;
    const num = el("span", "rail-row-num", String(n + 1));
    const txt = el("span", "rail-row-text", truncate(m.content, 64));
    row.append(num, txt);
    row.addEventListener("click", () => jumpToMessage(scroller, i));
    panel.appendChild(row);
  });

  updateRailCurrent(scroller);
}

function jumpToMessage(container, i) {
  const target = document.getElementById(`msg-${i}`);
  if (!target) return;
  container.scrollTop = Math.max(0, target.offsetTop - (container.clientHeight - target.clientHeight) / 2);
  updateRailCurrent(container);
  saveSession();
}

// the strip follows the conversation: the current message's line stays
// highlighted and inside the small visible window
function updateRailCurrent(container) {
  // the rail floats on the chat wrapper, not inside the scrolling content
  const rail = document.getElementById("msg-rail");
  if (!rail || rail.classList.contains("empty")) return;
  const lines = rail.querySelectorAll(".rail-line");
  if (!lines.length) return;
  const viewMid = container.scrollTop + container.clientHeight / 2;
  let current = null;
  let bestDist = Infinity;
  for (const line of lines) {
    const target = document.getElementById(`msg-${line.dataset.index}`);
    if (!target) continue;
    const mid = target.offsetTop + target.offsetHeight / 2;
    const dist = Math.abs(mid - viewMid);
    if (dist < bestDist) { bestDist = dist; current = line; }
  }
  for (const l of lines) l.classList.toggle("current", l === current);
  if (current) {
    const strip = rail;
    const top = current.offsetTop;
    const bottom = top + current.offsetHeight;
    if (top < strip.scrollTop || bottom > strip.scrollTop + strip.clientHeight) {
      strip.scrollTop = Math.max(0, top - strip.clientHeight / 2);
    }
  }
}

// kept as an alias so the chat-scroll handler stays wired
function updateRailPositions(container) {
  updateRailCurrent(container);
}

function renderBranches() {
  const wrap = $("#branch-switcher");
  if (!wrap) return;
  wrap.innerHTML = "";
  for (const name of Object.keys(state.branches)) {
    const b = state.branches[name] || {};
    const turns = (b.messages || []).length;
    const pill = el("button", "branch-pill" + (name === state.currentBranch ? " active" : ""), name);
    pill.type = "button";
    // Merge-peek: what a branch holds and where it came from, without switching
    // to it. `forked_at_index` is the turn the branch was copied at, so "N turns
    // since the fork" is read from the session rather than inferred.
    const peek = [`${turns} turn${turns === 1 ? "" : "s"}`];
    if (b.parent_branch) {
      const since = Math.max(0, turns - (b.forked_at_index || 0));
      peek.push(`forked from "${b.parent_branch}" at turn ${b.forked_at_index}`);
      if (since) peek.push(`${since} new turn${since === 1 ? "" : "s"} since`);
    }
    pill.title = (name === state.currentBranch ? "Current branch — " : `Switch to "${name}" — `)
      + peek.join(" · ");
    pill.addEventListener("click", () => switchBranch(name));
    wrap.appendChild(pill);
  }

  // The fork entry point. It was once removed "per the writer's preference",
  // which left the flagship branch system with no way to create a second branch —
  // a switcher with nothing to switch to, which is why M2 read it as unreachable.
  // Restored deliberately; the review doc records the reversal.
  //
  // Projects only: the idea room has no fork or switch route on the server, so a
  // button there would be the same class of lie this pass is fixing.
  if (state.currentProject && !state.premise) {
    // `.add` is the dashed-accent pill style that was already in the stylesheet,
    // orphaned when the fork button was removed. Reused rather than reinvented.
    const forkBtn = el("button", "branch-pill add", "＋ fork");
    forkBtn.type = "button";
    forkBtn.title = "Fork this conversation — try an alternative without losing this one";
    forkBtn.addEventListener("click", openForkModal);
    wrap.appendChild(forkBtn);
  }
}

function openForkModal() {
  const input = $("#fork-name-input");
  if (input) input.value = "";
  openModal("#fork-modal");
  if (input) input.focus();
}

async function switchBranch(name) {
  if (name === state.currentBranch) return;
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${state.currentSession}/switch`, {
      method: "POST", body: JSON.stringify({ name }),
    });
    state.currentBranch = name;
    resetChatHistory();
    renderMessages();
    renderBranches();
    populateSelectors();
  } catch (e) {
    showError("Couldn't switch branches: " + e.message);
  }
}

async function createFork() {
  const name = $("#fork-name-input").value.trim();
  if (!name) return;
  try {
    // A fresh project has NO session until the first message (see the lazy
    // comment in openProject), but the fork button renders on currentProject
    // alone -- so clicking it POSTed to /chat/sessions/null/fork and 404'd
    // ("Session or project not found"): an offered control that could not
    // succeed. Establish the session first; ensureSession is idempotent and is
    // the same lazy path the first message uses.
    await ensureSession();
    await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${state.currentSession}/fork`, {
      method: "POST", body: JSON.stringify({ name }),
    });
    closeModal("#fork-modal");
    $("#fork-name-input").value = "";
    await loadSession(state.currentSession);
  } catch (e) {
    showError("Couldn't create fork: " + e.message);
  }
}

function populateSelectors() {
  const b = currentBranchData();
  // Prefer the server-provided lists; fall back to the built-ins only if the
  // server didn't supply them (co-writer missing or an old config response).
  const personas = (state.config && state.config.personas && state.config.personas.length)
    ? state.config.personas : FALLBACK_PERSONAS;
  const modes = (state.config && state.config.modes && state.config.modes.length)
    ? state.config.modes : FALLBACK_MODES;
  const personaLabels = { ...FALLBACK_PERSONA_LABELS };
  const modeLabels = { ...FALLBACK_MODE_LABELS };

  const pSel = $("#persona-select");
  pSel.innerHTML = "";
  personas.forEach((p) => pSel.appendChild(new Option(personaLabels[p] || p, p, false, p === b.active_persona)));

  const mSel = $("#mode-select");
  mSel.innerHTML = "";
  modes.forEach((m) => mSel.appendChild(new Option(modeLabels[m] || m, m, false, m === b.active_mode)));
}

async function updateSettings() {
  if (!state.currentSession) return;
  const persona = $("#persona-select").value;
  const mode = $("#mode-select").value;
  await _setPersonaMode(persona, mode);
}

async function resetToPartner() {
  // "back to Sameer": reset the current branch to the writing-partner default
  await _setPersonaMode("writing_partner", "peer");
  renderMessages();
}

// ---- Sameer's notes on you (writer relationship memory) ----
async function loadSamNotes() {
  const data = await api("/writer-memory");
  renderSamNotes(data);
}
function renderSamNotes(data) {
  const dims = $("#sam-notes-dimensions"), obsList = $("#sam-notes-observations"), empty = $("#sam-notes-empty");
  dims.innerHTML = "";
  obsList.innerHTML = "";
  // The chips come from the server's suppression-aware gate (the same set
  // that steers Sameer), so a forgotten belief stops showing here too.
  const gated = Object.entries(data.gated || {});
  gated.forEach(([name, entry]) => {
    const chip = document.createElement("span");
    chip.className = "sam-notes-chip";
    chip.textContent = `${name.replace(/_/g, " ")}: ${entry.value} (${Math.round(entry.confidence * 100)}%)`;
    dims.appendChild(chip);
  });
  const observations = (data.profile && data.profile.observations || []).filter((o) => !o.suppressed);
  observations.forEach((o) => {
    const li = document.createElement("li");
    li.className = "sam-notes-obs";
    const text = document.createElement("span");
    text.textContent = o.text;
    const forget = document.createElement("button");
    forget.className = "btn-secondary btn-small";
    forget.textContent = "forget this";
    forget.addEventListener("click", async () => {
      await api(`/writer-memory/observations/${encodeURIComponent(o.id)}/suppress`, { method: "POST" });
      loadSamNotes();
    });
    li.append(text, forget);
    obsList.appendChild(li);
  });
  empty.style.display = (!gated.length && !observations.length) ? "" : "none";
}
async function openSamNotes() {
  openModal("#sam-notes-modal");
  await loadSamNotes();
}
function closeSamNotes() {
  closeModal("#sam-notes-modal");
}

async function _setPersonaMode(persona, mode) {
  if (!state.currentSession) return;
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${state.currentSession}/settings`, {
      method: "POST", body: JSON.stringify({ persona, mode }),
    });
    if (state.branches[state.currentBranch]) {
      state.branches[state.currentBranch].active_persona = persona;
      state.branches[state.currentBranch].active_mode = mode;
    }
  } catch (e) {
    showError("Couldn't update persona/mode: " + e.message);
  }
}

async function sendMessage() {
  const input = $("#input");
  const text = input.value.trim();
  if (!text) return;

  const quote = pendingQuote;      // snapshot the selected passage: sent once
  input.value = "";
  input.style.height = "auto";
  resetChatHistory();
  clearPendingQuote();
  $("#send-btn").disabled = true;

  const container = $("#messages-scroll");
  if (container.querySelector(".chat-empty-hint")) container.innerHTML = "";
  const optimisticIndex = (currentBranchData().messages || []).length;
  const userMsg = renderMessage({ role: "user", content: text, quote }, optimisticIndex);
  container.appendChild(userMsg);
  const workingLabel = state.inIdea ? "Thinking it through" : "Reading the pages";

  // One turn may be attempted more than once: when the generation watchdog
  // fires (the model was still working at the per-turn cap), the writer can
  // choose to keep waiting — which re-POSTs the same turn. That's safe
  // because the backend appends the user message only after the model call
  // succeeds, so a timed-out turn was never stored.
  const finishTurn = () => {
    $("#send-btn").disabled = false;
    input.focus();
  };
  const attemptTurn = async () => {
    // pending/pendingBubble/stopTicker live at function scope (not inside
    // the try) so the watchdog branch in catch can reach them.
    let pending = null, pendingBubble = null, stopTicker = null;
    try {
      const sessionId = await ensureSession();
      // ensureSession may re-render (a brand-new session's loadSession wipes
      // the optimistic DOM) — re-attach the user message if it was detached,
      // and build the pending bubble fresh so it's never orphaned.
      if (!container.contains(userMsg)) {
        container.appendChild(userMsg);
        container.scrollTop = container.scrollHeight;
      }
      pending = el("div", "msg assistant msg-pending");
      pending.appendChild(el("div", "msg-role", "Studio"));
      pendingBubble = el("div", "msg-bubble");
      pendingBubble.appendChild(document.createTextNode(workingLabel));
      const dots = el("span", "typing-dots");
      dots.appendChild(el("i")); dots.appendChild(el("i")); dots.appendChild(el("i"));
      pendingBubble.appendChild(dots);
      pendingBubble.appendChild(el("span", "elapsed"));
      pending.appendChild(pendingBubble);
      container.appendChild(pending);
      container.scrollTop = container.scrollHeight;
      stopTicker = startElapsedTicker(pendingBubble, workingLabel);
      const base = state.inIdea
        ? `/ideas/${encodeURIComponent(state.currentIdea.id)}`
        : `/projects/${encodeURIComponent(state.currentProject)}`;
      const res = await streamChatTurn(`${base}/chat/sessions/${sessionId}`, text, quote, pendingBubble, container);
      stopTicker();
      state.branches[state.currentBranch] = { ...currentBranchData(), messages: res.messages };
      renderMessages();
      refreshMetrics();  // reply timing landed — update the loop readout
      finishTurn();
    } catch (e) {
      if (e.stillWorking && pendingBubble) {
        // Watchdog: the turn hit its cap mid-generation. Offer a choice
        // instead of failing the turn. IMPORTANT: keep the .elapsed span
        // alive — the ticker updates ONLY that span, and if it's gone the
        // ticker's fallback overwrites the whole bubble, erasing this dialog
        // one second after it appears. So drop just the typing dots.
        const dotsEl = pendingBubble.querySelector(".typing-dots");
        if (dotsEl) dotsEl.remove();
        const ask = el("span", "wd-ask", workingLabel + " — still working. Keep waiting?");
        pendingBubble.appendChild(ask);
        const keepBtn = el("button", "wd-btn wd-keep", "Keep waiting");
        const stopBtn = el("button", "wd-btn wd-stop", "Give up");
        pendingBubble.appendChild(keepBtn);
        pendingBubble.appendChild(stopBtn);
        keepBtn.addEventListener("click", () => {
          attemptTurn();  // same text+quote — safe to resend
        });
        stopBtn.addEventListener("click", () => {
          stopTicker();
          pending.classList.remove("msg-pending");
          pendingBubble.textContent = "Stopped waiting — Sam was still working when the time cap hit. Send the message again to retry.";
          pendingBubble.style.color = "var(--danger)";
          finishTurn();
        });
      } else if (pendingBubble) {
        stopTicker();
        pendingBubble.textContent = "Couldn't get a reply: " + e.message;
        pending.classList.remove("msg-pending");
        pendingBubble.style.color = "var(--danger)";
        showError("Chat message failed: " + e.message);
        finishTurn();
      } else {
        // ensureSession itself failed before the bubble existed
        showError("Couldn't start the conversation: " + e.message);
        finishTurn();
      }
    }
  };
  await attemptTurn();
}

// ---- idea-room explore paths (Sudowrite-style guided spins) ----
// One tap sends a framed prompt to whichever lens is active (Sameer explores,
// the premise doctor validates). The card context rides every turn already.

function sendPrefilled(text) {
  const input = $("#input");
  if (!input) return;
  input.value = text;
  sendMessage();
}

// Single source of truth for the explore-path chips — rendered into every
// .explore-chips container at init so the premise pane and the idea drawer
// can never drift apart again (they had quietly diverged, 6 vs 5).
const EXPLORE_CHIPS = [
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><path d="M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/></svg>', label: "What if…?", prompt: "Give me 3 unexpected 'what if' twists on this idea — each one pushing it in a different genre direction. Keep each to a sentence." },
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><path d="M12 20s-7-4.5-9-9c-1.5-3.5 1-7 4.5-7C9.5 4 12 6 12 6s2.5-2 4.5-2c3.5 0 6 3.5 4.5 7-2 4.5-9 9-9 9z"/></svg>', label: "Who's the heart?", prompt: "Who is this really about? Name the protagonist, what they want more than anything, and what they're afraid of losing. Then tell me why I should care in one line." },
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><path d="M12 3c3 4 5.5 6 5.5 9.5A5.5 5.5 0 1 1 6.5 12.5C6.5 10 8 8.5 9 7c.3 1.6 1.6 2.6 1.6 2.6S9.5 5.5 12 3z"/></svg>', label: "Where's the heat?", prompt: "Where is the conflict hiding in this idea? Show me 3 pressure points that could drive whole scenes, and which one is the strongest." },
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><circle cx="12" cy="12" r="9"/><path d="M10 8.5l5.5 3.5-5.5 3.5z"/></svg>', label: "Cold open", prompt: "How could this open on screen in the first 60 seconds? Give me 2-3 cold open options that hook without exposition." },
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><path d="M13 2L4 14h6l-1 8 9-12h-6z"/></svg>', label: "Push it further", prompt: "What's the riskiest, boldest version of this idea? Push past the safe version and show me what it becomes." },
  { icon: '<svg viewBox="0 0 24 24" class="chip-ic"><path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20c0-3 3-5 6-5s6 2 6 5M14 20c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4"/></svg>', label: "Who's it for?", prompt: "Who is this story for, and what would make them lean in? Give me the genre positioning and the audience hook." },
];

function renderExploreChips() {
  document.querySelectorAll(".explore-chips").forEach((wrap) => {
    wrap.innerHTML = "";
    for (const chip of EXPLORE_CHIPS) {
      const b = el("button", "explore-chip");
      b.type = "button";
      b.dataset.prompt = chip.prompt;
      b.innerHTML = `${chip.icon}<span class="lbl">${chip.label}</span>`;
      wrap.appendChild(b);
    }
  });
}

function wireExploreChips() {
  const wire = (wrap) => {
    if (!wrap) return;
    wrap.querySelectorAll(".explore-chip").forEach((chip) => {
      chip.addEventListener("click", async () => {
        const prompt = (chip.dataset.prompt || "").trim();
        if (!prompt) return;
        if (state.inIdea && state.currentIdea) {
          // idea phase: chips live in the Sameer chat — summon it, then send
          await summonIdeaSam();
          sendPrefilled(prompt);
          return;
        }
        if (!state.currentProject) {
          showError("Open an idea first — the explore paths need a page to work with.");
          return;
        }
        sendPrefilled(prompt);
      });
    });
  };
  wire(document.getElementById("premise-explore"));
  wire(document.getElementById("idea-explore"));
}

// ---------- chat input history (↑/↓ like Claude / the shell) ----------
// ArrowUp at the top of the composer opens a Claude-style list of the
// messages YOU sent in this branch. Walk it with ↑/↓, hover to peek,
// click to reuse-and-edit; Escape closes and restores your draft.

let chatHistoryIndex = -1;   // -1 = not browsing history
let chatHistoryDraft = null; // the draft restored when browsing is cancelled

function chatUserHistory() {
  return (currentBranchData().messages || [])
    .filter((m) => m.role === "user")
    .map((m) => m.content)
    .filter((t) => t && t.trim());
}

function resetChatHistory() {
  chatHistoryIndex = -1;
  chatHistoryDraft = null;
  const pop = $("#history-pop");
  if (pop) pop.hidden = true;
}

function applyChatHistory(input, text) {
  input.value = text;
  input.style.height = "auto";
  autoResizeTextarea();
  input.setSelectionRange(input.value.length, input.value.length);
}

function renderHistoryPop() {
  const pop = $("#history-pop");
  const history = chatUserHistory();
  if (!history.length || chatHistoryIndex === -1) { pop.hidden = true; return; }
  pop.innerHTML = "";
  history.forEach((text, i) => {
    const item = el("button", "history-item" + (i === chatHistoryIndex ? " current" : ""));
    item.type = "button";
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", i === chatHistoryIndex ? "true" : "false");
    const num = el("span", "history-num", String(history.length - i).padStart(2, "0"));
    const body = el("span", "history-text", truncate(text, 90));
    item.appendChild(num);
    item.appendChild(body);
    item.title = text;
    // mousedown-preventDefault keeps focus in the textarea so blur doesn't
    // cancel the browse before the click lands
    item.addEventListener("mousedown", (ev) => ev.preventDefault());
    item.addEventListener("click", () => {
      applyChatHistory($("#input"), history[i]);
      resetChatHistory();
      $("#input").focus();
    });
    pop.appendChild(item);
  });
  pop.hidden = false;
  const cur = pop.querySelector(".current");
  if (cur) cur.scrollIntoView({ block: "nearest" });
}

function chatHistoryArrowUp(e) {
  const input = $("#input");
  const history = chatUserHistory();
  if (!history.length) return false;
  // entering history requires the caret at the top of the field (otherwise
  // ArrowUp is a normal caret move); once browsing, ↑ always walks older
  if (chatHistoryIndex === -1 && input.selectionStart !== 0) return false;
  e.preventDefault();
  if (chatHistoryIndex === -1) {
    chatHistoryDraft = input.value;
    chatHistoryIndex = history.length - 1;
  } else if (chatHistoryIndex > 0) {
    chatHistoryIndex--;
  }
  applyChatHistory(input, history[chatHistoryIndex]);
  renderHistoryPop();
  return true;
}

function chatHistoryCancel() {
  // exit browsing: read the draft BEFORE reset wipes it, then restore it
  const draft = chatHistoryDraft || "";
  resetChatHistory();
  applyChatHistory($("#input"), draft);
}

function chatHistoryArrowDown(e) {
  const input = $("#input");
  const history = chatUserHistory();
  if (chatHistoryIndex === -1 || !history.length) return false;
  e.preventDefault();
  if (chatHistoryIndex < history.length - 1) {
    chatHistoryIndex++;
    applyChatHistory(input, history[chatHistoryIndex]);
    renderHistoryPop();
  } else {
    // walked past the newest — back to the draft that was being written
    chatHistoryCancel();
  }
  return true;
}

function chatHistoryEscape(e) {
  if (chatHistoryIndex === -1) return false;
  e.preventDefault();
  chatHistoryCancel();
  $("#input").focus();
  return true;
}

// ---------- script & notes view (revision loop) ----------

const SEVERITY_CLASS = { high: "", medium: " sev-medium", low: " sev-low" };
const CATEGORY_LABELS = {
  theme: "Theme", character: "Character", structure: "Structure", dialogue: "Dialogue",
  scene_function: "Scene function", plot_thread: "Plot economy", genre: "Genre",
  voice: "Voice", subtext: "Subtext", continuity: "Continuity",
};

async function loadScriptData() {
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  const [script, edits, drafts, notes] = await Promise.all([
    api(`${base}/script`),
    api(`${base}/edits`),
    api(`${base}/drafts`),
    api(`${base}/notes`),
  ]);
  state.script = script;
  state.editsData = edits;
  state.drafts = drafts;
  state.notes = (notes && notes.notes) || [];
  let findings = [];
  let report = null;
  // Skip the report fetch when the manifest says analysis hasn't completed —
  // the endpoint would 400 and every fresh project would land a console error
  // for a perfectly normal "no analysis yet" state.
  const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
  const analyzeState = projSummary && projSummary.stages && projSummary.stages.analyze;
  if (!projSummary || analyzeState === "complete" || analyzeState === "failed") {
    try {
      report = await api(`${base}/report`);
      findings = report.findings || [];
    } catch (_) { /* failed analysis may still have no report file — script-only mode */ }
  }
  state.findings = findings;
  state.report = report;
  state.reportStats = (report && report.stats) || null;
  // content-hash identity: the client computes the SAME id the server
  // observes (revision.py compute_finding_id). Status reads prefer id —
  // the writer's marks survive re-scoring and scene insert-shift — and
  // fall back to legacy index entries for old projects.
  state.findingIds = findings.map((f) => computeFindingId(f));
  const statusById = {};
  for (const s of (state.editsData.findings_status && state.editsData.findings_status.findings) || []) {
    if (s.finding_id) statusById[s.finding_id] = s.status;
    statusById[String(s.index)] = s.status;
  }
  state.findingStatus = statusById;
  // writer intent (R2-b/R3) + last-pass scorekeeping (R4) ride /edits
  state.findingMarks = (edits && edits.finding_intents) || {};
  const lp = (edits && edits.last_pass) || null;
  const arrived = !!(lp && lp.computed_at && state.lastPassKey !== lp.computed_at);
  state.lastPass = lp;
  if (lp && lp.computed_at) state.lastPassKey = lp.computed_at;
  if (lp && lp.ghosted_marks) state.ghostedIds = new Set(lp.ghosted_marks.map((g) => g.finding_id));
  try {
    state.fixQueue = await api(`${base}/fixqueue`);
  } catch (_) {
    state.fixQueue = { items: [], acts: [] };
  }
  if (arrived && findings.length) scheduleArrivalPeek();
  renderDraftBar();
  await renderDiffBanner();
  // The desk status line reads state.findings, which this function just set.
  // At project-open the toolbar refresh runs BEFORE this async load resolves, so
  // without this re-render a 36-finding desk read "a clean bill" forever (audit
  // gap C). Idempotent -- state-driven, so calling it twice is safe.
  refreshDeskToolbar();
}

// ---- fix queue / craft panels ----
// append-or-push: the panels render into the script pane's craft shelf (an
// array) or directly into the Feedback room's Fix Queue tab (a real node).
function addPanel(container, panel) {
  if (container && container.push) container.push(panel);
  else if (container) container.appendChild(panel);
}

function renderFixQueuePanel(container) {
  const items = (state.fixQueue && state.fixQueue.items) || [];
  // the ONE filter applies to the queue too (R5-b completed): rows whose
  // severity/category the chips hide stay in the report but out of the
  // writer's to-do view — page, board and queue cannot disagree (N3).
  // Dismissed rows keep their separate toggle; addressed ride as before.
  const inFilter = inFindingFilter; // ONE predicate: the queue cannot drift from the strip
  const shown = items.filter((i) => state.fixQueueShowDismissed && i.dismissed ? true : inFilter(i) && !i.dismissed);
  if (!shown.length) {
    if (!items.length && !state.fixQueueShowDismissed) return;
    const panel = el("div", "craft-panel fix-queue");
    const head = el("div", "craft-panel-head");
    head.appendChild(el("span", "craft-panel-title", "Fix queue — 0 shown / " + (state.fixQueue && (state.fixQueue.total_count != null ? state.fixQueue.total_count : items.length) || items.length) + " total"));
    panel.appendChild(head);
    const hint = el("p", "fix-row-why", "No rows match the current filter — toggle a severity or category chip on the Evidence board to widen the to-do.");
    panel.appendChild(hint);
    addPanel(container, panel); // container may be an array (craft shelf) or a node
    return;
  }
  const total = (state.fixQueue && (state.fixQueue.total_count != null ? state.fixQueue.total_count : items.length)) || items.length;
  const openShown = shown.filter((i) => i.status !== "addressed").length;

  const panel = el("div", "craft-panel fix-queue");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", `Fix queue — ${openShown} open / ${shown.length} shown / ${total} total`));
  // dawn meter: night → dawn as findings get resolved (the room literally warms)
  const dm = el("div", "dawn-meter");
  dm.title = "The dawn meter — the share of findings you've resolved. The room warms as it climbs.";
  dm.innerHTML = '<span class="dawn-cap">night</span><span class="dawn-track"><span class="dawn-fill"></span></span><span class="dawn-pct">0%</span>';
  head.appendChild(dm);
  // triage: dismissed findings stay in the report but out of the writer's way
  const dismissedCount = (state.fixQueue && state.fixQueue.dismissed_count) || 0;
  if (dismissedCount) {
    const show = !!state.fixQueueShowDismissed;
    const toggleBtn = el("button", "fq-toggle-dismissed", show ? `Hide dismissed (${dismissedCount})` : `Show dismissed (${dismissedCount})`);
    toggleBtn.type = "button";
    toggleBtn.addEventListener("click", async () => {
      state.fixQueueShowDismissed = !show;
      await reloadFixQueue();
      if (state.view === "feedback") loadFeedbackPanels();
      else     renderManuscript(document.getElementById('manuscript-container'));
    });
    head.appendChild(toggleBtn);
  }
  panel.appendChild(head);

  for (const item of shown) {
    const row = el("div", "fix-row" + (item.status === "addressed" ? " done" : "") + (item.dismissed ? " dismissed" : ""));
    row.dataset.findex = String(item.index);
    const sev = el("span", "sev-badge sev-" + (item.severity || "low"), (item.severity || "low").toUpperCase());
    const act = el("span", "act-chip", item.act_name || "Script-level");
    const sceneLabel = item.scene_heading ? `Scene ${(item.scene_refs || [])[0]} — ${item.scene_heading}` : "General";
    const body = el("div", "fix-row-body");
    const issue = el("div", "fix-row-issue", `${sceneLabel}: ${item.issue}`);
    if (item.why_it_matters) issue.appendChild(el("div", "fix-row-why", item.why_it_matters));
    body.appendChild(issue);
    const actions = el("div", "fix-row-actions");
    const locateBtn = el("button", "", "🎯 Locate");
    locateBtn.type = "button";
    locateBtn.title = "Jump to the exact line in the script";
    locateBtn.addEventListener("click", () => locateFinding(item, item.index));
    const rewriteBtn = el("button", "", "Rewrite");
    rewriteBtn.type = "button";
    rewriteBtn.addEventListener("click", () => {
      const refs = item.scene_refs || [];
      openRewriteModal(refs[0] || 1, item, item.index);
    });
    const discussBtn = el("button", "", "Discuss");
    discussBtn.type = "button";
    discussBtn.addEventListener("click", () => discussFinding(item, item.index));
    const triageBtn = el("button", item.dismissed ? "fq-undismiss" : "fq-dismiss", item.dismissed ? "Restore" : "Dismiss");
    triageBtn.type = "button";
    triageBtn.title = item.dismissed
      ? "Put this finding back in the queue"
      : "I've read it — choosing to live with this one (hidden from the queue, kept in the report)";
    triageBtn.addEventListener("click", async () => {
      try {
        const verb = item.dismissed ? "undismiss" : "dismiss";
        await api(`/projects/${encodeURIComponent(state.currentProject)}/findings/${item.index}/${verb}`,
          { method: "POST", body: JSON.stringify({ issue: item.issue || "" }) });
        await reloadFixQueue();
        if (state.view === "feedback") loadFeedbackPanels();
        else     renderManuscript(document.getElementById('manuscript-container'));
      } catch (err) { showError("Triage failed: " + err.message); }
    });
    actions.appendChild(locateBtn);
    actions.appendChild(rewriteBtn);
    actions.appendChild(discussBtn);
    actions.appendChild(triageBtn);
    body.appendChild(actions);
    row.appendChild(sev);
    row.appendChild(act);
    row.appendChild(body);
    panel.appendChild(row);
  }
  addPanel(container, panel);
  updateDawnMeter();
}

function renderPacingPanel(container) {
  const pacing = state.reportStats && state.reportStats.pacing;
  if (!pacing || !pacing.segments || !pacing.segments.length) return;
  const segs = pacing.segments;
  const maxW = Math.max(1, ...segs.map((s) => s.dialogue_words + s.action_words));
  const W = 720, H = 150, pad = 26;
  const barW = (W - pad - 10) / segs.length;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pacing chart: dialogue vs action words per page segment" class="pacing-svg">`;
  segs.forEach((s, i) => {
    const x = pad + i * barW;
    const dH = Math.max(1, (s.dialogue_words / maxW) * (H - 44));
    const aH = Math.max(1, (s.action_words / maxW) * (H - 44));
    svg += `<rect x="${x}" y="${H - 34 - dH}" width="${barW - 3}" height="${dH}" class="bar-dialogue"/>`;
    svg += `<rect x="${x}" y="${H - 34 - dH - aH}" width="${barW - 3}" height="${aH}" class="bar-action"/>`;
    if (i % 2 === 0 || segs.length < 8) svg += `<text x="${x + barW / 2}" y="${H - 14}" class="bar-label">${s.page_start}</text>`;
  });
  svg += `</svg>`;
  const panel = el("div", "craft-panel");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", `Pacing — ${pacing.total_pages} pages`));
  const legend = el("span", "pacing-legend");
  legend.appendChild(el("span", "legend-dialogue", "dialogue"));
  legend.appendChild(el("span", "legend-action", "action"));
  head.appendChild(legend);
  panel.appendChild(head);
  const body = el("div", "pacing-body");
  body.innerHTML = svg;
  panel.appendChild(body);
  addPanel(container, panel);
}

function renderCharacterPanel(container) {
  const arcs = state.reportStats && state.reportStats.character_arc;
  if (!arcs || !arcs.length) return;
  const totalScenes = state.script ? state.script.scene_count : 1;
  const panel = el("div", "craft-panel");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", "Characters"));
  panel.appendChild(head);
  for (const c of arcs.slice(0, 10)) {
    const row = el("div", "char-row");
    const name = el("span", "char-name", c.character);
    const track = el("span", "char-track");
    const fill = el("span", "char-fill");
    fill.style.width = `${Math.round((c.scene_count / totalScenes) * 100)}%`;
    track.appendChild(fill);
    const meta = el("span", "char-meta", `scenes ${c.first_scene}–${c.last_scene} · ${c.scene_count}/${totalScenes} · ${c.dialogue_lines} lines`);
    row.appendChild(name);
    row.appendChild(track);
    row.appendChild(meta);
    panel.appendChild(row);
  }
  addPanel(container, panel);
}

// ---- character dials: trait scores per main character ----
// The dials used to render ONLY into #struct-rail (style.css declares the rail
// display:none -- dead chrome) and into the since-deleted #feedback-view clone, so on the live
// desk 15 dial rows existed with none of them reachable (audit gap
// B/character_dials). ONE renderer now feeds three reachable surfaces: the page-one
// craft shelf, the dock Evidence lens and the feedback report.
function renderCharacterDialsPanel(container) {
  const dials = state.report && state.report.character_dials;
  if (!dials || !dials.length) return;
  const card = el("div", "craft-panel");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", "Character dials — how each main character reads"));
  card.appendChild(head);
  for (const d of dials) {
    const block = el("div", "dial-block");
    block.appendChild(el("div", "dial-char-name", d.character));
    for (const t of (d.traits || [])) {
      const row = el("div", "dial-row");
      row.appendChild(el("span", "dial-label", t.trait));
      const trackEl = el("span", "dial-track");
      const fill = el("span", "dial-fill");
      fill.style.width = `${t.score * 10}%`;
      trackEl.appendChild(fill);
      row.appendChild(trackEl);
      row.appendChild(el("span", "dial-score", String(t.score)));
      if (t.note) row.title = t.note;
      block.appendChild(row);
    }
    card.appendChild(block);
  }
  addPanel(container, card);
}

// ---- writer's mirror: logline test + character-perception read ----
// Tier-1 additions: how the premise lands in one sentence, and how each
// character actually comes across to a stranger vs. the apparent intent.

const LOGLINE_SIGNAL_CLASS = { strong: " sig-strong", workable: " sig-workable", muddled: " sig-muddled" };

function renderWriterMirrorPanel(container) {
  const lt = state.report && state.report.logline_test;
  const reads = (state.report && state.report.character_reads) || [];
  if (!lt && !reads.length) return;

  const panel = el("div", "craft-panel writer-mirror");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", "Writer's Mirror"));
  panel.appendChild(head);

  if (lt) {
    const block = el("div", "wm-block");
    const row = el("div", "wm-logline-row");
    const signal = el("span", "wm-signal" + (LOGLINE_SIGNAL_CLASS[lt.signal] || ""), (lt.signal || "?").toUpperCase());
    row.appendChild(signal);
    row.appendChild(el("span", "wm-logline", `“${lt.logline || ""}”`));
    block.appendChild(row);
    const rows = [
      ["What works", lt.what_works],
      ["What muddles it", lt.what_muddles],
      ["Missing from a clean logline", lt.missing],
      ["Tightened (premise intact)", lt.tightened],
    ];
    for (const [label, text] of rows) {
      if (!text) continue;
      const r = el("div", "wm-detail");
      r.appendChild(el("span", "wm-label", label));
      r.appendChild(el("span", "wm-text", text));
      block.appendChild(r);
    }
    panel.appendChild(block);
  }

  if (reads.length) {
    const block = el("div", "wm-block");
    const intro = el("p", "wm-intro",
      "An impartial first-time reader's impression — what each character actually comes across as, vs. what the script appears to intend.");
    block.appendChild(intro);
    for (const r of reads) {
      const card = el("div", "wm-char");
      card.appendChild(el("div", "wm-char-name", r.character));
      const lines = [
        ["Reads as", r.how_reads],
        ["Apparent intent", r.apparent_intent],
        ["The gap", r.gap],
      ];
      for (const [label, text] of lines) {
        if (!text) continue;
        const d = el("div", "wm-detail");
        d.appendChild(el("span", "wm-label", label));
        d.appendChild(el("span", "wm-text", text));
        card.appendChild(d);
      }
      const quote = r.evidence_quote;
      const verified = r.verification && r.verification.status === "verified";
      if (quote) {
        const d = el("div", "wm-detail");
        d.appendChild(el("span", "wm-label", verified ? "Evidence" : "Evidence (unverified)"));
        d.appendChild(el("span", "wm-text wm-quote", `“${quote}”`));
        card.appendChild(d);
      }
      block.appendChild(card);
    }
    panel.appendChild(block);
  }

  addPanel(container, panel);
}

// ---- Craft shelf: a collapsed-by-default lid over the analysis panels ----
// The four panels (fix queue · pacing · characters · writer's mirror) used to
// stack ABOVE the first scene — a 9,000px wall of analysis between the writer
// and page one. Now they live behind a slim header: the manuscript owns the
// top of the page, and one click opens the whole shelf. The choice persists,
// but the default is always closed. (The script-level notes chips stay out —
// they're small, and they include the writer's own pinned notes.)
let craftOpen = loadPrefs().craft_open === true;

function buildCraftShelf(panels) {
  const wrap = el("div", "craft-shelf" + (craftOpen ? " open" : ""));
  const head = el("button", "craft-shelf-head");
  head.type = "button";
  head.setAttribute("aria-expanded", craftOpen ? "true" : "false");
  head.appendChild(el("span", "craft-shelf-title", "Craft"));
  const bits = [];
  const items = (state.fixQueue && state.fixQueue.items) || [];
  const open = items.filter((i) => i.status !== "addressed");
  if (items.length) bits.push(`${open.length} open · ${items.length} total`);
  const pacing = state.reportStats && state.reportStats.pacing;
  if (pacing && pacing.segments && pacing.segments.length) bits.push(`${pacing.total_pages}-page pacing`);
  if (state.report && (state.report.logline_test || (state.report.character_reads || []).length)) bits.push("mirror");
  head.appendChild(el("span", "craft-shelf-summary", bits.join(" · ")));
  head.appendChild(el("span", "craft-shelf-caret", craftOpen ? "▾" : "▸"));
  head.addEventListener("click", toggleCraftShelf);
  wrap.appendChild(head);
  const body = el("div", "craft-shelf-body");
  for (const p of panels) body.appendChild(p);
  wrap.appendChild(body);
  return wrap;
}

// flip the shelf from anywhere — the header click, the `a` shortcut, Esc
function toggleCraftShelf() {
  craftOpen = !craftOpen;
  savePrefs({ craft_open: craftOpen });
  const shelf = document.querySelector(".craft-shelf");
  if (!shelf) return;
  shelf.classList.toggle("open", craftOpen);
  const head = shelf.querySelector(".craft-shelf-head");
  if (head) {
    head.setAttribute("aria-expanded", craftOpen ? "true" : "false");
    const caret = head.querySelector(".craft-shelf-caret");
    if (caret) caret.textContent = craftOpen ? "▾" : "▸";
  }
}

// ---- drafts & diffing ----

function renderDraftBar() {
  const bar = $("#draft-bar");
  // Always visible while a project is open — the "+ Upload new draft" entry
  // is how a writer discovers draft management in the first place, and hiding
  // it until a second draft exists means it's never discovered.
  const inProject = Boolean(state.currentProject);
  const hasDrafts = state.drafts && state.drafts.drafts && state.drafts.drafts.length > 0;
  bar.style.display = inProject ? "flex" : "none";
  if (!inProject) return;

  const sel = $("#draft-select");
  const active = state.drafts.active_draft || "original";
  sel.innerHTML = "";
  const optOriginal = new Option("original (first upload)", "original", false, active === "original");
  optOriginal.disabled = active === "original"; // nothing to switch to
  sel.appendChild(optOriginal);
  for (const d of state.drafts.drafts) {
    sel.appendChild(new Option(d.name + " — " + d.source_filename, d.name, false, active === d.name));
  }
  sel.value = active;
  sel.title = "Switch drafts — switching preserves the current one";
}

async function uploadNewDraft(file) {
  const status = $("#upload-draft-status");
  status.textContent = `Reading "${file.name}"…`;
  const form = new FormData();
  form.append("file", file);
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/drafts`, { method: "POST", body: form });
    status.textContent = `Draft parsed — ${file.name}`;
    await loadProjects();
    await openProject(state.currentProject);
  } catch (e) {
    status.classList.add("error");
    status.textContent = "Couldn't read that draft: " + e.message;
  }
}

async function activateDraft(name) {
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/drafts/activate`, {
      method: "POST", body: JSON.stringify({ name }),
    });
    await loadProjects();
    await openProject(state.currentProject);
  } catch (e) {
    showError("Couldn't switch drafts: " + e.message);
  }
}

function previousDraftName() {
  if (!state.drafts || !state.drafts.drafts || !state.drafts.drafts.length) return null;
  const active = state.drafts.active_draft;
  const list = state.drafts.drafts.map((d) => d.name);
  const idx = list.indexOf(active);
  if (idx > 0) return list[idx - 1];
  if (idx === 0) return "original";
  return list[list.length - 2] || "original"; // active is 'original'
}

async function renderDiffBanner() {
  const banner = $("#diff-banner");
  banner.style.display = "none";
  banner.innerHTML = "";

  const project = (state.projects || []).find((p) => p.project === state.currentProject);
  if (!project || project.stages.analyze !== "complete") return;
  const prev = previousDraftName();
  if (!prev) return;

  let diff;
  try {
    const base = `/projects/${encodeURIComponent(state.currentProject)}`;
    diff = await api(`${base}/diff?from=${encodeURIComponent(prev)}&to=active`);
  } catch (e) {
    return; // diff is a bonus view — never block the script on it
  }

  const s = diff.findings.summary;
  const chips = el("div", "diff-chips");
  chips.appendChild(el("span", "diff-chip resolved", `${s.resolved} resolved`));
  chips.appendChild(el("span", "diff-chip new", `${s.new} new`));
  chips.appendChild(el("span", "diff-chip carried", `${s.carried} carried`));
  chips.appendChild(el("span", "diff-chip open", `${s.still_present} still open`));
  const added = diff.scenes.added_scenes.length;
  const removed = diff.scenes.removed_scenes.length;
  if (added || removed) {
    chips.appendChild(el("span", "diff-chip scene", `scenes ${added ? "+" + added : ""}${removed ? " −" + removed : ""}`));
  }

  const head = el("div", "diff-head");
  head.appendChild(el("span", "diff-title", `vs ${prev}`));
  head.appendChild(chips);
  head.appendChild(el("button", "diff-toggle", "details"));
  banner.appendChild(head);

  const detail = el("div", "diff-detail");
  detail.style.display = "none";
  const groups = [
    ["Resolved in this draft", diff.findings.resolved],
    ["Newly flagged in this draft", diff.findings.new],
    ["Still present (not yet fixed)", diff.findings.still_present],
  ];
  for (const [title, items] of groups) {
    if (!items.length) continue;
    const g = el("div", "diff-group");
    g.appendChild(el("div", "diff-group-title", `${title} (${items.length})`));
    for (const f of items.slice(0, 8)) {
      const refs = (f.scene_refs || []).map((n) => "Scene " + n).join(", ") || "General";
      g.appendChild(el("div", "diff-item", `[${f.severity}] ${refs} — ${f.issue}`));
    }
    if (items.length > 8) g.appendChild(el("div", "diff-item muted", `…and ${items.length - 8} more`));
    detail.appendChild(g);
  }
  const changedScenes = diff.scenes.changed_scenes;
  if (changedScenes.length) {
    const g = el("div", "diff-group");
    g.appendChild(el("div", "diff-group-title", `Scenes with changed lines (${changedScenes.length})`));
    for (const cs of changedScenes.slice(0, 6)) {
      g.appendChild(el("div", "diff-item", `Scene ${cs.scene_number} — ${cs.heading}`));
    }
    detail.appendChild(g);
  }
  banner.appendChild(detail);

  head.querySelector(".diff-toggle").addEventListener("click", () => {
    const showing = detail.style.display === "none";
    detail.style.display = showing ? "block" : "none";
    head.querySelector(".diff-toggle").textContent = showing ? "hide" : "details";
  });

  banner.style.display = "block";
}

function findingStatusSummary() {
  const summary = { addressed: 0, open: 0 };
  (state.findings || []).forEach((f, index) => {
    if (f.category === "formatting") return;
    const d = findingDisposition(f, index);
    if (d === "addressed") summary.addressed += 1;
    else summary.open += 1;
  });
  return summary;
}

function findingNoteEl(f, index, opts = {}) {
  const disp = opts.disposition || "open";
  // forward-compatible states (Phase D defer / Phase E ghosting): muted
  // rendering only — never red, never reflowing script text (CSS-only)
  const stateClass = disp === "deferred" ? " deferred" : disp === "ghosted" ? " ghosted" : "";
  const note = el("div", "finding-note" + (SEVERITY_CLASS[f.severity] || "") + (opts.addressed ? " addressed" : "") + stateClass);
  note.dataset.findingIndex = String(index);
  const top = el("div", "finding-note-top");
  const cat = el("span", "finding-note-cat", CATEGORY_LABELS[f.category] || f.category);
  const stateEl = el("span", "finding-note-state", opts.addressed ? "addressed" : (disp === "deferred" ? "next pass" : disp === "ghosted" ? "stale" : ""));
  top.appendChild(cat);
  top.appendChild(stateEl);
  note.appendChild(top);
  note.appendChild(el("span", "finding-note-text", f.issue));

  // evidence-deep (opt-in): diagnosis + verified quote + trust badge — the
  // card answers WHY the doctor says it and WHERE it was verified. Dock lens
  // only; margin pins and feedback-room buckets stay shallow.
  if (opts.deep) {
    const deep = el("div", "finding-deep");
    if (f.why_it_matters) deep.appendChild(el("span", "finding-deep-why", f.why_it_matters));
    if (f.evidence_quote) deep.appendChild(el("span", "finding-deep-quote", "\u201C" + f.evidence_quote + "\u201D"));
    const v = f.verification;
    if (v && v.status) {
      const badge = el("span", "finding-deep-badge " + (v.status === "verified" ? "verified" : "unverified"));
      badge.textContent = v.status === "verified"
        ? "\u2713 verified" + (v.confidence != null ? " \u00B7 " + Number(v.confidence).toFixed(2) : "") + (v.matched_scene != null ? " \u00B7 S" + v.matched_scene : "")
        : "\u26A0 unverified";
      deep.appendChild(badge);
    }
    if (deep.children.length) note.appendChild(deep);
    if (f.rule_id) cat.title = "Grounded in knowledge-base rule " + f.rule_id;
  }

  const actions = el("div", "finding-note-actions");
  if (opts.pin) note.classList.add("finding-pin");
  // writer intent + copy (deep cards only — the loop's home surface; the
  // dock is where the writer's judgment is made, margin pins stay read-only)
  if (opts.deep) {
    const id = (state.findingIds && state.findingIds[index]) || String(index);
    const mkIntent = (label, intent, title) => {
      const b = el("button", "intent-btn" + (state.findingMarks[id] === intent ? " active" : ""), label);
      b.type = "button";
      b.title = title;
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        setFindingIntent(id, state.findingMarks[id] === intent ? null : intent);
      });
      return b;
    };
    actions.appendChild(mkIntent("\u2713", "addressed", "My call: addressed (survives re-analysis)"));
    actions.appendChild(mkIntent("\u23ED", "deferred", "Park for the next pass"));
    const cp = el("button", "intent-btn", "\u29C9");
    cp.type = "button";
    cp.title = "Copy the evidence + scene slug";
    cp.addEventListener("click", (e) => { e.stopPropagation(); copyFindingEvidence(f); });
    actions.appendChild(cp);
    // GAP-4: the escalation gesture — ask Dr. Sushruta WHY this was flagged,
    // with the finding (and its quote) riding into the consult turn
    const why = el("button", "intent-btn", "\uD83E\uDE7A");
    why.type = "button";
    why.title = "Ask Dr. Sushruta why this was flagged — the finding rides along";
    why.addEventListener("click", (e) => { e.stopPropagation(); discussWithDoctor(f, index); });
    actions.appendChild(why);
  }
  const locateBtn = el("button", "", "🎯 Locate");
  locateBtn.type = "button";
  locateBtn.title = "Jump to the exact line this finding quotes";
  locateBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    locateFinding(f, index);
  });
  const rewriteBtn = el("button", "", "Rewrite");
  rewriteBtn.type = "button";
  rewriteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const refs = f.scene_refs || [];
    openRewriteModal(refs[0] || 1, f, index);
  });
  const discussBtn = el("button", "", "Discuss");
  discussBtn.type = "button";
  discussBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    discussFinding(f, index);
  });
  actions.appendChild(locateBtn);
  // R6: the margin pin points, the board/dock judge — Rewrite and Discuss are
  // the writer's judgment and have one home each (the board's card and the
  // dock's deep card). Rendering them here too is what made one finding read
  // as four competing surfaces at once.
  if (!opts.pin) {
    actions.appendChild(rewriteBtn);
    actions.appendChild(discussBtn);
  }
  note.appendChild(actions);
  return note;
}

// ---- writer's margin notes ----

async function reloadNotesAndRender() {
  try {
    const base = `/projects/${encodeURIComponent(state.currentProject)}`;
    const res = await api(`${base}/notes`);
    state.notes = (res && res.notes) || [];
    renderManuscript(document.getElementById('manuscript-container'));
    renderRailNotes(); // Phase 13: the dock's notes panel is #rail-notes now
  } catch (e) {
    showError("Couldn't refresh notes: " + e.message);
  }
}

function noteTextarea(placeholder, initial) {
  const ta = document.createElement("textarea");
  ta.className = "note-editor";
  ta.rows = 2;
  ta.placeholder = placeholder;
  if (initial !== undefined) ta.value = initial;
  return ta;
}

/** Inline add-editor: shows a textarea where the trigger button was. */
function startNoteEditor(sceneNumber, triggerBtn) {
  const ta = noteTextarea("Your margin note… (Enter to save, Esc to cancel)");
  triggerBtn.replaceWith(ta);
  ta.focus();
  let done = false;
  const finish = (saved, text) => {
    if (done) return;
    done = true;
    if (saved && text) {
      api(`/projects/${encodeURIComponent(state.currentProject)}/notes`, {
        method: "POST",
        body: JSON.stringify({ scene_number: sceneNumber, text }),
      }).then(reloadNotesAndRender).catch((e) => showError("Couldn't save note: " + e.message));
    } else {
      reloadNotesAndRender();
    }
  };
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); finish(true, ta.value.trim()); }
    else if (e.key === "Escape") { finish(false); }
  });
  ta.addEventListener("blur", () => { if (ta.value.trim()) finish(true, ta.value.trim()); else finish(false); });
}

function writerNoteEl(note) {
  const wrap = el("div", "note-mine" + (note.dirty ? " dirty" : ""));
  wrap.dataset.noteId = note.id;

  const view = el("div", "note-mine-view");
  const text = el("span", "note-mine-text", note.text);
  const actions = el("div", "note-mine-actions");
  const editBtn = el("button", "", "edit");
  editBtn.type = "button";
  editBtn.title = "Edit this note";
  editBtn.addEventListener("click", () => {
    const ta = noteTextarea("Your margin note…", note.text);
    view.replaceWith(ta);
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
    let done = false;
    const finish = (saved, text) => {
      if (done) return;
      done = true;
      if (saved && text) {
        api(`/projects/${encodeURIComponent(state.currentProject)}/notes/${note.id}`, {
          method: "PATCH", body: JSON.stringify({ text }),
        }).then(reloadNotesAndRender).catch((e) => showError("Couldn't update note: " + e.message));
      } else {
        reloadNotesAndRender();
      }
    };
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); finish(true, ta.value.trim()); }
      else if (e.key === "Escape") { finish(false); }
    });
    ta.addEventListener("blur", () => { if (ta.value.trim()) finish(true, ta.value.trim()); else finish(false); });
  });
  const delBtn = el("button", "", "✕");
  delBtn.type = "button";
  delBtn.title = "Delete this note";
  delBtn.addEventListener("click", async () => {
    if (!confirm("Delete this margin note?")) return;
    try {
      await api(`/projects/${encodeURIComponent(state.currentProject)}/notes/${note.id}`, { method: "DELETE" });
      reloadNotesAndRender();
    } catch (e) {
      showError("Couldn't delete note: " + e.message);
    }
  });
  actions.appendChild(editBtn);
  // anchored notes (Google-Docs style): the ↩ returns to the exact line
  if (note.anchor) {
    wrap.classList.add("anchored");
    const jumpBtn = el("button", "", "↩");
    jumpBtn.type = "button";
    jumpBtn.title = "Jump to the line this note is pinned to";
    jumpBtn.addEventListener("click", () => {
      scrollToSceneInPlace(note.scene_number);
      setTimeout(() => {
        const page = document.getElementById(`scene-page-${note.scene_number}`);
        if (!page) return;
        const q = normText(note.anchor);
        if (q.length < 2) return;
        for (const line of page.querySelectorAll("[class^=el-]")) {
          if (normText(line.textContent) === q || (q.length > 4 && normText(line.textContent).includes(q))) {
            line.classList.add("finding-highlight");
            line.scrollIntoView({ behavior: "smooth", block: "center" });
            setTimeout(() => line.classList.remove("finding-highlight"), 2600);
            break;
          }
        }
      }, 140);
    });
    actions.appendChild(jumpBtn);
  }
  actions.appendChild(delBtn);
  view.appendChild(text);
  view.appendChild(actions);
  wrap.appendChild(view);
  return wrap;
}

function renderScenePage(scene, findings, searchQuery, notes = [], discussed = false, changedTexts = [], idPrefix = "") {
  const page = el("article", "scene-page");
  page.id = `${idPrefix}scene-page-${scene.scene_number}`;
  page.dataset.sceneNumber = String(scene.scene_number);

  const head = el("div", "scene-page-head");
  head.appendChild(el("span", "scene-page-num", `Scene ${scene.scene_number}`));
  const heading = el("span", "scene-heading-line", scene.heading_raw);
  // a11y (WCAG 1.3.1 Info and Relationships): the scenes are one continuous
  // column now (no card chrome), so the slug line is the only programmatic
  // boundary left between scenes — expose it as a heading so screen-reader
  // users can navigate scene by scene.
  heading.setAttribute("role", "heading");
  heading.setAttribute("aria-level", "2");
  if (searchQuery) highlightMatches(heading, scene.heading_raw, searchQuery);
  head.appendChild(heading);
  if (scene.page_estimate) {
    head.appendChild(el("span", "scene-page-est", `≈ ${scene.page_estimate} min`));
  }
  if (discussed) {
    const discussedTag = el("span", "scene-discussed", "discussed");
    discussedTag.title = "You asked Sameer about a passage in this scene";
    head.appendChild(discussedTag);
  }
  const addNoteBtn = el("button", "note-add", "✎ note");
  addNoteBtn.type = "button";
  addNoteBtn.title = "Pin your own margin note to this scene";
  addNoteBtn.addEventListener("click", () => startNoteEditor(scene.scene_number, addNoteBtn));
  head.appendChild(addNoteBtn);
  page.appendChild(head);

  // ink (R5-b): the ONE filter drives the page — active search wins
  // (transient beats persistent); anchors computed once per scene
  const inkAnchors = searchQuery ? [] : inkAnchorsFor(findings);
  for (const e of scene.elements) {
    if (e.type === "scene_heading") continue;
    const line = el("div", `el-${e.type}`);
    let text = e.text;
    if (e.type === "parenthetical" && !text.startsWith("(")) text = `(${text})`;
    line.textContent = text;
    if (searchQuery) highlightMatches(line, text, searchQuery);
    else if (inkAnchors.length) decorateLineWithInk(line, text, inkAnchors);
    // change-mark star: this line is the NEW text of an applied edit (Arc
    // Studio's most-praised touch) — hover shows what it replaced
    wireInlineEdit(line, scene.scene_number, e.text);
    const changed = changedTexts.find((rep) => normText(rep.new) === normText(text) && normText(rep.new).length >= 2);
    if (changed) {
      line.classList.add("el-changed");
      line.title = `Edited — was: ${changed.old}`;
    }
    page.appendChild(line);
  }

  if (findings.length || notes.length) {
    const margin = el("div", "scene-notes");
    for (const { f, index } of findings) {
      const addressed = findingStatusOf(f, index) === "addressed";
      // R6: a margin PIN, not a fourth card. The finding already renders in
      // the Problem Board and in the dock's Evidence lens; the margin's job is
      // to say what sits on this line while the writer is reading it, so it
      // keeps Locate (navigation) and drops the judgment controls
      // (Rewrite / Discuss) — which is what findingNoteEl's own contract
      // always claimed ("margin pins stay read-only").
      margin.appendChild(findingNoteEl(f, index, { addressed, pin: true }));
    }
    if (notes.length) {
      const label = el("div", "notes-mine-label", "your notes");
      margin.appendChild(label);
      for (const n of notes) margin.appendChild(writerNoteEl(n));
    }
    page.appendChild(margin);
  }
  return page;
}

function prepareManuscriptData() {
  const findings = state.findings || [];
  const editsData = state.editsData;
  const notes = state.notes || [];

  const byScene = {};
  const scriptLevel = [];
  findings.forEach((f, index) => {
    const refs = f.scene_refs || [];
    if (!refs.length) { scriptLevel.push({ f, index }); return; }
    for (const n of refs) {
      (byScene[n] = byScene[n] || []).push({ f, index });
    }
  });

  const changedByScene = {};
  for (const ed of (editsData && editsData.edits) || []) {
    if (!ed.scene_number || !(ed.applied || []).length) continue;
    (changedByScene[ed.scene_number] = changedByScene[ed.scene_number] || []).push(...ed.applied);
  }

  const anchorsByScene = {};
  findings.forEach((f, index) => {
    const sc = findingTargetScene(f);
    if (sc == null || !(f.evidence_quote || "").trim()) return;
    (anchorsByScene[sc] = anchorsByScene[sc] || []).push({ f, index });
  });

  const bySceneNotes = {};
  const scriptLevelNotes = [];
  for (const n of notes) {
    if (n.scene_number == null) scriptLevelNotes.push(n);
    else (bySceneNotes[n.scene_number] = bySceneNotes[n.scene_number] || []).push(n);
  }

  const discussedScenes = new Set();
  for (const m of (currentBranchData().messages || [])) {
    if (m.quote && m.quote.scene_number != null) discussedScenes.add(m.quote.scene_number);
  }

  return {
    byScene,
    scriptLevel,
    changedByScene,
    anchorsByScene,
    bySceneNotes,
    scriptLevelNotes,
    discussedScenes,
  };
}

function highlightMatches(node, text, query) {
  const q = query.trim();
  if (!q) return;
  const lower = text.toLowerCase();
  const idx = lower.indexOf(q.toLowerCase());
  if (idx === -1) return;
  node.innerHTML = "";
  node.appendChild(document.createTextNode(text.slice(0, idx)));
  const mark = document.createElement("mark");
  mark.textContent = text.slice(idx, idx + q.length);
  node.appendChild(mark);
  node.appendChild(document.createTextNode(text.slice(idx + q.length)));
}

// ---- Stage 3B: the manuscript renderer ----
// The single renderer (Phase 13: the legacy renderScriptView fallback was
// removed — this is the only manuscript path). Renders into the container
// it is given (#manuscript-container). All DOM contracts survive:
// .scene-page, data-scene-number, scene-page-N ids, the el-* line classes
// — jumpToScene, focus mode, river read, Problem Board sync and
// selection-to-ask all depend on them.
// a11y (WCAG 4.1.3 Status Messages): announce a NEW manuscript load. Every
// re-render (typing, undo, notes, search) flows through renderManuscript, so
// gate on the scene count actually changing — otherwise the polite live
// region would fire on every keystroke.
let lastAnnouncedSceneCount = -1;
function announceManuscriptLoad(count) {
  if (count === lastAnnouncedSceneCount) return;
  lastAnnouncedSceneCount = count;
  const el = document.getElementById("a11y-status");
  if (el) {
    el.textContent = count
      ? `Manuscript loaded: ${count} scene${count === 1 ? "" : "s"}.`
      : "";
  }
}

function renderManuscript(container) {
  if (!container) container = getManuscriptContainer();
  if (!container) return;
  container.innerHTML = "";
  const q = ($("#script-search").value || "").trim();

  if (!state.script) {
    container.appendChild(el("p", "script-empty-hint", "Parsing the script…"));
    return;
  }
  if (!state.script.scenes || !state.script.scenes.length) {
    container.appendChild(el("p", "script-empty-hint", "No scenes found in this script."));
    return;
  }

  const {
    byScene,
    scriptLevel,
    changedByScene,
    anchorsByScene,
    bySceneNotes,
    scriptLevelNotes,
    discussedScenes,
  } = prepareManuscriptData();

  // the analysis panels ride in a collapsed craft shelf — page one first
  const craftPanels = [];
  renderFixQueuePanel(craftPanels);
  renderPacingPanel(craftPanels);
  renderCharacterPanel(craftPanels);
  renderCharacterDialsPanel(craftPanels);
  renderWriterMirrorPanel(craftPanels);
  if (craftPanels.length) container.appendChild(buildCraftShelf(craftPanels));

  if (scriptLevel.length || scriptLevelNotes.length) {
    const bucket = el("div", "script-level-notes");
    bucket.setAttribute("aria-label", "Script-level notes");
    for (const { f, index } of scriptLevel) {
      bucket.appendChild(findingNoteEl(f, index));
    }
    if (scriptLevelNotes.length) {
      for (const n of scriptLevelNotes) bucket.appendChild(writerNoteEl(n));
    }
    container.appendChild(bucket);
  }

  let matchCount = 0;
  for (const scene of state.script.scenes) {
    const page = renderScenePage(scene, byScene[scene.scene_number] || [], q, bySceneNotes[scene.scene_number] || [], discussedScenes.has(scene.scene_number), changedByScene[scene.scene_number] || []);
    if (q) {
      const text = (scene.heading_raw + " " + scene.elements.map((e) => e.text).join(" ")).toLowerCase();
      const matches = text.includes(q.toLowerCase());
      if (!matches) { page.classList.add("hidden"); }
      else matchCount += 1;
    }
    // anchor pass: mark the quoted lines so a click opens the finding
    for (const { f, index } of anchorsByScene[scene.scene_number] || []) {
      const qq = normText(f.evidence_quote);
      if (qq.length < 4) continue;
      for (const line of page.querySelectorAll("[class^=el-]")) {
        const lt = normText(line.textContent);
        if (lt.length >= 4 && (lt.includes(qq) || qq.includes(lt.slice(0, 40)))) {
          line.classList.add("el-anchored");
          line.title = `${CATEGORY_LABELS[f.category] || f.category}: ${f.issue}`;
          line.addEventListener("click", () => {
            if (!openFindingCard(index)) locateFinding(f, index);
          });
          break;
        }
      }
    }
    // anchored margin notes: lines with a pinned note get a marker; click opens it
    for (const n of bySceneNotes[scene.scene_number] || []) {
      if (!n.anchor) continue;
      const qq = normText(n.anchor);
      if (qq.length < 2) continue;
      for (const line of page.querySelectorAll("[class^=el-]")) {
        const lt = normText(line.textContent);
        if (lt === qq || (qq.length > 4 && lt.includes(qq))) {
          line.classList.add("el-noted");
          line.title = `Your margin note: ${n.text}`;
          line.addEventListener("click", () => openNoteCard(n.id));
          break;
        }
      }
    }
    container.appendChild(page);
  }
  if (q && matchCount === 0) {
    container.appendChild(el("p", "script-empty-hint", `No scenes match "${q}".`));
  }

  renderSceneIndex();
  updateSceneIndexHighlight();
  // announce only when the manuscript itself changed (see announceManuscriptLoad)
  announceManuscriptLoad(state.script && state.script.scenes ? state.script.scenes.length : 0);
  // Phase 6: an open Evidence lens re-assembles after every manuscript
  // re-render — undo/redo, rewrites, notes, retry, search all flow through
  // here, so the dock never shows a stale ledger.
  refreshDockEvidence();

  // finding summary chips
  const summary = findingStatusSummary();
  const summaryEl = $("#finding-summary");
  summaryEl.innerHTML = "";
  summaryEl.appendChild(el("span", "fs-chip open", `${summary.open} open`));
  summaryEl.appendChild(el("span", "fs-chip addressed", `${summary.addressed} addressed`));
  buildRiverDots();

  // undo/redo + reset + export targets
  const hasEdits = state.editsData && state.editsData.edits && state.editsData.edits.length > 0;
  $("#reset-edits-btn").style.display = hasEdits ? "inline-block" : "none";
  $("#undo-btn").disabled = !hasEdits;
  $("#redo-btn").disabled = !(state.editsData && state.editsData.can_redo);
  const base = `/api/projects/${encodeURIComponent(state.currentProject)}/export?format=`;
  $("#export-fountain").href = base + "fountain";
  $("#export-fdx").href = base + "fdx";
  $("#export-txt").href = base + "txt";
  $("#export-fountain").download = `${state.script.title || "script"}.fountain`;
  $("#export-fdx").download = `${state.script.title || "script"}.fdx`;
  $("#export-txt").download = `${state.script.title || "script"}.txt`;
  $("#export-backup").href = `/api/projects/${encodeURIComponent(state.currentProject)}/backup`;
  $("#export-backup").download = `${state.currentProject}-backup.zip`;

  renderRailScenes();
  renderRailNotes();
  loadCharacters();
  if (document.body.classList.contains("focus-mode")) markCurrentScene();
}

// ---- Phase 4: Scene Index ----
// The 44px rail / 240px expanded overlay that replaces the old structural
// rail's scene-navigation role. One entry per scene, open-severity
// aggregates, click (or Enter) jumps to the scene, and the current scene
// tracks the manuscript as it scrolls.

let sceneIndexRAF = null;

function sceneIndexSeverity(sceneNumber) {
  const counts = { high: 0, medium: 0, low: 0 };
  (state.findings || []).forEach((f, index) => {
    if (!findingOpen(f, index)) return;
    const refs = (f.scene_refs && f.scene_refs.length) ? f.scene_refs : (f.scene ? [f.scene] : []);
    if (!refs.includes(sceneNumber)) return;
    const sev = (f.severity || "low").toLowerCase();
    if (counts[sev] != null) counts[sev] += 1;
  });
  return counts;
}

function renderSceneIndex() {
  const list = document.getElementById("scene-index-list");
  if (!list) return;
  list.innerHTML = "";
  const scenes = state.script && state.script.scenes;
  if (!scenes || !scenes.length) {
    list.appendChild(el("div", "scene-index-empty", "—"));
    return;
  }
  scenes.forEach((scene) => {
    const item = el("div", "scene-index-item");
    item.dataset.sceneNumber = String(scene.scene_number);
    item.setAttribute("role", "button");
    item.setAttribute("tabindex", "0");
    const counts = sceneIndexSeverity(scene.scene_number);
    const total = counts.high + counts.medium + counts.low;
    const label = (scene.heading_raw || `Scene ${scene.scene_number}`) +
      (total ? ` — ${total} open finding${total === 1 ? "" : "s"} (${counts.high} high · ${counts.medium} medium · ${counts.low} low)` : "");
    item.title = label;
    item.setAttribute("aria-label", label);
    item.appendChild(el("span", "scene-index-num", String(scene.scene_number)));
    item.appendChild(el("span", "scene-index-head", (scene.heading_raw || "").slice(0, 60)));
    if (total > 0) {
      const dots = el("span", "scene-index-dots");
      // the item's own aria-label already spells out the counts, so the
      // decorative dots stay out of the a11y tree (no double announcement)
      dots.setAttribute("aria-hidden", "true");
      for (const sev of ["high", "medium", "low"]) {
        if (counts[sev] > 0) {
          const d = el("i", "dot " + sev);
          d.title = `${counts[sev]} ${sev}`;
          dots.appendChild(d);
        }
      }
      item.appendChild(dots);
      item.appendChild(el("span", "scene-index-count", String(total)));
    }
    item.addEventListener("click", () => jumpToScene(scene.scene_number));
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); jumpToScene(scene.scene_number); }
    });
    list.appendChild(item);
  });
}

function updateSceneIndexHighlight() {
  const list = document.getElementById("scene-index-list");
  if (!list) return;
  const container = getManuscriptContainer();
  let currentNum = null;
  if (container) {
    const pages = [...container.querySelectorAll(".scene-page")];
    const viewportMid = container.getBoundingClientRect().top + container.clientHeight / 2;
    for (const p of pages) {
      if (p.getBoundingClientRect().top <= viewportMid) currentNum = p.dataset.sceneNumber;
      else break;
    }
  }
  let active = null;
  list.querySelectorAll(".scene-index-item").forEach((it) => {
    const on = it.dataset.sceneNumber === currentNum;
    it.classList.toggle("active", on);
    if (on) active = it;
  });
  if (active && list.scrollHeight > list.clientHeight) {
    const top = active.offsetTop - list.clientHeight / 2 + active.offsetHeight / 2;
    list.scrollTop = Math.max(0, top);
  }
}

function setupSceneIndexScroll() {
  const container = getManuscriptContainer();
  if (!container) return;
  container.addEventListener("scroll", () => {
    if (sceneIndexRAF) return;
    sceneIndexRAF = requestAnimationFrame(() => {
      sceneIndexRAF = null;
      updateSceneIndexHighlight();
      // Phase 6: a scroll that lands on a new scene retitles the Evidence
      // lens's scene strip (cheap by design — no panel re-renders).
      refreshDockEvidenceScene();
    });
  }, { passive: true });
}

// ---------- Phase 5: the Context Dock ----------
// One lens at a time beside the page (Evidence / Sameer / Sushruta). An
// in-flow sibling of the manuscript — the page keeps at least half the room.
// Opening, closing, and lens switching never re-render or scroll the page;
// the dock is additive chrome, and its content arrives in later phases.

const DOCK_LENSES = ["evidence", "sameer", "sushruta", "notes"];
let dockLens = "evidence";
let _dockFocusReturn = null;

function dockIsOpen() {
  const d = $("#context-dock");
  return !!(d && d.classList.contains("open"));
}

function setDockLens(lens) {
  if (!DOCK_LENSES.includes(lens)) lens = "evidence";
  const changed = lens !== dockLens;
  dockLens = lens;
  const dock = $("#context-dock");
  if (!dock) return;
  DOCK_LENSES.forEach((l) => {
    const tab = $("#dock-tab-" + l);
    if (tab) tab.setAttribute("aria-selected", l === lens ? "true" : "false");
    const panel = dock.querySelector(`.dock-lens[data-lens="${l}"]`);
    if (panel) panel.hidden = l !== lens;
  });
  // Phase 6: the evidence lens assembles on every activation — it reads live
  // state (report, fix queue, manuscript data), never a stale copy.
  if (lens === "evidence" && dockIsOpen()) renderDockEvidence();
  // the unread dot lives until the writer actually opens the Evidence lens
  if (lens === "evidence") clearEvidenceUnread();
  // Phase 13: the Stash & Notes lens renders from live state on activation
  // (same renderers the rail used — no second data path)
  if (lens === "notes" && dockIsOpen()) renderDockNotesLens();
  // Phase 7: chat lenses adopt the live conversation; leaving a chat lens
  // returns it to its room panel (the conversation never lives in two places)
  if (changed) {
    if (lens === "sameer" || lens === "sushruta") adoptChatIntoDock(lens);
    else returnChatFromDock();
  }
  savePrefs({ dock_lens: lens });
}

function openDock(lens) {
  const dock = $("#context-dock");
  const edge = $("#right-edge-affordance");
  if (!dock) return;
  if (lens) setDockLens(lens);
  else setDockLens(dockLens); // normalize + keep tabs in sync on first open
  if (!dockIsOpen()) _dockFocusReturn = document.activeElement;
  dock.classList.add("open");
  if (edge) edge.hidden = true;
  // Phase 6: opening straight into the evidence ledger
  if (dockLens === "evidence") renderDockEvidence();
  // Phase 13: opening into Stash & Notes renders from live state
  if (dockLens === "notes") renderDockNotesLens();
  // Phase 7: opening into a chat lens adopts the conversation even when the
  // lens is unchanged (e.g. reopen after close returned it to the room)
  if (dockLens === "sameer" || dockLens === "sushruta") adoptChatIntoDock(dockLens);
  const tab = $("#dock-tab-" + dockLens);
  if (tab) tab.focus();
}

function closeDock() {
  const dock = $("#context-dock");
  const edge = $("#right-edge-affordance");
  if (!dock) return;
  dock.classList.remove("open");
  if (edge) edge.hidden = false;
  // Phase 7: closing the dock returns the conversation to its room panel —
  // the chat never stays trapped in a hidden lens
  returnChatFromDock();
  if (_dockFocusReturn && document.contains(_dockFocusReturn)) {
    try { _dockFocusReturn.focus(); } catch (_) { /* detached node */ }
  }
  _dockFocusReturn = null;
}

// ---------- Phase 13: Stash & Notes dock lens ----------
// The retired structure rail's Stash + margin-notes panels, relocated into
// the Context Dock (the rail was globally display:none — dead chrome; these
// are live features). The SAME renderers the rail used fill the containers:
// renderStashList → #stash-list, renderRailNotes → #rail-notes. One data
// path, one presentation home.

function renderDockNotesLens() {
  if (!state.currentProject) return;
  renderStashList();
  renderRailNotes();
}

/** Refresh the notes lens when stash/notes change while it's open. */
function refreshDockNotesLens() {
  if (!dockIsOpen() || dockLens !== "notes") return;
  renderDockNotesLens();
}

// ---------- Phase 6: Evidence Overview (the dock's primary lens) ----------
// The writer's four questions, in order: What is wrong? Where? How serious?
// What should I do next? Everything renders through the SAME functions the
// legacy surfaces use (renderFixQueuePanel, renderPacingPanel,
// renderCharacterPanel, renderWriterMirrorPanel, findingNoteEl) — no second
// data path, no duplicated aggregation (prepareManuscriptData is the single
// source). Sections stack vertically and collapse under one header each;
// this is a contextual ledger, not a dashboard of equal cards.

let dockEvidenceCurrentScene = null;

/** The scene the writer is currently on (mid-viewport), or null. */
function currentManuscriptScene() {
  const container = getManuscriptContainer();
  if (!container) return null;
  const pages = [...container.querySelectorAll(".scene-page")];
  if (!pages.length) return null;
  const viewportMid = container.getBoundingClientRect().top + container.clientHeight / 2;
  let current = null;
  for (const p of pages) {
    if (p.getBoundingClientRect().top <= viewportMid) current = p.dataset.sceneNumber;
    else break;
  }
  return current != null ? Number(current) : null;
}

/** Refresh ONLY the scene strip + scene findings when the writer scrolls to
 *  a different scene (the heavy craft sections stay put). Cheap by design:
 *  called from the existing scroll RAF loop, so it must not re-render
 *  panels or touch the manuscript. */
function refreshDockEvidenceScene() {
  if (!dockIsOpen() || dockLens !== "evidence") return;
  const now = currentManuscriptScene();
  if (now === dockEvidenceCurrentScene) return;
  dockEvidenceCurrentScene = now;
  const sceneBox = document.querySelector(".dock-evidence-scene");
  if (sceneBox) renderDockEvidenceSceneBox(sceneBox);
  refreshDockRulerMarker();
}

function renderDockEvidenceSceneBox(box) {
  box.innerHTML = "";
  const sceneNum = currentManuscriptScene();
  const scenes = (state.script && state.script.scenes) || [];
  const scene = scenes.find((s) => s.scene_number === sceneNum) || null;
  const head = el("div", "dock-scene-head");
  if (scene) {
    head.appendChild(el("span", "dock-scene-num", "Scene " + scene.scene_number));
    head.appendChild(el("span", "dock-scene-heading", (scene.heading_raw || "").slice(0, 80)));
  } else {
    head.appendChild(el("span", "dock-scene-num", "Script level"));
    head.appendChild(el("span", "dock-scene-heading", "whole-script findings"));
  }
  box.appendChild(head);
  // severity aggregate for THIS scene — same counting the scene index uses
  // (open findings only), never communicated by color alone: dots carry
  // titles AND the counts are printed as text.
  if (scene) {
    const counts = sceneIndexSeverity(scene.scene_number);
    const total = counts.high + counts.medium + counts.low;
    const sev = el("div", "dock-scene-sev");
    if (total) {
      for (const s of ["high", "medium", "low"]) {
        if (!counts[s]) continue;
        const dot = el("span", "sev-dot " + s);
        dot.title = `${counts[s]} ${s}`;
        sev.appendChild(dot);
        sev.appendChild(el("span", "dock-sev-count", `${counts[s]} ${s}`));
      }
      sev.appendChild(el("span", "dock-sev-total", `${total} open`));
    } else {
      sev.appendChild(el("span", "dock-sev-total clean", "clean — no open findings"));
    }
    box.appendChild(sev);
  }
}

/**
 * Full Evidence Overview render. Called when: the dock opens on the evidence
 * lens, the lens switches to evidence, and after any manuscript re-render
 * (the renderManuscript tail calls refreshDockEvidence()) so undo/redo/
 * rewrite/notes/search all stay in sync through the one central hook.
 */
function renderDockEvidence() {
  const lens = document.querySelector('.dock-lens[data-lens="evidence"]');
  if (!lens) return;
  lens.innerHTML = "";

  const hasReport = !!(state.report && (state.report.findings || state.report.coverage));
  const hasQueue = !!(state.fixQueue && state.fixQueue.items && state.fixQueue.items.length);

  if (!hasReport && !hasQueue) {
    const empty = el("div", "dock-evidence-empty");
    empty.appendChild(el("p", "dock-lens-hint",
      "No analysis yet. Run Analysis from the toolbar — the evidence ledger assembles itself here when the report lands."));
    lens.appendChild(empty);
    return;
  }

  // -- 0b. the arrival strip (R4): the "finally" — scorekeeping + trust +
  // inline retry + ghosted marks, at the top of the board where arrival lands.
  const arrival = buildArrivalStrip();
  if (arrival) lens.appendChild(arrival);

  // -- 0a. the ONE filter row (R5-b + R8): severity toggles drive ink,
  // board list, loop and counts together; category chips count and filter —
  // tap = filtered view, NO regrouping. The loop button engages the
  // keyboard fix loop (R2-b); N/↓ step findings until Esc.
  const filterRow = buildFindingFilterRow();
  const loopBtn = el("button", "fchip fchip-loop");
  loopBtn.type = "button";
  loopBtn.textContent = "\u21C9 fix loop";
  loopBtn.title = "Keyboard fix loop: N/\u2193 next finding \u00B7 P/\u2191 previous \u00B7 mark, park, discuss, copy \u00B7 Esc to leave";
  loopBtn.addEventListener("click", () => startLoop());
  filterRow.appendChild(loopBtn);
  lens.appendChild(filterRow);

  // -- 0. script mass strip + ruler (orientation) ---------------------------
  const strip = buildScriptMassStrip();
  if (strip.children.length) lens.appendChild(strip);
  lens.appendChild(buildScriptRuler());

  // -- 1. current-scene strip (What is wrong HERE? Where?) ----------------
  const sceneBox = el("div", "dock-evidence-scene");
  renderDockEvidenceSceneBox(sceneBox);
  lens.appendChild(sceneBox);
  dockEvidenceCurrentScene = currentManuscriptScene();
  refreshDockRulerMarker();

  // -- 2. Fix Queue (What should I do next?) -------------------------------
  // The queue is the doctor's ordered to-do; it opens first for a reason.
  // addPanel() appends the .craft-panel straight into this section div.
  const fqWrap = el("div", "dock-section dock-section-fixqueue");
  renderFixQueuePanel(fqWrap); // existing function, reused verbatim
  if (fqWrap.children.length) lens.appendChild(fqWrap);

  // -- 3. findings on the current scene (Where, precisely) -----------------
  const data = prepareManuscriptData(); // the single source of truth
  const sceneNum = currentManuscriptScene();
  const isAddressed = (f, index) => findingStatusOf(f, index) === "addressed";
  const sceneFindings = sceneNum != null
    ? (data.byScene[sceneNum] || []).filter(({ f, index }) => findingPassesFilter(f, index))
    : [];
  if (sceneFindings.length) {
    const sec = el("div", "dock-section dock-section-scene-findings");
    const title = el("div", "dock-section-title",
      sceneNum != null ? `Findings — Scene ${sceneNum}` : "Findings — script level");
    sec.appendChild(title);
    const list = el("div", "dock-finding-list");
    for (const { f, index } of sceneFindings) {
      // Addressed / Still Present rides along (MD §7 preserve list)
      list.appendChild(findingNoteEl(f, index, { addressed: isAddressed(f, index), disposition: findingDisposition(f, index), deep: true }));
    }
    sec.appendChild(list);
    lens.appendChild(sec);
  }
  // script-level findings ride beneath the scene's own
  const scriptLevel = (data.scriptLevel || []).filter(({ f, index }) => findingPassesFilter(f, index));
  if (scriptLevel.length) {
    const sec = el("div", "dock-section");
    sec.appendChild(el("div", "dock-section-title", "Script-level findings"));
    const list = el("div", "dock-finding-list");
    for (const { f, index } of scriptLevel) {
      list.appendChild(findingNoteEl(f, index, { addressed: isAddressed(f, index), disposition: findingDisposition(f, index), deep: true }));
    }
    sec.appendChild(list);
    lens.appendChild(sec);
  }

  // -- 4. findings grouped by category (How serious, organized) ------------
  // Reuses the same grouping renderReportPanel performs, but with the full
  // findingNoteEl card (actions intact) instead of the read-only row.
  // The ONE filter applies here too (R5-b): the chips above drive what
  // shows, so the board and the page agree by construction.
  const byCat = {};
  (state.report && state.report.findings || []).forEach((f, i) => {
    const index = f.index != null ? f.index : i;
    if (!findingPassesFilter(f, index)) return;
    (byCat[f.category] = byCat[f.category] || []).push({ f, index });
  });
  for (const [cat, list] of Object.entries(byCat)) {
    const sec = el("div", "dock-section");
    const title = el("div", "dock-section-title");
    title.appendChild(el("span", "", CATEGORY_LABELS[cat] || cat));
    title.appendChild(el("span", "dock-section-count", String(list.length)));
    sec.appendChild(title);
    const wrap = el("div", "dock-finding-list");
    for (const { f, index } of list) wrap.appendChild(findingNoteEl(f, index, { addressed: isAddressed(f, index), disposition: findingDisposition(f, index), deep: true }));
    sec.appendChild(wrap);
    lens.appendChild(sec);
  }
  // honest emptiness: findings exist but the filter hides them all — the
  // writer asked for a narrower view, and the board says so (never a blank)
  const anyBoardCards = sceneFindings.length + scriptLevel.length;
  if (!anyBoardCards && Object.keys(byCat).length === 0 && (state.findings || []).length) {
    const sec = el("div", "dock-section");
    sec.appendChild(el("div", "dock-lens-hint",
      "No findings match the current filter — toggle a severity or category chip above to widen the view."));
    lens.appendChild(sec);
  }

  // -- 5. Coverage ----------------------------------------------------------
  const cov = state.report && state.report.coverage;
  if (cov) {
    const sec = el("div", "dock-section");
    const head = el("div", "dock-section-title",
      `Coverage — ${(cov.recommendation || "").toUpperCase()}`);
    sec.appendChild(head);
    if (cov.logline) sec.appendChild(el("p", "dock-cov-logline", cov.logline));
    (cov.weaknesses || []).forEach((w) => sec.appendChild(el("p", "dock-cov-weak", "• " + w)));
    // Evidence depth (§5 item 4): how much of this report read the pages, and how
    // much read a model-written summary of them. Absent on reports analysed before
    // the field existed, so it is rendered only when present.
    const depth = state.report && state.report.stats && state.report.stats.evidence_depth;
    if (depth && depth.total) {
      const covStats = state.report.stats || {};
      const mixed = depth.overview_and_checkpoints || 0;
      let depthTxt = `Evidence depth — ${depth.full_text} of ${depth.total} from the full script text, `
        + `${depth.overview} from scene summaries`;
      if (mixed) {
        const cov2 = covStats.checkpoint_coverage;
        const where = (cov2 && cov2.scenes && cov2.scenes.length)
          ? ` (scenes ${cov2.scenes.join(", ")})` : "";
        depthTxt += `, ${mixed} from scene summaries plus the raw pages of the key scenes${where}`;
      }
      const line = el("p", "dock-cov-depth", depthTxt + ".");
      line.title = "Script-level passes reason mostly from scene summaries rather than the raw pages. "
        + "Treat those findings as a second opinion on structure, not a reading of your pages.";
      sec.appendChild(line);
    }
    lens.appendChild(sec);
  }

  // -- 6. Setup / Payoff ------------------------------------------------------
  // The ledger twice: once as a scene spine (promise structure at a glance —
  // setup/payoff markers connected by status-shaped lines), once as the full
  // text rows below (the record — nothing lost, flag don't drop).
  const sp = state.report && state.report.setup_payoff;
  if (sp && sp.length) {
    const sec = el("div", "dock-section");
    sec.appendChild(el("div", "dock-section-title", "Setup / Payoff"));
    sec.appendChild(buildSetupPayoffSpine(sp));
    sp.forEach((e2) => {
      const setScenes = (e2.setup_scenes || []).map((n) => "S" + n).join(", ") || "General";
      const payScenes = (e2.payoff_scenes && e2.payoff_scenes.length) ? e2.payoff_scenes.map((n) => "S" + n).join(", ") : "never";
      const row = el("p", "dock-sp-row", `[${SP_STATUS[e2.status] || e2.status}] ${e2.setup} — set up in ${setScenes}, payoff: ${payScenes}`);
      if (e2.kind) row.appendChild(el("span", "dock-sp-kind", e2.kind));
      if (e2.note) row.appendChild(el("p", "fix-row-why", e2.note));
      sec.appendChild(row);
    });
    lens.appendChild(sec);
  }

  // -- 7. Pacing (per-report pace bars) + Character dials + Writer's Mirror -
  // Same panels the craft shelf and the feedback room render — verbatim.
  const craftWrap = el("div", "dock-section dock-craft");
  renderPacingPanel(craftWrap);
  renderCharacterPanel(craftWrap);
  renderCharacterDialsPanel(craftWrap);
  renderWriterMirrorPanel(craftWrap);
  if (craftWrap.children.length) lens.appendChild(craftWrap);

  // any lens rebuild mid-loop (filter toggle, intent change) wiped the
  // transient bar + card state — re-dock it here (idempotent when inactive)
  renderLoopBar();
}

// ---------- evidence orientation helpers (mass strip / script ruler / sp spine) ----------
// SP_STATUS lives at module scope: the ledger rows print it, the spine
// tooltips announce it — one source, two presentations.
const SP_STATUS = { paid: "✓ Paid off", dangling: "🚩 Dangling", abandoned: "🪦 Abandoned", red_herring: "🪄 Red herring" };

// ---------- the ONE filter predicate (GAP-1 fix, R5-b completed) ----------
// ONE predicate behind ink, board list, loop list and fix queue: a finding
// shows iff its disposition passes (open, or deferred when Next-pass is on)
// AND its severity AND category pass the chips. Every surface reads it, so
// the page and the board cannot disagree (N3 law) — by construction.
function findingPassesFilter(f, index) {
  const d = findingDisposition(f, index);
  if (d === "deferred" ? !state.findingFilter.showDeferred : d !== "open") return false;
  const sev = (f.severity || "low").toLowerCase();
  if (!state.findingFilter.severities.includes(sev)) return false;
  if (state.findingFilter.category && (f.category || "other") !== state.findingFilter.category) return false;
  return true;
}

// ---------- ink (R5-b): the ONE filter drives page ink, board list, loop ----------
// Ink anchors per scene: open findings with quotes that pass the filter,
// highest severity first — one ink per line, several findings collapse to
// one numbered chip (the number = how many collapsed here).
function inkAnchorsFor(findings) {
  const out = [];
  for (const { f, index } of findings || []) {
    const q = (f.evidence_quote || "").trim();
    if (q.length < 2) continue;
    if (!findingPassesFilter(f, index)) continue;
    out.push({ f, index, id: (state.findingIds && state.findingIds[index]) || String(index), q, sev: (f.severity || "low").toLowerCase() });
  }
  const order = { high: 0, medium: 1, low: 2 };
  out.sort((a, b) => (order[a.sev] - order[b.sev]) || (b.q.length - a.q.length));
  return out;
}
// wrap ONE anchor's first occurrence inline — same technique as
// highlightMatches; an inline mark inherits the line's font so text never
// reflows. Returns how many anchors live on this line (the chip count).
// Where does an anchor's quote sit on THIS line? Requiring the WHOLE quote
// inside one line is what made the manuscript render zero ink pins on a real
// report: a quote the model cited across a line wrap (two elements) can never
// be found whole on any single line, and every one of those findings was also
// the dialogue category (GAP-6's last surface). So fall back to the quote's
// longest leading fragment that IS present on the line — a pin's job is to
// point at the line, and the board card carries the full quote. Quote marks are
// stripped per word because a model writes straight quotes where a script may
// have curly ones.
const INK_MIN_WORDS = 3;
const INK_MIN_CHARS = 8;
function inkMatch(text, q) {
  const whole = text.indexOf(q);
  if (whole !== -1) return { idx: whole, len: q.length };
  const words = q.split(/\s+/)
    .map((w) => w.replace(/^[\u201c\u201d"'\u2018\u2019(\[]+|[\u201c\u201d"'\u2018\u2019)\]]+$/g, ""))
    .filter(Boolean);
  for (let n = words.length - 1; n >= INK_MIN_WORDS; n--) {
    const frag = words.slice(0, n).join(" ");
    if (frag.length < INK_MIN_CHARS) break;
    const idx = text.indexOf(frag);
    if (idx !== -1) return { idx, len: frag.length };
  }
  return null;
}
function decorateLineWithInk(line, text, anchors) {
  let hits = 0, first = null, firstMatch = null;
  for (const a of anchors) {
    const m = inkMatch(text, a.q);
    if (m) { hits += 1; if (!first) { first = a; firstMatch = m; } }
  }
  if (!first) return 0;
  const { idx, len } = firstMatch;
  line.textContent = "";
  line.appendChild(document.createTextNode(text.slice(0, idx)));
  const mark = document.createElement("mark");
  mark.className = "finding-ink ink-" + first.sev;
  mark.dataset.findingId = first.id;
  mark.setAttribute("aria-hidden", "true"); // the margin pins + board carry semantics
  mark.title = (first.f.issue || "").slice(0, 140);
  mark.textContent = text.slice(idx, idx + len);
  if (hits > 1) {
    const chip = document.createElement("i");
    chip.className = "ink-chip";
    chip.textContent = "\u00D7" + hits;
    chip.title = hits + " findings share this line";
    mark.appendChild(chip);
  }
  line.appendChild(mark);
  line.appendChild(document.createTextNode(text.slice(idx + len)));
  return hits;
}

// ---------- writer intent (R2-b / R3): one setter, every surface re-renders ----------
async function setFindingIntent(findingId, intent) {
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  try {
    await api(`${base}/findings/intent`, { method: "POST", body: JSON.stringify({ finding_id: findingId, intent }) });
  } catch (e) {
    showError("Could not save your mark: " + e.message);
    return;
  }
  if (intent) state.findingMarks[findingId] = intent;
  else delete state.findingMarks[findingId];
  renderDockEvidence();
  renderManuscript();
  renderSceneIndex();
}

// ---------- arrival (R5-b peek + R9-adjacent unread dot) ----------
// One ambient window per arrival: the first inked line gets a halo, the dock
// tab carries a lasting unread dot until the Evidence lens is opened. No
// other ambience runs during the window (one-ambient-event cap, R8).
let arrivalTimer = null;
function scheduleArrivalPeek() {
  clearTimeout(arrivalTimer);
  arrivalTimer = setTimeout(() => {
    const tab = document.getElementById("dock-tab-evidence");
    if (tab && !(document.getElementById("context-dock") || {}).classList?.contains("open")) {
      tab.classList.add("has-unread");
    }
    const firstInk = document.querySelector(".finding-ink");
    if (firstInk) {
      firstInk.classList.add("ink-halo");
      setTimeout(() => firstInk.classList.remove("ink-halo"), 4000);
    }
  }, 700);
}
function clearEvidenceUnread() {
  const tab = document.getElementById("dock-tab-evidence");
  if (tab) tab.classList.remove("has-unread");
}

// ---------- arrival strip (R4 + N1 + N2): the "finally" ----------
// The pass line ("Pass: 62 → 41 still live · 14 no longer flagged · 7 new") +
// a scope chip + the trust readout + the writer's OWN progress ("Your draft: N
// addressed") + inline retry when the pass arrived partially. GAP-5: the four
// pass numbers are analyzer re-read drift and can never track writer edits —
// the scope chip says so on-screen, and the draft clause carries the
// working-copy truth (observed "addressed") that used to be missing here.
// Ghosted marks expand to a muted list — never red, in no open count (R9).
function buildArrivalStrip() {
  const lp = state.lastPass;
  if (!lp || !lp.computed_at) return null;
  const strip = el("div", "dock-arrival-strip");
  const head = el("div", "dock-arrival-head");
  // GAP-5: these four numbers diff THIS pass against the PREVIOUS one — both
  // read the parse-of-record (orchestrator.py loads m.parsed_path), so writer
  // edits can never move them. Say "Pass:", not "Last pass… Fixed", so the
  // line reads as analyzer drift instead of borrowed writer progress.
  // GAP-7: when the script is byte-identical to the last pass there is no delta
  // to draw, so the four numbers collapse to the report the desk is holding
  // (lp.last_total is the BOARD's row count there, not the previous pass's) and
  // the re-wording clause below names the previous total. A headline that
  // disagreed with the board would be the UI pretending.
  head.appendChild(el("span", "dock-arrival-line",
    `Pass: ${lp.last_total} \u2192 ${lp.still_live} still live \u00B7 ${lp.fixed} no longer flagged \u00B7 ${lp.new} new`));
  const scope = el("span", "dock-arrival-scope", "from the last run, not your edits");
  // GAP-7: on a byte-identical script the pass numbers can only be the model
  // re-wording its own findings. Say that, so "0 no longer flagged" reads as
  // what it is instead of as a quiet draft. The churn is disclosed, never hidden.
  if (lp.same_input) {
    const rwTxt = lp.prev_total
      ? `${lp.rewritten} of the last pass's ${lp.prev_total} DISTINCT findings reworded by the model — your script did not change`
      : `${lp.rewritten} findings reworded by the model — your script did not change`;
    const rw = el("span", "dock-arrival-rewrite", rwTxt);
    rw.title = "The analysis re-read the same script. The wording of its findings moved; your draft did not, so none of this is your progress.";
    head.appendChild(rw);
  }
  scope.title = "These compare one analysis pass to the previous one. They never respond to your edits \u2014 your own progress rides beside them.";
  head.appendChild(scope);
  // GAP-5's honest counterpart: the working-copy truth the pass line cannot
  // carry. Same counting contract as the revision strip (N3) — the writer's
  // number agrees with every other surface. Sits with the pass line (left) so
  // "what the passes say / what you've done" reads in one breath; the
  // secondary quote-trust metric stays pushed right.
  const prog = findingStatusSummary();
  if (prog.addressed || prog.open) {
    head.appendChild(el("span", "dock-arrival-draft",
      `${prog.addressed} of ${prog.addressed + prog.open} addressed by you`));
  }
  const vs = state.report && state.report.verification_summary;
  if (vs) {
    const vTotal = (vs.verified || 0) + (vs.not_found || 0) + (vs.no_quote || 0) + (vs.scene_not_found || 0);
    if (vTotal) head.appendChild(el("span", "dock-trust",
      (vs.verified || 0) + " of " + vTotal + " quotes verified (" + Math.round(100 * (vs.verified || 0) / vTotal) + "%)"));
  }
  strip.appendChild(head);
  // inline retry (N2): the moment a partial arrival is seen is the moment it's fixed
  const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
  const failed = (projSummary && projSummary.failed_categories) || [];
  if (failed.length) {
    const retry = el("button", "dock-arrival-retry");
    retry.type = "button";
    retry.textContent = "Retry failed (" + failed.length + ")";
    retry.title = "Re-run only the failed categories — the report merges";
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      retry.textContent = "Retrying\u2026";
      try {
        await api(`/projects/${encodeURIComponent(state.currentProject)}/analyze/retry-failed`, { method: "POST" });
        await loadScriptData();
        renderDockEvidence();
        renderManuscript();
      } catch (e) {
        retry.disabled = false;
        retry.textContent = "Retry failed";
        showError("Retry failed: " + e.message);
      }
    });
    strip.appendChild(retry);
  }
  // ghosted: the writer's marks that transformed — muted, expandable, never red
  const ghosted = lp.ghosted_marks || [];
  if (ghosted.length) {
    const det = el("details", "dock-ghosted");
    det.appendChild(el("summary", "dock-ghosted-summary", ghosted.length + " of your marks moved on"));
    for (const g of ghosted) {
      const r = el("div", "dock-ghosted-row");
      r.appendChild(el("span", "dock-ghosted-issue", (g.issue || "finding").slice(0, 110)));
      if (g.intent) r.appendChild(el("span", "dock-ghosted-intent", g.intent === "addressed" ? "was marked addressed" : "was next pass"));
      det.appendChild(r);
    }
    strip.appendChild(det);
  }
  return strip;
}

// ---------- the keyboard fix loop (R2-b, contextual keys per 2A) ----------
// When engaged, N/↓ step findings and P/↑ steps back — scene-stepping
// muscle memory is untouched the moment the loop exits (Esc).
const loopState = { active: false, pos: -1 };
function loopList() {
  const out = [];
  (state.findings || []).forEach((f, index) => {
    if (!findingPassesFilter(f, index)) return;
    out.push({ f, index, id: (state.findingIds && state.findingIds[index]) || String(index) });
  });
  return out;
}
function startLoop() {
  if (!state.findings || !state.findings.length) return;
  loopState.active = true;
  loopState.pos = -1;
  openDock("evidence");
  renderLoopBar();
  stepLoop(1);
}
function exitLoop() {
  loopState.active = false;
  loopState.pos = -1;
  renderLoopBar();
}
function stepLoop(dir) {
  const list = loopList();
  if (!list.length) return;
  loopState.pos = (loopState.pos + dir + list.length) % list.length; // wrap — no dead ends
  const { f, index, id } = list[loopState.pos];
  // span-level first: the ink anchor; scene-level fallback (cross-line quotes)
  const ink = document.querySelector(`.finding-ink[data-finding-id="${CSS.escape(id)}"]`);
  if (ink) {
    ink.scrollIntoView({ behavior: "smooth", block: "center" });
    ink.classList.remove("flash");
    void ink.offsetWidth; // restart the animation
    ink.classList.add("flash");
    setTimeout(() => ink.classList.remove("flash"), 1600);
  } else {
    jumpToScene(findingTargetScene(f));
  }
  // chip auto-open: the dock card expands to the same finding
  const card = document.querySelector(`.dock-lens[data-lens="evidence"] .finding-note[data-finding-index="${index}"]`);
  if (card) {
    card.classList.add("expanded", "loop-current");
    card.scrollIntoView({ block: "nearest" });
    document.querySelectorAll(".dock-lens[data-lens=\"evidence\"] .finding-note.loop-current").forEach((n) => {
      if (n !== card) n.classList.remove("loop-current");
    });
  }
  renderLoopBar();
}
function renderLoopBar() {
  const old = document.getElementById("loop-bar");
  if (old) old.remove();
  if (!loopState.active) return;
  const list = loopList();
  // a filter change mid-loop can shrink the list past pos — the bar never
  // lies; the next step normalizes state.pos through the wrap math
  const shownPos = list.length ? Math.min(loopState.pos, list.length - 1) : -1;
  const bar = el("div", "loop-bar");
  bar.id = "loop-bar";
  bar.appendChild(el("span", "loop-pos", list.length ? (shownPos + 1) + " of " + list.length : "none open"));
  const mk = (label, title, fn) => {
    const b = el("button", "loop-btn");
    b.type = "button";
    b.textContent = label;
    b.title = title;
    b.addEventListener("click", fn);
    return b;
  };
  bar.appendChild(mk("\u2191", "Previous finding (P)", () => stepLoop(-1)));
  bar.appendChild(mk("\u2193", "Next finding (N)", () => stepLoop(1)));
  const cur = loopList()[shownPos];
  if (cur) {
    bar.appendChild(mk("\u2713 addressed", "Mark addressed (the writer's call — survives re-analysis)",
      () => setFindingIntent(cur.id, state.findingMarks[cur.id] === "addressed" ? null : "addressed")));
    bar.appendChild(mk("\u23ED next pass", "Park it for the next pass (R3)",
      () => setFindingIntent(cur.id, state.findingMarks[cur.id] === "deferred" ? null : "deferred")));
    bar.appendChild(mk("\u{1F4AC} discuss", "Ask Sameer about this exact line",
      () => { setPendingQuote({ scene_number: findingTargetScene(cur.f), text: cur.f.evidence_quote || cur.f.issue || "" }); setDockLens("sameer"); }));
    bar.appendChild(mk("\u29C9 copy", "Copy the evidence + scene slug (R7)", () => copyFindingEvidence(cur.f)));
  }
  bar.appendChild(mk("esc", "Leave the loop — N goes back to next-scene", exitLoop));
  const lens = document.querySelector('.dock-lens[data-lens="evidence"]');
  if (lens) lens.prepend(bar);
  // transient card state rides the re-render: re-dock the current expansion
  if (cur) {
    const card = document.querySelector(`.dock-lens[data-lens="evidence"] .finding-note[data-finding-index="${cur.index}"]`);
    if (card) card.classList.add("expanded", "loop-current");
  }
}
function copyFindingEvidence(f) {
  const sc = findingTargetScene(f);
  const scene = sc != null ? (state.script.scenes || []).find((s) => s.scene_number === sc) : null;
  const text = (f.evidence_quote || f.issue || "") + (sc != null ? `\n\u2014 Scene ${sc}${scene && scene.heading_raw ? " (" + scene.heading_raw + ")" : ""}` : "");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => {});
  } else {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (_) { /* clipboard unavailable */ }
    ta.remove();
  }
}

// ---------- content-hash finding identity (R1 refined) ----------
// `_strHash` / `_base36` / `computeFindingId` live in core.js: they are
// DOM-free pure helpers and core.js is the home for those, which is what makes
// them unit-testable under `node --test` instead of reachable only through a
// browser. core.js loads first (index.html:765), so they are still plain
// globals here — and they MUST stay byte-identical to `revision.py`'s
// `compute_finding_id`, which `tests/e2e_browser_finding_id_parity.py` proves.

// ---------- the finding counting contract (N3) ----------
// ONE source for disposition (open / addressed / deferred / ghosted /
// dismissed). Every counting surface — mass strip, script ruler, scene
// index counts, summary, fix queue, keyboard loop — reads this; the
// writer's totals cannot disagree between surfaces. Deferred (client
// intent) and ghosted (server-observed drift) stores are forward-compatible
// hooks for Phase D/E; today they resolve empty and count exactly as
// before, which the live probe verifies.
function findingDisposition(f, index) {
  const id = (state.findingIds && state.findingIds[index]) || String(index);
  const st = state.findingStatus || {};
  const status = st[id] != null ? st[id] : (st[String(index)] != null ? st[String(index)] : st[index]);
  if (status === "addressed") return "addressed";
  const intent = state.findingMarks && state.findingMarks[id];
  if (intent === "deferred") return "deferred";
  if (intent === "addressed") return "addressed";
  if (state.ghostedIds && state.ghostedIds.has(id)) return "ghosted";
  if (isFindingDismissed(index, id)) return "dismissed";
  return "open";
}
function findingOpen(f, index) {
  return findingDisposition(f, index) === "open";
}
/** The ONE filter predicate (severity + category). The mass strip and the fix
 *  queue both read it, so the two scopes can never drift apart. Fix-queue items
 *  carry the same two fields, so they pass through it unchanged. */
function inFindingFilter(f) {
  const sev = ((f && f.severity) || "low").toLowerCase();
  if (!state.findingFilter.severities.includes(sev)) return false;
  if (state.findingFilter.category && ((f && f.category) || "other") !== state.findingFilter.category) return false;
  return true;
}
/** Scope + disposition counts — the second half of the N3 counting contract.
 *  `total`/`open` describe the WHOLE script; `shown`/`openShown` describe what
 *  the ONE filter currently admits. Every surface must print which scope it
 *  shows, so a whole-script total can never be read as a filtered one (the
 *  "6 open of 6 findings" over "0 shown / 6 total" contradiction). */
function findingCounts() {
  const findings = state.findings || [];
  const c = { total: findings.length, open: 0, shown: 0, openShown: 0 };
  findings.forEach((f, index) => {
    const isOpen = findingOpen(f, index);
    if (isOpen) c.open += 1;
    if (inFindingFilter(f)) {
      c.shown += 1;
      if (isOpen) c.openShown += 1;
    }
  });
  return c;
}
function isFindingDismissed(index, id) {
  const flags = (state.fixQueue && state.fixQueue.dismissed_flags) || [];
  return flags.some((d) => (id && d.finding_id === id) || d.index === index);
}
// the module's status read, exposed for surfaces that need the raw
// addressed/still_present/unknown judgment (never for counting — count via
// findingDisposition/findingOpen so totals cannot disagree)
function findingStatusOf(f, index) {
  const st = state.findingStatus || {};
  const id = (state.findingIds && state.findingIds[index]) || String(index);
  return st[id] != null ? st[id] : (st[String(index)] != null ? st[String(index)] : st[index]);
}

/** The ONE filter row (R5-b + R8, GAP-1 completed): severity toggles +
 *  category count-chips + the next-pass toggle. Every surface (ink, board
 *  list, loop list, fix queue) reads the same state.findingFilter through
 *  findingPassesFilter — the page and the board cannot disagree. Category
 *  chips count open findings (severity-agnostic orientation); dismissed
 *  rows keep their own separate toggle in the queue. */
function buildFindingFilterRow() {
  const row = el("div", "dock-filter-row");
  const mk = (label, active, title, onClick) => {
    const c = el("button", "fchip" + (active ? " active" : ""));
    c.type = "button";
    c.textContent = label;
    c.title = title;
    c.setAttribute("aria-pressed", active ? "true" : "false");
    c.addEventListener("click", onClick);
    return c;
  };
  const rerender = () => { renderDockEvidence(); renderManuscript(); };
  for (const s of ["high", "medium", "low"]) {
    const on = state.findingFilter.severities.includes(s);
    row.appendChild(mk(s[0].toUpperCase() + s.slice(1), on, (on ? "Inked on the page" : "Hidden from the page") + " — click to toggle", () => {
      const i = state.findingFilter.severities.indexOf(s);
      if (i >= 0) state.findingFilter.severities.splice(i, 1);
      else state.findingFilter.severities.push(s);
      if (!state.findingFilter.severities.length) state.findingFilter.severities.push(s); // never all-off
      rerender();
    }));
  }
  // category count-chips: counts over open findings (severity-agnostic),
  // tap filters the board list + ink to that category, tap again clears
  const catCounts = {};
  (state.findings || []).forEach((f, index) => {
    if (findingDisposition(f, index) !== "open") return;
    const c = f.category || "other";
    catCounts[c] = (catCounts[c] || 0) + 1;
  });
  for (const c of Object.keys(catCounts).sort((a, b) => catCounts[b] - catCounts[a])) {
    const active = state.findingFilter.category === c;
    row.appendChild(mk((CATEGORY_LABELS[c] || c) + " " + catCounts[c], active,
      (active ? "Showing all categories" : "Show only " + (CATEGORY_LABELS[c] || c)),
      () => { state.findingFilter.category = active ? null : c; rerender(); }));
  }
  const dp = state.findingFilter.showDeferred;
  row.appendChild(mk("Next pass", dp, dp ? "Deferred findings shown" : "Deferred findings parked", () => {
    state.findingFilter.showDeferred = !dp;
    rerender();
  }));
  return row;
}

/** Whole-script orientation strip: open/total + severity mass + category
 *  weights + the trust readout (verification_summary ships in the report and
 *  rendered nowhere else). Static by design — orientation, not interaction. */
function buildScriptMassStrip() {
  const strip = el("div", "dock-mass-strip");
  const findings = state.findings || [];
  if (!findings.length) return strip;
  const open = (f, index) => findingOpen(f, index);
  const sev = { high: 0, medium: 0, low: 0 };
  const cat = {};
  let openTotal = 0;
  findings.forEach((f, index) => {
    if (!open(f, index)) return;
    openTotal += 1;
    const s = (f.severity || "low").toLowerCase();
    if (sev[s] != null) sev[s] += 1;
    const c = f.category || "other";
    cat[c] = (cat[c] || 0) + 1;
  });
  if (!openTotal) return strip;
  const head = el("div", "dock-mass-head");
  // scope honesty: this strip always describes the WHOLE script. When the ONE
  // filter narrows the view, it says how much of the total is in view — without
  // that, "6 open of 6" reads as a claim about the filtered board below it.
  const mV = findingCounts();
  const mText = openTotal + " open of " + findings.length + " findings" +
    (mV.shown < mV.total ? " \u00B7 " + mV.openShown + " shown by filter" : "");
  head.appendChild(el("span", "dock-mass-total", mText));
  // Trust readout: only findings that CARRY a quote can be verified, so
  // `no_quote` findings must not sit in the denominator. Counting them turned
  // the demo report (every finding no_quote) into a red-looking "0 of 6 quotes
  // verified (0%)" — which reads as the analysis failing rather than as "there
  // was nothing to check" (UI audit 2026-09-20, defect #10).
  const vs = state.report && state.report.verification_summary;
  if (vs) {
    const checkable = (vs.verified || 0) + (vs.not_found || 0) + (vs.scene_not_found || 0);
    const unquoted = vs.no_quote || 0;
    if (checkable) {
      const pct = Math.round(100 * (vs.verified || 0) / checkable);
      head.appendChild(el("span", "dock-trust",
        (vs.verified || 0) + " of " + checkable + " quotes verified (" + pct + "%)" +
        (unquoted ? " \u00B7 " + unquoted + " carried no quote" : "")));
    } else if (unquoted) {
      head.appendChild(el("span", "dock-trust",
        unquoted + " finding" + (unquoted === 1 ? "" : "s") + " carried no quote to verify"));
    }
  }
  strip.appendChild(head);
  // severity mass: dots + printed counts — never color-alone
  const mass = el("div", "dock-mass-sev");
  for (const s of ["high", "medium", "low"]) {
    if (!sev[s]) continue;
    const m = el("span", "dock-mass-mark");
    m.title = sev[s] + " " + s;
    m.appendChild(el("i", "sev-dot " + s));
    m.appendChild(el("span", "dock-mass-count", String(sev[s])));
    mass.appendChild(m);
  }
  strip.appendChild(mass);
  // category weights: single-hue stacked bar (decorative, aria-hidden) with
  // the printed counts row beneath — same pattern as scene-index dots
  const catKeys = Object.keys(cat).sort((a, b) => cat[b] - cat[a]);
  if (catKeys.length) {
    const bar = el("div", "dock-mass-cat");
    bar.setAttribute("aria-hidden", "true");
    for (const c of catKeys) {
      const seg = el("span", "dock-mass-cat-seg");
      seg.style.width = (100 * cat[c] / openTotal) + "%";
      bar.appendChild(seg);
    }
    strip.appendChild(bar);
    strip.appendChild(el("div", "dock-mass-cat-row", catKeys.map((c) => (CATEGORY_LABELS[c] || c) + " " + cat[c]).join(" \u00B7 ")));
  }
  return strip;
}

/** Script ruler: one tick per scene; tick weight = open findings; the tick
 *  the writer is reading carries the current marker. Orientation read of
 *  where the diagnostic weight sits — the Scene Index stays the navigator. */
function buildScriptRuler() {
  const scenes = (state.script && state.script.scenes) || [];
  if (!scenes.length) return document.createDocumentFragment();
  const ruler = el("div", "dock-ruler");
  ruler.appendChild(el("div", "dock-ruler-title", "Diagnostic weight by scene"));
  const track = el("div", "dock-ruler-track");
  for (const scene of scenes) {
    const counts = sceneIndexSeverity(scene.scene_number);
    const total = counts.high + counts.medium + counts.low;
    const tick = el("button", "dock-ruler-tick" + (total ? " hot" : "") +
      (counts.high ? " sev-high" : counts.medium ? " sev-medium" : counts.low ? " sev-low" : ""));
    tick.type = "button";
    tick.dataset.sceneNumber = String(scene.scene_number);
    const label = "S" + scene.scene_number + " \u2014 " + (scene.heading_raw || "").slice(0, 60) +
      (total ? " (" + counts.high + " high \u00B7 " + counts.medium + " medium \u00B7 " + counts.low + " low)" : " clean");
    tick.title = label;
    tick.setAttribute("aria-label", label);
    const stem = el("i", "dock-ruler-stem");
    stem.style.height = Math.min(26, 4 + total * 5) + "px";
    tick.appendChild(stem);
    tick.addEventListener("click", () => jumpToScene(scene.scene_number));
    track.appendChild(tick);
  }
  ruler.appendChild(track);
  return ruler;
}

/** Mark the ruler tick the writer is currently reading (cheap: class only —
 *  called from the scene-tracking scroll hook and the full evidence render). */
function refreshDockRulerMarker() {
  const track = document.querySelector(".dock-ruler-track");
  if (!track) return;
  const now = String(currentManuscriptScene());
  track.querySelectorAll(".dock-ruler-tick").forEach((t) => {
    t.classList.toggle("current", t.dataset.sceneNumber === now);
  });
}

/** Setup/Payoff spine: the ledger's promise structure on a scene scale —
 *  setup ● and payoff ◆ markers, connected by status-shaped lines (solid =
 *  paid, dashed = red herring, dotted = abandoned, missing + ghost ✗ =
 *  dangling). Markers jump to their scenes; the text rows below remain the
 *  record (flag don't drop). */
function buildSetupPayoffSpine(sp) {
  const frag = document.createDocumentFragment();
  const scenes = (state.script && state.script.scenes) || [];
  const maxScene = scenes.length ? Math.max(...scenes.map((s) => s.scene_number)) : 0;
  if (!maxScene) return frag;
  const spine = el("div", "dock-sp-spine");
  const pct = (n) => Math.max(1, Math.min(99, 100 * n / maxScene));
  sp.forEach((e2) => {
    const setScenes = e2.setup_scenes || [];
    const payScenes = e2.payoff_scenes || [];
    const setupN = setScenes.length ? Math.min(setScenes[0], maxScene) : null;
    const payoffN = payScenes.length ? Math.min(payScenes[payScenes.length - 1], maxScene) : null;
    const line = el("div", "dock-sp-line " + (e2.status || ""));
    line.title = (e2.note || e2.setup || "").slice(0, 200);
    if (setupN != null && payoffN != null) {
      const conn = el("i", "dock-sp-conn " + (e2.status || ""));
      conn.style.left = pct(setupN) + "%";
      conn.style.width = Math.max(0, pct(payoffN) - pct(setupN)) + "%";
      line.appendChild(conn);
    }
    if (setupN != null) {
      const mk = el("button", "dock-sp-mk setup");
      mk.type = "button";
      mk.style.left = pct(setupN) + "%";
      mk.title = "Setup \u00B7 S" + setupN + " \u00B7 " + (e2.setup || "").slice(0, 120);
      mk.setAttribute("aria-label", mk.title);
      mk.textContent = "\u25CF";
      mk.addEventListener("click", () => jumpToScene(setupN));
      line.appendChild(mk);
    }
    if (payoffN != null) {
      const mk = el("button", "dock-sp-mk payoff");
      mk.type = "button";
      mk.style.left = pct(payoffN) + "%";
      mk.title = "Payoff \u00B7 S" + payoffN + " \u00B7 " + (SP_STATUS[e2.status] || e2.status);
      mk.setAttribute("aria-label", mk.title);
      mk.textContent = "\u25C6";
      mk.addEventListener("click", () => jumpToScene(payoffN));
      line.appendChild(mk);
    } else if (e2.status === "dangling") {
      const brk = el("i", "dock-sp-mk ghost");
      brk.style.left = "97%";
      brk.textContent = "\u00D7";
      line.appendChild(brk);
    }
    spine.appendChild(line);
  });
  const scale = el("div", "dock-sp-scale");
  const step = Math.max(1, Math.round(maxScene / 8));
  for (let n = 1; n <= maxScene; n += step) scale.appendChild(el("span", "dock-sp-tick", "S" + n));
  spine.appendChild(scale);
  frag.appendChild(spine);
  return frag;
}

/** Central refresh hook — called from the renderManuscript tail and after
 *  analysis/retry/reparse. No-ops when the dock is closed or on another
 *  lens, so legacy flows pay ~nothing when the dock isn't watching. */
function refreshDockEvidence() {
  if (!dockIsOpen() || dockLens !== "evidence") return;
  renderDockEvidence();
}

// ---------- Phase 7: Sameer / Sushruta — conversation lenses ----------
// The dock ADOPTS the live conversation DOM (portal re-parenting) instead of
// duplicating it: #cowrite-panel's messages+composer move into the Sameer
// lens slot while the dock is open, and return to the room panel on close.
// Every contract survives because the same nodes keep their IDs, listeners,
// streaming sinks, rail, and branch wiring — no second store, no forked
// send path, and never two chat columns at once (the room panel is emptied
// while the dock holds the conversation).

let _dockChatAdopted = null; // "sameer" | "sushruta" | null

/** The room needs its conversation back — the dock steps aside entirely
 *  (same convention as the Phase 6 Discuss handoff: one partner at a time
 *  beside the page). No-op when no chat lens is adopted. */
function dockYieldToRoom() {
  if (_dockChatAdopted) closeDock(); // closeDock returns the conversation
}

function dockChatSlot(lens) {
  return document.querySelector(`.dock-lens[data-lens="${lens}"] .dock-chat-slot`);
}

/** Move the live conversation surface into the dock lens. */
function adoptChatIntoDock(lens) {
  if (_dockChatAdopted === lens) return;
  if (_dockChatAdopted) returnChatFromDock(); // never two adopted surfaces
  const slot = dockChatSlot(lens);
  if (!slot) return;
  const fallback = slot.parentElement.querySelector(".dock-chat-fallback");
  if (!state.currentProject) {
    if (fallback) fallback.hidden = false;
    // P0.1: the consult column lives in the sushruta slot permanently — with
    // no project the lens shows its honest hint, not empty doctor chrome
    const parked = slot.querySelector(".fv-consult");
    if (parked) parked.style.display = "none";
    return; // no project: the lens keeps its honest hint
  }
  if (fallback) fallback.hidden = true;

  // Sameer lens adopts the co-write conversation (messages + rail + composer).
  // The Sushruta lens needs no adoption: the consultant's chat column lives
  // permanently in the dock's sushruta slot — P0.1 deleted its old host, the
  // dormant #feedback-view clone.
  if (lens === "sameer") {
    const panel = document.getElementById("cowrite-panel");
    if (!panel) return;
    slot.appendChild(panel); // the whole panel moves; IDs + listeners ride along
    panel.classList.add("dock-adopted-away");
  } else if (lens === "sushruta") {
    const consult = slot.querySelector(".fv-consult");
    if (consult) consult.style.display = ""; // un-parked (see the no-project branch)
    renderFvChat("fv-consult-messages", "consult"); // refresh on lens entry
  }
  _dockChatAdopted = lens;
  // persona contract: the lens IS the partner — Sameer lens speaks as the
  // writing partner, Sushruta lens as the script consultant. Set on the
  // live session so the backend prompt follows the lens.
  dockLensPersona(lens);
}

/** Return the adopted conversation to its room panel. */
function returnChatFromDock() {
  if (!_dockChatAdopted) return;
  const lens = _dockChatAdopted;
  const slot = dockChatSlot(lens);
  if (!slot) { _dockChatAdopted = null; return; }
  if (lens === "sameer") {
    const panel = document.getElementById("cowrite-panel");
    if (panel) {
      panel.classList.remove("dock-adopted-away");
      // home is inside #room-drawer (between drawer-head and feedback-panel)
      const drawer = document.getElementById("room-drawer");
      if (drawer) {
        const fb = document.getElementById("feedback-panel");
        if (fb) drawer.insertBefore(panel, fb);
        else drawer.appendChild(panel);
      } else slot.appendChild(panel); // no home (early boot) — stay in-slot
      panel.style.display = ""; // setRoom decides visibility again
    }
  } else if (lens === "sushruta") {
    // the consult column's home IS the dock slot (P0.1) — nothing moves back
  }
  _dockChatAdopted = null;
}

/** Lens ↔ persona: switching lenses switches WHO answers. Uses the existing
 *  settings endpoint; keeps mode untouched. */
async function dockLensPersona(lens) {
  const persona = lens === "sushruta" ? "script_consultant" : "writing_partner";
  // switch persona ONLY on the live session — no fork, no second store
  try {
    if (state.currentSession && state.branches[state.currentBranch] &&
        state.branches[state.currentBranch].active_persona !== persona) {
      await _setPersonaMode(persona, state.branches[state.currentBranch].active_mode || "peer");
      renderMessages();
    }
  } catch (e) { /* persona switch is best-effort; the conversation still works */ }
}

async function hideAllViews() {
  // full-screen tools only — the rooms are handled by setRoom()
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  $("#revision-view").style.display = "none";
  $("#premise-view").style.display = "none";
  const ws = document.querySelector(".workspace");
  if (ws) ws.style.display = "none";
}

// The script pane is always visible now; kept as a thin alias so callers
// (palette commands, session restore) that used to "open the script view"
// simply ensure the shared pane is loaded and rendered.
async function openScriptView() {
  if (state.view === "cowrite" || state.view === "feedback") return;
  openCowriteRoom();
  try {
    await loadScriptData();
  } catch (e) {
    showError("Couldn't load the script: " + e.message);
  }
  renderManuscript(document.getElementById('manuscript-container'));
}

function discussFinding(f, index) {
  openCowriteRoom();
  const refs = (f.scene_refs || []).map((n) => "Scene " + n).join(", ") || "the whole script";
  const sceneNumber = (f.scene_refs || [])[0] || null;
  const quoteText = f.evidence_quote || f.issue;
  if (quoteText) setPendingQuote({ scene_number: sceneNumber, text: quoteText });
  $("#input").value = `About the note on ${refs}: how should I approach fixing it?`;
  autoResizeTextarea();
  $("#input").focus();
}

// GAP-4: the escalation route — one gesture from a finding card to Dr.
// Sushruta WITH the finding in hand. Pins the quote (so the consult turn
// rides it into the doctor's context), opens the doctor's lens (the persona
// switch is the lens contract), and seeds the "why" question the writer
// was about to type.
function discussWithDoctor(f, index) {
  const sceneNumber = (f.scene_refs || [])[0] || null;
  const quoteText = f.evidence_quote || f.issue;
  if (quoteText) setPendingQuote({ scene_number: sceneNumber, text: quoteText });
  openDock("sushruta");
  const input = document.getElementById("fv-consult-input");
  if (input) {
    const cat = CATEGORY_LABELS[f.category] || f.category || "this";
    input.value = `Why was the ${cat.toLowerCase()} finding on ${sceneNumber != null ? "Scene " + sceneNumber : "the whole script"} flagged? What exactly is wrong?`;
    input.focus();
    const ev = new Event("input", { bubbles: true });
    input.dispatchEvent(ev);
  }
}

let welcomeShownFor = null;
function maybeShowWelcome() {
  if (!state.currentProject) return;
  if (welcomeShownFor === state.currentProject) return;
  welcomeShownFor = state.currentProject;
  const container = $("#messages-scroll");
  if (!container) return;
  const branch = currentBranchData();
  if ((branch.messages || []).length > 0) return;
  if (!container.querySelector(".chat-empty-hint")) {
    container.appendChild(el("div", "chat-empty-hint", "Sameer: Hey — I'm here. What are we working on?"));
  }
}

async function loadFeedbackPanels() {
  // NOTE: no leading /api here — the api() wrapper already prefixes API = "/api";
  // a doubled prefix 404s and the room shows "No analysis yet" after a good run
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  try {
    if (!state.report) state.report = await api(`${base}/report`);
  } catch (_) { /* no analysis yet */ }
  try {
    if (!state.fixQueue) state.fixQueue = await api(`${base}/fixqueue`);
  } catch (_) { /* no analysis yet */ }
  // partial-analysis recovery: offer a one-click retry when categories failed
  const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
  const failedCats = (projSummary && projSummary.failed_categories) || [];
  const retryBtn = $("#retry-failed-btn");
  if (retryBtn) {
    retryBtn.style.display = failedCats.length ? "inline-block" : "none";
    if (failedCats.length) retryBtn.textContent = `⚠ Retry failed (${failedCats.length})`;
  }
  const hasReport = !!(state.report && (state.report.findings || state.report.coverage));
  const empty = $("#feedback-empty");
  const tabs = $("#feedback-tabs");
  if (empty) empty.style.display = hasReport ? "none" : "block";
  if (tabs) tabs.style.display = hasReport ? "flex" : "none";
  if (hasReport) {
    renderReportPanel();
    const fq = $("#feedback-fixqueue");
    if (fq) {
      fq.innerHTML = "";
      renderFixQueuePanel(fq);   // existing function, reused verbatim
    }
    switchFeedbackTab("report");  // show the Report pane (both panes start hidden)
  }
}

function switchFeedbackTab(tab) {
  const reportBtn = $("#tab-report-btn");
  const fqBtn = $("#tab-fixqueue-btn");
  const report = $("#feedback-report");
  const fq = $("#feedback-fixqueue");
  if (reportBtn) reportBtn.classList.toggle("active", tab === "report");
  if (fqBtn) fqBtn.classList.toggle("active", tab === "fixqueue");
  if (report) report.style.display = tab === "report" ? "block" : "none";
  if (fq) fq.style.display = tab === "fixqueue" ? "block" : "none";
  // self-heal: a tab should never show a blank pane — if the target is empty
  // but data exists in memory, render it now (e.g. a render was skipped when
  // the room opened before the report fetch landed)
  if (tab === "fixqueue" && fq && !fq.children.length && state.fixQueue) {
    renderFixQueuePanel(fq);
  }
}

function renderReportPanel() {
  const c = $("#feedback-report");
  if (!c) return;
  // the doctor's report is the writer's document — let them take it away
  const exp = $("#report-export-btn");
  if (exp && state.currentProject && state.report) {
    exp.href = `/api/projects/${encodeURIComponent(state.currentProject)}/report/export`;
    exp.download = `${state.currentProject}-report.md`;
    exp.style.display = "";
  } else if (exp) exp.style.display = "none";
  c.innerHTML = "";
  const cov = state.report && state.report.coverage;
  if (cov) {
    const card = el("div", "craft-panel");
    const head = el("div", "craft-panel-head");
    head.appendChild(el("span", "craft-panel-title", `Coverage — ${(cov.recommendation || "").toUpperCase()}`));
    card.appendChild(head);
    if (cov.logline) card.appendChild(el("p", "", `Logline: ${cov.logline}`));
    if (cov.one_page_synopsis) card.appendChild(el("p", "", cov.one_page_synopsis));
    (cov.weaknesses || []).forEach((w) => card.appendChild(el("p", "fix-row-why", `• ${w}`)));
    c.appendChild(card);
  }
  // Setup / Payoff — the end-of-pipeline whole-script audit (paid / dangling /
  // abandoned / red herring). Rendered as its own card above the findings.
  const sp = state.report && state.report.setup_payoff;
  if (sp && sp.length) {
    const spCard = el("div", "craft-panel");
    const spHead = el("div", "craft-panel-head");
    spHead.appendChild(el("span", "craft-panel-title", "Setup / Payoff"));
    spCard.appendChild(spHead);
    sp.forEach((e) => {
      const setScenes = (e.setup_scenes || []).map((n) => "S" + n).join(", ") || "General";
      const payScenes = (e.payoff_scenes && e.payoff_scenes.length) ? e.payoff_scenes.map((n) => "S" + n).join(", ") : "never";
      const row = el("p", "fix-row-issue", `[${SP_STATUS[e.status] || e.status}] ${e.setup} — set up in ${setScenes}, payoff: ${payScenes}`);
      if (e.note) row.appendChild(el("p", "fix-row-why", e.note));
      spCard.appendChild(row);
    });
    c.appendChild(spCard);
  }

  // Pacing — the per-scene pace index as an SVG line. Scene numbers on the
  // x-axis, drags flagged in amber, click a bar to jump to that scene.
  const pacing = state.report && state.report.pacing;
  if (pacing && pacing.length) {
    const paceCard = el("div", "craft-panel");
    const paceHead = el("div", "craft-panel-head");
    paceHead.appendChild(el("span", "craft-panel-title", "Pacing — where the script drags"));
    paceCard.appendChild(paceHead);
    const W = 720, H = 170, pad = 30;
    const scores = pacing.map((r) => r.pace_score || 0);
    const maxScore = Math.max(68, ...scores);
    const barW = (W - pad - 10) / pacing.length;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pace per scene; flagged scenes are drags" class="pacing-svg">`;
    svg += `<line x1="${pad}" y1="${H - 34 - (68 / maxScore) * (H - 60)}" x2="${W - 6}" y2="${H - 34 - (68 / maxScore) * (H - 60)}" class="pace-drag-line"/>`;
    pacing.forEach((r, i) => {
      const x = pad + i * barW;
      const h = Math.max(2, (r.pace_score / maxScore) * (H - 60));
      const y = H - 34 - h;
      const cls = r.drag ? "bar-pace drag" : "bar-pace";
      svg += `<rect data-scene="${r.scene_number}" class="${cls}" x="${x}" y="${y}" width="${barW - 3}" height="${h}"><title>Scene ${r.scene_number} — pace ${r.pace_score}/100${r.drag ? " (drag)" : ""}</title></rect>`;
      if (pacing.length <= 26) svg += `<text x="${x + barW / 2}" y="${H - 14}" class="bar-label">${r.scene_number}</text>`;
    });
    svg += `</svg>`;
    const body = el("div", "pacing-body");
    body.innerHTML = svg;
    body.addEventListener("click", (ev) => {
      const rect = ev.target.closest(".bar-pace");
      if (rect && rect.dataset.scene) jumpToScene(Number(rect.dataset.scene));
    });
    paceCard.appendChild(body);
    const legend = el("p", "pacing-legend", "Amber bars = pace drags (long, low-movement scenes). Click a bar to jump to the scene. The dashed line is the drag threshold.");
    paceCard.appendChild(legend);
    c.appendChild(paceCard);
  }

  // Character dials -- the ONE shared panel (re-homed out of the dead
  // #struct-rail by the 2026-09-19 gaps pass; it used to render only here
  // and in the rail, so the live desk had none).
  renderCharacterDialsPanel(c);

  // Writer's Mirror — how the premise lands in one sentence + how each
  // character reads to a stranger. Same panel as the craft shelf, reused
  // verbatim so the doctor's desk carries the whole analysis.
  renderWriterMirrorPanel(c);

  const byCat = {};
  (state.report.findings || []).forEach((f) => { (byCat[f.category] = byCat[f.category] || []).push(f); });
  for (const [cat, list] of Object.entries(byCat)) {
    const card = el("div", "craft-panel");
    const head = el("div", "craft-panel-head");
    head.appendChild(el("span", "craft-panel-title", CATEGORY_LABELS[cat] || cat));
    card.appendChild(head);
    list.forEach((f) => {
      const refs = (f.scene_refs || []).map((n) => "Scene " + n).join(", ") || "General";
      const issue = el("p", "fix-row-issue", `[${(f.severity || "low").toUpperCase()}] ${refs}: ${f.issue}`);
      if (f.why_it_matters) issue.appendChild(el("p", "fix-row-why", f.why_it_matters));
      const rowBtns = el("span", "fix-row-locate", "🎯 Locate");
      rowBtns.title = "Jump to the exact line in the script";
      rowBtns.style.cursor = "pointer";
      rowBtns.addEventListener("click", () => locateFinding(f));
      issue.appendChild(rowBtns);
      card.appendChild(issue);
    });
    c.appendChild(card);
  }
}

// ---- compare (side-by-side drafts) ----

let compareFrom = "original";
let comparePrevRoom = "cowrite";

async function openCompareView() {
  if (state.view === "compare") return;
  exitSpotlight();
  comparePrevRoom = state.view === "cowrite" || state.view === "feedback" ? state.view : "cowrite";
  state.view = "compare";
  hideAllViews();
  $("#compare-view").style.display = "flex";
  try {
    await loadCompare();
  } catch (e) {
    showError("Couldn't load the comparison: " + e.message);
  }
  saveSession();
}

function closeCompareView() {
  setRoom(comparePrevRoom);
}

async function loadCompare() {
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  try { state.drafts = await api(`${base}/drafts`); } catch (_) { state.drafts = { drafts: [], active_draft: null }; }
  const drafts = state.drafts;
  const sel = $("#compare-from-select");
  const active = drafts.active_draft || "original";
  const options = ["original"];
  for (const d of drafts.drafts || []) if (d.name !== active) options.push(d.name);
  if (!options.includes(compareFrom)) compareFrom = options[0];
  sel.innerHTML = "";
  for (const o of options) {
    sel.appendChild(new Option(o, o, false, o === compareFrom));
  }
  sel.value = compareFrom;
  $("#compare-to-label").textContent = active;

  // nothing to compare against — one draft and no snapshots of the original.
  // Say so in the pane instead of a bare 400 toast over an empty screen.
  if (!(drafts.drafts || []).length && compareFrom === "original" && active === "original") {
    const pane = $("#compare-panes");
    pane.innerHTML = "";
    pane.appendChild(el("p", "script-empty-hint",
      "Nothing to compare yet — this project has a single draft. Upload a new draft (Draft bar → \u201c+ Upload new draft\u201d) and the side-by-side diff will appear here."));
    return;
  }

  try {
    const data = await api(`${base}/compare?from=${encodeURIComponent(compareFrom)}&to=active`);
    renderCompare(data);
  } catch (e) {
    const pane = $("#compare-panes");
    pane.innerHTML = "";
    pane.appendChild(el("p", "script-empty-hint",
      `Couldn't build the comparison: ${e.message}`));
  }
}

function compareLineClass(kind) {
  return kind === "same" ? "cmp-same" : kind === "changed" ? "cmp-changed" : kind === "added" ? "cmp-added" : "cmp-removed";
}

function renderCompare(data) {
  const pane = $("#compare-panes");
  pane.innerHTML = "";
  if (!data.scenes || !data.scenes.length) {
    pane.appendChild(el("p", "script-empty-hint", "No scenes in common to compare — the drafts don't share scenes."));
    return;
  }
  const summary = el("div", "compare-summary");
  summary.appendChild(el("span", "diff-chip", `${data.common_scene_count} scenes compared`));
  pane.appendChild(summary);

  for (const sc of data.scenes) {
    const block = el("div", "cmp-scene");
    const head = el("div", "cmp-scene-head", `Scene ${sc.scene_number} — ${sc.heading}`);
    block.appendChild(head);
    const cols = el("div", "cmp-columns");
    const left = el("div", "cmp-col");
    const right = el("div", "cmp-col");
    left.appendChild(el("div", "cmp-col-label", data.from));
    right.appendChild(el("div", "cmp-col-label", data.to));
    for (const r of sc.rows) {
      const cls = compareLineClass(r.kind);
      const l = el("div", "cmp-line " + cls, r.left || "");
      const rEl = el("div", "cmp-line " + cls, r.right || "");
      if (r.kind === "same") { l.classList.add("muted"); rEl.classList.add("muted"); }
      left.appendChild(l);
      right.appendChild(rEl);
    }
    cols.appendChild(left);
    cols.appendChild(right);
    block.appendChild(cols);
    pane.appendChild(block);
  }
}

// ---- revision view: the doctor's desk beside the draft ----
// A summoned full-screen view (like the Beat Board / Compare): scene
// navigator | the pages | the findings queue, plus a mono status strip.
// Everything reuses the manuscript renderers — this view only changes WHERE
// things live, so the default workspace is untouched.

let revisionPrevRoom = "cowrite";

async function openRevisionView() {
  if (state.view === "revision") return;
  exitSpotlight();
  revisionPrevRoom = state.view === "cowrite" || state.view === "feedback" ? state.view : "cowrite";
  state.view = "revision";
  hideAllViews();
  closeRoomDrawer();
  $("#revision-view").style.display = "flex";
  try {
    await loadScriptData();
  } catch (e) {
    showError("Couldn't load the script: " + e.message);
  }
  // Re-hide workspace — loadScriptData may restore it via setRoom
  const wsRev = document.querySelector(".workspace");
  if (wsRev) wsRev.style.display = "none";
  renderRevisionView();
  saveSession();
}

function closeRevisionView() {
  setRoom(revisionPrevRoom);
}

// "Feedback" opens the Evidence dock: the dock's Evidence lens IS the ledger
// and the dock carries both partners — one real manuscript, no shrunken
// clone, one ledger. The old 3-panel #feedback-view was deleted in P0.1.
async function openFeedbackView() {
  if (state.view !== "cowrite") setRoom("cowrite");
  if (state.currentProject && !state.script) {
    try { await loadScriptData(); } catch (e) { showError("Could not load the script: " + e.message); }
  }
  openDock("evidence");
}

// tiny escape for the legacy FV bubbles (innerHTML path) — messages are
// writer/model text; never trust them into raw HTML
function _fvEscape(s) {
  return String(s).replace(/[&<>"']/g, function(c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

function renderFvChat(containerId, room) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var branchData = currentBranchData();
  if (!branchData || !branchData.messages || !branchData.messages.length) {
    container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);font-size:var(--fs-sm);">Start a conversation...</div>';
    return;
  }
  var msgs = branchData.messages;
  if (room === 'consult') {
    // GAP-4: the doctor's column shows the CONSULTANT'S side of the thread —
    // assistant turns tagged partner=script_consultant AND the writer's own
    // questions from those turns (partner-tagged user messages). Legacy
    // sessions (partner undefined) keep the old assistant-only view so no
    // history silently vanishes.
    msgs = msgs.filter(function(m) {
      if (m.partner) return m.partner === 'script_consultant';
      return m.role === 'assistant';
    });
  } else {
    msgs = msgs.filter(function(m) {
      if (m.partner) return m.partner === 'writing_partner';
      return m.role === 'user' || (m.role === 'assistant' && (!m.partner || m.partner === 'sameer'));
    });
  }
  var html = '';
  msgs.forEach(function(m) {
    var cls = m.role === 'user' ? 'user' : 'ai';
    // the writer's consult question shows what it was ABOUT: the pinned
    // quote rides as a chip above the question (same info the doctor saw)
    if (m.role === 'user' && m.quote && m.quote.text) {
      var q = String(m.quote.text).slice(0, 140);
      html += '<div class="fv-msg-quote" title="The passage this question was about">' +
              _fvEscape(q) + '</div>';
    }
    html += '<div class="fv-msg ' + cls + '">' + _fvEscape(m.content || m.text || '') + '</div>';
  });
  container.innerHTML = html || '<div style="text-align:center;padding:20px;color:var(--text-muted);font-size:var(--fs-sm);">Start a conversation...</div>';
  container.scrollTop = container.scrollHeight;
}

async function sendFvMessage(partner) {
  var inputId = partner === 'consultant' ? 'fv-consult-input' : 'fv-cowrite-input';
  var containerId = partner === 'consultant' ? 'fv-consult-messages' : 'fv-cowrite-messages';
  var input = document.getElementById(inputId);
  var container = document.getElementById(containerId);
  if (!input || !container) return;
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  // GAP-4: the consult turn carries the pinned quote when one exists — the
  // doctor answers ABOUT the finding the writer was looking at, not the
  // project in general. Sent once, then cleared (same semantics as the
  // main composer's pendingQuote).
  var quote = null;
  if (partner === 'consultant' && pendingQuote) {
    quote = pendingQuote;
    clearPendingQuote();
  }
  var userDiv = document.createElement('div');
  userDiv.className = 'fv-msg user';
  userDiv.textContent = text;
  container.appendChild(userDiv);
  container.scrollTop = container.scrollHeight;
  var typingDiv = document.createElement('div');
  typingDiv.className = 'fv-msg ai';
  typingDiv.textContent = partner === 'consultant' ? 'Dr. Sushruta is reading...' : 'Sameer is thinking...';
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;
  try {
    var sessionId = await ensureSession();
    // The composer's partner IS the voice. A session created by this very
    // send starts on the default persona (Sameer) — flush the lens persona
    // BEFORE the turn is stored, or the doctor's first answer gets tagged
    // and spoken as Sameer (same first-send contract as the idea room's
    // premise-doctor path).
    var wantPersona = partner === 'consultant' ? 'script_consultant' : 'writing_partner';
    var branchNow = currentBranchData() || {};
    if (branchNow.active_persona !== wantPersona) {
      try { await _setPersonaMode(wantPersona, branchNow.active_mode || 'peer'); } catch (_) { /* lens still shows */ }
    }
    var base = '/projects/' + encodeURIComponent(state.currentProject);
    var res = await streamChatTurn(base + '/chat/sessions/' + sessionId, text, quote, typingDiv, container);
    state.branches[state.currentBranch] = Object.assign({}, currentBranchData(), { messages: res.messages });
    renderFvChat(containerId, partner === 'consultant' ? 'consult' : 'cowrite');
  } catch (err) {
    typingDiv.textContent = 'Error: ' + err.message;
    typingDiv.style.color = 'var(--danger)';
  }
}

function jumpRevisionScene(num) {
  const box = $("#revision-script");
  if (!box) return;
  const page = box.querySelector(`#revision-scene-page-${num}`);
  if (!page) return;
  page.scrollIntoView({ behavior: "smooth", block: "start" });
  page.classList.remove("flash");
  void page.offsetWidth;
  page.classList.add("flash");
  setTimeout(() => page.classList.remove("flash"), 1600);
  // mark the nav row that points at the scene the writer is looking at
  document.querySelectorAll(".revision-nav-row").forEach((r) => {
    const rn = r.querySelector(".rn-num");
    if (rn && rn.textContent.trim() === `S${num}`) r.classList.add("active");
    else r.classList.remove("active");
  });
}

function flashFindingRow(index) {
  const box = $("#revision-findings");
  if (!box) return;
  const row = box.querySelector(`.fix-row[data-findex="${index}"]`);
  if (!row) return;
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  row.classList.remove("finding-flash");
  void row.offsetWidth;
  row.classList.add("finding-flash");
  setTimeout(() => row.classList.remove("finding-flash"), 1800);
}

function renderRevisionView() {
  const nav = $("#revision-nav");
  const box = $("#revision-script");
  const findings = $("#revision-findings");
  nav.innerHTML = "";
  box.innerHTML = "";
  findings.innerHTML = "";

  if (!state.script || !state.script.scenes || !state.script.scenes.length) {
    box.appendChild(el("p", "script-empty-hint", "No scenes to revise yet — upload a script first."));
    updateRevisionStatus();
    return;
  }

  // groupings — the same data-shaping the manuscript uses (kept local so the
  // main workspace renderer is untouched)
  const byScene = {};
  const scriptLevel = [];
  state.findings.forEach((f, index) => {
    const refs = f.scene_refs || [];
    if (!refs.length) { scriptLevel.push({ f, index }); return; }
    for (const n of refs) (byScene[n] = byScene[n] || []).push({ f, index });
  });
  const changedByScene = {};
  for (const ed of (state.editsData && state.editsData.edits) || []) {
    if (!ed.scene_number || !(ed.applied || []).length) continue;
    (changedByScene[ed.scene_number] = changedByScene[ed.scene_number] || []).push(...ed.applied);
  }
  const bySceneNotes = {};
  const scriptLevelNotes = [];
  for (const n of state.notes) {
    if (n.scene_number == null) scriptLevelNotes.push(n);
    else (bySceneNotes[n.scene_number] = bySceneNotes[n.scene_number] || []).push(n);
  }
  const discussedScenes = new Set();
  for (const m of (currentBranchData().messages || [])) {
    if (m.quote && m.quote.scene_number != null) discussedScenes.add(m.quote.scene_number);
  }

  // navigator: one row per scene — severity dots + count; click jumps the page
  for (const scene of state.script.scenes) {
    const fg = byScene[scene.scene_number] || [];
    const allAddressed = fg.length > 0 && fg.every(({ f, index }) => findingStatusOf(f, index) === "addressed");
    const row = el("button", "revision-nav-row" + (allAddressed ? " ok" : ""));
    row.type = "button";
    row.title = `Scene ${scene.scene_number} — ${fg.length} finding${fg.length === 1 ? "" : "s"}${allAddressed ? " (all addressed)" : ""}`;
    row.appendChild(el("span", "rn-num", `S${scene.scene_number}`));
    row.appendChild(el("span", "rn-head", scene.heading_raw));
    if (fg.length) {
      const dots = el("span", "sev-dots");
      for (const sev of ["high", "medium", "low"]) {
        if (fg.some(({ f }) => (f.severity || "low") === sev)) dots.appendChild(el("i", "sev-dot " + sev));
      }
      row.appendChild(dots);
      row.appendChild(el("span", "rn-count", String(fg.length)));
    } else {
      row.appendChild(el("span", "rn-count none", "·"));
    }
    row.addEventListener("click", () => jumpRevisionScene(scene.scene_number));
    nav.appendChild(row);
  }
  if (scriptLevel.length) {
    nav.appendChild(el("div", "rn-level", `${scriptLevel.length} script-level finding${scriptLevel.length === 1 ? "" : "s"} — in the queue`));
  }

  // the pages — the same renderer the manuscript uses (margin notes, change stars)
  for (const scene of state.script.scenes) {
    const page = renderScenePage(
      scene,
      byScene[scene.scene_number] || [],
      "",
      bySceneNotes[scene.scene_number] || [],
      discussedScenes.has(scene.scene_number),
      changedByScene[scene.scene_number] || [],
      "revision-"
    );
    // anchored findings: clicking the quoted line flashes its queue row
    for (const { f, index } of byScene[scene.scene_number] || []) {
      const qq = normText(f.evidence_quote);
      if (qq.length < 4) continue;
      for (const line of page.querySelectorAll("[class^=el-]")) {
        const lt = normText(line.textContent);
        if (lt.length >= 4 && (lt.includes(qq) || qq.includes(lt.slice(0, 40)))) {
          line.classList.add("el-anchored");
          line.title = `${CATEGORY_LABELS[f.category] || f.category}: ${f.issue}`;
          line.addEventListener("click", () => flashFindingRow(index));
          break;
        }
      }
    }
    // anchored margin notes: 📌 opens the note card
    for (const n of bySceneNotes[scene.scene_number] || []) {
      if (!n.anchor) continue;
      const qq = normText(n.anchor);
      if (qq.length < 2) continue;
      for (const line of page.querySelectorAll("[class^=el-]")) {
        const lt = normText(line.textContent);
        if (lt === qq || (qq.length > 4 && lt.includes(qq))) {
          line.classList.add("el-noted");
          line.title = `Your margin note: ${n.text}`;
          line.addEventListener("click", () => openNoteCard(n.id));
          break;
        }
      }
    }
    box.appendChild(page);
  }

  // the findings queue — the doctor's desk beside the draft (Locate stays
  // inside this view via the locateFinding guard)
  if ((state.fixQueue && state.fixQueue.items && state.fixQueue.items.length)) {
    renderFixQueuePanel(findings);
  } else {
    findings.appendChild(el("p", "rf-empty", "No findings yet — Run Analysis in the Feedback room to generate the queue."));
  }

  updateRevisionStatus();
}

function updateRevisionStatus() {
  const box = $("#revision-script");
  const pages = box ? box.querySelectorAll(".scene-page") : [];
  let cur = pages.length ? 1 : 0;
  const mid = (box ? box.scrollTop : 0) + 60;
  for (let i = 0; i < pages.length; i++) {
    if (pages[i].offsetTop <= mid) cur = i + 1;
  }
  // keep the nav row pointing at the scene the writer is actually reading
  // (fires on scroll as well as on nav clicks — one source of truth)
  document.querySelectorAll(".revision-nav-row").forEach((r) => {
    const rn = r.querySelector(".rn-num");
    if (rn) r.classList.toggle("active", rn.textContent.trim() === `S${cur}`);
  });
  const scenes = (state.script && state.script.scenes) || [];
  const words = scenes.reduce((a, s) => a + (s.word_count || 0), 0);
  const sum = findingStatusSummary();
  const strip = $("#revision-status");
  if (!strip) return;
  strip.innerHTML = "";
  strip.appendChild(el("span", "", `Scene ${cur} of ${pages.length}`));
  strip.appendChild(el("span", "", `${words.toLocaleString()} words`));
  strip.appendChild(el("span", "", `${sum.open} open / ${sum.addressed} addressed`));
  const title = state.script && state.script.title;
  if (title) strip.appendChild(el("span", "", title));
}

// ---- beat board ----

let bbOrder = [];       // the working (possibly unsaved) order
let bbCards = [];       // card data keyed by scene_number
let bbDirty = false;

let bbPrevRoom = "cowrite";

async function openBeatboardView() {
  if (state.view === "beatboard") return;
  exitSpotlight();
  bbPrevRoom = state.view === "cowrite" || state.view === "feedback" ? state.view : "cowrite";
  state.view = "beatboard";
  hideAllViews();
  $("#beatboard-view").style.display = "flex";
  try {
    await loadBeatboard();
  } catch (e) {
    showError("Couldn't load the beat board: " + e.message);
  }
  saveSession();
}

function closeBeatboardView() {
  setRoom(bbPrevRoom);
}

async function loadBeatboard() {
  const base = `/projects/${encodeURIComponent(state.currentProject)}`;
  const data = await api(`${base}/beatboard`);
  bbOrder = data.order.slice();
  bbCards = data.cards;
  bbDirty = false;
  renderBeatboard();
}

function bbCardByNumber(num) {
  return bbCards.find((c) => c.scene_number === num) || {};
}

function renderBeatboard() {
  const board = $("#beatboard-board");
  board.innerHTML = "";
  if (!bbOrder.length) {
    board.appendChild(el("p", "script-empty-hint", "No scenes in this script yet."));
    return;
  }
  bbOrder.forEach((num, i) => {
    const c = bbCardByNumber(num);
    const card = el("div", "bb-card");
    card.draggable = true;
    card.dataset.num = num;
    const top = el("div", "bb-card-top");
    top.appendChild(el("span", "bb-card-pos", String(i + 1).padStart(2, "0")));
    const head = el("span", "bb-card-head", c.heading_raw || `Scene ${num}`);
    top.appendChild(head);
    card.appendChild(top);
    const meta = el("div", "bb-card-meta");
    meta.appendChild(el("span", "act-chip", c.int_ext || "—"));
    meta.appendChild(el("span", "scene-page-est", `≈ ${c.page_estimate || 0} min`));
    if (c.your_notes) meta.appendChild(el("span", "bb-note-count", `${c.your_notes} note${c.your_notes > 1 ? "s" : ""}`));
    card.appendChild(meta);
    // finding flags: which scenes are bleeding — open findings only (addressed
    // ones are done; that's the Revision view's story). Same severity-dot
    // language as the Revision navigator, so the dots mean one thing everywhere.
    const openForScene = [];
    (state.findings || []).forEach((f, index) => {
      if (findingStatusOf(f, index) === "addressed") return;
      if ((f.scene_refs || []).includes(num)) openForScene.push(f);
    });
    if (openForScene.length) {
      const flags = el("div", "bb-card-findings");
      flags.title = `${openForScene.length} open finding${openForScene.length === 1 ? "" : "s"} in this scene`;
      const dots = el("span", "sev-dots");
      for (const sev of ["high", "medium", "low"]) {
        if (openForScene.some((f) => (f.severity || "low") === sev)) dots.appendChild(el("i", "sev-dot " + sev));
      }
      flags.appendChild(dots);
      flags.appendChild(el("span", "bb-find-count", `${openForScene.length} open`));
      card.appendChild(flags);
    }
    const moves = el("div", "bb-card-moves");
    const upBtn = el("button", "bb-move", "↑");
    upBtn.type = "button";
    upBtn.title = "Move earlier";
    upBtn.disabled = i === 0;
    upBtn.addEventListener("click", () => bbMove(i, -1));
    const downBtn = el("button", "bb-move", "↓");
    downBtn.type = "button";
    downBtn.title = "Move later";
    downBtn.disabled = i === bbOrder.length - 1;
    downBtn.addEventListener("click", () => bbMove(i, 1));
    moves.appendChild(upBtn);
    moves.appendChild(downBtn);
    card.appendChild(moves);
    board.appendChild(card);
  });
  $("#bb-save-btn").textContent = bbDirty ? "Save order" : "Order saved";
  $("#bb-save-btn").disabled = !bbDirty;
  $("#bb-save-btn").classList.toggle("dirty", bbDirty);
  $("#bb-export").href = `/api/projects/${encodeURIComponent(state.currentProject)}/beatboard/export?format=fountain`;
  $("#bb-export").download = `${(state.script && state.script.title) || "script"}-beatboard-order.fountain`;
  bindBeatboardDrag();
}

function bbMove(i, dir) {
  const j = i + dir;
  if (j < 0 || j >= bbOrder.length) return;
  [bbOrder[i], bbOrder[j]] = [bbOrder[j], bbOrder[i]];
  bbDirty = true;
  renderBeatboard();
}

async function saveBeatboard() {
  try {
    const base = `/projects/${encodeURIComponent(state.currentProject)}`;
    await api(`${base}/beatboard`, { method: "PUT", body: JSON.stringify({ order: bbOrder }) });
    bbDirty = false;
    renderBeatboard();
    appendSystemNote("Beat-board order saved. Export it when the arrangement feels right.");
  } catch (e) {
    showError("Couldn't save the beat board: " + e.message);
  }
}

async function restoreBeatboard() {
  try {
    const base = `/projects/${encodeURIComponent(state.currentProject)}`;
    await api(`${base}/beatboard/reset`, { method: "POST" });
    await loadBeatboard();
    appendSystemNote("Beat board restored to the original scene order.");
  } catch (e) {
    showError("Couldn't restore the beat board: " + e.message);
  }
}

function bindBeatboardDrag() {
  const board = $("#beatboard-board");
  let dragNum = null;
  board.querySelectorAll(".bb-card").forEach((card) => {
    card.addEventListener("dragstart", (e) => {
      dragNum = Number(card.dataset.num);
      e.dataTransfer.effectAllowed = "move";
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    card.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const overNum = Number(card.dataset.num);
      if (dragNum != null && overNum !== dragNum) {
        const from = bbOrder.indexOf(dragNum);
        const to = bbOrder.indexOf(overNum);
        bbOrder.splice(from, 1);
        bbOrder.splice(to, 0, dragNum);
        bbDirty = true;
        renderBeatboard();
        dragNum = Number(card.dataset.num);
      }
    });
  });
}

// ---- rewrite modal ----

let rewriteState = null;

function openRewriteModal(sceneNumber, f, findingIndex) {
  rewriteState = { sceneNumber, findingIndex: findingIndex != null ? findingIndex : null };
  $("#rewrite-scene-title").textContent = `Scene ${sceneNumber}`;
  const sev = (f && f.severity) ? f.severity.toUpperCase() : "LOW";
  $("#rewrite-finding").textContent = f ? `${sev} — ${f.issue} ${f.why_it_matters ? "(" + f.why_it_matters + ")" : ""}` : "";
  $("#rewrite-instruction").value = "";
  $("#rewrite-candidates").innerHTML = "";
  $("#rewrite-note").textContent = "";
  $("#rewrite-status").textContent = "";
  $("#rewrite-status").className = "rewrite-status";
  $("#rewrite-apply").style.display = "none";
  $("#rewrite-generate").style.display = "inline-block";
  openModal("#rewrite-modal");
}

async function generateRewrite() {
  if (!rewriteState) return;
  const genBtn = $("#rewrite-generate");
  const status = $("#rewrite-status");
  genBtn.disabled = true;
  status.className = "rewrite-status";
  status.textContent = "Asking the model for targeted line changes…";
  const stopTicker = startElapsedTicker(status, "Asking the model");
  try {
    const res = await api(`/projects/${encodeURIComponent(state.currentProject)}/rewrite`, {
      method: "POST",
      body: JSON.stringify({
        scene_number: rewriteState.sceneNumber,
        finding_index: rewriteState.findingIndex,
        instruction: $("#rewrite-instruction").value.trim(),
      }),
    });
    stopTicker();
    renderRewriteCandidates(res);
  } catch (e) {
    stopTicker();
    status.className = "rewrite-status error";
    status.textContent = "Rewrite failed: " + e.message;
  }
  genBtn.disabled = false;
}

// ---- word-level diff for a proposed rewrite (P1.4) ----
//
// A proposal used to render as the WHOLE old line struck through above the WHOLE
// new line in green. That is technically a diff, but it makes the writer re-read
// both lines to find the two words that actually moved — which is the opposite of
// what "show me the change" is for. This is a plain LCS over words.
//
// Deterministic on purpose (same pair in, same marks out), because that is what
// makes it assertable from a browser probe. Screenplay lines are short, so the
// O(n*m) table is nothing; a very long pair falls back to the whole-line form
// rather than allocating a table nobody will read.
const WORD_DIFF_MAX_WORDS = 400;

function _diffWords(s) {
  return String(s || "").trim().split(/\s+/).filter(Boolean);
}

function wordDiff(oldText, newText) {
  const a = _diffWords(oldText), b = _diffWords(newText);
  if (a.length > WORD_DIFF_MAX_WORDS || b.length > WORD_DIFF_MAX_WORDS) return null;
  const n = a.length, m = b.length;
  const dp = [];
  for (let i = 0; i <= n; i++) dp.push(new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const runs = [];
  const push = (kind, word) => {
    const last = runs[runs.length - 1];
    if (last && last.kind === kind) last.text += " " + word;
    else runs.push({ kind, text: word });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { push("same", a[i]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { push("del", a[i]); i++; }
    else { push("ins", b[j]); j++; }
  }
  while (i < n) { push("del", a[i]); i++; }
  while (j < m) { push("ins", b[j]); j++; }
  return runs;
}

function renderInlineDiff(rep) {
  const runs = wordDiff(rep.old, rep.new);
  if (!runs) {
    // Too long to mark word by word — say so rather than pretending.
    const pair = el("div", "rewrite-candidate-pair");
    pair.appendChild(el("span", "rewrite-old", rep.old));
    const newLine = el("span", "rewrite-new");
    newLine.appendChild(el("span", "rewrite-arrow", "→"));
    newLine.appendChild(document.createTextNode(rep.new));
    pair.appendChild(newLine);
    return pair;
  }
  const wrap = el("div", "rewrite-diff");
  for (const run of runs) {
    // del/ins rather than spans so the marks survive a screen reader and a
    // copy-paste; the classes carry the colour.
    const node = document.createElement(run.kind === "same" ? "span" : run.kind === "del" ? "del" : "ins");
    node.className = "rd-" + run.kind;
    node.textContent = run.text;
    wrap.appendChild(node);
  }
  return wrap;
}

function _proposalLabel() {
  const scene = rewriteState ? rewriteState.sceneNumber : null;
  return scene != null ? `Proposed rewrite — scene ${scene}` : "Proposed rewrite";
}

// `terminal` is the difference between deciding and parking. Apply and Reject
// END a proposal's life (the row keeps its diff, greyed, but stops offering
// actions); Stash does NOT — the writer parked it precisely in order to decide
// later, so Apply and Reject must still be there afterwards. Getting this
// backwards made Stash a one-way door, which is the opposite of what a stash is.
function _markProposalRow(row, state, terminal) {
  row.classList.add("rewrite-candidate-" + state);
  if (!terminal) return;
  const cb = row.querySelector("input[type=checkbox]");
  if (cb) cb.disabled = true;
  const actions = row.querySelector(".rewrite-candidate-actions");
  if (actions) actions.remove();
}

async function applyOneRewrite(rep, row) {
  const status = $("#rewrite-status");
  status.className = "rewrite-status";
  status.textContent = "Applying…";
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/apply`, {
      method: "POST",
      body: JSON.stringify({ scene_number: rewriteState.sceneNumber, replacements: [rep] }),
    });
    _markProposalRow(row, "applied", true);
    status.className = "rewrite-status ok";
    status.textContent = "Applied to the working copy — Undo is in the script toolbar.";
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
  } catch (e) {
    status.className = "rewrite-status error";
    status.textContent = "Apply failed: " + e.message;
  }
}

async function stashOneRewrite(rep, row, btn) {
  // Stash is the EXISTING scrapbook (stash_store.py), not a new store: the
  // proposed line goes beside the script with the scene it came from, so a
  // proposal the writer is not ready to take is parked rather than lost.
  const status = $("#rewrite-status");
  status.className = "rewrite-status";
  status.textContent = "Stashing…";
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/stash`, {
      method: "POST",
      body: JSON.stringify({
        text: rep.new,
        title: _proposalLabel(),
        scene_number: rewriteState.sceneNumber,
      }),
    });
    _markProposalRow(row, "stashed", false);
    if (btn) btn.disabled = true;   // no double-stashing; Apply/Reject stay live
    status.className = "rewrite-status ok";
    status.textContent = "Stashed beside the script — it's in the Stash list.";
    await loadStash();
  } catch (e) {
    status.className = "rewrite-status error";
    status.textContent = "Stash failed: " + e.message;
  }
}

function rejectOneRewrite(row) {
  const wrap = $("#rewrite-candidates");
  row.remove();
  const left = wrap.querySelectorAll(".rewrite-candidate").length;
  if (!left) {
    $("#rewrite-apply").style.display = "none";
    $("#rewrite-status").className = "rewrite-status";
    $("#rewrite-status").textContent = "All proposals set aside — nothing was changed.";
  }
}

function renderRewriteCandidates(res) {
  const wrap = $("#rewrite-candidates");
  wrap.innerHTML = "";
  $("#rewrite-note").textContent = res.note ? "Why: " + res.note : "";
  $("#rewrite-status").textContent = "";

  if (!res.replacements || !res.replacements.length) {
    $("#rewrite-status").textContent = "No changes proposed — the model thinks the scene is already fine. Try adding an instruction.";
    $("#rewrite-apply").style.display = "none";
    return;
  }

  rewriteState.replacements = res.replacements;
  for (const rep of res.replacements) {
    const row = el("div", "rewrite-candidate");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.setAttribute("aria-label", "Apply this change");
    const pair = renderInlineDiff(rep);
    row.appendChild(cb);
    row.appendChild(pair);
    // Apply / Stash / Reject per proposal. The checkbox above still drives the
    // bulk "Apply changes", so a writer who wants all of them takes one click.
    const actions = el("div", "rewrite-candidate-actions");
    const applyBtn = el("button", "rc-apply", "Apply");
    applyBtn.type = "button";
    applyBtn.title = "Write just this change into the working copy";
    applyBtn.addEventListener("click", () => applyOneRewrite(rep, row));
    const stashBtn = el("button", "rc-stash", "Stash");
    stashBtn.type = "button";
    stashBtn.title = "Park this version in the Stash and decide later";
    stashBtn.addEventListener("click", () => stashOneRewrite(rep, row, stashBtn));
    const rejectBtn = el("button", "rc-reject", "Reject");
    rejectBtn.type = "button";
    rejectBtn.title = "Drop this proposal — nothing is written";
    rejectBtn.addEventListener("click", () => rejectOneRewrite(row));
    actions.appendChild(applyBtn);
    actions.appendChild(stashBtn);
    actions.appendChild(rejectBtn);
    row.appendChild(actions);
    wrap.appendChild(row);
  }
  $("#rewrite-apply").style.display = "inline-block";
}

async function applyRewrite() {
  if (!rewriteState || !rewriteState.replacements) return;
  const checkboxes = document.querySelectorAll("#rewrite-candidates .rewrite-candidate input[type=checkbox]");
  const replacements = [];
  document.querySelectorAll("#rewrite-candidates .rewrite-candidate").forEach((row, i) => {
    if (row.querySelector("input").checked) replacements.push(rewriteState.replacements[i]);
  });
  if (!replacements.length) return;

  const applyBtn = $("#rewrite-apply");
  const status = $("#rewrite-status");
  applyBtn.disabled = true;
  status.className = "rewrite-status";
  status.textContent = "Applying…";
  try {
    const res = await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/apply`, {
      method: "POST",
      body: JSON.stringify({ scene_number: rewriteState.sceneNumber, replacements }),
    });
    closeModal("#rewrite-modal");
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    const msg = res.skipped && res.skipped.length
      ? `Applied ${res.applied.length} change(s); ${res.skipped.length} couldn't be matched — ${res.skipped.map((s) => s.reason).join("; ")}`
      : `Applied ${res.applied.length} change(s) to Scene ${rewriteState.sceneNumber}.`;
    appendSystemNote(msg);
  } catch (e) {
    status.className = "rewrite-status error";
    status.textContent = "Couldn't apply changes: " + e.message;
  }
  applyBtn.disabled = false;
}

async function undoEdit() {
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/undo`, { method: "POST" });
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    appendSystemNote("Undid the last applied edit.");
  } catch (e) {
    showError("Couldn't undo: " + e.message);
  }
}

async function redoEdit() {
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/redo`, { method: "POST" });
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    appendSystemNote("Re-applied the undone edit.");
  } catch (e) {
    showError("Couldn't redo: " + e.message);
  }
}

async function resetEdits() {
  if (!confirm("Discard all applied edits and return the script to its original parsed state?")) return;
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/reset`, { method: "POST" });
    await loadScriptData();
    renderManuscript(document.getElementById('manuscript-container'));
    appendSystemNote("All edits discarded — the script is back to its original state.");
  } catch (e) {
    showError("Couldn't reset edits: " + e.message);
  }
}

// ---------- command palette + keyboard shortcuts ----------

const SHORTCUTS = [
  ["Ctrl/⌘ K", "Command palette"],
  ["Ctrl/⌘ Z", "Undo last applied edit"],
  ["Ctrl/⌘ Shift Z", "Redo the undone edit"],
  ["c", "Switch to Co-write (Sameer)"],
  ["f", "Switch to Feedback (Consultant)"],
  ["s", "Focus the manuscript — dismiss the partner, back to the page"],
  ["a", "Toggle the Craft shelf (analysis panels)"],
  ["r", "Toggle the Structure rail"],
  ["z", "Spotlight mode — nothing but the page (Esc leaves)"],
  ["Esc", "Leave spotlight → dismiss partner drawer → craft shelf → structure rail"],
  ["b", "Open the Beat Board"],
  ["d", "Compare drafts side by side"],
  ["j / n", "Next scene (script view)"],
  ["k / p", "Previous scene (script view)"],
  ["/", "Search the script"],
  ["?", "Show all shortcuts"],
];

function paletteCommands() {
  // Project-only commands are HIDDEN without a project, never listed-and-dead.
  // In the idea room (no pages yet) they used to render as commands that
  // silently did nothing when clicked (UI audit 2026-09-20, defect #8).
  const hasProject = !!state.currentProject;
  const projectOnly = hasProject ? [
    { type: "command", label: "Open the Beat Board", keys: "b", run: () => openBeatboardView() },
    { type: "command", label: "Compare drafts side by side", keys: "d", run: () => openCompareView() },
    { type: "command", label: "Open the Revision view", keys: "v", run: () => openRevisionView() },
    { type: "command", label: "Spotlight mode — nothing but the page", keys: "z", run: toggleSpotlight },
    { type: "command", label: "Run Analysis", keys: "", run: () => runAnalysis() },
    { type: "command", label: "Toggle the Craft shelf (analysis panels)", keys: "a", run: toggleCraftShelf },
    { type: "command", label: "Toggle the Structure rail", keys: "r", run: () => toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")) },
    // no key hint: "b" is the Beat Board (see SHORTCUTS + the keydown handler).
    // This entry advertised "b" too, so the palette showed one shortcut for two
    // different commands.
    { type: "command", label: "Toggle the Problem Board", keys: "", run: toggleProblemBoard },
    { type: "command", label: "Search the script", keys: "/", run: () => { if (state.view !== "cowrite" && state.view !== "feedback") openCowriteRoom(); setTimeout(() => $("#script-search").focus(), 80); } },
    { type: "command", label: "Export working draft (.fountain)", keys: "", run: () => $("#export-fountain").click() },
  ] : [];
  return [
    { type: "command", label: "Switch to Co-write", keys: "c", run: () => { openCowriteRoom(); } },
    { type: "command", label: "Switch to Feedback", keys: "f", run: () => { if (hasProject) openFeedbackView(); else openFeedbackRoom(); } },
    ...projectOnly,
    { type: "command", label: "Start a new page", keys: "", run: () => { $("#new-project-btn").click(); } },
    { type: "command", label: "Focus the conversation", keys: "", run: () => { openCowriteRoom(); setTimeout(() => $("#input").focus(), 60); } },
    { type: "command", label: "Study settings", keys: "", run: () => $("#settings-btn").click() },
    // Nocta craft-first questions — surface craft intelligence first
    { type: "craft", label: "Why doesn't my dialogue land?", hint: "McKee — Gap Analysis", keys: "", run: () => openSameerWith("Analyze my dialogue for subtext gaps. Where am I telling instead of showing?") },
    { type: "craft", label: "Is my Act II sagging?", hint: "Snyder — Midpoint", keys: "", run: () => openSameerWith("Check my Act II pacing. Does the midpoint land with enough force to redirect the story?") },
    { type: "craft", label: "Am I violating setup/payoff?", hint: "McKee — Setup/Payoff", keys: "", run: () => openSameerWith("Audit my setup/payoff balance. What have I planted that never pays off, or what pays off without a plant?") },
    { type: "craft", label: "What does each scene accomplish?", hint: "Field — Scene Function", keys: "", run: () => openSameerWith("For every scene: what changes? Value shift, character decision, new information — name it.") },
    { type: "craft", label: "Are my characters distinct?", hint: "Vogler — Character Arc", keys: "", run: () => openSameerWith("Check character distinctiveness. Could I remove a name and still tell who's speaking?") },
    { type: "craft", label: "Is my theme coming through?", hint: "Swain — Story Promise", keys: "", run: () => openSameerWith("What is this script about — not what happens, but what it SAYS? Is the theme alive in the scenes?") },
    { type: "craft", label: "Am I using visual storytelling?", hint: "Snyder — Show Don't Tell", keys: "", run: () => openSameerWith("Find every moment where dialogue explains what should be shown. Mark them with alternatives.") },
  ];
}

function paletteScenes() {
  if (!state.script || !state.script.scenes) return [];
  return state.script.scenes.map((sc) => ({
    type: "scene",
    label: `Scene ${sc.scene_number} — ${sc.heading_raw}`,
    keys: "",
    sceneNumber: sc.scene_number,
    run: () => {
      // openScriptView resolves after the async load + render — only then
      // does a scroll land correctly (scrolling earlier hits stale DOM and
      // the re-render keeps the wrong scroll position).
      (async () => {
        if (state.view !== "script") await openScriptView();
        const page = document.getElementById(`scene-page-${sc.scene_number}`);
        if (page) page.scrollIntoView({ behavior: "auto", block: "start" });
        saveSession();
      })();
    },
  }));
}

function paletteHelp() {
  return SHORTCUTS.map(([k, what]) => ({
    type: "help", label: what, keys: k, run: null,
  }));
}

let paletteResults = [];
let paletteIndex = 0;
let paletteHelpMode = false;

function openPalette(helpMode) {
  paletteHelpMode = !!helpMode;
  const input = $("#palette-input");
  input.value = "";
  $("#palette-results").innerHTML = "";
  openModal("#palette-modal");
  input.focus();
  renderPalette();
  // warm the scene list: fetch the script on demand so scene jumps work
  // even before the writer has visited the Script & Notes view
  if (!paletteHelpMode && state.currentProject && !state.script) {
    api(`/projects/${encodeURIComponent(state.currentProject)}/script`)
      .then((s) => { state.script = s; renderPalette(); })
      .catch(() => {});
  }
}

function closePalette() {
  closeModal("#palette-modal");
  const input = $("#palette-input");
  if (input) input.blur();
}

function renderPalette() {
  const q = ($("#palette-input").value || "").trim().toLowerCase();
  const all = paletteHelpMode ? paletteHelp() : [...paletteCommands(), ...paletteScenes()];
  paletteResults = all
    .map((item) => ({ item, score: fuzzyScore(q, item.label) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || (all.indexOf(a.item) - all.indexOf(b.item)))
    .map((x) => x.item);
  paletteIndex = 0;
  const wrap = $("#palette-results");
  wrap.innerHTML = "";
  if (!paletteResults.length) {
    wrap.appendChild(el("div", "palette-empty", "Nothing matches — press Esc."));
    return;
  }
  paletteResults.forEach((item, i) => {
    const row = el("button", "palette-row" + (i === 0 ? " sel" : ""), item.label);
    row.type = "button";
    row.dataset.i = i;
    if (item.keys) row.appendChild(el("span", "palette-keys", item.keys));
    row.addEventListener("mousemove", () => {
      paletteIndex = i;
      document.querySelectorAll(".palette-row").forEach((r) => r.classList.toggle("sel", r.dataset.i == i));
    });
    row.addEventListener("click", () => { paletteRun(i); });
    wrap.appendChild(row);
  });
}

function paletteRun(i) {
  const item = paletteResults[i];
  if (!item) return;
  closePalette();
  if (item.run) item.run();
}

function paletteMove(dir) {
  if (!paletteResults.length) return;
  paletteIndex = (paletteIndex + dir + paletteResults.length) % paletteResults.length;
  document.querySelectorAll(".palette-row").forEach((r) => r.classList.toggle("sel", r.dataset.i == paletteIndex));
  const sel = document.querySelector(".palette-row.sel");
  if (sel) sel.scrollIntoView({ block: "nearest" });
}

function stepScene(dir) {
  const container = getManuscriptContainer();
  if (!container) return;
  const pages = [...container.querySelectorAll(".scene-page:not(.hidden)")];
  if (!pages.length) return;
  const viewportTop = container.getBoundingClientRect().top + 24;
  let idx = pages.findIndex((p) => p.getBoundingClientRect().top >= viewportTop - 8);
  if (idx === -1) idx = pages.length - 1;
  const target = pages[Math.max(0, Math.min(pages.length - 1, idx + dir))];
  target.scrollIntoView({ behavior: "auto", block: "start" });
  saveSession();
}

function isTypingTarget(t) {
  return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
}

function bindGlobalShortcuts() {
  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;

    // Ctrl/Cmd+K — palette (works everywhere, even while typing)
    if (mod && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if ($("#palette-modal").style.display === "flex") closePalette();
      else openPalette(false);
      return;
    }
    // Esc closes the palette
    if (e.key === "Escape" && $("#palette-modal").style.display === "flex") {
      closePalette();
      return;
    }

    // Esc closes the top-most open modal — even while typing inside it,
    // so this must sit ABOVE the isTypingTarget bail-out further down.
    if (e.key === "Escape") {
      const overlays = [...document.querySelectorAll(".modal-overlay")].filter((m) => m.style.display === "flex");
      if (overlays.length) {
        closeModal("#" + overlays[overlays.length - 1].id);
        return;
      }
      // river read: the page wins — Esc drifts you back to the wall (desk)
      if (document.body.classList.contains("river-read")) {
        applyFlowMode(false);
        savePrefs({ flow: false });
        return;
      }
    }

    // palette navigation while it's open
    if ($("#palette-modal").style.display === "flex") {
      if (e.key === "ArrowDown") { e.preventDefault(); paletteMove(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); paletteMove(-1); }
      else if (e.key === "Enter") { e.preventDefault(); paletteRun(paletteIndex); }
      return;
    }

    // undo/redo — meaningful in the script view (or anywhere with edits)
    if (mod && e.key.toLowerCase() === "z") {
      if ((state.view === "cowrite" || state.view === "feedback") && state.editsData && (state.editsData.can_undo || e.shiftKey)) {
        e.preventDefault();
        if (e.shiftKey) redoEdit(); else undoEdit();
      }
      return;
    }

    if (isTypingTarget(e.target)) return;

    // Esc — the page wins: dismiss the partner drawer, then the craft shelf,
    // then the structure rail (palette Esc is handled above; modals keep Esc).
    if (e.key === "Escape") {
      if (loopState.active) { exitLoop(); return; }
      if (document.body.classList.contains("spotlight-mode")) { exitSpotlight(); return; }
      if (state.view === "revision") { closeRevisionView(); return; }
      if (state.view === "premise") { closePremiseView(); return; }
      if (state.view === "compare") { closeCompareView(); return; }
      if (state.view === "beatboard") { closeBeatboardView(); return; }
      // (open modals already returned above — dock/drawer/shelf/rail are safe)
      {
        if (dockIsOpen()) { closeDock(); return; }
        const drawer = $("#room-drawer");
        if (drawer && drawer.classList.contains("open")) { closeRoomDrawer(); return; }
        const shelf = document.querySelector(".craft-shelf");
        if (shelf && shelf.classList.contains("open")) { toggleCraftShelf(); return; }
        const rail = $("#struct-rail");
        if (rail && !rail.classList.contains("rail-collapsed")) { toggleRail(true); return; }
      }
      return;
    }

    // idea room has no project — but the room keys (c/f), the craft shelf (a)
    // and the rail (r) belong there too
    if (!state.currentProject && !state.inIdea) return;

    // the keyboard fix loop (R2-b, contextual per 2A): while engaged, the
    // finding keys OWN n/j/p/k — scene-stepping resumes the moment the loop
    // exits. Esc is handled above (loop exits before the dock closes).
    if (loopState.active) {
      if (e.key === "n" || e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); stepLoop(1); return; }
      if (e.key === "p" || e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); stepLoop(-1); return; }
      return;
    }
    if (e.key === "?") { e.preventDefault(); openPalette(true); }
    else if (e.key === "/") { e.preventDefault(); paletteCommands().find((c) => c.keys === "/").run(); }
    else if (e.key === "c") { openCowriteRoom(); }
    else if (e.key === "f") {
      if (state.currentProject) openFeedbackView();
      else openFeedbackRoom();
    }
    else if (e.key === "a") { toggleCraftShelf(); }
    else if (e.key === "r") { toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")); }
    else if (e.key === "s") { closeRoomDrawer(); const sc = getManuscriptContainer(); if (sc) sc.focus(); }
    else if (e.key === "b" && state.currentProject) { openBeatboardView(); }
    else if (e.key === "d" && state.currentProject) { openCompareView(); }
    else if (e.key === "v" && state.currentProject) { if (state.view === "revision") closeRevisionView(); else openRevisionView(); }
    else if (e.key === "z" && state.currentProject) { toggleSpotlight(); }
    else if (e.key === "j" || e.key === "n") { if (state.view === "cowrite" || state.view === "feedback") { e.preventDefault(); stepScene(1); } }
    else if (e.key === "k" || e.key === "p") { if (state.view === "cowrite" || state.view === "feedback") { e.preventDefault(); stepScene(-1); } }
  });
}

// ---------- modals ----------
// Focus-managed show/hide: remembers what had focus, moves focus into the
// dialog, traps Tab inside while open, restores focus on close. Esc-to-close
// lives in bindGlobalShortcuts (top-most visible overlay wins), which is why
// that check sits ABOVE the typing-target bail-out there.

let _modalFocusReturn = null;

function _modalFocusables(overlay) {
  return [...overlay.querySelectorAll("button, input:not([type='hidden']), textarea, select, a[href]")]
    .filter((n) => !n.disabled && n.offsetParent !== null);
}

function _trapModalTab(e) {
  if (e.key !== "Tab") return;
  const focusables = _modalFocusables(e.currentTarget);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function openModal(sel) {
  const overlay = $(sel);
  if (!overlay) return;
  _modalFocusReturn = document.activeElement;
  overlay.style.display = "flex";
  const all = _modalFocusables(overlay);
  const target = all.find((n) => n.matches("input, textarea, select")) || all[0];
  if (target) target.focus();
  overlay.addEventListener("keydown", _trapModalTab);
}

function closeModal(sel) {
  const overlay = $(sel);
  if (!overlay) return;
  overlay.style.display = "none";
  overlay.removeEventListener("keydown", _trapModalTab);
  if (_modalFocusReturn && document.contains(_modalFocusReturn)) {
    try { _modalFocusReturn.focus(); } catch (_) { /* detached node */ }
  }
  _modalFocusReturn = null;
}

// ---------- wiring ----------

function autoResizeTextarea() {
  const input = $("#input");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

// ---------- sidebar flyouts: collapsed shelves that open on hover ----------
// The three shelves (Ideas / On the shelf / Your library) stay collapsed as
// labeled chips; hovering a section floats its scrollable list over the desk
// (click pins it open). Same visual language as the chat checkpoint rail.
function setSectionCount(sel, n) {
  const badge = document.querySelector(sel);
  if (!badge) return;
  badge.textContent = n ? String(n) : "";
}

function closeSidebarFlyouts(except) {
  for (const s of document.querySelectorAll(".sidebar-section.open")) {
    if (s === except) continue;
    s.classList.remove("open", "pinned");
    const t = s.querySelector(".sidebar-section-trigger");
    if (t) t.setAttribute("aria-expanded", "false");
  }
}

function wireSidebarFlyouts() {
  for (const section of document.querySelectorAll(".sidebar-section")) {
    const trigger = section.querySelector(".sidebar-section-trigger");
    if (!trigger) continue;
    let hideTimer = null;
    const open = () => {
      clearTimeout(hideTimer);
      closeSidebarFlyouts(section);
      section.classList.add("open");
      trigger.setAttribute("aria-expanded", "true");
    };
    const scheduleClose = () => {
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => {
        if (section.classList.contains("pinned")) return;
        section.classList.remove("open");
        trigger.setAttribute("aria-expanded", "false");
      }, 220);
    };
    // Hover opens from the SECTION TRIGGER only -- a section head can carry
    // sibling actions beside the trigger (the Ideas row also holds
    // "+ New idea"), and hovering those must never drop the list. The 220ms
    // grace covers the hop from the trigger into its own flyout below.
    trigger.addEventListener("mouseenter", open);
    trigger.addEventListener("mouseleave", scheduleClose);
    trigger.addEventListener("click", () => {
      if (section.classList.contains("open") && section.classList.contains("pinned")) {
        section.classList.remove("pinned", "open");
        trigger.setAttribute("aria-expanded", "false");
        return;
      }
      closeSidebarFlyouts(section);
      section.classList.add("open", "pinned");
      trigger.setAttribute("aria-expanded", "true");
    });
    // interacting inside a pinned flyout keeps it open
    section.querySelector(".sidebar-flyout").addEventListener("mouseenter", () => clearTimeout(hideTimer));
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSidebarFlyouts(null); });
  // A dropped-down flyout OVERLAYS the sections beneath it -- and sliding the
  // pointer across it keeps cancelling its close timer, so it lingers over
  // the shelf/library triggers and swallows their hover/clicks (invisible
  // dead zones). The moment the pointer leaves the owning section's box,
  // close it so the triggers underneath are reachable again. Pinned flyouts
  // stay until an explicit dismissal.
  document.addEventListener("mousemove", (e) => {
    const opened = document.querySelector(".sidebar-section.open:not(.pinned)");
    if (!opened) return;
    // the keep-open region is the section PLUS its dropped-down flyout (the
    // flyout is absolutely positioned, so the section's own rect excludes it)
    const r = opened.getBoundingClientRect();
    let left = r.left, right = r.right, top = r.top, bottom = r.bottom;
    const fly = opened.querySelector(".sidebar-flyout");
    if (fly && getComputedStyle(fly).display !== "none") {
      const f = fly.getBoundingClientRect();
      left = Math.min(left, f.left); right = Math.max(right, f.right);
      top = Math.min(top, f.top); bottom = Math.max(bottom, f.bottom);
    }
    if (e.clientX < left || e.clientX > right || e.clientY < top || e.clientY > bottom) {
      opened.classList.remove("open");
      const t = opened.querySelector(".sidebar-section-trigger");
      if (t) t.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("click", (e) => {
    if (!(e.target instanceof Element) || !e.target.closest(".sidebar-section")) closeSidebarFlyouts(null);
  });
}

// ---------- local dictation (STT): a mic chip beside every writing surface ----------
// Fully local: MediaRecorder captures -> /api/stt -> faster-whisper (or the
// writer's own local whisper server) -> text lands at the caret. No cloud.
const STT_LANG_LABELS = {
  auto: "Auto-detect",
  en: "English",
  hi: "\u0939\u093f\u0928\u094d\u0926\u0940",
  te: "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41",
};
const MIC_LANGS = Object.entries(STT_LANG_LABELS);

function sttLanguage() {
  return localStorage.getItem("studio-stt-lang") || "auto";
}

// ---- Session elapsed: how long you've been at the desk today ----
// Spotlight keeps this lit by design (see .spotlight-mode status rules).
const SESSION_START_KEY = "studio.session.start";
function sessionStart() {
  let t = Number(sessionStorage.getItem(SESSION_START_KEY) || 0);
  if (!t) { t = Date.now(); sessionStorage.setItem(SESSION_START_KEY, String(t)); }
  return t;
}
function fmtDeskElapsed(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m` : `${Math.max(s, 1)}s`;
}
function tickSessionElapsed() {
  const elc = $("#status-elapsed");
  if (elc) elc.textContent = `\u23F1 ${fmtDeskElapsed(Date.now() - sessionStart())} at the desk`;
}
setInterval(tickSessionElapsed, 30000);

// The mic menu prefers the engine's own language list (so adding a whisper
// language server-side shows up here), falling back to these built-ins.
async function refreshSttLanguages() {
  try {
    const res = await api("/stt/languages");
    const codes = (res && Array.isArray(res.languages)) ? res.languages : [];
    if (!codes.length) return;
    MIC_LANGS.length = 0;
    for (const code of codes) MIC_LANGS.push([code, STT_LANG_LABELS[code] || code]);
  } catch (_) { /* engine offline: built-ins stay */ }
}

function insertAtCaret(input, text) {
  const start = input.selectionStart != null ? input.selectionStart : input.value.length;
  const end = input.selectionEnd != null ? input.selectionEnd : start;
  const before = input.value.slice(0, start);
  const after = input.value.slice(end);
  const glue = before && !/\s$/.test(before) && !/^\s/.test(text) ? " " : "";
  input.value = before + glue + text + after;
  const pos = (before + glue + text).length;
  input.setSelectionRange(pos, pos);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
}

// Generic studio-mic glyph (SVG) -- the emoji stage mic read as a gadget.
const MIC_ICON_SVG = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
const REC_ICON_SVG = '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="6"/></svg>';

// The lang menu lives on <body>: the drawer/room/message ancestors carry
// identity transforms, which turn them into the containing block for
// position:fixed and would drag the menu out of place. Body has none.
function dismissStrayLangMenus() {
  document.querySelectorAll(".lang-menu").forEach((m) => {
    // while the writer still points at the owning globe, an auto-scroll from
    // a streaming reply must NOT yank the menu away from under the cursor
    const t = LANG_MENU_TRIGGER.get(m);
    if (t && t.matches(":hover")) return;
    if (!m.matches(":hover")) m.remove();
  });
}
const LANG_MENU_TRIGGER = new WeakMap();
let _langMenuScrollWired = false;
function wireLangMenuDismiss() {
  if (_langMenuScrollWired) return;
  _langMenuScrollWired = true;
  document.addEventListener("scroll", (e) => {
    if (e.target && e.target.closest && e.target.closest(".messages-scroll")) {
      dismissStrayLangMenus();
    }
  }, true);
}

function attachMic(inputEl) {
  if (!inputEl || inputEl.dataset.micAttached) return;
  inputEl.dataset.micAttached = "1";
  const wrap = document.createElement("div");
  wrap.className = "mic-wrap";
  inputEl.parentNode.insertBefore(wrap, inputEl);
  wrap.appendChild(inputEl);

  const btn = el("button", "mic-btn");
  btn.innerHTML = MIC_ICON_SVG;
  btn.type = "button";
  btn.title = "Dictate \u2014 hands-free typing. Right-click to pick the spoken language.";
  btn.setAttribute("aria-label", "Dictate");
  wrap.appendChild(btn);

  let recorder = null;
  let chunks = [];
  let stream = null;
  const setRecording = (on) => {
    btn.classList.toggle("recording", on);
    btn.innerHTML = on ? REC_ICON_SVG : MIC_ICON_SVG;
    btn.title = on ? "Recording \u2014 click again to transcribe"
                   : "Dictate \u2014 hands-free typing. Right-click to pick the spoken language.";
  };

  const stopAndSend = async () => {
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop(); // onstop below does the upload
  };

  recorder = null;
  btn.addEventListener("click", async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
      appendSystemNote("Dictation isn't available in this browser \u2014 it needs microphone access.", true);
      return;
    }
    if (btn.classList.contains("recording")) { await stopAndSend(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (_) {
      appendSystemNote("Microphone access was blocked \u2014 allow it in the browser to dictate.", true);
      return;
    }
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      if (!blob.size) return;
      btn.textContent = "\u2026";
      btn.title = "Transcribing\u2026";
      try {
        const fd = new FormData();
        fd.append("audio", blob, "speech.webm");
        fd.append("language", sttLanguage());
        const res = await fetch("/api/stt", { method: "POST", body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "transcription failed");
        if ((data.text || "").trim()) insertAtCaret(inputEl, data.text.trim());
      } catch (err) {
        appendSystemNote("Dictation failed: " + err.message, true);
      } finally {
        btn.innerHTML = MIC_ICON_SVG;
      }
    };
    recorder.start();
    setRecording(true);
  });

  // right-click: pick the spoken language (remembered per writer)
  btn.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    document.querySelectorAll(".mic-lang-menu").forEach((m) => m.remove());
    const menu = el("div", "mic-lang-menu");
    for (const [code, label] of MIC_LANGS) {
      const opt = el("button", "mic-lang-item" + (sttLanguage() === code ? " current" : ""), label);
      opt.type = "button";
      opt.addEventListener("click", () => {
        localStorage.setItem("studio-stt-lang", code);
        menu.remove();
      });
      menu.appendChild(opt);
    }
    wrap.appendChild(menu);
    const dismiss = (ev) => {
      if (menu.contains(ev.target)) return;
      menu.remove();
      document.removeEventListener("click", dismiss);
    };
    setTimeout(() => document.addEventListener("click", dismiss), 0);
  });
}

function wireMics() {
  ["#idea-content", "#input", "#premise-logline", "#premise-text",
   "#premise-questions", "#idea-logline", "#idea-questions", "#dock-note-input",
  ].forEach((sel) => attachMic(document.querySelector(sel)));
}

function init() {
  loadConfig();
  wireSidebarFlyouts();
  wireMics();
  const projectsPromise = Promise.all([loadProjects(), loadIdeas()]);
  loadLibrary();

  // the den greets the writer by the hour
  const greeting = $("#welcome-greeting");
  if (greeting) {
    const h = new Date().getHours();
    greeting.textContent =
      h < 5 ? "Still up, writer?" :
      h < 12 ? "The kettle's on." :
      h < 18 ? "The desk is yours." :
      "Evening, writer.";
  }

  // upload
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadFile(fileInput.files[0]); });
  ["dragover", "dragenter"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("drag-over"); })
  );
  dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  $("#new-project-btn").addEventListener("click", () => showWelcomeDesk());
  $("#new-idea-btn").addEventListener("click", createIdea);
  // Phase 0: structural rail
  $("#rail-toggle").addEventListener("click", () => toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")));
  // Phase 4: scene index — expand/collapse + scroll-synced current-scene highlight
  const sceneIndexToggle = $("#scene-index-toggle");
  if (sceneIndexToggle) {
    const syncSceneIndexGlyph = () => {
      // Phase 11: on narrow screens the index is an overlay SHEET — the
      // toggle doubles as its ✕ dismiss so the sheet is never a trap.
      const idx = $("#scene-index");
      const sheet = window.matchMedia("(max-width: 767px)").matches;
      const open = idx.classList.contains("expanded");
      sceneIndexToggle.textContent = sheet && open ? "✕" : "☰";
      sceneIndexToggle.title = open ? "Collapse scene index" : "Toggle scene index";
      sceneIndexToggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    sceneIndexToggle.addEventListener("click", () => {
      $("#scene-index").classList.toggle("expanded");
      syncSceneIndexGlyph();
    });
    // outside tap closes the mobile sheet (the manuscript is the tap layer)
    document.addEventListener("click", (e) => {
      const idx = $("#scene-index");
      if (!idx.classList.contains("expanded")) return;
      if (window.matchMedia("(max-width: 767px)").matches && !idx.contains(e.target)) {
        idx.classList.remove("expanded");
        syncSceneIndexGlyph();
      }
    });
    syncSceneIndexGlyph();
  }
  setupSceneIndexScroll();
  // Phase 5: context dock — right-edge summon, ✕ + Esc dismiss, lens tabs
  const dockEdge = $("#right-edge-affordance");
  if (dockEdge) dockEdge.addEventListener("click", () => openDock());
  const dockCloseBtn = $("#dock-close");
  if (dockCloseBtn) dockCloseBtn.addEventListener("click", closeDock);
  DOCK_LENSES.forEach((l) => {
    const tab = $("#dock-tab-" + l);
    if (tab) tab.addEventListener("click", () => setDockLens(l));
  });
  // Phase 6: Discuss inside the dock is a handoff — the conversation (the
  // room drawer until Phase 7 moves it into the dock) gets the quote and
  // the dock steps aside, so two side panels never fight for the page.
  // Locate and Rewrite keep the dock open. Delegated ONCE here in the
  // CAPTURE phase: findingNoteEl's own Discuss handler calls
  // stopPropagation(), so a bubble-phase listener would never see the click.
  const dockEvidenceLens = document.querySelector('.dock-lens[data-lens="evidence"]');
  if (dockEvidenceLens) {
    dockEvidenceLens.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".finding-note-actions button, .fix-row-actions button");
      if (btn && /Discuss/.test(btn.textContent || "")) closeDock();
    }, { capture: true });
  }
  // collapsible sidebar (the shelf)
  const sidebarToggle = $("#sidebar-toggle");
  if (sidebarToggle) sidebarToggle.addEventListener("click", () => toggleSidebar(!$("#sidebar").classList.contains("sidebar-collapsed")));
  const sidebarEdge = $("#sidebar-edge-tab");
  if (sidebarEdge) sidebarEdge.addEventListener("click", () => toggleSidebar(false));
  // Phase 13: the rail-foot Beats/Compare buttons retired with the stash
  // foot — both actions stay reachable (keyboard b/d, overflow icons) and
  // P13-B gives them desk-toolbar buttons.
  // Phase 13: the margin-note form lives in the dock's Stash & Notes lens now
  // (the rail's form retired with the rail's stash/notes sections)
  $("#dock-note-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#dock-note-input");
    const text = (input.value || "").trim();
    if (!text || !state.currentProject) return;
    try {
      await api(`/projects/${encodeURIComponent(state.currentProject)}/notes`, {
        method: "POST", body: JSON.stringify({ scene_number: null, text }),
      });
      input.value = "";
      await reloadNotesAndRender();
      renderRailNotes();
    } catch (err) {
      showError("Couldn't pin the note: " + err.message);
    }
  });
  $("#status-dawn").addEventListener("click", () => {
    const dawn = !document.body.classList.contains("dawn");
    applyDawn(dawn);
    savePrefs({ dawn });
  });
  $("#idea-btn").addEventListener("click", createIdea);
  $("#premise-save-btn").addEventListener("click", () => savePremise());
  $("#premise-graduate-btn").addEventListener("click", () => $("#premise-file-input").click());
  $("#premise-close-btn").addEventListener("click", closePremiseView);
  $("#premise-file-input").addEventListener("change", () => {
    if ($("#premise-file-input").files[0]) graduateIdea($("#premise-file-input").files[0]);
    $("#premise-file-input").value = "";
  });
  // idea canvas: the blank page, autosaved; /sameer; the pill; structure
  $("#idea-content").addEventListener("input", handleIdeaContentInput);
  $("#idea-content").addEventListener("blur", saveIdeaContent);

  // Closing/reloading within the autosave debounce must not eat keystrokes:
  // flush any pending save (sendBeacon survives unload).
  window.addEventListener("pagehide", () => {
    if (!state.currentIdea || !state.inIdea || !ideaSaveTimer) return;
    clearTimeout(ideaSaveTimer);
    ideaSaveTimer = null;
    const content = $("#idea-content").value;
    if (content === state.currentIdea.content) return;
    const url = `${API}/ideas/${encodeURIComponent(state.currentIdea.id)}/content`;
    try {
      navigator.sendBeacon(url, new Blob([JSON.stringify({ content })], { type: "application/json" }));
    } catch (_) {
      fetch(url, { method: "POST", body: JSON.stringify({ content }), keepalive: true });
    }
  });

  tickSessionElapsed();
  refreshSttLanguages();

  // the strip never lies quietly: re-check every 30s so a llama-server that
  // comes up AFTER the studio gets noticed (demo mode offers the switch)
  $("#status-conn").addEventListener("click", async () => {
    if (!(state.realServer && state.realServer.available)) return;
    try {
      await api("/config", { method: "POST", body: JSON.stringify({ server_url: state.realServer.url }) });
      await loadConfig();
      state.realServer = { available: false };
      await checkConnection();
    } catch (e) {
      showError("Couldn't switch to your model: " + e.message);
    }
  });

  // back to the page = the partner steps back: clicking/focusing the editor
  // dismisses the room drawer so the writer always has the full page
  for (const ev of ["focus", "click"]) {
    $("#idea-content").addEventListener(ev, () => {
      const d = $("#room-drawer");
      if (d && d.classList.contains("open")) closeRoomDrawer();
    });
  }

  // select-to-ask on the IDEA PAGE: highlight any lines -> "Ask Sameer"
  // floats up -> the passage rides as a quote card, exactly like the script
  // pane. Precision by construction: he answers THOSE words.
  const ideaEl = $("#idea-content");

  function updateIdeaQuoteFloat() {
    const btn = $("#idea-quote-float");
    if (!btn) return;
    const sel = window.getSelection();
    // NOTE: no isCollapsed check -- some engines report textarea selections
    // as collapsed while toString() still carries the full text. The length
    // guard below is the real gate.
    if (!sel || !sel.rangeCount) { hideIdeaQuoteFloat(); return; }
    // Textarea selections report unreliable ancestors (sometimes the document
    // itself). The editor OWNS this selection when it holds focus -- that's
    // the real gate; the ancestor walk is only a secondary check.
    const node = sel.getRangeAt(0).commonAncestorContainer;
    const el = node && node.nodeType === 1 ? node : (node ? node.parentElement : null);
    const ownedByEditor = document.activeElement === ideaEl
      || ideaEl.contains(node)
      || (el && ideaEl.contains(el));
    if (!ownedByEditor) { hideIdeaQuoteFloat(); return; }
    const text = sel.toString().trim().replace(/\s+/g, " ");
    if (!text || text.length < 4 || text.length > 600) { hideIdeaQuoteFloat(); return; }
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    const hostRect = ideaEl.closest(".idea-canvas, .editor-wrap, body").getBoundingClientRect();
    btn.dataset.text = text;
    btn.hidden = false;
    if (rect && (rect.width || rect.height)) {
      btn.style.left = Math.max(8, Math.min(rect.right - hostRect.left - 60, hostRect.width - 140)) + "px";
      btn.style.top = Math.max(4, rect.bottom - hostRect.top + 6) + "px";
    } else {
      // degenerate range rect (some engines/headless): anchor bottom-right of
      // the editor -- still next to the writer's eyes, never in the way
      btn.style.left = Math.max(8, hostRect.width - 150) + "px";
      btn.style.top = Math.max(4, hostRect.height - 44) + "px";
    }
  }

  ideaEl.addEventListener("mouseup", () => setTimeout(updateIdeaQuoteFloat, 10));
  // keyboard selections (shift+arrows, shift+home) never fire mouseup
  let _ideaSelTimer = null;
  document.addEventListener("selectionchange", () => {
    if (!state.inIdea) return;
    clearTimeout(_ideaSelTimer);
    _ideaSelTimer = setTimeout(updateIdeaQuoteFloat, 60);
  });
  document.addEventListener("mousedown", (e) => {
    const btn = $("#idea-quote-float");
    if (btn && !btn.hidden && !btn.contains(e.target) && e.target !== ideaEl) hideIdeaQuoteFloat();
  });
  $("#idea-quote-float").addEventListener("click", function () { askSamAboutSelection(this); });
  $("#idea-title-input").addEventListener("change", () => renameIdea($("#idea-title-input").value.trim()));
  $("#idea-sam-pill").addEventListener("click", () => summonIdeaSam());
  $("#idea-structure-btn").addEventListener("click", toggleIdeaStructure);
  $("#idea-structure-save").addEventListener("click", saveIdeaStructure);
  $("#idea-graduate-btn").addEventListener("click", () => $("#idea-file-input").click());
  $("#idea-file-input").addEventListener("change", () => {
    if ($("#idea-file-input").files[0]) graduateIdea($("#idea-file-input").files[0]);
    $("#idea-file-input").value = "";
  });
  $("#premise-btn").addEventListener("click", togglePremisePane);

  // dawn theme + reader mode + shortcut hint (persisted preferences)
  const prefs = loadPrefs();
  applyDawn(prefs.dawn);
  // dock lens preference (the dock itself always starts closed — the
  // page owns the room on arrival; the lens is just which tab is active)
  if (DOCK_LENSES.includes(prefs.dock_lens)) dockLens = prefs.dock_lens;
  // Manuscript Stage: the structure rail starts off-canvas — the page owns the
  // room. Only an explicit "open" preference keeps it out; anything else (or
  // nothing) collapses it.
  if (prefs.rail_collapsed !== false) toggleRail(true);
  // sidebar: honor saved collapse preference (default open — unlike the rail)
  if (prefs.sidebar_collapsed) toggleSidebar(true);
  applyReaderMode(prefs.reader);
  applyFocusMode(prefs.focus);
  wireSprint();
  $("#dawn-btn").addEventListener("click", () => {
    const dawn = !document.body.classList.contains("dawn");
    applyDawn(dawn);
    savePrefs({ dawn });
  });
  $("#reader-btn").addEventListener("click", () => {
    const on = !document.body.classList.contains("reader-mode");
    applyReaderMode(on);
    savePrefs({ reader: on });
    closeOverflow();
  });
  // Overflow menu toggle
  const overflowToggle = $("#overflow-toggle");
  const overflowDropdown = $("#overflow-dropdown");
  function closeOverflow() { if (overflowDropdown) overflowDropdown.style.display = "none"; }
  if (overflowToggle && overflowDropdown) {
    const syncOverflowAria = () => overflowToggle.setAttribute("aria-expanded", overflowDropdown.style.display !== "none" ? "true" : "false");
    overflowToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      overflowDropdown.style.display = overflowDropdown.style.display === "none" ? "block" : "none";
      syncOverflowAria();
    });
    document.addEventListener("click", (e) => {
      if (!overflowDropdown.contains(e.target) && e.target !== overflowToggle) { closeOverflow(); syncOverflowAria(); }
    });
  }
  // river read (Spark Wall): one continuous flow + current nav; Esc leaves
  applyFlowMode(!!prefs.flow);
  $("#flow-btn").addEventListener("click", () => {
    const on = !document.body.classList.contains("river-read");
    applyFlowMode(on);
    savePrefs({ flow: on });
  });
  const mc = getManuscriptContainer(); if (mc) mc.addEventListener("scroll", () => {
    if (document.body.classList.contains("river-read")) onRiverScroll();
  }, { passive: true });
  // explore chips collapse: first real input anywhere (idea page or composer)
  // tucks the chips away to icons; clearing the box brings them back
  const chipInputHook = (elx) => {
    if (!elx) return;
    elx.addEventListener("input", () => setExploreChipsCollapsed(!!elx.value.trim()));
  };
  chipInputHook($("#idea-content"));
  chipInputHook($("#input"));
  $("#focus-btn").addEventListener("click", () => {
    const on = !document.body.classList.contains("focus-mode");
    applyFocusMode(on);
    savePrefs({ focus: on });
  });
  if (!prefs.hintDismissed) {
    $("#shortcut-hint").style.display = "flex";
  }
  $("#shortcut-hint-dismiss").addEventListener("click", () => {
    $("#shortcut-hint").style.display = "none";
    savePrefs({ hintDismissed: true });
  });

  $("#sample-btn").addEventListener("click", async () => {
    const btn = $("#sample-btn");
    btn.disabled = true;
    try {
      const project = await api("/sample", { method: "POST" });
      await loadProjects();
      await openProject(project.project);
    } catch (e) {
      showError("Couldn't open the sample page: " + e.message);
    } finally {
      btn.disabled = false;
    }
  });

  // pick up where the writer left off — last idea OR project, view, and scene
  projectsPromise.then(() => {
    const s = restoreSession();
    if (!s) return;
    // the idea room is restored too: refresh lands you back in the
    // brainstorming session, not just on the script desk
    if (s.idea && (state.ideas || []).some((i) => i.id === s.idea)) {
      openIdea(s.idea).catch(() => showWelcomeDesk());
      return;
    }
    if (!s.project || !(state.projects || []).some((p) => p.project === s.project)) return;
    openProject(s.project).then(() => {
      if (s.view === "chat" || s.view === "script") {
        // legacy saved views map to the Co-write room (the script is the shared pane)
        openProject(s.project).then(() => {
          if (s.scene) {
            const page = document.getElementById(`scene-page-${s.scene}`);
            if (page) page.scrollIntoView({ behavior: "auto", block: "start" });
          }
        });
      } else if (s.view === "beatboard") openBeatboardView();
      else if (s.view === "compare") openCompareView();
      else if (s.view === "revision") openRevisionView();
      else if (s.view === "premise") openPremiseView();
      else if (s.view === "fv") openFeedbackView();
      else if (s.view === "feedback") openFeedbackRoom();
    }).catch(() => { /* project vanished — stay on the welcome scene */ });
  });

  $("#analyze-btn").addEventListener("click", runAnalysis);
  $("#reparse-btn").addEventListener("click", reparseProject);
  $("#retry-failed-btn").addEventListener("click", retryFailedCategories);
  // Phase 8: the desk toolbar — same lifecycle actions beside the page
  const deskAnalyzeBtn = $("#desk-analyze-btn");
  if (deskAnalyzeBtn) deskAnalyzeBtn.addEventListener("click", runAnalysis);
  const deskRetryBtn = $("#desk-retry-failed-btn");
  if (deskRetryBtn) deskRetryBtn.addEventListener("click", retryFailedCategories);

  // script pane
  $("#script-search").addEventListener("input", () => renderManuscript(document.getElementById('manuscript-container')));
  $("#reset-edits-btn").addEventListener("click", resetEdits);
  $("#undo-btn").addEventListener("click", undoEdit);
  $("#redo-btn").addEventListener("click", redoEdit);
  $("#rewrite-generate").addEventListener("click", generateRewrite);
  $("#rewrite-apply").addEventListener("click", applyRewrite);
  $("#rewrite-cancel").addEventListener("click", () => closeModal("#rewrite-modal"));
  $("#draft-select").addEventListener("change", (e) => { if (e.target.value) activateDraft(e.target.value); });
  $("#upload-draft-btn").addEventListener("click", () => $("#draft-file-input").click());
  $("#draft-file-input").addEventListener("change", () => {
    if ($("#draft-file-input").files[0]) uploadNewDraft($("#draft-file-input").files[0]);
  });

  // composer
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); sendMessage(); });

  // select-to-reply: highlight a passage in the script → ask Sameer about it
  $("#quote-float").addEventListener("click", () => {
    const btn = $("#quote-float");
    if (btn.hidden) return;
    const quote = {
      scene_number: btn.dataset.sceneNumber ? parseInt(btn.dataset.sceneNumber, 10) : null,
      text: btn.dataset.text,
    };
    window.getSelection().removeAllRanges();
    hideQuoteFloat();
    openCowriteRoom();
    setPendingQuote(quote);
    $("#input").focus();
  });
  // The Stash: park a selected passage beside the script — cut material,
  // good lines, saved without leaving the page. Listed in the Stash panel.
  $("#stash-float").addEventListener("click", async () => {
    const btn = $("#stash-float");
    if (btn.hidden || !state.currentProject) return;
    const entry = {
      text: btn.dataset.text || "",
      scene_number: btn.dataset.sceneNumber ? parseInt(btn.dataset.sceneNumber, 10) : null,
    };
    window.getSelection().removeAllRanges();
    hideQuoteFloat();
    if (!entry.text) return;
    const original = btn.textContent;
    try {
      await api(`/projects/${encodeURIComponent(state.currentProject)}/stash`, {
        method: "POST", body: JSON.stringify(entry),
      });
      btn.textContent = "Stashed ✓";
      setTimeout(() => { btn.textContent = original; }, 1200);
      await loadStash();
    } catch (err) {
      showError("Couldn't stash that: " + err.message);
    }
  });
  // 📝 Note this line — pin a margin note to the exact line (Google-Docs style)
  $("#note-float").addEventListener("click", () => {
    const btn = $("#note-float");
    if (btn.hidden || !state.currentProject) return;
    const anchor = (btn.dataset.text || "").trim();
    const sceneNum = btn.dataset.sceneNumber ? parseInt(btn.dataset.sceneNumber, 10) : null;
    window.getSelection().removeAllRanges();
    hideQuoteFloat();
    if (!anchor) return;
    const editor = noteTextarea("A margin note pinned to this line… (Enter to save, Esc to cancel)");
    const line = document.querySelector(`[data-scene-number="${sceneNum}"] .scene-notes`);
    const container = line || getManuscriptContainer();
    editor.dataset.anchorScene = String(sceneNum);
    editor.dataset.anchorText = anchor;
    container.prepend(editor);
    editor.focus();
    let done = false;
    const finish = (saved, text) => {
      if (done) return;
      done = true;
      if (saved && text) {
        api(`/projects/${encodeURIComponent(state.currentProject)}/notes`, {
          method: "POST",
          body: JSON.stringify({ scene_number: sceneNum, text, anchor }),
        }).then(reloadNotesAndRender).catch((e) => showError("Couldn't save note: " + e.message));
      } else {
        reloadNotesAndRender();
      }
    };
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); finish(true, editor.value.trim()); }
      else if (e.key === "Escape") { finish(false); }
    });
    editor.addEventListener("blur", () => { if (editor.value.trim()) finish(true, editor.value.trim()); else finish(false); });
  });
  document.addEventListener("mouseup", handleScriptSelection);
  document.addEventListener("keyup", handleScriptSelection);
  document.addEventListener("selectionchange", () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) hideQuoteFloat();
    else if (!selectionInScriptPane()) hideQuoteFloat();
  });
  document.addEventListener("mousedown", (e) => {
    if ($("#quote-float").hidden) return;
    // same guard: a synthetic/document-targeted mousedown must not throw
    const t = e.target instanceof Element ? e.target : null;
    const mc = getManuscriptContainer(); if (t && !t.closest("#quote-float") && !t.closest("#stash-float") && !t.closest("#note-float") && (!mc || !mc.contains(t))) hideQuoteFloat();
  });
  const scrollPane = getManuscriptContainer(); if (scrollPane) scrollPane.addEventListener("scroll", hideQuoteFloat, { passive: true });

  // resizable script pane — drag the divider; double-click resets to 70%
  // (the manuscript is center stage by default; the chat is the right pane)
  const paneDivider = $("#pane-divider");
  const scriptPane = $("#script-pane");
  let paneDragging = false;
  const deskEl = () => document.querySelector(".desk") || document.querySelector(".workspace");
  const railOffset = () => {
    const rail = document.getElementById("struct-rail");
    return (rail && !rail.classList.contains("rail-collapsed")) ? rail.offsetWidth : 0;
  };
  const applyPaneWidth = (px) => {
    const desk = deskEl();
    // the manuscript never shrinks below half the desk (Phase 0 rule)
    const min = desk ? Math.round(desk.clientWidth * 0.5) : 300;
    const max = desk ? Math.round(desk.clientWidth * 0.78) : 1200;
    px = Math.max(min, Math.min(px, max));
    scriptPane.style.flex = `0 0 ${px}px`;
    localStorage.setItem("pane-width-v2", String(px));
  };
  // v2 key: the v1 value was saved while the layout still defaulted to a wide
  // chat, so honoring it now would override the small-chat default. A stale
  // v1 value is deliberately ignored. The same rule extends to v2: a stored
  // width that would leave the chat under ~30% is treated as a leftover from
  // a wide-drag session and dropped, so the manuscript is center stage on
  // every fresh load (drag to resize still works live, up to the 78% clamp).
  const savedPaneWidth = parseFloat(localStorage.getItem("pane-width-v2"));
  const wsEl = deskEl();
  // honor a stored width only inside the 50–78% band; anything wider (a
  // leftover from a wide-drag session) is treated as stale and dropped
  const minPane = wsEl ? Math.round(wsEl.clientWidth * 0.5) : 300;
  if (savedPaneWidth && wsEl && savedPaneWidth >= minPane && savedPaneWidth <= Math.round(wsEl.clientWidth * 0.78)) {
    applyPaneWidth(savedPaneWidth);
  }
  paneDivider.addEventListener("mousedown", (e) => {
    e.preventDefault();
    paneDragging = true;
    document.body.classList.add("resizing");
  });
  window.addEventListener("mousemove", (e) => {
    if (!paneDragging) return;
    const ws = document.querySelector(".workspace");
    const wsRect = ws.getBoundingClientRect();
    // measure from the desk's left edge (past the rail), so the drag gives
    // the script exactly the width the pointer asks for
    applyPaneWidth(e.clientX - wsRect.left - railOffset());
  });
  window.addEventListener("mouseup", () => {
    if (!paneDragging) return;
    paneDragging = false;
    document.body.classList.remove("resizing");
  });
  paneDivider.addEventListener("dblclick", () => {
    scriptPane.style.flex = "";
    localStorage.removeItem("pane-width-v2");
  });
  $("#input").addEventListener("input", autoResizeTextarea);
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp" && chatHistoryArrowUp(e)) return;
    if (e.key === "ArrowDown" && chatHistoryArrowDown(e)) return;
    if (e.key === "Escape" && chatHistoryEscape(e)) return;
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  $("#input").addEventListener("blur", () => {
    // leaving the composer mid-browse closes the list and restores the draft
    if (chatHistoryIndex !== -1) chatHistoryCancel();
  });

  // conversation rail — keep marker positions honest as the thread scrolls
  let railFrame = null;
  const railScroll = () => {
    const container = $("#messages-scroll");
    if (railFrame) return;
    railFrame = requestAnimationFrame(() => {
      railFrame = null;
      updateRailPositions(container);
    });
  };
  $("#messages-scroll").addEventListener("scroll", railScroll, { passive: true });
  window.addEventListener("resize", railScroll);

  // selectors
  $("#persona-select").addEventListener("change", updateSettings);
  $("#mode-select").addEventListener("change", updateSettings);

  // settings modal
  $("#settings-btn").addEventListener("click", () => {
    $("#test-connection-result").textContent = "";
    // Re-fill from the desk's current state: the modal outlives a save, and a
    // form that still shows the pre-save world reads as a failed save.
    fillSettingsForm();
    openModal("#settings-modal");
  });
  $("#settings-cancel").addEventListener("click", () => closeModal("#settings-modal"));
  $("#settings-save").addEventListener("click", saveConfig);
  $("#test-connection-btn").addEventListener("click", testConnection);

  // fork modal
  $("#fork-cancel").addEventListener("click", () => closeModal("#fork-modal"));
  $("#fork-save").addEventListener("click", createFork);
  $("#fork-name-input").addEventListener("keydown", (e) => { if (e.key === "Enter") createFork(); });

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.style.display = "none"; });
  });

  // rooms
  $("#room-cowrite-btn").addEventListener("click", openCowriteRoom);
  $("#room-feedback-btn").addEventListener("click", () => {
    if (state.currentProject) openFeedbackView();
    else openFeedbackRoom();
  });
  // Manuscript Stage: the gutter tabs summon the partner drawer
  $("#gutter-sam").addEventListener("click", openCowriteRoom);
  $("#gutter-doc").addEventListener("click", () => {
    if (state.currentProject) openFeedbackView();
    else openFeedbackRoom();
  });
  $("#drawer-close").addEventListener("click", closeRoomDrawer);
  $("#rail-edge-tab").addEventListener("click", () => toggleRail(false));
  $("#bb-icon").addEventListener("click", () => { closeOverflow(); openBeatboardView(); });
  $("#compare-icon").addEventListener("click", () => { closeOverflow(); openCompareView(); });
  $("#revise-btn").addEventListener("click", openRevisionView);
  $("#revision-close").addEventListener("click", closeRevisionView);
  // Consultant chat composer (the doctor's column lives in the dock's
  // sushruta slot — P0.1)
  $("#fv-consult-composer").addEventListener("submit", function(e) { e.preventDefault(); sendFvMessage("consultant"); });
  // Problem Board toggle and filter
  var pbToggle = document.getElementById('pb-toggle');
  if (pbToggle) pbToggle.addEventListener('click', toggleProblemBoard);
  var pbEdgeTab = document.getElementById('pb-edge-tab');
  if (pbEdgeTab) pbEdgeTab.addEventListener('click', function() { toggleProblemBoard(); });
  var pbFilter = document.getElementById('pb-filter');
  if (pbFilter) pbFilter.addEventListener('change', function() { renderProblemBoard(); });

  // Problem Board rows: one delegated listener instead of an onclick built
  // into each row's markup. Rows carry data-* only, so no finding text ever
  // lands in an attribute — and script-src can stay 'self' (an inline handler
  // would require 'unsafe-inline', which is exactly what the CSP must not have).
  var pbList = document.getElementById('pb-list');
  if (pbList) {
    pbList.addEventListener('click', function(e) {
      var row = e.target && e.target.closest ? e.target.closest('.pb-item') : null;
      if (!row || !pbList.contains(row)) return;
      var findex = Number(row.dataset.findex);
      if (!isFinite(findex)) return;
      pbItemClick(findex, row.dataset.scene);
    });
  }

  $("#revision-script").addEventListener("scroll", updateRevisionStatus);
  $("#reset-partner-btn").addEventListener("click", resetToPartner);
  $("#clear-chat-btn").addEventListener("click", clearChat);
  $("#sam-notes-btn").addEventListener("click", openSamNotes);
  $("#sam-notes-close").addEventListener("click", closeSamNotes);
  $("#sam-notes-refresh").addEventListener("click", async () => {
    if (!state.currentProject || !state.currentSession) return;
    const btn = $("#sam-notes-refresh");
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Refreshing…";
    try {
      await api("/writer-memory/refresh", {
        method: "POST",
        body: JSON.stringify({ project: state.currentProject, session_id: state.currentSession }),
      });
      await loadSamNotes();
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  });
  $("#tab-report-btn").addEventListener("click", () => switchFeedbackTab("report"));
  $("#tab-fixqueue-btn").addEventListener("click", () => switchFeedbackTab("fixqueue"));
  $("#print-btn").addEventListener("click", () => { closeOverflow();
    if (state.view === "cowrite" || state.view === "feedback") window.print();
  });
  $("#compare-from-select").addEventListener("change", (e) => {
    compareFrom = e.target.value;
    loadCompare().catch((err) => showError("Couldn't reload comparison: " + err.message));
  });

  // beat board
  $("#bb-save-btn").addEventListener("click", saveBeatboard);
  $("#bb-restore-btn").addEventListener("click", restoreBeatboard);
  $("#bb-back-btn").addEventListener("click", closeBeatboardView);
  $("#compare-back-btn").addEventListener("click", closeCompareView);
  $("#bb-print-btn").addEventListener("click", () => {
    document.body.classList.add("print-cards");
    window.print();
    setTimeout(() => document.body.classList.remove("print-cards"), 500);
  });
  $("#bb-export").addEventListener("click", () => {
    // the export href is set on every render so the download carries the saved order
  });

  // palette — platform-honest hint (macOS shows ⌘K, everything else Ctrl K)
  const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
  const palBtn = $("#palette-btn");
  if (palBtn) {
    palBtn.textContent = isMac ? "⌘K" : "Ctrl K";
    palBtn.title = isMac ? "Command palette (⌘K)" : "Command palette (Ctrl+K)";
  }
  $("#palette-btn").addEventListener("click", () => openPalette(false));
  const homeBtn = $("#home-btn");
  if (homeBtn) homeBtn.addEventListener("click", goHome);
  renderExploreChips();
  wireExploreChips();
  $("#palette-input").addEventListener("input", renderPalette);
  bindGlobalShortcuts();

  // error banner
  $("#error-banner-dismiss").addEventListener("click", hideError);

  // surface anything unexpected instead of failing silently
  window.addEventListener("error", (e) => showError("Something went wrong: " + e.message));
  window.addEventListener("unhandledrejection", (e) => showError("Something went wrong: " + (e.reason && e.reason.message ? e.reason.message : e.reason)));
}



// ============================================================
// Problem Board: findings panel synced with script scroll
// ============================================================

let pbCurrentScene = -1;
let pbScrollObserver = null;

function renderProblemBoard() {
  var list = document.getElementById('pb-list');
  if (!list) return;
  var findings = state.findings || [];
  var filter = (document.getElementById('pb-filter') || {}).value || 'all';
  var filtered = filter === 'all' ? findings : findings.filter(function(f) { return (f.severity || 'medium').toLowerCase() === filter; });
  
  if (!filtered.length) {
    list.innerHTML = '<div class="pb-empty">No findings to show.<br>Run Analysis to generate findings.</div>';
    return;
  }
  
  var html = '';
  filtered.forEach(function(f, idx) {
    var sev = (f.severity || 'medium').toLowerCase();
    var sceneNum = (f.scene_refs && f.scene_refs[0]) || f.scene || '?';
    var realIdx = findings.indexOf(f);
    // Finding text is MODEL OUTPUT derived from the writer's own script, and a
    // screenplay is a file a collaborator can send you — so every interpolation
    // here is escaped. Row wiring is DELEGATED (see the #pb-list listener in
    // init): building onclick="…" out of data both invites attribute injection
    // and would force script-src 'unsafe-inline', defeating the CSP that
    // contains any sink we might still miss.
    html += '<div class="pb-item" data-findex="' + escapeHtml(realIdx) + '" data-scene="' + escapeHtml(sceneNum) + '">';
    html += '<span class="pb-sev ' + escapeHtml(sev) + '"></span>';
    html += '<span class="pb-scene">Sc ' + escapeHtml(sceneNum) + '</span>';
    html += '<div class="pb-body">';
    html += '<div class="pb-cat">' + escapeHtml(f.category || 'General') + '</div>';
    html += '<div class="pb-issue">' + escapeHtml(f.description || f.issue || '') + '</div>';
    html += '</div></div>';
  });
  list.innerHTML = html;
  update_pb_highlight();
}

function pbItemClick(findex, sceneNum) {
  // Scroll the script pane to the scene
  var page = document.getElementById('scene-page-' + sceneNum);
  if (page) {
    page.scrollIntoView({ behavior: 'smooth', block: 'start' });
    page.classList.remove('flash');
    void page.offsetWidth;
    page.classList.add('flash');
    setTimeout(function() { page.classList.remove('flash'); }, 1600);
  }
}

function update_pb_highlight() {
  var list = document.getElementById('pb-list');
  if (!list) return;
  var items = list.querySelectorAll('.pb-item');
  for (var i = 0; i < items.length; i++) {
    var sceneNum = parseInt(items[i].dataset.scene);
    items[i].classList.toggle('active', sceneNum === pbCurrentScene);
  }
}

function initProblemBoardScrollSync() {
  if (pbScrollObserver) pbScrollObserver.disconnect();
  var container = getManuscriptContainer();
  if (!container) return;

  // Build a set of scene numbers that have findings for auto-hide/show
  var scenesWithFindings = {};
  (state.findings || []).forEach(function(f) {
    var refs = f.scene_refs || [];
    if (f.scene) refs = refs.concat([f.scene]);
    refs.forEach(function(n) { scenesWithFindings[n] = true; });
  });

  pbScrollObserver = new IntersectionObserver(function(entries) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].isIntersecting) {
        var sceneNum = parseInt(entries[i].target.dataset.sceneNumber);
        if (sceneNum && sceneNum !== pbCurrentScene) {
          pbCurrentScene = sceneNum;
          update_pb_highlight();
          // Auto-scroll the Problem Board to show the active finding
          var activeItem = document.querySelector('.pb-item[data-scene="' + sceneNum + '"]');
          if (activeItem) activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          // Auto-expand/collapse: the board slides in when the active scene
          // has findings, and slides away when it doesn’t.
          var board = document.getElementById('problem-board');
          if (board && board.classList.contains('visible')) {
            if (scenesWithFindings[sceneNum]) {
              expandProblemBoard();
            } else {
              collapseProblemBoard();
            }
          }
        }
        break;
      }
    }
  }, { root: container, threshold: 0.3 });

  var scenes = container.querySelectorAll('.scene-page');
  for (var j = 0; j < scenes.length; j++) {
    pbScrollObserver.observe(scenes[j]);
  }
}

function showProblemBoard() {
  var board = document.getElementById('problem-board');
  if (board) {
    board.style.display = 'flex';
    board.classList.add('visible');
    board.classList.remove('pb-collapsed');
    var edgeTab = document.getElementById('pb-edge-tab');
    if (edgeTab) edgeTab.style.display = 'none';
    renderProblemBoard();
    initProblemBoardScrollSync();
  }
}

function hideProblemBoard() {
  var board = document.getElementById('problem-board');
  if (board) {
    board.classList.remove('visible');
    board.classList.remove('pb-collapsed');
    board.style.display = 'none';
  }
  if (pbScrollObserver) { pbScrollObserver.disconnect(); pbScrollObserver = null; }
  pbCurrentScene = -1;
}

function toggleProblemBoard() {
  var board = document.getElementById('problem-board');
  if (!board) return;
  if (!board.classList.contains('visible')) {
    // Board not shown at all yet -- show it expanded
    showProblemBoard();
  } else if (board.classList.contains('pb-collapsed')) {
    // Board is collapsed -- expand it (slide in from right)
    board.classList.remove('pb-collapsed');
    var edgeTab = document.getElementById('pb-edge-tab');
    if (edgeTab) edgeTab.style.display = 'none';
  } else {
    // Board is visible and expanded -- collapse it (slide out to right)
    board.classList.add('pb-collapsed');
    var edgeTab2 = document.getElementById('pb-edge-tab');
    if (edgeTab2) edgeTab2.style.display = '';
  }
}

function collapseProblemBoard() {
  var board = document.getElementById('problem-board');
  if (!board || !board.classList.contains('visible')) return;
  board.classList.add('pb-collapsed');
  var edgeTab = document.getElementById('pb-edge-tab');
  if (edgeTab) edgeTab.style.display = '';
}

function expandProblemBoard() {
  var board = document.getElementById('problem-board');
  if (!board) return;
  board.classList.remove('pb-collapsed');
  var edgeTab = document.getElementById('pb-edge-tab');
  if (edgeTab) edgeTab.style.display = 'none';
}

// ============================================================
// NOCTA DESIGN SYSTEM — Craft Precision
// Auto-hide chrome, Sameer panel, level badge, cursor spotlight
// ============================================================

// ---- Craft palette helper: pre-fill the composer that actually sends ----
//
// This used to open the off-canvas #sameer-panel and fill #sameer-ta — a surface
// whose Send button echoed the text into its own thread and made no API call, and
// whose three "messages" were hardcoded prose about a script nobody had opened.
// Because all seven craft questions in the command palette route through here,
// every one of them was silently discarded (H3). The panel is deleted; the
// question now lands in the Co-write room's real composer, one keystroke from
// being sent.
function openSameerWith(question) {
  if (state.view !== "cowrite") openCowriteRoom();
  const input = $("#input");
  if (input) {
    input.value = question;
    input.focus();
  }
}

// ---- Level badge (progressive revelation) ----
let craftLevel = 1;
const levelNames = {
  1: "Level 1 \u00b7 Upload & Discover",
  2: "Level 2 \u00b7 Explore Findings",
  3: "Level 3 \u00b7 Deep Dive",
  4: "Level 4 \u00b7 Master View",
};

function setCraftLevel(n) {
  craftLevel = Math.max(1, Math.min(4, n));
  document.body.className = document.body.className.replace(/level-\d/g, "") + " level-" + craftLevel;
  const text = $("#level-text");
  if (text) text.textContent = levelNames[craftLevel];
}

// ---- Auto-hide chrome ----
let chromeHideTimer = null;
const CHROME_HIDE_DELAY = 4000; // 4s idle

function showChrome() {
  document.body.classList.add("chrome-visible");
  clearTimeout(chromeHideTimer);
  chromeHideTimer = setTimeout(hideChrome, CHROME_HIDE_DELAY);
}

function hideChrome() {
  document.body.classList.remove("chrome-visible");
}

// ---- Cursor spotlight ----
function initSpotlight() {
  const spot = $("#cursor-spotlight");
  if (!spot) return;
  document.addEventListener("mousemove", (e) => {
    spot.style.setProperty("--gx", e.clientX + "px");
    spot.style.setProperty("--gy", e.clientY + "px");
  });
}

// ---- Wire everything on DOMContentLoaded ----
function initNoctaDesign() {
  // Auto-hide chrome
  document.body.classList.add("auto-hide-chrome");
  // Show chrome once on load so the writer sees the toolbar immediately.
  // The existing 4s idle timer hides it after that.
  showChrome();
  document.addEventListener("mousemove", (e) => {
    if (e.clientY < 120) showChrome();
  });
  // Always show chrome when hovering over sidebar or modals
  $("#sidebar").addEventListener("mouseenter", showChrome);
  document.querySelectorAll(".modal-overlay").forEach((m) => {
    m.addEventListener("mouseenter", showChrome);
  });
  // a11y pass 12 (WCAG 2.4.7): keyboard focus into either bar reveals the
  // chrome and re-arms the same 4s idle timer the mouse path uses —
  // Tab-only users could otherwise focus invisible controls after idle-hide.
  ["#project-bar", "#desk-toolbar"].forEach((sel) => {
    const bar = $(sel);
    if (bar) bar.addEventListener("focusin", showChrome);
  });

  // (The off-canvas Sameer panel's handlers were removed with the panel itself —
  // H3. Its Send echoed the text into its own thread and never called the API.)

  // Level badge — auto-advance on finding interaction
  document.addEventListener("click", (e) => {
    const card = e.target instanceof Element ? e.target.closest(".finding-card, .fix-row, .cat") : null;
    if (card && craftLevel < 2) setCraftLevel(2);
    if (card && craftLevel < 3) setTimeout(() => setCraftLevel(3), 2000);
  });
  setCraftLevel(1);

  // Cursor spotlight
  initSpotlight();
}

document.addEventListener("DOMContentLoaded", initNoctaDesign);

document.addEventListener("DOMContentLoaded", init);

// Text selection popup — context-aware actions on highlight
(function initTextPopup() {
  const popup = $("#text-popup");
  if (!popup) return;
  let activeSelection = null;
  let hideTimeout = null;

  function showPopup(x, y, context) {
    // Hide all items first
    popup.querySelectorAll(".text-popup-item").forEach(el => el.style.display = "none");
    // Show context-appropriate items
    const askSameer = popup.querySelector('[data-action="ask-sameer"]');
    const askConsultant = popup.querySelector('[data-action="ask-consultant"]');
    const marginNote = popup.querySelector('[data-action="margin-note"]');
    const stash = popup.querySelector('[data-action="stash"]');
    const addLogline = popup.querySelector('[data-action="add-logline"]');
    const rewrite = popup.querySelector('[data-action="rewrite"]');
    const locate = popup.querySelector('[data-action="locate"]');

    if (context === "idea") {
      askSameer.style.display = "";
      addLogline.style.display = "";
      marginNote.style.display = "";
      stash.style.display = "";
    } else if (context === "script") {
      askSameer.style.display = "";
      askConsultant.style.display = "";
      marginNote.style.display = "";
      stash.style.display = "";
    } else if (context === "revision") {
      askSameer.style.display = "";
      askConsultant.style.display = "";
      rewrite.style.display = "";
      locate.style.display = "";
    }

    // Position popup near cursor, keep in viewport
    popup.style.left = Math.min(x, window.innerWidth - 200) + "px";
    popup.style.top = Math.min(y, window.innerHeight - 200) + "px";
    popup.style.display = "block";
  }

  function hidePopup() {
    popup.style.display = "none";
    activeSelection = null;
  }

  function getSelectionContext() {
    if (state.inIdea) return "idea";
    if (document.getElementById("revision-view") && !document.getElementById("revision-view").style.display.includes("none")) return "revision";
    return "script";
  }

  // Listen for mouseup (text selection end)
  document.addEventListener("mouseup", (e) => {
    clearTimeout(hideTimeout);
    // Don't show popup if clicking inside the popup itself or a chat composer
    if (popup.contains(e.target)) return;
    // e.target can be a non-Element (document/window) when the event is
    // synthetic or lands on the document node — closest only exists on
    // Elements, and one stray throw would kill the selection popup for
    // the rest of the session
    if (e.target && e.target.closest && (e.target.closest(".composer") || e.target.closest("#input"))) {
      hidePopup();
      return;
    }
    // Check if there's a selection
    const sel = window.getSelection();
    if (sel && sel.toString().trim().length > 2) {
      activeSelection = sel.toString().trim();
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      showPopup(rect.left + rect.width / 2, rect.bottom + 8, getSelectionContext());
    } else {
      // Delay hide to allow clicking popup items
      hideTimeout = setTimeout(hidePopup, 200);
    }
  });

  // Hide on Esc
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hidePopup();
  });

  // Handle popup item clicks
  popup.addEventListener("click", (e) => {
    const item = e.target.closest(".text-popup-item");
    if (!item) return;
    const action = item.dataset.action;
    const text = activeSelection || "";
    if (action === "ask-sameer") {
      // Open Sameer drawer with the selected text quoted
      openCowriteRoom();
      const input = $("#input");
      if (input) {
        input.value = '/sameer "' + text.substring(0, 200) + '"';
        input.focus();
      }
    } else if (action === "ask-consultant") {
      openFeedbackRoom();
      const input = $("#input");
      if (input) {
        input.value = '"' + text.substring(0, 200) + '"';
        input.focus();
      }
    } else if (action === "margin-note") {
      // Pin a note to the current line — the form lives in the dock's
      // Stash & Notes lens now (Phase 13; the structure rail is retired)
      const noteInput = $("#dock-note-input");
      if (noteInput) {
        noteInput.value = text.substring(0, 200);
        openDock("notes");
        noteInput.focus();
      }
    } else if (action === "stash") {
      // Stash the selected text — same POST the 📥 float uses. The rail-era
      // code parked "[STASH]" text in the note form, which filed it as a
      // margin note (wrong store — the Stash list never saw it). Phase 13.
      const entry = { text: text.substring(0, 200), scene_number: null };
      if (entry.text && state.currentProject) {
        api(`/projects/${encodeURIComponent(state.currentProject)}/stash`, {
          method: "POST", body: JSON.stringify(entry),
        }).then(loadStash).catch((err) => showError("Couldn't stash that: " + err.message));
      }
    }
    hidePopup();
  });
})();
