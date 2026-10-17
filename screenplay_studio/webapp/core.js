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

// ============ Queue lanes and rank v0 (Track B) ============
//
// IMPACT is a hand-authored judgment stated as reviewable data. It is
// UNCALIBRATED, and the UI says so. The numbers encode a hypothesis about what a
// writer should fix first. A real-model calibration has now run over three
// scripts (spec 14.10) and a reviewer agreed the resulting order was defensible -
// which is evidence the ORDERING is sane, not that these values are correct.
// Track C and a writer sitting are what would settle that. Do not tune these
// from a demo run: the verifier and the analyzer are deterministic, but the
// WEIGHTS are a product decision no synthetic score can make.
//
// NOTE: an earlier version of this comment claimed these weights "ship labelled
// as such" while the only occurrences of the word UNCALIBRATED were in this
// file. The writer saw nothing. Section 9c requires the marking in the UI COPY,
// and it now lives in the ledger section head.
//
// Coverage is the load-bearing property, not the values. Every category that
// can reach a finding MUST have an entry: an absent one makes
// IMPACT[category] undefined, undefined * 10 is NaN, and NaN in a sort
// comparator is unspecified behaviour. `tests/test_queue_lane_coverage.py`
// fails the build if that happens again.
const IMPACT = {
  structure: 5, plot_thread: 5, character: 4,
  scene_function: 3, dialogue: 3,
  // Track B requirement 1 and 2: `voice` and `subtext` are real finding
  // categories - voice.py emits them and pipeline.py:1331-1341 runs those
  // passes - and they are absent from FINDING_CATEGORIES, which constrains only
  // what the LLM grammar may emit (grammar.py:76). They are line-level craft
  // notes with quotes and scene refs, so they belong in the Line lane, and they
  // need weights or they score NaN.
  voice: 3, subtext: 3,
  continuity: 2, theme: 1, genre: 1,
};

// Lane assignment. `observation` is NOT a queue lane: a finding with no
// scene_refs has nothing to locate, and a thesis or a conformance note is not a
// task. It is still shown, just never queued.
const LANE_OF = {
  structure: "structure", plot_thread: "structure",
  dialogue: "line", scene_function: "line",
  voice: "line", subtext: "line",
  character: "line",          // binned by span at rank time (spec 1.2)
  continuity: "deterministic",
};

const LANE_LABELS = {
  structure: "Structure",
  line: "Line",
  deterministic: "Deterministic",
  uncategorised: "Uncategorised",
};

// Why a lane is a group rather than a rank position. These strings are the
// product answering the obvious question - "why is this above that?" - before
// the writer has to ask it.
const LANE_BLURB = {
  structure: "Missing turns and setup-payoff economy. The fixes that change what the script is about.",
  line: "The scene says it, the character states it, and it lands flat. Craft notes on the words themselves.",
  deterministic: "Locatable, one-line fixes - continuity breaks. Not ranked below the others: six of these are one kind of fix and read best in one pass.",
  uncategorised: "Findings in a category nothing weighs. Never dropped and never ranked against rows the table has no opinion about - they are here so the gap is visible.",
};

/**
 * Does this finding belong in the queue at all?
 *
 * Membership requires a verb, and usually a scene to locate it by.
 *
 * This comment used to say an observation "is shown outside the queue". That was
 * false and was searched for and confirmed false: no dock surface renders
 * observation-lane findings as cards. A false claim about graceful degradation
 * is worse than the degradation, because it reads as a guarantee.
 *
 * The honest statement: an observation is not on the desk because it is not
 * something you act on there. It stays in the report and the export, so nothing
 * is dropped (AGENTS.md:66) - it is simply not worklist. See 14.37 for the
 * mechanical-check exception, which exists because the old rule ate its own
 * defect. Unknown categories are queued, because AGENTS.md:66 outranks any
 * tidiness argument about the table above.
 */
function findingLane(f) {
  if (!f) return "observation";
  const cat = (f.category || "").toLowerCase();
  // theme and genre are observations UNCONDITIONALLY: a thesis or a conformance
  // note is not a task, and a scene anchor does not turn one into a task. They
  // are absent from LANE_OF for the same reason - see spec 1.2.
  if (cat === "theme" || cat === "genre") return "observation";
  const refs = f.scene_refs;
  if (!Array.isArray(refs) || refs.length === 0) {
    // SPEC 14.37, THE MEMBERSHIP RULING. A scene-less finding used to be an
    // observation unconditionally, on the reasoning that it "cannot be located,
    // so it is not a task". That reasoning is CIRCULAR for a mechanical check,
    // whose subject is frequently the missing anchor itself: "this clock jump
    // has no slugline" cannot cite a slugline. Requiring one makes the rule eat
    // the defect it describes, and the row then reached no card surface at all.
    //
    // A finding that a rule or check produced is therefore a TASK even with no
    // scene. The signal is `rule_id` / `check_id`, which the analyzer really does
    // set (continuity.py:91-92, 157-158), not a new category invented for this.
    //
    // A scene-less finding with NO mechanical provenance stays an observation:
    // an opinion with nowhere to point is a thought, and the worklist is for
    // things you act on. It remains in the report and the export - not dropped,
    // simply not on the desk.
    if (f.rule_id || f.check_id) return LANE_OF[cat] || "uncategorised";
    return "observation";
  }
  // An unknown category gets its OWN lane rather than falling into "line".
  //
  // Both alternatives were wrong. Falling into "line" while scoring IMPACT 0 is
  // a 30-point demotion - an unknown row tops out at 5 against a known
  // `dialogue` floor of 30 - which is the silent demotion section 1.3 ruled out
  // ("penalising a row twice for the same property is how a ranking silently
  // becomes a demotion"). Sending it to "observation" would drop it from the
  // queue, and AGENTS.md:66 says flag, don't drop.
  //
  // A lane is the one option that is neither: the row is visible, it is not
  // ranked against rows it has no opinion about, and a category nobody weighed
  // becomes a group header someone can SEE instead of a diff nobody notices.
  return LANE_OF[cat] || "uncategorised";
}

