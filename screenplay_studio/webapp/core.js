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

/** Escape text for ANY HTML context — an element body OR a quoted attribute.
 *
 * This is the ONE helper every `innerHTML` sink must route untrusted text
 * through. It exists because a finding's `issue` is model output derived from
 * the writer's own script, and a screenplay is a file a collaborator or a
 * contest can send you: `<img src=x onerror=...>` in a dialogue line used to
 * reach `innerHTML` raw and execute in the app origin.
 *
 * `&` is replaced FIRST so an existing entity cannot be double-decoded back
 * into markup (`&lt;script&gt;` must stay inert, not become a tag). Quotes are
 * escaped too, so the result is safe inside `attr="..."` as well as in text.
 * Non-strings are coerced, and null/undefined become "" rather than "null".
 */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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

// ---- content-hash finding identity (R1 refined) ----------------------------
// The JS twin of `revision.py:compute_finding_id`. The server observes, the
// client displays, and the two MUST produce the same id — a finding's id is the
// key for the writer's marks (`finding_marks.json`), their dismissals
// (`dismissed_findings.json`), ghost detection, and the doctor's case file. If
// the two implementations disagree, every one of those silently stops matching.
//
// Key = category + verified evidence_quote; scene_refs ride as data
// (insert-shift keeps the id); severity is a judgment, not identity. The
// no_quote tier keys on category + the normalized issue (documented weak tier).
//
// This lives here rather than in app.js because it is a DOM-free pure helper,
// and core.js is the home for those — which is what makes it unit-testable
// under `node --test` (tests/js/core.test.js) instead of only reachable through
// a browser.
function _strHash(s) {
  // Iterate CODE POINTS, not UTF-16 code units. `for..of` over a string yields
  // whole code points, matching Python's `for ch in s`. The previous
  // `charCodeAt(i)` over `s.length` walked an emoji's surrogate pair as TWO
  // values, so any finding whose quote or issue contained a non-BMP character
  // hashed to a different id than the server's. Verified live:
  // tests/e2e_browser_finding_id_parity.py (3 of 6 probe cases diverged before
  // this line changed; ASCII and BMP-accented text always agreed).
  //
  // The rest of the arithmetic already matched: JS `(x | 0) >>> 0` is exactly
  // Python's `& 0xFFFFFFFF`, and the intermediate is well inside 2^53, so no
  // precision is lost.
  let h = 5381;
  for (const ch of s) h = (((h << 5) + h + ch.codePointAt(0)) | 0) >>> 0;
  return h;
}

function _base36(h) {
  const D = "0123456789abcdefghijklmnopqrstuvwxyz";
  if (!h) return "0";
  let out = "";
  while (h) { out = D[h % 36] + out; h = Math.floor(h / 36); }
  return out;
}

function computeFindingId(f) {
  const quote = (f.evidence_quote || "").trim();
  const norm = quote ? quote : "issue:" + (f.issue || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 100);
  return "f" + _base36(_strHash((f.category || "other") + "|" + norm));
}

function _stageStep(label, status) {
  const cls = status === "complete" ? "done" : status === "failed" ? "failed" : status === "running" ? "running" : "";
  // status lands inside a quoted attribute — it comes from the project
  // manifest, so it is escaped rather than trusted.
  return `<span class="step ${cls}" title="${escapeHtml(label)}: ${escapeHtml(status || "pending")}"><i></i>${escapeHtml(label)}</span>`;
}

// ---- Node test hook (browsers never take this branch) ----
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    fuzzyScore,
    formatMessageContent,
    escapeHtml,
    truncate,
    formatElapsed,
    fmtDuration,
    shortModelId,
    computeFindingId,
    _strHash,
    _base36,
    _stageStep,
  };
}
