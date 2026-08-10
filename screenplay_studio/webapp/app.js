// Script Doctor Studio — frontend logic (vanilla JS, no build step)

const API = "/api";

const state = {
  projects: [],
  currentProject: null,   // project name (string)
  currentSession: null,   // session id
  branches: {},           // { branchName: { messages, active_persona, active_mode, parent_branch } }
  currentBranch: "main",
  config: { server_url: "http://localhost:8080", model: null, timeout: 600 },
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

async function openProject(name) {
  try {
    state.currentProject = name;
    const project = await api(`/projects/${encodeURIComponent(name)}`);
    renderProjectList();

    $("#welcome-view").style.display = "none";
    $("#chat-view").style.display = "flex";
    $("#project-title").textContent = project.title;
    $("#project-title").title = project.title;

    $("#analyze-btn").textContent = project.stages.analyze === "complete" ? "Re-run Analysis" : "Run Analysis";
    $("#analyze-btn").disabled = project.stages.parse !== "complete";

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
      state.branches = { main: { messages: [], active_persona: "script_consultant", active_mode: "evidence_discussion" } };
      state.currentBranch = "main";
      renderMessages();
      renderBranches();
      renderCheckpoints();
      populateSelectors();
    }
  } catch (e) {
    showError("Couldn't open that project: " + e.message);
  }
}

async function runAnalysis() {
  const btn = $("#analyze-btn");
  const original = btn.textContent;
  btn.disabled = true;
  const stopTicker = startElapsedTicker(btn, "Analyzing");
  try {
    await api(`/projects/${encodeURIComponent(state.currentProject)}/analyze`, { method: "POST" });
    stopTicker();
    btn.textContent = "Re-run Analysis";
    appendSystemNote("Analysis complete. The report is now grounding this conversation.");
    await loadProjects();
  } catch (e) {
    stopTicker();
    showError("Analysis failed: " + e.message, true);
    appendSystemNote("Analysis failed: " + e.message, true);
    btn.textContent = original;
  }
  btn.disabled = false;
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
}

function renderMessage(m, index) {
  const wrap = el("div", "msg " + (m.role === "user" ? "user" : "assistant"));
  wrap.id = `msg-${index}`;
  wrap.appendChild(el("div", "msg-role", m.role === "user" ? "You" : "Studio"));
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
  const personas = ["script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"];
  const modes = ["evidence_discussion", "brainstorm", "character_interview"];
  const personaLabels = {
    script_consultant: "Script Consultant", producer: "Producer", dev_exec: "Dev Exec",
    teacher: "Teacher", audience: "Audience", genre_specialist: "Genre Specialist",
  };
  const modeLabels = { evidence_discussion: "Grounded Discussion", brainstorm: "Brainstorm", character_interview: "Character Interview" };

  const pSel = $("#persona-select");
  pSel.innerHTML = "";
  personas.forEach((p) => pSel.appendChild(new Option(personaLabels[p], p, false, p === b.active_persona)));

  const mSel = $("#mode-select");
  mSel.innerHTML = "";
  modes.forEach((m) => mSel.appendChild(new Option(modeLabels[m], m, false, m === b.active_mode)));
}

async function updateSettings() {
  if (!state.currentSession) return;
  const persona = $("#persona-select").value;
  const mode = $("#mode-select").value;
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
  loadProjects();
  setInterval(checkConnection, 30000);

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
    $("#chat-view").style.display = "none";
    state.currentProject = null;
    renderProjectList();
  });

  $("#analyze-btn").addEventListener("click", runAnalysis);

  // composer
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); sendMessage(); });
  $("#input").addEventListener("input", autoResizeTextarea);
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

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

  // error banner
  $("#error-banner-dismiss").addEventListener("click", hideError);

  // surface anything unexpected instead of failing silently
  window.addEventListener("error", (e) => showError("Something went wrong: " + e.message));
  window.addEventListener("unhandledrejection", (e) => showError("Something went wrong: " + (e.reason && e.reason.message ? e.reason.message : e.reason)));
}

document.addEventListener("DOMContentLoaded", init);
