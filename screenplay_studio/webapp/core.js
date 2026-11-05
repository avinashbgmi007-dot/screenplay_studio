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
// Key = category + verified evidence_quote + the scene's slugline key
// (`scene_key`, stamped server-side); scene_refs ride as data (insert-shift
// keeps the id); severity is a judgment, not identity. The no_quote tier keys
// on category + the normalized issue (documented weak tier). Scene keys were
// added by HIGH-1: content alone collided, and a mark on a collided id
// counted nine findings done.
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
  let norm = quote ? quote : "issue:" + (f.issue || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 100);
  // HIGH-1: the scene the finding points at, by slugline — the tie-breaker
  // that stops two findings which say the same words about different places
  // from sharing one id (9 of 16 rows on Pain_3 did, so one mark counted nine
  // findings addressed). The value is STAMPED, not derived here: the analyzer
  // writes `scene_key` when it writes the report and the desk re-stamps old
  // reports on read, so this side reads one field rather than owning a second
  // slug derivation that could drift from the Python one. Empty/absent means
  // no scene component — the pre-scene-key id, unchanged.
  const scene = (f.scene_key || "").trim();
  if (scene) norm += "|s:" + scene;
  return "f" + _base36(_strHash((f.category || "other") + "|" + norm));
}

function _stageStep(label, status) {
  const cls = status === "complete" ? "done" : status === "failed" ? "failed" : status === "running" ? "running" : "";
  // status lands inside a quoted attribute — it comes from the project
  // manifest, so it is escaped rather than trusted.
  return `<span class="step ${cls}" title="${escapeHtml(label)}: ${escapeHtml(status || "pending")}"><i></i>${escapeHtml(label)}</span>`;
}

/** The trust-line words for the dock's verification readout: appends the
 *  element to the page — that is app.js's job; this just builds the words.
 *  Reads report.verification_summary (also served for pre-bundle reports —
 *  the server recomputes the block at serve time). The denominator is
 *  quote-bearing findings only; `no_quote` rows have nothing checkable and
 *  are reported as a count instead of a lie.
 */
function verificationReadoutText(vs) {
  if (!vs || typeof vs !== "object") return null;
  const checkable = (vs.verified || 0) + (vs.not_found || 0) + (vs.scene_not_found || 0);
  const unquoted = vs.no_quote || 0;
  if (checkable) {
    return (vs.verified || 0) + " of " + checkable + " quotes verified ("
      + Math.round(100 * (vs.verified || 0) / checkable) + "%)"
      + (unquoted ? " \u00B7 " + unquoted + " carried no quote" : "");
  }
  return unquoted
    ? unquoted + " finding" + (unquoted === 1 ? "" : "s") + " carried no quote to verify"
    : null;
}

/**
 * Gap 58: what the settings panel must say about existing projects.
 *
 * `connectionMode` describes the GLOBAL setting. It is not the same question as
 * "will my turns go off this machine", because every project carries its own
 * server_url and credential in its manifest, and those are what the client
 * factory reads. A "go local" that reset the desk while a project stayed remote
 * produced the worst possible state: a green "Local" label over turns that were
 * still being sent to a provider.
 *
 * Server-side, `_sync_server_url_to_projects` now keeps them in step, so this
 * should normally return null. When it does not — a hand-edited manifest, a
 * project directory that could not be written — the writer must be told, named,
 * rather than shown a reassurance that is false. Pure, so the wording is tested
 * in node without a browser.
 */
function destinationMismatchText(destinations) {
  if (!destinations || typeof destinations !== "object") return null;
  const remote = Array.isArray(destinations.remote_projects)
    ? destinations.remote_projects : [];
  if (!remote.length) return null;
  const names = remote.map((r) => (r && r.project) || "a project");
  const listed = names.length <= 3
    ? names.join(", ")
    : names.slice(0, 3).join(", ") + " and " + (names.length - 3) + " more";
  return "Still sending to a provider: " + listed + " "
    + (names.length === 1 ? "has its own" : "have their own")
    + " server URL and " + (remote.some((r) => r && r.has_credential)
      ? "an API token saved" : "no token")
    + ". Save again, or open the project, before assuming this desk is local.";
}

/**
 * Gap 129: what the desk may claim about a finding after the writer edits.
 *
 * The engine answers three things: the quoted line is `unchanged`, the line was
 * `changed` (still recognisably there, text moved), or it is `gone`. Two answers
 * could not be honest — a typo fix and a two-word edit measure 0.992 and 0.950
 * against a 0.95 line a one-word edit (0.928) falls below, so calling either one
 * "addressed" credits a fix the writer may not have made, and calling either one
 * "still in the script, untouched" hides work they did do.
 *
 * `changed` therefore gets its own words and stays OPEN. The engine cannot know
 * whether the edit was meant to answer the finding; the writer can, and their
 * existing "addressed" mark is how they close it. This function only decides the
 * label, never the count.
 */