/** How many scenes this finding touches, tolerating numeric AND string refs.
 *  findingOnScene (app.js) already tests both forms; this must agree with it or
 *  the span bonus is computed off a different rule than the filter admits. */
function sceneRefCount(f) {
  if (!f || !Array.isArray(f.scene_refs)) return 0;
  return f.scene_refs.length;
}

/**
 * rank v0 — WITHIN A LANE ONLY. Never across lanes: the deterministic lane is
 * not sorted to the bottom, it is a group of equal weight with its own header,
 * because six continuity notes are one kind of fix and interleaving them with
 * structural notes destroys the batching they exist for.
 *
 *   score = IMPACT[category] * 10
 *         + 3 if verified
 *         + (min(sceneRefs, 3) - 1)
 *         + 5 if the writer addressed it
 *
 * NOTE: the spec sketch says "+5 if marked fix"; the mark value that actually
 * ships in state.findingMarks is "addressed" (app.js:43, 4288). The code follows
 * the shipped vocabulary, because a rank term keyed on a mark value nothing ever
 * writes is a constant 0 wearing the costume of a tiebreaker.
 *
 * UNCALIBRATED. See the note above.
 */
function rankScore(f) {
  if (!f) return 0;
  const cat = (f.category || "").toLowerCase();
  const impact = Object.prototype.hasOwnProperty.call(IMPACT, cat)
    ? IMPACT[cat]
    : 0;
  const verified = f.verification && f.verification.status === "verified" ? 3 : 0;
  const span = Math.max(0, Math.min(sceneRefCount(f), 3) - 1);
  // Writer intent is sticky. `state.findingMarks` lives in app.js, which loads
  // after core.js, so it is read through a typeof guard rather than a bare
  // reference: a rank function that throws when the writer has marked nothing
  // would take the whole queue down.
  const marks = (typeof state !== "undefined" && state && state.findingMarks) || null;
  const sticky = (marks && marks[computeFindingId(f)] === "addressed") ? 5 : 0;
  return impact * 10 + verified + span + sticky;
}


/**
 * SPEC 14.35. Bind queue items to findings BY ID, as a consuming multimap.
 *
 * Why this lives in core.js and not in app.js: the 14.29 version of this join
 * was inline in the render path, and the guard that mutation-verified it could
 * not tell the new code from the old one. An inline `if (item._seen == null) at
 * = -1` made the id path UNREACHABLE on every render, so every row fell back to
 * positional binding and the suite still went green. The defect was invisible
 * to every check because the thing under test was never executed.
 *
 * So the join is a pure function here, and tests/js/queue_lanes.test.js pins it
 * with the only mutation that distinguishes id-binding from positional binding:
 * findings in one order, items in another, ids that disagree with position.
 *
 * The consuming counter is what makes duplicate ids correct. Two findings can
 * share one content id - the same quote judged by two rules is real and shipped
 * (Rain_C courier_7, gun_pen_2) - and indexOf() sends both items to the first
 * one, which renders the same card twice.
 *
 * Positional binding remains the fallback ONLY for an older server payload that
 * carries no `finding_id` at all.
 */
function bindQueueItems(items, findings, findingIds) {
  const fs = findings || [];
  const ids = findingIds || fs.map(computeFindingId);
  const taken = Object.create(null);
  return (items || []).map((item) => {
    if (!item || !item.finding_id) return item ? item.index : -1;
    const nth = taken[item.finding_id] || 0;
    let seen = 0, hit = -1;
    for (let k = 0; k < ids.length; k++) {
      if (ids[k] !== item.finding_id) continue;
      if (seen === nth) { hit = k; break; }
      seen++;
    }
    if (hit < 0) return item.index;          // id absent: positional fallback
    taken[item.finding_id] = nth + 1;
    return hit;
  });
}

/**
 * The order lanes appear in: descending MAX impact, so the lane holding the
 * heaviest thing on the desk leads.
 *
 * This is a rendering order, never a quality verdict. The deterministic lane is
 * NOT last: six continuity notes are one kind of fix, and burying them below
 * structural notes destroys the batching they exist for. Where two lanes tie on
 * max impact the tie breaks on the lane NAME, so two loads of the same script
 * produce the same order - a queue that reshuffles itself between loads is a
 * queue the writer stops trusting.
 */
