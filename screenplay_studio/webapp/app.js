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
  findingStatus: {},      // finding index -> addressed / still_present / unknown
  editsData: null,        // { edits, findings_status } from /edits
  drafts: null,           // { active_draft, drafts } from /drafts
  fixQueue: null,         // { items, acts } from /fixqueue
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

async function api(path, options = {}) {
  const resp = await fetch(API + path, {
    headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
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
  const resp = await fetch(API + base + "/messages/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
}

// ---- retry only the failed analysis categories (partial-report recovery) ----
async function retryFailedCategories() {
  const btn = $("#retry-failed-btn");
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "Retrying…";
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/analyze/retry-failed`, {
      method: "POST", body: JSON.stringify({}),
    });
    appendSystemNote("Failed categories re-run — the report has been merged and updated.");
    await loadProjects();
    await loadScriptData();
    renderScriptView();
    loadFeedbackPanels();
    refreshMetrics();
  } catch (e) {
    showError("Retry failed: " + e.message, true);
  } finally {
    btn.disabled = false;
    const projSummary = (state.projects || []).find((p) => p.project === state.currentProject);
    const still = ((projSummary && projSummary.failed_categories) || []).length;
    btn.textContent = still ? `⚠ Retry failed (${still})` : label;
    btn.style.display = still ? "inline-block" : "none";
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
        renderScriptView();
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
      renderScriptView();
      refreshMetrics();
    };
    lineEl.addEventListener("blur", () => finish(true), { once: true });
    lineEl.addEventListener("keydown", (kev) => {
      if (kev.key === "Enter" && !kev.shiftKey) { kev.preventDefault(); lineEl.blur(); }
      if (kev.key === "Escape") { kev.preventDefault(); cancelled.value = true; lineEl.blur(); }
    });
  });
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

async function loadConfig() {
  try {
    state.config = await api("/config");
    $("#server-url-input").value = state.config.server_url || "";
    $("#timeout-input").value = state.config.timeout || 600;
    $("#fast-model-input").value = state.config.fast_model || "";
    $("#turn-timeout-input").value = state.config.turn_timeout || 120;
  } catch (e) {
    console.warn("Could not load config:", e);
  }
  updateStatusStrip();
  checkConnection();
}

async function saveConfig() {
  const server_url = $("#server-url-input").value.trim();
  const timeout = parseInt($("#timeout-input").value, 10) || 600;
  const fast_model = $("#fast-model-input").value.trim();
  const turn_timeout = parseInt($("#turn-timeout-input").value, 10) || 120;
  try {
    state.config = await api("/config", {
      method: "POST",
      body: JSON.stringify({ server_url, timeout, fast_model, turn_timeout }),
    });
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

// ---- loop instrumentation (IMPROVEMENT_AUDIT 1.3) ----
// Quiet metrics in the status strip: avg reply time · findings fixed,
// with analysis duration / discussed count in the hover detail.

function fmtDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

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
  try {
    const res = await api("/test-connection", { method: "POST", body: JSON.stringify({}) });
    state.connState = { ok: !!res.ok, message: res.message };
    renderDashboard();  // the dashboard's connection pill follows the strip
    dot.className = "connection-dot " + (res.ok ? "ok" : "fail");
    dot.title = res.message;
    if (connEl) {
      connEl.textContent = res.ok ? "● model ready" : "● model unreachable";
      connEl.className = "status-item " + (res.ok ? "ok" : "fail");
      connEl.title = res.message;
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
}

function updateStatusStrip() {
  const modelEl = $("#status-model");
  if (!modelEl) return;
  const url = state.config && state.config.server_url;
  modelEl.textContent = url ? `llama · ${url.replace(/^https?:\/\//, "")}` : "model server not set";
  modelEl.title = url ? `Model server: ${url}` : "Set the model server in Settings";
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

function _stageStep(label, status) {
  const cls = status === "complete" ? "done" : status === "failed" ? "failed" : status === "running" ? "running" : "";
  return `<span class="step ${cls}" title="${label}: ${status || "pending"}"><i></i>${label}</span>`;
}

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

function jumpToScene(sceneNumber) {
  const page = document.getElementById(`scene-page-${sceneNumber}`);
  if (!page) return;
  page.scrollIntoView({ behavior: "auto", block: "start" });
  // a search filter would hide the scene — clear it so the jump lands
  const search = $("#script-search");
  if (search && search.value.trim()) {
    search.value = "";
    renderScriptView();
  }
  const railItem = [...document.querySelectorAll("#rail-scenes .rail-scene")]
    .find((n) => n.querySelector(".rail-scene-num").textContent === String(sceneNumber));
  if (railItem) {
    railItem.classList.remove("flash");
    void railItem.offsetWidth; // restart the animation
    railItem.classList.add("flash");
  }
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
  if (btn) btn.textContent = collapsed ? "»" : "«";
  savePrefs({ rail_collapsed: collapsed });
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
    $("#premise-pane").style.display = "none";
    $("#idea-canvas").style.display = "flex";
    $("#script-toolbar").style.display = "none";
    $("#script-scenes").style.display = "none";
    $("#draft-bar").style.display = "none";
    $("#premise-btn").style.display = "none";
    populateIdeaCanvas(idea);

    const ws = document.querySelector(".workspace");
    if (ws) ws.style.display = "flex";
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

// the summon pill only makes sense when there's something to talk ABOUT —
// on a blank page it hides; the first word typed brings him back
function updateIdeaSamPill() {
  const pill = $("#idea-sam-pill");
  if (!pill) return;
  const has = (($("#idea-content") || {}).value || "").trim().length > 0;
  pill.style.display = has ? "" : "none";
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
    partnerName.textContent = "Premise Doctor — Development Exec";
    input.placeholder = "Ask the premise doctor to test the idea…";
    document.body.dataset.room = "feedback";
  } else {
    partnerName.textContent = "Sameer — AI writing partner";
    input.placeholder = "Talk it through with Sameer…";
    document.body.dataset.room = "cowrite";
  }
  const chip = $("#room-chip");
  if (chip) chip.textContent = room === "feedback" ? "📋 Concept Validation" : "✍️ Idea Room";
  $("#room-cowrite-btn").classList.toggle("active", room === "cowrite");
  $("#room-feedback-btn").classList.toggle("active", room === "feedback");
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
let premisePaneOpen = false;
function togglePremisePane() {
  premisePaneOpen = !premisePaneOpen;
  $("#premise-pane").style.display = premisePaneOpen ? "flex" : "none";
  $("#script-toolbar").style.display = premisePaneOpen ? "none" : "flex";
  $("#premise-graduate-btn").style.display = "none";
  if (premisePaneOpen) populatePremiseFields(state.premise || {});
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

// ---- Focus mode: the page dims to the line you're on ----
// One ambient-mode toggle. On: chrome dims, the script's non-current scenes
// fade, and the script scrolls typewriter-style — the current scene stays
// centered and the others follow behind it.
let focusScrollRAF = null;

function applyFocusMode(on) {
  document.body.classList.toggle("focus-mode", !!on);
  const btn = $("#focus-btn");
  if (btn) btn.classList.toggle("active", !!on);
  if (on) {
    markCurrentScene();
    markCurrentLine();
    document.getElementById("script-scenes")?.addEventListener("scroll", onFocusScroll, { passive: true });
  } else {
    document.getElementById("script-scenes")?.removeEventListener("scroll", onFocusScroll);
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
  const container = document.getElementById("script-scenes");
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
}

// typewriter focus: within the current scene, the line nearest the pane's
// vertical center is the live line — everything else greys out (CSS)
function markCurrentLine() {
  if (!document.body.classList.contains("focus-mode")) return;
  const container = document.getElementById("script-scenes");
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
  renderSprint();
}

function saveSession() {
  try {
    const payload = { project: state.currentProject, view: state.view, idea: state.currentIdea ? state.currentIdea.id : null };
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

// ---- Home: back to the welcome desk (shelf · library · ideas) ----
// Distinct from the room toggle and the idea room: this leaves the project
// entirely. The session is cleared so a refresh lands on the desk, not back
// inside the script.

function goHome() {
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
    $("#premise-pane").style.display = "none";
    // leaving the idea room must put the canvas AWAY, or it stays stacked
    // above the project's pages (reported: idea page took the top half)
    $("#idea-canvas").style.display = "none";
    $("#script-toolbar").style.display = "flex";
    $("#script-scenes").style.display = "";
    $(".partner-name").textContent = "Sameer — AI writing partner";
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
    $("#project-bar").style.display = "flex";
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
      populateSelectors();
    }

    // the script pane is always visible in both rooms — render it once
    try { await loadScriptData(); } catch (_) { /* no parse yet — pane shows its hint */ }
    renderScriptView();
    maybeShowWelcome();

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
  const d = $("#room-drawer");
  if (d) d.classList.add("open");
  syncGutter();
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
  $("#room-cowrite-btn").classList.toggle("active", room === "cowrite");
  $("#room-feedback-btn").classList.toggle("active", room === "feedback");
  $("#cowrite-panel").style.display = room === "cowrite" ? "flex" : "none";
  $("#feedback-panel").style.display = room === "feedback" ? "flex" : "none";
  // closing a full-screen tool returns to the active room
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  $("#revision-view").style.display = "none";
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
  // idea phase has no doctor — there's only Sameer here; feedback is a
  // script-desk room. (The room toggle and gutter tab are hidden in idea
  // mode; this guards the keyboard and palette paths too.)
  if (state.inIdea) { openCowriteRoom(); return; }
  if (state.view === "feedback") { openRoomDrawer(); return; }
  setRoom("feedback");
  if (state.inIdea) { renderMessages(); openRoomDrawer(); return; }
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
  btn.classList.add("analyzing");
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
  const btn = $("#analyze-btn");
  if (btn) { btn.disabled = false; btn.classList.remove("analyzing"); }
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
    refreshMetrics();
  } catch (e) {
    if (analysisUi) analysisUi.stop();
    hideAnalysisProgressUI();
    btn.textContent = "Run Analysis";
    showError("Analysis failed: " + e.message, true);
    appendSystemNote("Analysis failed: " + e.message, true);
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
    renderScriptView();
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

function renderMessage(m, index) {
  const wrap = el("div", "msg " + (m.role === "user" ? "user" : "assistant"));
  wrap.id = `msg-${index}`;
  const head = el("div", "msg-head");
  head.appendChild(el("div", "msg-role", m.role === "user" ? "You" : "Studio"));
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
      hideMenuTimer = setTimeout(() => { if (!menu?.matches(":hover")) closeMenu(); }, 260);
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
  if (isError) bubble.style.color = "var(--rust-flag)";
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

function jumpToScene(sceneNumber) {
  if (sceneNumber == null) return;
  openCowriteRoom();
  let page = document.getElementById(`scene-page-${sceneNumber}`);
  if (!page || page.classList.contains("hidden")) {
    // a search filter may have hidden the scene — clear it so the jump lands
    $("#script-search").value = "";
    renderScriptView();
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
    renderScriptView();
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
  const pane = $("#script-scenes");
  if (!page || !pane || !pane.contains(node)) return null;
  const text = sel.toString().trim().replace(/\s+/g, " ");
  if (!text || text.length < 4) return null;
  return { scene_number: parseInt(page.dataset.sceneNumber, 10) || null, text };
}

function showQuoteFloat(quote) {
  const btn = $("#quote-float");
  const stashBtn = $("#stash-float");
  const noteBtn = $("#note-float");
  const pane = $("#script-pane");
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
  wrap.innerHTML = "";
  for (const name of Object.keys(state.branches)) {
    const pill = el("button", "branch-pill" + (name === state.currentBranch ? " active" : ""), name);
    pill.type = "button";
    pill.title = name === state.currentBranch ? "Current branch" : `Switch to "${name}"`;
    pill.addEventListener("click", () => switchBranch(name));
    wrap.appendChild(pill);
  }
  // (the fork action was removed from the UI per the writer's preference)
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
  const observations = (data.profile?.observations || []).filter((o) => !o.suppressed);
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
          pendingBubble.style.color = "var(--rust-flag)";
          finishTurn();
        });
      } else if (pendingBubble) {
        stopTicker();
        pendingBubble.textContent = "Couldn't get a reply: " + e.message;
        pending.classList.remove("msg-pending");
        pendingBubble.style.color = "var(--rust-flag)";
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
// append-or-push: the panels render into the script pane's craft shelf (an
// array) or directly into the Feedback room's Fix Queue tab (a real node).
function addPanel(container, panel) {
  if (container && container.push) container.push(panel);
  else if (container) container.appendChild(panel);
}

function renderFixQueuePanel(container) {
  const items = (state.fixQueue && state.fixQueue.items) || [];
  const open = items.filter((i) => i.status !== "addressed" && !i.dismissed);
  if (!items.length && !state.fixQueueShowDismissed) return;
  const total = (state.fixQueue && (state.fixQueue.total_count ?? items.length)) || items.length;

  const panel = el("div", "craft-panel fix-queue");
  const head = el("div", "craft-panel-head");
  head.appendChild(el("span", "craft-panel-title", `Fix queue — ${open.length} open / ${total} total`));
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
      else renderScriptView();
    });
    head.appendChild(toggleBtn);
  }
  panel.appendChild(head);

  for (const item of items) {
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
        else renderScriptView();
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
  for (const [idx, status] of Object.entries(state.findingStatus)) {
    if (state.findings[idx] && state.findings[idx].category === "formatting") continue;
    if (status === "addressed") summary.addressed += 1;
    else summary.open += 1;
  }
  return summary;
}

function findingNoteEl(f, index, opts = {}) {
  const note = el("div", "finding-note" + (SEVERITY_CLASS[f.severity] || "") + (opts.addressed ? " addressed" : ""));
  note.dataset.findingIndex = String(index);
  const top = el("div", "finding-note-top");
  const cat = el("span", "finding-note-cat", CATEGORY_LABELS[f.category] || f.category);
  const stateEl = el("span", "finding-note-state", opts.addressed ? "addressed" : "");
  top.appendChild(cat);
  top.appendChild(stateEl);
  note.appendChild(top);
  note.appendChild(el("span", "finding-note-text", f.issue));

  const actions = el("div", "finding-note-actions");
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

function renderScenePage(scene, findings, searchQuery, notes = [], discussed = false, changedTexts = []) {
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

  for (const e of scene.elements) {
    if (e.type === "scene_heading") continue;
    const line = el("div", `el-${e.type}`);
    let text = e.text;
    if (e.type === "parenthetical" && !text.startsWith("(")) text = `(${text})`;
    line.textContent = text;
    if (searchQuery) highlightMatches(line, text, searchQuery);
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

  // change-mark stars: which lines are the NEW text of an applied edit
  const changedByScene = {};
  for (const ed of (state.editsData && state.editsData.edits) || []) {
    if (!ed.scene_number || !(ed.applied || []).length) continue;
    (changedByScene[ed.scene_number] = changedByScene[ed.scene_number] || []).push(...ed.applied);
  }

  // anchored findings: the verification pass records the scene each
  // evidence quote actually lives in — those lines become clickable
  const anchorsByScene = {};
  state.findings.forEach((f, index) => {
    const sc = findingTargetScene(f);
    if (sc == null || !(f.evidence_quote || "").trim()) return;
    (anchorsByScene[sc] = anchorsByScene[sc] || []).push({ f, index });
  });

  // the writer's own notes, grouped the same way
  const bySceneNotes = {};
  const scriptLevelNotes = [];
  for (const n of state.notes) {
    if (n.scene_number == null) scriptLevelNotes.push(n);
    else (bySceneNotes[n.scene_number] = bySceneNotes[n.scene_number] || []).push(n);
  }

  // scenes the writer has quoted in conversation — marked on the paper
  const discussedScenes = new Set();
  for (const m of (currentBranchData().messages || [])) {
    if (m.quote && m.quote.scene_number != null) discussedScenes.add(m.quote.scene_number);
  }

  // the analysis panels ride in a collapsed craft shelf — page one first
  const craftPanels = [];
  renderFixQueuePanel(craftPanels);
  renderPacingPanel(craftPanels);
  renderCharacterPanel(craftPanels);
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
    // anchored margin notes: lines with a pinned note get a 📌; click opens it
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
  $("#export-backup").href = `/api/projects/${encodeURIComponent(state.currentProject)}/backup`;
  $("#export-backup").download = `${state.currentProject}-backup.zip`;

  renderRailScenes();
  renderRailNotes();
  loadCharacters();
  if (document.body.classList.contains("focus-mode")) markCurrentScene();
}

async function hideAllViews() {
  // full-screen tools only — the rooms are handled by setRoom()
  $("#beatboard-view").style.display = "none";
  $("#compare-view").style.display = "none";
  $("#revision-view").style.display = "none";
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
  const base = `/api/projects/${encodeURIComponent(state.currentProject)}`;
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
    const SP_STATUS = { paid: "✓ Paid off", dangling: "🚩 Dangling", abandoned: "🪦 Abandoned", red_herring: "🪄 Red herring" };
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

  // Character dials — ScreenplayIQ-style trait scores per main character
  const dials = state.report && state.report.character_dials;
  if (dials && dials.length) {
    const dialCard = el("div", "craft-panel");
    const dialHead = el("div", "craft-panel-head");
    dialHead.appendChild(el("span", "craft-panel-title", "Character dials — how each main character reads"));
    dialCard.appendChild(dialHead);
    dials.forEach((d) => {
      const block = el("div", "dial-block");
      block.appendChild(el("div", "dial-char-name", d.character));
      (d.traits || []).forEach((t) => {
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
      });
      dialCard.appendChild(block);
    });
    c.appendChild(dialCard);
  }

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

async function openCompareView() {
  if (state.view === "compare") return;
  exitSpotlight();
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
  renderRevisionView();
  saveSession();
}

function closeRevisionView() {
  setRoom(revisionPrevRoom);
}

function jumpRevisionScene(num) {
  const box = $("#revision-script");
  if (!box) return;
  const page = box.querySelector(`#scene-page-${num}`);
  if (!page) return;
  page.scrollIntoView({ behavior: "smooth", block: "start" });
  page.classList.remove("flash");
  void page.offsetWidth;
  page.classList.add("flash");
  setTimeout(() => page.classList.remove("flash"), 1600);
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
    const allAddressed = fg.length > 0 && fg.every(({ index }) => state.findingStatus[index] === "addressed");
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
      changedByScene[scene.scene_number] || []
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

async function openBeatboardView() {
  if (state.view === "beatboard") return;
  exitSpotlight();
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
    // finding flags: which scenes are bleeding — open findings only (addressed
    // ones are done; that's the Revision view's story). Same severity-dot
    // language as the Revision navigator, so the dots mean one thing everywhere.
    const openForScene = [];
    (state.findings || []).forEach((f, index) => {
      if (state.findingStatus[index] === "addressed") return;
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
  return [
    { type: "command", label: "Switch to Co-write", keys: "c", run: () => { openCowriteRoom(); } },
    { type: "command", label: "Switch to Feedback", keys: "f", run: () => { openFeedbackRoom(); } },
    { type: "command", label: "Open the Beat Board", keys: "b", run: () => openBeatboardView() },
    { type: "command", label: "Compare drafts side by side", keys: "d", run: () => { if (state.currentProject) openCompareView(); } },
    { type: "command", label: "Open the Revision view", keys: "v", run: () => { if (state.currentProject) openRevisionView(); } },
    { type: "command", label: "Spotlight mode — nothing but the page", keys: "z", run: () => { if (state.currentProject) toggleSpotlight(); } },
    { type: "command", label: "Run Analysis", keys: "", run: () => runAnalysis() },
    { type: "command", label: "Start a new page", keys: "", run: () => { $("#new-project-btn").click(); } },
    { type: "command", label: "Focus the conversation", keys: "", run: () => { openCowriteRoom(); setTimeout(() => $("#input").focus(), 60); } },
    { type: "command", label: "Toggle the Craft shelf (analysis panels)", keys: "a", run: toggleCraftShelf },
    { type: "command", label: "Toggle the Structure rail", keys: "r", run: () => toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")) },
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

// Spotlight-style fuzzy ranking: subsequence match with bonuses for
// adjacency and word starts. 'rv' finds "Open the Revision view"; a plain
// substring match scores highest (100+), then true fuzzy matches by score.
function fuzzyScore(q, label) {
  if (!q) return 1;
  const s = label.toLowerCase();
  if (s.includes(q)) return 100 + s.length - q.length;
  let qi = 0;
  let score = 0;
  let prev = -2;
  for (let i = 0; i < s.length && qi < q.length; i++) {
    if (s[i] !== q[qi]) continue;
    score += i === prev + 1 ? 2 : 1;
    if (i === 0 || s[i - 1] === " " || s[i - 1] === "-") score += 5;
    prev = i;
    qi++;
  }
  return qi === q.length ? score : 0;
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

    // Esc — the page wins: dismiss the partner drawer, then the craft shelf,
    // then the structure rail (palette Esc is handled above; modals keep Esc).
    if (e.key === "Escape") {
      if (document.body.classList.contains("spotlight-mode")) { exitSpotlight(); return; }
      if (state.view === "revision") { closeRevisionView(); return; }
      const modalOpen = [...document.querySelectorAll(".modal-overlay")].some((m) => m.style.display === "flex");
      if (!modalOpen) {
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

    if (e.key === "?") { e.preventDefault(); openPalette(true); }
    else if (e.key === "/") { e.preventDefault(); paletteCommands().find((c) => c.keys === "/").run(); }
    else if (e.key === "c") { openCowriteRoom(); }
    else if (e.key === "f") { openFeedbackRoom(); }
    else if (e.key === "a") { toggleCraftShelf(); }
    else if (e.key === "r") { toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")); }
    else if (e.key === "s") { closeRoomDrawer(); const sc = $("#script-scenes"); if (sc) sc.focus(); }
    else if (e.key === "b" && state.currentProject) { openBeatboardView(); }
    else if (e.key === "d" && state.currentProject) { openCompareView(); }
    else if (e.key === "v" && state.currentProject) { if (state.view === "revision") closeRevisionView(); else openRevisionView(); }
    else if (e.key === "z" && state.currentProject) { toggleSpotlight(); }
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
    if (!e.target.closest(".sidebar-section")) closeSidebarFlyouts(null);
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
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? start;
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
   "#premise-questions", "#idea-logline", "#idea-questions", "#rail-note-input",
  ].forEach((sel) => attachMic(document.querySelector(sel)));
}

function init() {
  loadConfig();
  wireSidebarFlyouts();
  wireMics();
  const projectsPromise = Promise.all([loadProjects(), loadIdeas()]);
  loadLibrary();
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

  $("#new-project-btn").addEventListener("click", () => showWelcomeDesk());
  $("#new-idea-btn").addEventListener("click", createIdea);
  // Phase 0: structural rail
  $("#rail-toggle").addEventListener("click", () => toggleRail(!$("#struct-rail").classList.contains("rail-collapsed")));
  $("#rail-beats-btn").addEventListener("click", openBeatboardView);
  $("#rail-compare-btn").addEventListener("click", openCompareView);
  $("#rail-note-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#rail-note-input");
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
  // Manuscript Stage: the structure rail starts off-canvas — the page owns the
  // room. Only an explicit "open" preference keeps it out; anything else (or
  // nothing) collapses it.
  if (prefs.rail_collapsed !== false) toggleRail(true);
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
  });
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
    }).catch(() => { /* project vanished — stay on the welcome scene */ });
  });

  $("#analyze-btn").addEventListener("click", runAnalysis);
  $("#reparse-btn").addEventListener("click", reparseProject);
  $("#retry-failed-btn").addEventListener("click", retryFailedCategories);

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
    const container = line || document.getElementById("script-scenes");
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
    if (!e.target.closest("#quote-float") && !e.target.closest("#stash-float") && !e.target.closest("#note-float") && !e.target.closest("#script-scenes")) hideQuoteFloat();
  });
  $("#script-scenes").addEventListener("scroll", hideQuoteFloat, { passive: true });

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
  // Manuscript Stage: the gutter tabs summon the partner drawer
  $("#gutter-sam").addEventListener("click", openCowriteRoom);
  $("#gutter-doc").addEventListener("click", openFeedbackRoom);
  $("#drawer-close").addEventListener("click", closeRoomDrawer);
  $("#rail-edge-tab").addEventListener("click", () => toggleRail(false));
  $("#bb-icon").addEventListener("click", openBeatboardView);
  $("#compare-icon").addEventListener("click", openCompareView);
  $("#revise-btn").addEventListener("click", openRevisionView);
  $("#revision-close").addEventListener("click", closeRevisionView);
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
  const homeBtn = $("#home-btn");
  if (homeBtn) homeBtn.addEventListener("click", goHome);
  wireExploreChips();
  $("#palette-input").addEventListener("input", renderPalette);
  bindGlobalShortcuts();

  // error banner
  $("#error-banner-dismiss").addEventListener("click", hideError);

  // surface anything unexpected instead of failing silently
  window.addEventListener("error", (e) => showError("Something went wrong: " + e.message));
  window.addEventListener("unhandledrejection", (e) => showError("Something went wrong: " + (e.reason && e.reason.message ? e.reason.message : e.reason)));
}

document.addEventListener("DOMContentLoaded", init);