function findingStateLabel(status, disposition) {
  if (disposition === "addressed" || status === "addressed") return "addressed";
  if (disposition === "deferred") return "next pass";
  if (disposition === "ghosted") return "stale";
  if (status === "changed") return "edited" + " \u2014 you decide";
  return "";
}

/** The hover. Long enough to be unambiguous, short enough to read once. */
function findingStateTitle(status, disposition) {
  if (status === "changed" && disposition !== "addressed") {
    return "You edited the quoted line, but not enough to read as a rewrite."
      + " The desk can't tell a correction of a typo from a repair of the issue, so it"
      + " isn't calling this fixed either way. Mark it addressed if your edit was meant"
      + " to answer it, or leave it open if you were only tidying the prose.";
  }
  return null;
}

/**
 * Gap 131: the provider badge, and WHEN it was true.
 *
 * The status strip re-probes on load, so its green dot describes the moment the
 * tab opened. A remembered check is the other half of "connected status", and
 * the only honest way to show it is with its timestamp: "connected 4 minutes
 * ago" is information, "connected" alone is a claim about now that the app has
 * not checked. A check made against a DIFFERENT endpoint is not shown at all —
 * the server reports it stale for exactly that reason.
 */
function providerStatusLine(provider, nowSeconds) {
  if (!provider || typeof provider !== "object") return null;
  const lc = provider.last_check || {};
  const at = lc.checked_at;
  if (at == null) {
    return provider.saved_to_disk
      ? "Saved. No connection check has run yet."
      : "Not saved yet — this will not survive a restart.";
  }
  const secs = Math.max(0, (nowSeconds || 0) - at);
  const when = secs < 90 ? "just now"
    : secs < 5400 ? Math.round(secs / 60) + " min ago"
      : Math.round(secs / 3600) + " h ago";
  if (lc.stale) {
    return "Last checked " + when + ", against a different endpoint. Re-check to be sure.";
  }
  if (lc.ok) {
    return "Connected " + when + (lc.model ? " — " + lc.model : "")
      + (provider.saved_to_disk ? "" : " (not saved)");
  }
  return "Not answering (" + when + ")" + (lc.detail ? " — " + lc.detail : "");
}

/** The badge word. Never "connected" without a check behind it. */
function providerBadgeState(provider) {
  if (!provider || typeof provider !== "object") return "unknown";
  const lc = provider.last_check || {};
  if (lc.checked_at == null) return provider.saved_to_disk ? "saved" : "unsaved";
  if (lc.stale) return "stale";
  return lc.ok ? "connected" : "failed";
}

// ---- gap 5: one terminal state for a stop, whichever watcher sees it first ----
//
// A stopped run can be announced by two independent watchers: the response
// handler of the request that started it (POST /analyze, POST .../retry-failed)
// and the 2s progress poller. Both must say the same thing, and neither may
// ever say "complete" — that sentence is reserved for a run that published a
// report. This helper is the single source of that wording; app.js only mounts
// it, so the copy cannot drift between the two paths.
//
// `published` is whether a report arrived in this session. It changes the
// promise we are allowed to make: with a previous report on disk we can say it
// is unchanged; on a first run there is nothing yet, and saying otherwise would
// be the same lie in the other direction.
function cancellationNote(published) {
  return published
    ? "Analysis stopped at your request — the script and your previous report are unchanged."
    : "Analysis stopped at your request — the script is unchanged and no report was written.";
}

/** Is this response the server telling us the run was stopped?
 *  `/analyze` and the retry route both answer `{cancelled: true, ...}`. */
function isCancelledAck(ack) {
  return !!(ack && typeof ack === "object" && ack.cancelled === true);
}

/** A 409 from the stop endpoint means the run got there first. That is not a
 *  failure to report as one — the next poll lands the real state. */
function isStopRace(err) {
  if (!err) return false;
  if (err.status === 409) return true;
  return /no analysis is running|already finished/i.test(String(err.message || ""));
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
    verificationReadoutText,
    destinationMismatchText,
    findingStateLabel,
    findingStateTitle,
    providerStatusLine,
    providerBadgeState,
    cancellationNote,
    isCancelledAck,
    isStopRace,
  };
}