function laneOrder(groups) {
  const maxImpact = (lane) => {
    let max = -1;
    for (const item of groups[lane] || []) {
      const cat = ((item && item.f && item.f.category) || "").toLowerCase();
      if (Object.prototype.hasOwnProperty.call(IMPACT, cat)) max = Math.max(max, IMPACT[cat]);
    }
    return max;
  };
  return Object.keys(groups).sort((a, b) =>
    (maxImpact(b) - maxImpact(a)) || String(a).localeCompare(String(b)));
}

/**
 * Group findings into lanes for display.
 *
 * Lane order is descending max-IMPACT; row order inside a lane is rankScore,
 * descending. Observation rows are NOT returned: a finding with nothing to
 * locate is not a task and must not occupy the queue. They are still SHOWN
 * elsewhere - this function filters a view, it does not drop a finding
 * (AGENTS.md:66, "Flag, don't drop").
 *
 * Pure: takes entries, returns groups. No DOM, no state, no filtering by
 * chips - the ONE predicate upstream decides what is admitted here, so this
 * cannot fork GAP-1's single-predicate contract.
 */
function groupByLane(entries) {
  const groups = {};
  for (const item of entries || []) {
    const lane = findingLane(item && item.f);
    if (lane === "observation") continue;   // not a task; shown, not queued
    (groups[lane] = groups[lane] || []).push(item);
  }
  for (const lane of Object.keys(groups)) {
    groups[lane].sort((a, b) =>
      (rankScore(b && b.f) - rankScore(a && a.f)) || ((a && a.index || 0) - (b && b.index || 0)));
  }
  return { groups, order: laneOrder(groups) };
}

/**
 * SPEC 14.54 — THE ORDERED QUEUE PROJECTION: the ONE traversal the ranked
 * queue renders and the keyboard loop walks.
 *
 * This is the repair of the last code-confirmed loop/queue divergence (14.53):
 * loopList() walked state.findings in REPORT order through findingPassesFilter,
 * so it admitted observations and hidden ungrounded rows the queue never
 * renders, and stepped them in a different order (measured: queue [1,0,5] vs
 * loop [0,1,2,3,4,5]).
 *
 * The projection is the queue's own chain in the queue's own order:
 *   bindQueueItems -> per-item admission (the caller's predicate; this is
 *   where findingPassesFilter / inFindingFilter / the kit-A clause enter) ->
 *   groupByLane. Lane membership is NOT a predicate clause: groupByLane drops
 *   observations because they are not tasks, and every reader inherits that
 *   ruling by consuming THIS function, not by copying the rule.
 *
 * Returns { groups, order, entries, byIndex }:
 *   groups/order — exactly what groupByLane returned (the renderer walks it);
 *   entries — the same members flattened in render order (the loop walks it);
 *   byIndex — the renderer's finding-position -> queue-item map, kept
 *   identical to the inline version this replaced, including its last-wins
 *   behaviour if two items ever bind to the same position.
 *
 * Binding runs over the FULL item list before admission: the multimap's
 * consuming counter must see every item, exactly as the queue's first render
 * did, or duplicate-id rows would bind to different findings depending on
 * which sibling happened to be filtered out.
 */
function queueProjection(items, findings, findingIds, admit) {
  const all = items || [];
  const bound = bindQueueItems(all, findings, findingIds);
  const byIndex = new Map();
  for (const item of all) byIndex.set(bound[item.index], item);
  const entries = [];
  for (const item of all) {
    const at = bound[item.index];
    const f = at >= 0 ? (findings || [])[at] : null;
    if (!f) continue;
    if (typeof admit === "function" && !admit(item, f, at)) continue;
    entries.push({ f, index: at });
  }
  const laneCut = groupByLane(entries);
  const ordered = [];
  for (const lane of laneCut.order) {
    for (const e of laneCut.groups[lane] || []) ordered.push(e);
  }
  return { groups: laneCut.groups, order: laneCut.order, entries: ordered, byIndex };
}

/** The string that makes a rank auditable (spec 1.5). A row that cannot print
 *  its own reason is not ranked, it is sorted by something nobody can audit. */
function rankReasonText(f) {
  if (!f) return "";
  const cat = (f.category || "").toLowerCase();
  const lane = findingLane(f);
  const parts = [LANE_LABELS[lane] || cat || "Uncategorised"];
  const weighed = Object.prototype.hasOwnProperty.call(IMPACT, cat);
  if (weighed) parts.push(`impact ${IMPACT[cat]}`);
  else parts.push("unweighed");
  if (f.verification && f.verification.status === "verified") parts.push("verified");
  const refs = sceneRefCount(f);
  if (refs > 1) parts.push(`spans ${refs} scenes`);
  return "ranked here: " + parts.join(", ");
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
    IMPACT,
    LANE_OF,
    LANE_LABELS,
    LANE_BLURB,
    findingLane,
    sceneRefCount,
    rankScore,
    rankReasonText,
    bindQueueItems,
    laneOrder,
    groupByLane,
    queueProjection,
  };
}
