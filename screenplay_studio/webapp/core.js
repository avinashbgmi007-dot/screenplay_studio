// Script Doctor Studio — shared pure helpers (no DOM access).
//
// Loaded BEFORE app.js via a plain <script> tag: these functions stay
// globals exactly as when they lived in app.js, so nothing else changes.
// The CommonJS guard at the bottom exists purely so `node --test tests/js/`
// can require this same file the browser runs — there is no build step.
//
// When editing here: keep functions DOM-free and deterministic so they stay
// unit-testable in both environments.

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

function truncate(text, n) {
  text = text.trim().replace(/\s+/g, " ");
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function fmtDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function shortModelId(id) {
  if (!id) return "";
  return id.length > 30 ? id.slice(0, 29) + "…" : id;
}

function _stageStep(label, status) {
  const cls = status === "complete" ? "done" : status === "failed" ? "failed" : status === "running" ? "running" : "";
  return `<span class="step ${cls}" title="${label}: ${status || "pending"}"><i></i>${label}</span>`;
}

// ---- Node test hook (browsers never take this branch) ----
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    fuzzyScore,
    formatMessageContent,
    truncate,
    formatElapsed,
    fmtDuration,
    shortModelId,
    _stageStep,
  };
}
