// Script Doctor Studio — frontend logic (vanilla JS, no build step)

const API = "/api";

const state = {
  projects: [],
  currentProject: null,   // project name (string)
  currentSession: null,   // session id
  branches: {},           // { branchName: { messages, active_persona, active_mode, parent_branch } }
  currentBranch: "main",
  config: { server_url: "http://localhost:8080", model: null, timeout: 600 },
  view: "chat",          // "chat" | "script"
  script: null,           // working-copy ScriptDocument JSON (script view)
  findings: [],           // findings from report.findings.json
  findingStatus: {},      // finding index -> addressed / still_present / unknown
  editsData: null,        // { edits, findings_status } from /edits
  drafts: null,           // { active_draft, drafts } from /drafts
  fixQueue: null,         // { items, acts } from /fixqueue
  reportStats: null,      // stats from report.findings.json
  notes: [],              // the writer's own margin notes
};

// ---------- utilities ----------

function $(sel) { return document.querySelector(sel); }
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function api(path, options = {}) {
  const resp = await fetch(API + path, {
    headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  let data = null;
  try { data = await resp.json(); } catch (_) { /* no body */ }
  if (!resp.ok) {
    const message = (data && data.error) || `Request failed (${resp.status})`;
    throw new Error(message);
  }
  return data;
}

function truncate(text, n) {
  text = text.trim().replace(/\s+/g, " ");
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** Starts a live "Xm Ys elapsed" ticker inside a target element, prefixed
 * with a fixed label. Returns a stop function. Exists specifically so long
 * local-model waits (which are normal, not broken) read as "working", not
 * "frozen". */
function startElapsedTicker(targetEl, label) {
  const startedAt = Date.now();
  const tick = () => {
    const elapsed = (Date.now() - startedAt) / 1000;
    targetEl.textContent = `${label} — ${formatElapsed(elapsed)} elapsed`;
  };
  tick();
  const handle = setInterval(tick, 1000);
  return () => clearInterval(handle);
}

/** Minimal, SAFE text formatting for assistant replies: escapes HTML first
 * (so nothing the model writes can inject markup), then supports just
 * **bold** and "- " bullet lines -- enough to make dense analysis notes
 * readable without pulling in a full markdown parser. */
function formatMessageContent(raw) {
  const escaped = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const bolded = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const lines = bolded.split("\n");
  let html = "";
  let inList = false;
  for (const line of lines) {
    const bulletMatch = line.match(/^\s*[-•]\s+(.*)/);
    if (bulletMatch) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${bulletMatch[1]}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += line.length ? `<p>${line}</p>` : "<br>";
    }
  }
  if (inList) html += "</ul>";
  return html;
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
const FALLBACK_PERSONAS = ["script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"];
const FALLBACK_MODES = ["evidence_discussion", "brainstorm", "character_interview"];
const FALLBACK_PERSONA_LABELS = {
  script_consultant: "Script Consultant", producer: "Producer", dev_exec: "Dev Exec",
  teacher: "Teacher", audience: "Audience", genre_specialist: "Genre Specialist",
};
const FALLBACK_MODE_LABELS = { evidence_discussion: "Grounded Discussion", brainstorm: "Brainstorm", character_interview: "Character Interview" };

async function loadConfig() {
  try {
    state.config = await api("/config");
    $("#server-url-input").value = state.config.server_url || "";
    $("#timeout-input").value = state.config.timeout || 600;
  } catch (e) {
    console.warn("Could not load config:", e);
  }
  checkConnection();
}

async function saveConfig() {
  const server_url = $("#server-url-input").value.trim();
  const timeout = parseInt($("#timeout-input").value, 10) || 600;
  try {
    state.config = await api("/config", { method: "POST", body: JSON.stringify({ server_url, timeout }) });
    closeModal("#settings-modal");
    checkConnection();
  } catch (e) {
    showError("Couldn't save settings: " + e.message);
  }
}

async function testConnection() {
  const btn = $("#test-connection-btn");
  const resultEl = $("#test-connection-result");
  const url = $("#server-url-input").value.trim();
  btn.disabled = true;
  resultEl.className = "test-connection-result";
  resultEl.textContent = "Checking…";
  try {
    const res = await api("/test-connection", { method: "POST", body: JSON.stringify({ server_url: url }) });
    resultEl.textContent = res.message;
    resultEl.classList.add(res.ok ? "ok" : "fail");
  } catch (e) {
    resultEl.textContent = "Couldn't check: " + e.message;
    resultEl.classList.add("fail");
  }
  btn.disabled = false;
}

async function checkConnection() {
  const dot = $("#connection-dot");
  try {
    const res = await api("/test-connection", { method: "POST", body: JSON.stringify({}) });
    dot.className = "connection-dot " + (res.ok ? "ok" : "fail");
    dot.title = res.message;
  } catch (e) {
    dot.className = "connection-dot fail";
    dot.title = "Couldn't check connection: " + e.message;
  }
}

// ---------- projects ----------

async function loadProjects() {
  try {
    state.projects = await api("/projects");
    renderProjectList();
  } catch (e) {
    showError("Couldn't load your projects: " + e.message, true);
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
  if (!state.projects.length) {
    list.appendChild(el("p", "empty-hint", "No screenplays yet — upload one to begin."));
    return;
  }
  for (const p of state.projects) {
    const item = el("div", "project-item" + (p.project === state.currentProject ? " active" : ""));
    const dotClass = p.stages.analyze === "complete" ? "complete" : p.stages.analyze === "failed" ? "failed" : "";
    const row = el("div", "project-item-row");
    row.appendChild(el("span", "stage-dot" + (dotClass ? " " + dotClass : "")));
    row.appendChild(document.createTextNode(p.title));
    item.appendChild(row);
    item.appendChild(el("div", "project-item-status", stageLabel(p)));
    const del = el("button", "project-delete", "✕");
    del.type = "button";
    del.title = `Remove "${p.title}" from the shelf (deletes its files)`;
    del.setAttribute("aria-label", `Remove ${p.title} from the shelf`);
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!window.confirm(`Remove "${p.title}" from the shelf?\nThis deletes the project and its analysis from this machine.`)) return;
      try {
        await api(`/projects/${encodeURIComponent(p.project)}`, { method: "DELETE" });
        if (state.currentProject === p.project) {
          state.currentProject = null;
          state.currentSession = null;
          state.script = null;
          state.findings = [];
          state.fixQueue = null;
          state.branches = { main: { messages: [], active_persona: "script_consultant", active_mode: "evidence_discussion" } };
          state.currentBranch = "main";
          hideAllViews();
          $("#welcome-view").style.display = "flex";
          $("#input").value = "";
        }
        await loadProjects();
        saveSession();
      } catch (err) {
        showError("Couldn't remove the project: " + err.message);
      }
    });
    item.appendChild(del);
    item.addEventListener("click", () => openProject(p.project));
    list.appendChild(item);
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
}

function applyReaderMode(on) {
  document.body.classList.toggle("reader-mode", !!on);
  const btn = $("#reader-btn");
  if (btn) btn.classList.toggle("active", !!on);
}

function saveSession() {
  try {
    const payload = { project: state.currentProject, view: state.view };
    if ((state.view === "cowrite" || state.view === "feedback") && state.script && state.script.scenes && state.script.scenes.length) {
      const container = document.getElementById("script-scenes");
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

async function openProject(name) {
  try {
    state.currentProject = name;
    state.script = null;
    state.findings = [];
    state.findingStatus = {};
    state.fixQueue = null;
    state.reportStats = null;
    const project = await api(`/projects/${encodeURIComponent(name)}`);
    renderProjectList();

    $("#welcome-view").style.display = "none";
    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "flex";
    $("#project-title").textContent = project.title;
    $("#project-title").title = project.title;

    $("#analyze-btn").textContent = project.stages.analyze === "complete" ? "Re-run Analysis" : "Run Analysis";
    $("#analyze-btn").disabled = project.stages.parse !== "complete";

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
      renderCheckpoints();
      populateSelectors();
    }

    // the script pane is always visible in both rooms — render it once
    try { await loadScriptData(); } catch (_) { /* no parse yet — pane shows its hint */ }
    renderScriptView();
    maybeShowWelcome();

    setRoom("cowrite");
    saveSession();
  } catch (e) {
    showError("Couldn't open that project: " + e.message);
  }
}

// ---------- rooms: Co-write (writer's desk) vs Feedback (consultant's desk) ----------
// The script pane is shared and always visible; the room toggle swaps the right
// panel and the room's visual identity (see body[data-room] in style.css).

function setRoom(room) {
  state.view = room;                       // "cowrite" | "feedback"
  document.body.dataset.room = room;       // drives CSS theming
  const chip = $("#room-chip");
  if (chip) chip.textContent = room === "feedback" ? "📋 Consultant's Desk" : "✍️ Writer's Desk";
  $("#room-cowrite-btn").classList.toggle("active", room === "cowrite");
  $("#room-feedback-btn").classList.toggle("active", room === "feedback");
  $("#cowrite-panel").style.display = room === "cowrite" ? "flex" : "none";
  $("#feedback-panel").style.display = room === "feedback" ? "flex" : "none";
  // closing a full-screen tool returns to the active room
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  const ws = document.querySelector(".workspace");
  if (ws) ws.style.display = "flex";
  saveSession();
}

function openCowriteRoom() {
  if (state.view === "cowrite") return;
  setRoom("cowrite");
  renderMessages();
  maybeShowWelcome();
}

function openFeedbackRoom() {
  if (state.view === "feedback") return;
  setRoom("feedback");
  if (typeof loadFeedbackPanels === "function") loadFeedbackPanels();  // defined in Task 10
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
  { key: "summaries", label: "Scene summaries", weight: 3 },
  { key: "dialogue", label: "Dialogue & action", weight: 5 },
  { key: "theme", label: "Theme & subtext", weight: 2 },
  { key: "character", label: "Character arcs", weight: 2 },
  { key: "structure", label: "Structure & pacing", weight: 2 },
  { key: "scene_function", label: "Scene functionality", weight: 2 },
  { key: "principles", label: "Setups & payoffs", weight: 3 },
  { key: "char_reads", label: "Character perception", weight: 2 },
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
  btn.disabled = true;
  chip.style.display = "flex";
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
    if (renderedFor !== currentKey) {
      renderedFor = currentKey;
      const old = chip.querySelector(".analyze-pipeline");
      if (old) old.remove();
      chip.appendChild(renderPipelinePopover(currentKey));
    }
  };

  const timer = setInterval(refresh, 1000);
  const poll = setInterval(async () => {
    try {
      const p = await api(`${base}/progress`);
      if (p.stage === "done" || p.stage === "failed") {
        // the run finished on its own (e.g. this page resumed mid-analysis)
        clearInterval(poll);
        clearInterval(timer);
        finished = true;
        analysisUi = null;
        hideAnalysisProgressUI();
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
  const btn = $("#analyze-btn");
  if (btn) btn.disabled = false;
}

async function runAnalysis() {
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
    await loadProjects();
    // script pane is shared — refresh it in either room after analysis
    await loadScriptData();
    renderScriptView();
    if (state.view === "feedback") loadFeedbackPanels();
  } catch (e) {
    if (analysisUi) analysisUi.stop();
    hideAnalysisProgressUI();
    btn.textContent = "Run Analysis";
    showError("Analysis failed: " + e.message, true);
    appendSystemNote("Analysis failed: " + e.message, true);
  }
}

// ---------- sessions / chat ----------

async function ensureSession() {
  if (state.currentSession) return state.currentSession;
  const res = await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/start`, { method: "POST" });
  state.currentSession = res.session_id;
  await loadSession(res.session_id);
  return res.session_id;
}

async function loadSession(sessionId) {
  const data = await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${sessionId}`);
  state.currentSession = data.session_id;
  state.branches = data.branches;
  state.currentBranch = data.current_branch;
  resetChatHistory();
  renderMessages();
  renderBranches();
  renderCheckpoints();
  populateSelectors();
}

function currentBranchData() {
  return state.branches[state.currentBranch] || { messages: [], active_persona: "script_consultant", active_mode: "evidence_discussion" };
}

function renderMessages() {
  const container = $("#messages");
  container.innerHTML = "";
  const msgs = currentBranchData().messages || [];
  if (!msgs.length) {
    const hint = el("div", "chat-empty-hint");
    hint.innerHTML =
      "Ask about a theme, a character, or a specific scene (e.g. <em>\"what about Scene 12?\"</em>) — " +
      "or just say hello and we'll take it from there. Run analysis first if you want the conversation " +
      "grounded in a full report; it works fine without one too, just more loosely.";
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

function renderMessage(m, index) {
  const wrap = el("div", "msg " + (m.role === "user" ? "user" : "assistant"));
  wrap.id = `msg-${index}`;
  const head = el("div", "msg-head");
  head.appendChild(el("div", "msg-role", m.role === "user" ? "You" : "Studio"));
  const origin = messageOriginBranch(index);
  const badge = el("span", "branch-badge", origin);
  badge.style.setProperty("--badge-h", branchHue(origin));
  badge.title = `This message belongs to the “${origin}” thread`;
  head.appendChild(badge);
  wrap.appendChild(head);
  const bubble = el("div", "msg-bubble");
  if (m.role === "user") {
    bubble.textContent = m.content;
  } else {
    bubble.innerHTML = formatMessageContent(m.content);
  }
  wrap.appendChild(bubble);
  return wrap;
}

function appendSystemNote(text, isError) {
  const container = $("#messages");
  if (container.querySelector(".chat-empty-hint")) container.innerHTML = "";
  const note = el("div", "msg assistant");
  note.appendChild(el("div", "msg-role", "Studio"));
  const bubble = el("div", "msg-bubble", text);
  if (isError) bubble.style.color = "var(--rust-flag)";
  note.appendChild(bubble);
  container.appendChild(note);
  container.scrollTop = container.scrollHeight;
  updateRailPositions(container);
}

// ---------- conversation rail (jump markers) ----------
// A thin track along the right edge of the chat, one tick per question the
// writer asked — hover a tick to peek at the question, click it to jump the
// conversation back to exactly that message. No scrolling the whole thread.

function renderMessageRail() {
  const container = $("#messages");
  let rail = container.querySelector("#msg-rail");
  if (!rail) {
    rail = el("div", "msg-rail");
    rail.id = "msg-rail";
    container.appendChild(rail);
  }
  rail.innerHTML = "";
  const msgs = currentBranchData().messages || [];
  const indices = msgs.map((m, i) => (m.role === "user" ? i : -1)).filter((i) => i >= 0);
  if (!indices.length) {
    rail.classList.add("empty");
    return;
  }
  rail.classList.remove("empty");
  for (const i of indices) {
    const marker = el("button", "rail-marker");
    marker.type = "button";
    marker.dataset.index = i;
    marker.title = msgs[i].content;
    marker.setAttribute("aria-label", `Jump to your message: ${msgs[i].content}`);
    marker.addEventListener("mouseenter", () => showRailTip(container, marker, msgs[i].content));
    marker.addEventListener("mouseleave", hideRailTip);
    marker.addEventListener("focus", () => showRailTip(container, marker, msgs[i].content));
    marker.addEventListener("blur", hideRailTip);
    marker.addEventListener("click", () => {
      const target = document.getElementById(`msg-${i}`);
      if (!target) return;
      container.scrollTop = Math.max(0, target.offsetTop - (container.clientHeight - target.clientHeight) / 2);
      updateRailCurrent(container);
      saveSession();
    });
    rail.appendChild(marker);
  }
  rail.appendChild(el("div", "rail-tip"));
  updateRailPositions(container);
}

function updateRailPositions(container) {
  const rail = container.querySelector("#msg-rail");
  if (!rail || rail.classList.contains("empty")) return;
  const scrollable = container.scrollHeight > container.clientHeight + 4;
  rail.classList.toggle("scrollable", scrollable);
  if (!scrollable) return;
  const markers = rail.querySelectorAll(".rail-marker");
  for (const marker of markers) {
    const target = document.getElementById(`msg-${marker.dataset.index}`);
    if (!target) continue;
    const pct = ((target.offsetTop + target.offsetHeight / 2) / container.scrollHeight) * 100;
    marker.style.top = Math.min(98, Math.max(2, pct)) + "%";
  }
  updateRailCurrent(container);
}

function updateRailCurrent(container) {
  const rail = container.querySelector("#msg-rail");
  if (!rail) return;
  const markers = rail.querySelectorAll(".rail-marker");
  const viewMid = container.scrollTop + container.clientHeight / 2;
  let current = null;
  let bestDist = Infinity;
  for (const marker of markers) {
    const target = document.getElementById(`msg-${marker.dataset.index}`);
    if (!target) continue;
    const mid = target.offsetTop + target.offsetHeight / 2;
    const dist = Math.abs(mid - viewMid);
    if (dist < bestDist) { bestDist = dist; current = marker; }
  }
  for (const m of markers) m.classList.toggle("current", m === current);
}

function showRailTip(container, marker, content) {
  const rail = container.querySelector("#msg-rail");
  if (!rail) return;
  let tip = rail.querySelector(".rail-tip");
  if (!tip) {
    tip = el("div", "rail-tip");
    rail.appendChild(tip);
  }
  tip.textContent = content;
  const markerTop = marker.offsetTop;
  tip.style.top = Math.max(0, Math.min(markerTop - 12, rail.clientHeight - 36)) + "px";
  tip.classList.add("visible");
}

function hideRailTip() {
  const tip = document.querySelector(".rail-tip");
  if (tip) tip.classList.remove("visible");
}

function renderBranches() {
  const wrap = $("#branch-switcher");
  wrap.innerHTML = "";
  for (const name of Object.keys(state.branches)) {
    const pill = el("button", "branch-pill" + (name === state.currentBranch ? " active" : ""), name);
    pill.type = "button";
    pill.title = name === state.currentBranch ? "Current branch" : `Switch to "${name}"`;
    pill.addEventListener("click", () => switchBranch(name));
    wrap.appendChild(pill);
  }
  const addBtn = el("button", "branch-pill add", "+ fork");
  addBtn.type = "button";
  addBtn.title = "Branch this conversation into a new thread from here";
  addBtn.addEventListener("click", () => openModal("#fork-modal"));
  wrap.appendChild(addBtn);
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
    renderCheckpoints();
    populateSelectors();
  } catch (e) {
    showError("Couldn't switch branches: " + e.message);
  }
}

async function createFork() {
  const name = $("#fork-name-input").value.trim();
  if (!name) return;
  try {
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
  // "back to Sam": reset the current branch to the writing-partner default
  await _setPersonaMode("writing_partner", "peer");
  renderMessages();
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

  input.value = "";
  input.style.height = "auto";
  resetChatHistory();
  $("#send-btn").disabled = true;

  const container = $("#messages");
  if (container.querySelector(".chat-empty-hint")) container.innerHTML = "";
  const optimisticIndex = (currentBranchData().messages || []).length;
  const userMsg = renderMessage({ role: "user", content: text }, optimisticIndex);
  container.appendChild(userMsg);
  const pending = el("div", "msg assistant msg-pending");
  pending.appendChild(el("div", "msg-role", "Studio"));
  const pendingBubble = el("div", "msg-bubble", "Reading the pages…");
  pending.appendChild(pendingBubble);
  container.appendChild(pending);
  container.scrollTop = container.scrollHeight;
  const stopTicker = startElapsedTicker(pendingBubble, "Reading the pages…");

  try {
    const sessionId = await ensureSession();
    const res = await api(`/projects/${encodeURIComponent(state.currentProject)}/chat/sessions/${sessionId}/messages`, {
      method: "POST", body: JSON.stringify({ text }),
    });
    stopTicker();
    state.branches[state.currentBranch] = { ...currentBranchData(), messages: res.messages };
    renderMessages();
    renderCheckpoints();
  } catch (e) {
    stopTicker();
    pendingBubble.textContent = "Couldn't get a reply: " + e.message;
    pending.classList.remove("msg-pending");
    pendingBubble.style.color = "var(--rust-flag)";
    showError("Chat message failed: " + e.message);
  }

  $("#send-btn").disabled = false;
  input.focus();
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

// ---------- checkpoint rail ----------

function renderCheckpoints() {
  const list = $("#checkpoint-list");
  list.innerHTML = "";
  const msgs = currentBranchData().messages || [];
  const userIndices = msgs.map((m, i) => (m.role === "user" ? i : -1)).filter((i) => i >= 0);

  if (!userIndices.length) {
    list.appendChild(el("p", "checkpoint-empty", "Your messages will show up here so you can jump back to them."));
    return;
  }

  for (const i of userIndices) {
    const card = el("div", "checkpoint-card", truncate(msgs[i].content, 70));
    card.title = "Jump to this point in the conversation";
    card.addEventListener("click", () => {
      const target = document.getElementById(`msg-${i}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
      document.querySelectorAll(".checkpoint-card.current").forEach((c) => c.classList.remove("current"));
      card.classList.add("current");
    });
    list.appendChild(card);
  }
}

// ---------- script & notes view (revision loop) ----------

const SEVERITY_CLASS = { high: "", medium: " sev-medium", low: " sev-low" };
const CATEGORY_LABELS = {
  theme: "Theme", character: "Character", structure: "Structure", dialogue: "Dialogue",
  scene_function: "Scene function", plot_thread: "Plot economy", genre: "Genre",
  voice: "Voice", subtext: "Subtext",
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
  try {
    report = await api(`${base}/report`);
    findings = report.findings || [];
  } catch (_) { /* analysis not complete — script-only mode */ }
  state.findings = findings;
  state.report = report;
  state.reportStats = (report && report.stats) || null;
  const statusByIndex = {};
  for (const s of (state.editsData.findings_status && state.editsData.findings_status.findings) || []) {
    statusByIndex[s.index] = s.status;
  }
  state.findingStatus = statusByIndex;
  try {
    state.fixQueue = await api(`${base}/fixqueue`);
  } catch (_) {
    state.fixQueue = { items: [], acts: [] };
  }
  renderDraftBar();
  await renderDiffBanner();
}

// ---- fix queue / craft panels ----

function renderFixQueuePanel(container) {
  const items = (state.fixQueue && state.fixQueue.items) || [];
  const open = items.filter((i) => i.status !== "addressed");
  if (!items.length) return;

  const panel = el("div", "craft-panel fix-queue");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", `Fix queue — ${open.length} open / ${items.length} total`));
  panel.appendChild(head);

  for (const item of items) {
    const row = el("div", "fix-row" + (item.status === "addressed" ? " done" : ""));
    const sev = el("span", "sev-badge sev-" + (item.severity || "low"), (item.severity || "low").toUpperCase());
    const act = el("span", "act-chip", item.act_name || "Script-level");
    const sceneLabel = item.scene_heading ? `Scene ${(item.scene_refs || [])[0]} — ${item.scene_heading}` : "General";
    const body = el("div", "fix-row-body");
    const issue = el("div", "fix-row-issue", `${sceneLabel}: ${item.issue}`);
    if (item.why_it_matters) issue.appendChild(el("div", "fix-row-why", item.why_it_matters));
    body.appendChild(issue);
    const actions = el("div", "fix-row-actions");
    const rewriteBtn = el("button", "", "Rewrite");
    rewriteBtn.type = "button";
    rewriteBtn.addEventListener("click", () => {
      const refs = item.scene_refs || [];
      openRewriteModal(refs[0] || 1, item, item.index);
    });
    const discussBtn = el("button", "", "Discuss");
    discussBtn.type = "button";
    discussBtn.addEventListener("click", () => discussFinding(item, item.index));
    actions.appendChild(rewriteBtn);
    actions.appendChild(discussBtn);
    body.appendChild(actions);
    row.appendChild(sev);
    row.appendChild(act);
    row.appendChild(body);
    panel.appendChild(row);
  }
  container.appendChild(panel);
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
  container.appendChild(panel);
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
  container.appendChild(panel);
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

  container.appendChild(panel);
}

// ---- drafts & diffing ----

function renderDraftBar() {
  const bar = $("#draft-bar");
  const hasDrafts = state.drafts && state.drafts.drafts && state.drafts.drafts.length > 0;
  bar.style.display = hasDrafts ? "flex" : "none";
  if (!hasDrafts) return;

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
  for (const [idx, status] of Object.entries(state.findingStatus)) {
    if (state.findings[idx] && state.findings[idx].category === "formatting") continue;
    if (status === "addressed") summary.addressed += 1;
    else summary.open += 1;
  }
  return summary;
}

function findingNoteEl(f, index, opts = {}) {
  const note = el("div", "finding-note" + (SEVERITY_CLASS[f.severity] || "") + (opts.addressed ? " addressed" : ""));
  const top = el("div", "finding-note-top");
  const cat = el("span", "finding-note-cat", CATEGORY_LABELS[f.category] || f.category);
  const stateEl = el("span", "finding-note-state", opts.addressed ? "addressed" : "");
  top.appendChild(cat);
  top.appendChild(stateEl);
  note.appendChild(top);
  note.appendChild(el("span", "finding-note-text", f.issue));

  const actions = el("div", "finding-note-actions");
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
  actions.appendChild(rewriteBtn);
  actions.appendChild(discussBtn);
  note.appendChild(actions);
  return note;
}

// ---- writer's margin notes ----

async function reloadNotesAndRender() {
  try {
    const base = `/projects/${encodeURIComponent(state.currentProject)}`;
    const res = await api(`${base}/notes`);
    state.notes = (res && res.notes) || [];
    renderScriptView();
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
  actions.appendChild(delBtn);
  view.appendChild(text);
  view.appendChild(actions);
  wrap.appendChild(view);
  return wrap;
}

function renderScenePage(scene, findings, searchQuery, notes = []) {
  const page = el("article", "scene-page");
  page.id = `scene-page-${scene.scene_number}`;
  page.dataset.sceneNumber = String(scene.scene_number);

  const head = el("div", "scene-page-head");
  head.appendChild(el("span", "scene-page-num", `Scene ${scene.scene_number}`));
  const heading = el("span", "scene-heading-line", scene.heading_raw);
  if (searchQuery) highlightMatches(heading, scene.heading_raw, searchQuery);
  head.appendChild(heading);
  if (scene.page_estimate) {
    head.appendChild(el("span", "scene-page-est", `≈ ${scene.page_estimate} min`));
  }
  const addNoteBtn = el("button", "note-add", "✎ note");
  addNoteBtn.type = "button";
  addNoteBtn.title = "Pin your own margin note to this scene";
  addNoteBtn.addEventListener("click", () => startNoteEditor(scene.scene_number, addNoteBtn));
  head.appendChild(addNoteBtn);
  page.appendChild(head);

  for (const e of scene.elements) {
    if (e.type === "scene_heading") continue;
    const line = el("div", `el-${e.type}`);
    let text = e.text;
    if (e.type === "parenthetical" && !text.startsWith("(")) text = `(${text})`;
    line.textContent = text;
    if (searchQuery) highlightMatches(line, text, searchQuery);
    page.appendChild(line);
  }

  if (findings.length || notes.length) {
    const margin = el("div", "scene-notes");
    for (const { f, index } of findings) {
      const addressed = state.findingStatus[index] === "addressed";
      margin.appendChild(findingNoteEl(f, index, { addressed }));
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

function renderScriptView() {
  const container = $("#script-scenes");
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

  // findings grouped by scene
  const byScene = {};
  const scriptLevel = [];
  state.findings.forEach((f, index) => {
    const refs = f.scene_refs || [];
    if (!refs.length) { scriptLevel.push({ f, index }); return; }
    for (const n of refs) {
      (byScene[n] = byScene[n] || []).push({ f, index });
    }
  });

  // the writer's own notes, grouped the same way
  const bySceneNotes = {};
  const scriptLevelNotes = [];
  for (const n of state.notes) {
    if (n.scene_number == null) scriptLevelNotes.push(n);
    else (bySceneNotes[n.scene_number] = bySceneNotes[n.scene_number] || []).push(n);
  }

  renderFixQueuePanel(container);
  renderPacingPanel(container);
  renderCharacterPanel(container);
  renderWriterMirrorPanel(container);

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
    const page = renderScenePage(scene, byScene[scene.scene_number] || [], q, bySceneNotes[scene.scene_number] || []);
    if (q) {
      const text = (scene.heading_raw + " " + scene.elements.map((e) => e.text).join(" ")).toLowerCase();
      const matches = text.includes(q.toLowerCase());
      if (!matches) { page.classList.add("hidden"); }
      else matchCount += 1;
    }
    container.appendChild(page);
  }
  if (q && matchCount === 0) {
    container.appendChild(el("p", "script-empty-hint", `No scenes match "${q}".`));
  }

  // finding summary chips
  const summary = findingStatusSummary();
  const summaryEl = $("#finding-summary");
  summaryEl.innerHTML = "";
  summaryEl.appendChild(el("span", "fs-chip open", `${summary.open} open`));
  summaryEl.appendChild(el("span", "fs-chip addressed", `${summary.addressed} addressed`));

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
}

async function hideAllViews() {
  // full-screen tools only — the rooms are handled by setRoom()
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
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
  renderScriptView();
}

function openChatView() {
  openCowriteRoom();
}

function discussFinding(f, index) {
  openCowriteRoom();
  const refs = (f.scene_refs || []).map((n) => "Scene " + n).join(", ") || "the whole script";
  $("#input").value = `About the note on ${refs} — "${f.issue}": how should I approach fixing it?`;
  autoResizeTextarea();
  $("#input").focus();
}

let welcomeShownFor = null;
function maybeShowWelcome() {
  if (!state.currentProject) return;
  if (welcomeShownFor === state.currentProject) return;
  welcomeShownFor = state.currentProject;
  const container = $("#messages");
  if (!container) return;
  const branch = currentBranchData();
  if ((branch.messages || []).length > 0) return;
  if (!container.querySelector(".chat-empty-hint")) {
    container.appendChild(el("div", "chat-empty-hint", "Sam: Hey — I'm here. What are we working on?"));
  }
}

async function loadFeedbackPanels() {
  const base = `/api/projects/${encodeURIComponent(state.currentProject)}`;
  try {
    if (!state.report) state.report = await api(`${base}/report`);
  } catch (_) { /* no analysis yet */ }
  try {
    if (!state.fixQueue) state.fixQueue = await api(`${base}/fixqueue`);
  } catch (_) { /* no analysis yet */ }
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
}

function renderReportPanel() {
  const c = $("#feedback-report");
  if (!c) return;
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
  const byCat = {};
  (state.report.findings || []).forEach((f) => { (byCat[f.category] = byCat[f.category] || []).push(f); });
  for (const [cat, list] of Object.entries(byCat)) {
    const card = el("div", "craft-panel");
    const head = el("div", "craft-panel-head");
    head.appendChild(el("span", "craft-panel-title", cat));
    card.appendChild(head);
    list.forEach((f) => {
      const refs = (f.scene_refs || []).map((n) => "Scene " + n).join(", ") || "General";
      const issue = el("p", "fix-row-issue", `[${(f.severity || "low").toUpperCase()}] ${refs}: ${f.issue}`);
      if (f.why_it_matters) issue.appendChild(el("p", "fix-row-why", f.why_it_matters));
      card.appendChild(issue);
    });
    c.appendChild(card);
  }
}

// ---- compare (side-by-side drafts) ----

let compareFrom = "original";

async function openCompareView() {
  if (state.view === "compare") return;
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

  const data = await api(`${base}/compare?from=${encodeURIComponent(compareFrom)}&to=active`);
  renderCompare(data);
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

// ---- beat board ----

let bbOrder = [];       // the working (possibly unsaved) order
let bbCards = [];       // card data keyed by scene_number
let bbDirty = false;

async function openBeatboardView() {
  if (state.view === "beatboard") return;
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
  rewriteState = { sceneNumber, findingIndex: findingIndex ?? null };
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
    const pair = el("div", "rewrite-candidate-pair");
    pair.appendChild(el("span", "rewrite-old", rep.old));
    const newLine = el("span", "rewrite-new");
    newLine.appendChild(el("span", "rewrite-arrow", "→"));
    newLine.appendChild(document.createTextNode(rep.new));
    pair.appendChild(newLine);
    row.appendChild(cb);
    row.appendChild(pair);
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
    renderScriptView();
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
    renderScriptView();
    appendSystemNote("Undid the last applied edit.");
  } catch (e) {
    showError("Couldn't undo: " + e.message);
  }
}

async function redoEdit() {
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/edits/redo`, { method: "POST" });
    await loadScriptData();
    renderScriptView();
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
    renderScriptView();
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
  ["c", "Switch to Co-write"],
  ["f", "Switch to Feedback"],
  ["s", "Focus the script pane"],
  ["b", "Open the Beat Board"],
  ["d", "Compare drafts side by side"],
  ["j / n", "Next scene (script view)"],
  ["k / p", "Previous scene (script view)"],
  ["/", "Search the script"],
  ["?", "Show all shortcuts"],
];

function paletteCommands() {
  return [
    { type: "command", label: "Switch to Co-write", keys: "c", run: () => { openCowriteRoom(); } },
    { type: "command", label: "Switch to Feedback", keys: "f", run: () => { openFeedbackRoom(); } },
    { type: "command", label: "Open the Beat Board", keys: "b", run: () => openBeatboardView() },
    { type: "command", label: "Compare drafts side by side", keys: "d", run: () => { if (state.currentProject) openCompareView(); } },
    { type: "command", label: "Run Analysis", keys: "", run: () => runAnalysis() },
    { type: "command", label: "Start a new page", keys: "", run: () => { $("#new-project-btn").click(); } },
    { type: "command", label: "Focus the conversation", keys: "", run: () => { openCowriteRoom(); setTimeout(() => $("#input").focus(), 60); } },
    { type: "command", label: "Search the script", keys: "/", run: () => { if (state.view !== "cowrite" && state.view !== "feedback") openCowriteRoom(); setTimeout(() => $("#script-search").focus(), 80); } },
    { type: "command", label: "Export working draft (.fountain)", keys: "", run: () => $("#export-fountain").click() },
    { type: "command", label: "Study settings", keys: "", run: () => $("#settings-btn").click() },
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
  paletteResults = all.filter((item) => !q || item.label.toLowerCase().includes(q));
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
  const container = $("#script-scenes");
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
    if (!state.currentProject) return;

    if (e.key === "?") { e.preventDefault(); openPalette(true); }
    else if (e.key === "/") { e.preventDefault(); paletteCommands().find((c) => c.keys === "/").run(); }
    else if (e.key === "c") { openCowriteRoom(); }
    else if (e.key === "f") { openFeedbackRoom(); }
    else if (e.key === "b") { openBeatboardView(); }
    else if (e.key === "d" && state.currentProject) { openCompareView(); }
    else if (e.key === "j" || e.key === "n") { if (state.view === "cowrite" || state.view === "feedback") { e.preventDefault(); stepScene(1); } }
    else if (e.key === "k" || e.key === "p") { if (state.view === "cowrite" || state.view === "feedback") { e.preventDefault(); stepScene(-1); } }
  });
}

// ---------- modals ----------

function openModal(sel) { $(sel).style.display = "flex"; }
function closeModal(sel) { $(sel).style.display = "none"; }

// ---------- wiring ----------

function autoResizeTextarea() {
  const input = $("#input");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

function init() {
  loadConfig();
  const projectsPromise = loadProjects();
  setInterval(checkConnection, 30000);

  // the den greets the writer by the hour
  const greeting = $("#welcome-greeting");
  if (greeting) {
    const h = new Date().getHours();
    greeting.textContent =
      h < 5 ? "Still up, writer?" :
      h < 12 ? "The kettle's on." :
      h < 18 ? "The desk is yours." :
      "The lamp's on.";
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

  $("#new-project-btn").addEventListener("click", () => {
    $("#welcome-view").style.display = "flex";
    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "none";
    state.currentProject = null;
    renderProjectList();
    saveSession();
  });

  // dawn theme + reader mode + shortcut hint (persisted preferences)
  const prefs = loadPrefs();
  applyDawn(prefs.dawn);
  applyReaderMode(prefs.reader);
  $("#dawn-btn").addEventListener("click", () => {
    const dawn = !document.body.classList.contains("dawn");
    applyDawn(dawn);
    savePrefs({ dawn });
  });
  $("#reader-btn").addEventListener("click", () => {
    const on = !document.body.classList.contains("reader-mode");
    applyReaderMode(on);
    savePrefs({ reader: on });
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

  // pick up where the writer left off — last project, view, and scene
  projectsPromise.then(() => {
    const s = restoreSession();
    if (!s || !s.project || !(state.projects || []).some((p) => p.project === s.project)) return;
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
    }).catch(() => { /* project vanished — stay on the welcome scene */ });
  });

  $("#analyze-btn").addEventListener("click", runAnalysis);

  // script pane
  $("#script-search").addEventListener("input", () => renderScriptView());
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
    const container = $("#messages");
    if (railFrame) return;
    railFrame = requestAnimationFrame(() => {
      railFrame = null;
      updateRailPositions(container);
    });
  };
  $("#messages").addEventListener("scroll", railScroll, { passive: true });
  window.addEventListener("resize", railScroll);

  // selectors
  $("#persona-select").addEventListener("change", updateSettings);
  $("#mode-select").addEventListener("change", updateSettings);

  // settings modal
  $("#settings-btn").addEventListener("click", () => { $("#test-connection-result").textContent = ""; openModal("#settings-modal"); });
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
  $("#room-feedback-btn").addEventListener("click", openFeedbackRoom);
  $("#bb-icon").addEventListener("click", openBeatboardView);
  $("#compare-icon").addEventListener("click", openCompareView);
  $("#reset-partner-btn").addEventListener("click", resetToPartner);
  $("#tab-report-btn").addEventListener("click", () => switchFeedbackTab("report"));
  $("#tab-fixqueue-btn").addEventListener("click", () => switchFeedbackTab("fixqueue"));
  $("#print-btn").addEventListener("click", () => {
    if (state.view === "cowrite" || state.view === "feedback") window.print();
  });
  $("#compare-from-select").addEventListener("change", (e) => {
    compareFrom = e.target.value;
    loadCompare().catch((err) => showError("Couldn't reload comparison: " + err.message));
  });

  // beat board
  $("#bb-save-btn").addEventListener("click", saveBeatboard);
  $("#bb-restore-btn").addEventListener("click", restoreBeatboard);
  $("#bb-print-btn").addEventListener("click", () => {
    document.body.classList.add("print-cards");
    window.print();
    setTimeout(() => document.body.classList.remove("print-cards"), 500);
  });
  $("#bb-export").addEventListener("click", () => {
    // the export href is set on every render so the download carries the saved order
  });

  // palette
  $("#palette-btn").addEventListener("click", () => openPalette(false));
  $("#palette-input").addEventListener("input", renderPalette);
  bindGlobalShortcuts();

  // error banner
  $("#error-banner-dismiss").addEventListener("click", hideError);

  // surface anything unexpected instead of failing silently
  window.addEventListener("error", (e) => showError("Something went wrong: " + e.message));
  window.addEventListener("unhandledrejection", (e) => showError("Something went wrong: " + (e.reason && e.reason.message ? e.reason.message : e.reason)));
}

document.addEventListener("DOMContentLoaded", init);
