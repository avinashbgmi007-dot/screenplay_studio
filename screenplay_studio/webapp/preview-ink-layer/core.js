/**
 * core.js — DOM-free primitives for Architecture I: The Ink Layer.
 *
 * Everything in this file is pure: no DOM, no network, no timers.
 * Unit-tested by tests/core.test.mjs (node --test) exactly like webapp/core.js.
 *
 * The three mechanisms of the architecture map to three sections here:
 *   §1  row traversal + Horizon geometry      (spatial logic)
 *   §2  dwell + fold state machine            (temporal logic)
 *   §3  take-casting string math + adapters   (mutation logic)
 *   §4  the keymap arbitration table          (input precedence)
 */

/* ══════════════════════════════════════════════════════════════════════════
   §0  CONSTANTS
   ══════════════════════════════════════════════════════════════════════════ */

/** Dwell before the fold blooms. Interaction primitive — not an animation delay. */
export const DWELL_MS = 420;

/** Fold transition. Kept separate from DWELL_MS so reduced-motion can mute one. */
export const FOLD_MS = 260;

/** Severity is an ordered scale everywhere in the system. */
export const SEV_ORDER = ['none', 'minor', 'major', 'critical'];
const SEV_RANK = { none: 0, minor: 1, major: 2, critical: 3 };

/**
 * THE DESK SPEAKS TWO VOCABULARIES. The findings a study emits carry
 * critical | major | minor; the summary route reports by_severity as
 * high | major | medium | low. Reading only ours scored every `high` finding as
 * `none` — no mark, no pip width, no severity at all — and a critique that
 * silently ranks an urgent note as noise is worse than no critique. The four
 * labels collapse onto the three marks by ORDER, and the collapse is stated
 * rather than hidden: `medium` and `low` are both the single mark.
 * (Open question for the product: whether the two middle tiers deserve their
 * own mark — see OPEN_QUESTIONS.md.)
 */
export const SEV_ALIAS = {
  critical: 'critical', blocker: 'critical', high: 'critical',
  major: 'major', medium: 'minor', moderate: 'minor',
  minor: 'minor', low: 'minor', none: 'none',
};
export const canonSev = (s) => SEV_ALIAS[String(s ?? 'none').trim().toLowerCase()] ?? 'none';
export const sevRank = (s) => SEV_RANK[canonSev(s)];
export const sevAtLeast = (s, floor) => sevRank(s) >= (Number(floor) || 0);

/** Horizontal mass of the ink pip inside the 12px track, in px. Geometry, not colour. */
const INK_PX = { none: 0, minor: 4, major: 8, critical: 12 };
export const inkPx = (worst) => INK_PX[canonSev(worst)] ?? 0;

/**
 * How many findings are ever authored into one fold. Bounds the fold's height.
 */
export const MAX_FINDS_PER_FOLD = 6;

/**
 * Column geometry of the screenplay grammar, in character cells.
 * THE SINGLE SOURCE OF TRUTH for indentation: the renderer composes the row
 * text from this map AND sets the fold's --indent from it, so the critique can
 * never open in a different column from the line it belongs to.
 */
export const INDENT = {
  scene_heading: 0, action: 0, shot: 0, transition: 0, general: 0,
  character: 22, parenthetical: 18, dialogue: 14,
};
export const CHARS_PER_SCREENPLAY_INCH = 10; // Courier 12pt, for width math later
export const indentOf = (type) => INDENT[type] ?? 0;

/** The renderer owns leading whitespace: element text is stripped on the way in
 *  and re-indented deterministically, so source drift cannot double-indent. */
export const stripLead = (text) => String(text ?? '').replace(/^[ \t]+/, '');
export const indentText = (type, text) => ' '.repeat(indentOf(type)) + stripLead(text);

/* ══════════════════════════════════════════════════════════════════════════
   §0b THE STUDIO'S CAPABILITY TOKEN
   ══════════════════════════════════════════════════════════════════════════
   The webapp's write guard (webapp_server._reject_cross_origin_writes) refuses
   every POST that does not carry `X-Studio-Token` when a token is configured,
   and hands the page its licence as the `studio_token` cookie — NOT HttpOnly,
   precisely so the page's own script can echo it. A prototype served by the
   studio on the same origin therefore has to do the same thing, or every write
   it makes comes back 403 while every read succeeds: the exact "looked
   authenticated until the write" failure the server's own comment names.
   Pure functions, so the rule is testable without a server.
*/
export const STUDIO_TOKEN_COOKIE = 'studio_token';

/** Read one cookie's value out of a `document.cookie` string, or null. */
export function tokenFromCookie(cookieHeader, name = STUDIO_TOKEN_COOKIE) {
  const raw = String(cookieHeader ?? '');
  for (const part of raw.split(';')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() !== name) continue;
    const v = part.slice(eq + 1).trim();
    return v ? decodeURIComponent(v) : null;
  }
  return null;
}

/** The headers a write carries: JSON, plus the page's licence when it has one. */
export function writeHeaders(cookieHeader, name = STUDIO_TOKEN_COOKIE) {
  const token = tokenFromCookie(cookieHeader, name);
  return token ? { 'Content-Type': 'application/json', 'X-Studio-Token': token }
               : { 'Content-Type': 'application/json' };
}

/* ══════════════════════════════════════════════════════════════════════════
   §1  ROW TRAVERSAL + HORIZON GEOMETRY
   ══════════════════════════════════════════════════════════════════════════ */

export function clampIndex(i, len) {
  if (len <= 0) return -1;
  return Math.max(0, Math.min(len - 1, i));
}

/** Step one row. Clamped, not wrapping: the ends are real places. */
export function stepIndex(i, len, delta) {
  if (len <= 0) return -1;
  return Math.max(0, Math.min(len - 1, i + delta));
}

/**
 * Nearest "wet" row in a direction. Steps off `from` first, so pressing n
 * while already on a wet row advances to the *next* wet row rather than
 * re-firing the current one. Returns -1 at the extreme (caller announces).
 */
export function nearestWet(rows, from, dir) {
  const n = rows.length;
  if (!n) return -1;
  let i = from + dir;
  while (i >= 0 && i < n) {
    if (rows[i].wet) return i;
    i += dir;
  }
  return -1;
}

/** Index of the row whose `lineStart` matches, else the nearest row after it. */
export function rowForLine(rows, lineStart) {
  if (lineStart == null) return -1;
  let best = -1;
  for (let i = 0; i < rows.length; i++) {
    const l = rows[i].lineStart;
    if (l == null) continue;
    if (l === lineStart) return i;
    if (l < lineStart) best = i;
  }
  return best;
}

/**
 * True-proportion scene bands for the 12px track.
 *
 * Integer accumulation guarantees the three invariants the Horizon depends on:
 *   • bands tile the track exactly (Σ h === trackHeight, no gaps, no overlaps)
 *   • tops are monotonically non-decreasing
 *   • every band is at least `minBandPx` tall (a 1-page scene stays clickable)
 *
 * `boxes` are content-space rects: { key, top, height } in px, already measured.
 * `domain` is the measured extent the track represents (scrollHeight or the
 * content box — see measure() in ink-layer.js).
 */
export function sceneBands(boxes, domain, trackHeight, { minBandPx = 1 } = {}) {
  const H = Math.max(1, domain);
  const T = Math.max(1, Math.round(trackHeight));
  if (!boxes.length) return [];
  const out = [];
  let prevBottom = 0;
  for (let i = 0; i < boxes.length; i++) {
    const b = boxes[i];
    const isLast = i === boxes.length - 1;
    let top = Math.round((b.top / H) * T);
    top = Math.max(prevBottom, Math.min(T - 1, top));
    const natural = isLast ? T : Math.round(((b.top + b.height) / H) * T);
    let bottom = Math.min(T, Math.max(natural, top + minBandPx));
    if (bottom - top < 1) bottom = Math.min(T, top + 1);
    out.push({
      key: b.key,
      topPx: top,
      hPx: bottom - top,
      topPct: (top / T) * 100,
      hPct: ((bottom - top) / T) * 100,
      page: b.page ?? null,
    });
    prevBottom = bottom;
  }
  return out;
}

/** Viewport window rect for the track, in track px. */
export function windowRect(scrollTop, clientHeight, scrollHeight, trackHeight) {
  const H = Math.max(1, scrollHeight);
  const T = Math.max(1, trackHeight);
  const top = (Math.max(0, scrollTop) / H) * T;
  const h = Math.max(8, (clientHeight / H) * T); // 8px floor keeps the window grabbable
  return { topPx: top, hPx: h };
}

/** Inverse: track y → scrollTop that puts that document position in view. */
export function scrubTo(trackY, clientHeight, scrollHeight, trackHeight, { center = false } = {}) {
  const H = Math.max(1, scrollHeight);
  const T = Math.max(1, trackHeight);
  const ratio = Math.max(0, Math.min(1, trackY / T));
  const target = ratio * H - (center ? clientHeight / 2 : 0);
  return Math.max(0, Math.min(H - clientHeight, target));
}

/** Bucket findings into per-scene ink channels. Tolerant of payload shapes. */
export function inkChannels(findings, { includeDismissed = false } = {}) {
  const map = new Map();
  for (const f of findings || []) {
    if (f.dismissed && !includeDismissed) continue;
    const refs = Array.isArray(f.scene_refs) && f.scene_refs.length ? f.scene_refs
      : (f.scene != null ? [f.scene] : []);
    for (const s of refs) {
      const c = map.get(s) || { scene: s, worst: 'none', open: 0, addressed: 0, flagged: 0 };
      if (f.status === 'addressed') {
        c.addressed += 1;
      } else {
        c.open += 1;
        // The channel's `worst` is the CANONICAL word (see SEV_ALIAS): the pip
        // geometry and the CSS both read this value, and a desk that spells the
        // same weight `high` must not produce a severity the page has no mark for.
        if (sevRank(f.severity) > sevRank(c.worst)) c.worst = canonSev(f.severity);
      }
      if (isFlagged(f)) c.flagged += 1;
      map.set(s, c);
    }
  }
  return map;
}

/** A finding is flagged when the verifier could not land its quote (0.72 gate). */
export function isFlagged(f) {
  if (f.verification && typeof f.verification === 'object' && f.verification.status) {
    return f.verification.status !== 'verified';
  }
  if (typeof f.verified === 'boolean') return f.verified === false;
  if (typeof f.verification === 'string') return f.verification !== 'verified';
  return false;
}

/** Provenance: attributed craft rule vs. mechanical deterministic pass. */
export function provenanceOf(f) {
  if (f.check_id) return 'measured';
  if (f.rule_id) return 'attributed';
  return 'unknown';
}

/**
 * The one counting contract (mirrors app.js findingDisposition): every surface
 * reads open/addressed/flagged from here, so the radar and the fold can never
 * disagree about the same finding.
 */
export function inkTotals(findings, { includeDismissed = false } = {}) {
  let open = 0, addressed = 0, flagged = 0, dismissed = 0;
  for (const f of findings || []) {
    if (f.dismissed) { dismissed += 1; if (!includeDismissed) continue; }
    if (f.status === 'addressed') addressed += 1; else open += 1;
    if (isFlagged(f)) flagged += 1;
  }
  return { open, addressed, flagged, dismissed };
}

/** Canonical /findings/summary reader. Unknown fields are `null`, never guessed. */
export function normalizeSummary(payload) {
  const s = payload || {};
  const t = s.totals || {};
  const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
  const pick = (...vals) => {
    for (const v of vals) if (v !== undefined && v !== null) return v;
    return null;
  };
  /* The route's own names come FIRST where they differ: GET /findings/summary
     answers { open_count, done_count, dismissed_count, by_status }, and
     `still_present + unknown` is exactly the open set that arithmetic uses.
     Reading only the legacy names made the drift check silently blind against a
     real studio — a reconciliation that can never disagree is not a check. */
  const byStatus = s.by_status || t.by_status || null;
  const sumStatus = (a, b) => (byStatus ? (Number(byStatus[a]) || 0) + (Number(byStatus[b]) || 0) : null);
  return {
    dawnPct: num(pick(s.dawn_pct, s.dawn, t.dawn_pct)),
    open: num(pick(s.open, t.open, s.open_count, sumStatus('still_present', 'unknown'))),
    addressed: num(pick(s.addressed, t.addressed, s.done_count, byStatus && Number(byStatus.addressed))),
    dismissed: num(pick(s.dismissed, t.dismissed, s.dismissed_count)),
    flagged: num(pick(s.flagged, t.flagged)),
    bySeverity: s.by_severity || t.by_severity || null,
    /** Capability flag: the summary carries per-scene buckets → the radar can
     *  paint the whole track from ONE call. Detected at boot, never assumed. */
    byScene: s.by_scene || s.byScene || t.by_scene || null,
  };
}

/**
 * Reconcile client-side buckets against the server's summary. The server number
 * WINS (the client is a cache); drift is reported so the UI can say so out loud
 * rather than quietly disagreeing with itself.
 */
export function reconcileInk(channels, summary) {
  const local = { open: 0, addressed: 0, flagged: 0 };
  for (const c of (channels instanceof Map ? channels.values() : Object.values(channels || {}))) {
    local.open += c.open; local.addressed += c.addressed; local.flagged += c.flagged;
  }
  const s = normalizeSummary(summary);
  // delta is SERVER − CLIENT. Positive means the client's cache is behind the
  // server (it has not seen the newest findings yet): stale, not wrong.
  const cmp = (server, client) => (server == null ? null : server - client);
  const delta = { open: cmp(s.open, local.open), addressed: cmp(s.addressed, local.addressed), flagged: cmp(s.flagged, local.flagged) };
  const drift = Object.values(delta).some((d) => d !== null && d !== 0);
  return { local, server: s, delta, drift, authority: 'server' };
}

/* ══════════════════════════════════════════════════════════════════════════
   §2  DWELL + FOLD STATE MACHINE
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Fold lifecycle. Data-attribute values on .rowgroup, in order.
 *   closed → armed → open → closing → closed
 * `pinned` is orthogonal: an open fold that the writer claimed with Enter/click,
 * which therefore no longer closes when the pointer leaves or focus moves.
 */
export const FOLD_STATE = ['closed', 'armed', 'open', 'closing'];

export function foldNext(state, event) {
  const T = {
    closed: { arm: 'armed', open: 'open' },
    armed: { cancel: 'closed', fire: 'open' },
    open: { close: 'closing' },
    closing: { settle: 'closed' },
  };
  return (T[state] || {})[event] || state;
}

/**
 * Does the fold's growth need a scroll correction to keep the focused LINE
 * stationary? Only when something above the line changes height: closing a
 * fold that sits above the focused row. Growth below the line never moves it.
 */
export function scrollCorrection({ closingHeightPx, closingTopPx, focusTopPx }) {
  const above = closingTopPx + closingHeightPx <= focusTopPx;
  return above ? -Math.max(0, closingHeightPx) : 0;
}

/**
 * Keep the focused row fully in the viewport after a fold opens, moving the
 * scroll ONLY by the overflow. scrollIntoView would move the line itself.
 */
export function overflowCorrection({ rowTop, rowBottom, foldBottom, viewTop, viewBottom }) {
  if (foldBottom > viewBottom) return foldBottom - viewBottom;
  if (rowTop < viewTop) return rowTop - viewTop;
  return 0;
}

/* ══════════════════════════════════════════════════════════════════════════
   §3  TAKE-CASTING — string math + payload adapters
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Capture the immutable frame a cast composes into: prefix + target + suffix.
 * The frame is captured ONCE per line per cast session. Never re-frame a line
 * you have already composed — that is how J→K→J accumulates text.
 *
 * Returns null when the evidence quote does not occur in the live line: the
 * candidate is not castable, and the caller must say so rather than guess.
 */
export function frameOf(text, target) {
  if (typeof text !== 'string' || typeof target !== 'string' || !target) return null;
  const at = text.indexOf(target);
  if (at < 0) return null;
  return {
    at,
    prefix: text.slice(0, at),
    target,
    suffix: text.slice(at + target.length),
    original: text,
    /** The quote occurs more than once — cast it, but say it is ambiguous. */
    ambiguous: text.indexOf(target, at + 1) >= 0,
  };
}

/** The single composition function. Pure string replacement, no DOM. */
export function composeLine(frame, candidateText) {
  if (!frame) return null;
  return frame.prefix + String(candidateText ?? '') + frame.suffix;
}

/** Byte-exact restore, by construction: the original was never mutated. */
export function restoreLine(frame) {
  return frame ? frame.original : null;
}

/** Take ring position. Clamped by default; `wrap` is opt-in, never implicit. */
export function stepRing(i, len, delta, { wrap = false } = {}) {
  if (len <= 0) return -1;
  /* A RING OF len + 1 PLACES. Position -1 is not "nothing selected": it is the
     writer's own line, and it is the zero point the first take is reached from
     and returned to. The ring therefore clamps at -1 and at len - 1 — the ends
     are real places (your line; the last take), not silent failures. */
  const n = i + delta;
  if (wrap) return ((n + 1) % (len + 1) + (len + 1)) % (len + 1) - 1;
  return Math.max(-1, Math.min(len - 1, n));
}

/* ══════════════════════════════════════════════════════════════════════════
   §3a  ANCHORING — a finding is placed by its quote, never by a line number
   ══════════════════════════════════════════════════════════════════════════
   The contract is unambiguous (contracts_UI §3.2): `line_start` "is an unstable
   parameter that drifts during edit loops", and every critique must ground on a
   fuzzy match (threshold 0.72) against `evidence_quote`. The renderer used to
   place findings by substring or fall back to the scene's first row, which meant
   a quote repeated in two places, or reworded slightly, attached to whatever
   line happened to be first. So: score every row in the finding's scenes, take
   the best match at or above the threshold, and when two rows are close enough
   to be a coin toss, SAY SO and never pick silently.
*/
export const ANCHOR_THRESHOLD = 0.72;
const normQ = (t) => String(t ?? '').toLowerCase()
  .replace(/[^a-z0-9' ]+/g, ' ').replace(/\s+/g, ' ').trim();

/**
 * Quote↔text similarity in 0..1. Containment is a match (a located quote is the
 * strongest evidence there is); otherwise Sørensen–Dice over character bigrams,
 * which tolerates the small rewordings that make line numbers useless.
 */
export function fuzzyScore(quote, text) {
  const a = normQ(quote), b = normQ(text);
  if (!a || !b) return 0;
  if (b.includes(a)) return 1;
  if (a.length < 3) return 0;
  const grams = (str) => {
    const m = new Map();
    for (let i = 0; i < str.length - 1; i++) {
      const g = str.slice(i, i + 2);
      m.set(g, (m.get(g) || 0) + 1);
    }
    return m;
  };
  const ga = grams(a), gb = grams(b);
  let hit = 0, total = 0;
  for (const [g, n] of ga) { total += n; hit += Math.min(n, gb.get(g) || 0); }
  for (const [, n] of gb) total += n;
  return total ? (2 * hit) / total : 0;
}

/**
 * Place one finding against the rows of its own scenes.
 * Returns { rowIndex, score, exact, ambiguous, loose } — never a silent guess:
 *   exact      the quote is contained in the row (score 1)
 *   ambiguous  two rows scored within `tie` of each other; `hint` (line_start)
 *              breaks the tie when it can, and the caller must say it did
 *   loose      nothing reached the threshold: the finding stays SCENE-anchored
 *              (shown, never dropped, and never re-pointed at a line it cannot
 *              prove it belongs to)
 */
export function anchorFinding(rows, finding, { threshold = ANCHOR_THRESHOLD, tie = 0.04 } = {}) {
  const refs = Array.isArray(finding?.scene_refs) && finding.scene_refs.length
    ? finding.scene_refs
    : (finding?.scene != null ? [finding.scene] : []);
  const pool = [];
  rows.forEach((r, i) => {
    if (refs.length && !refs.includes(r.scene)) return;
    pool.push({ i, score: fuzzyScore(finding?.evidence, r.baseText ?? r.text) });
  });
  const inScene = pool.length ? pool : rows.map((r, i) => ({ i, score: 0 }));
  if (!inScene.length) return { rowIndex: -1, score: 0, exact: false, ambiguous: false, loose: true };
  inScene.sort((a, b) => (b.score - a.score) || (a.i - b.i));
  const best = inScene[0];
  const rivals = inScene.filter((c) => c !== best && best.score - c.score <= tie);
  const hintIdx = finding?.line_start != null
    ? rows.findIndex((r) => r.lineStart === finding.line_start) : -1;
  if (best.score < threshold) return { rowIndex: -1, score: best.score, exact: false, ambiguous: false, loose: true };
  if (!rivals.length) return { rowIndex: best.i, score: best.score, exact: best.score >= 1, ambiguous: false, loose: false };
  const hinted = [best, ...rivals].find((c) => c.i === hintIdx);
  return { rowIndex: (hinted || best).i, score: best.score, exact: best.score >= 1, ambiguous: true, loose: false };
}

/* ══════════════════════════════════════════════════════════════════════════
   §3b  REHEARSAL — the comparison mechanic, chosen by what is being compared
   ══════════════════════════════════════════════════════════════════════════
   Rehearsal is a MODE of the strip, not a second surface. Which mechanic it
   uses is decided by the material, not by the writer's preference:

     voice  (dialogue, character cue, parenthetical)  → TEMPORAL
            takes are heard one at a time, on a beat, because the thing being
            judged is a rhythm you can only judge in time.
     space  (action, scene heading, shot, transition) → SPATIAL
            takes are stacked side by side with their size, because the thing
            being judged is how much text a line loses, and a deletion that
            only passes on the beat is a deletion nobody noticed.

   Their constraint is honoured literally: because temporal comparison alone
   can hide subtle deletions, the stack is always readable for a voice row too
   — the fold keeps the read-only diff, and the ledger states the delta against
   the passage. The beat is a reading pace, not an animation, so it is NOT
   disabled under reduced motion; only the strip's colour steps are.
*/
export const REHEARSAL_BEAT_MS = 1400;
const VOICE_TYPES = new Set(['dialogue', 'character', 'parenthetical']);
export const rehearsalMode = (type) => (VOICE_TYPES.has(type) ? 'temporal' : 'spatial');

/**
 * One beat of the audition. Ring positions run -1 (the writer's own line) ..
 * count - 1, so the reading starts at take 1, and -1 means "the reading is
 * over" — a sentinel, because a completed reading is not the same state as
 * never having started, and the caller must announce them differently.
 */
export function rehearsalStep({ ring, count }) {
  if (!(count > 0)) return -1;
  const next = ring + 1;
  return next < count ? next : -1;
}

/* ══════════════════════════════════════════════════════════════════════════
   §3c  THE PROPOSAL — what a take is, what it would read as, how it differs
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Word-level change map between the line as it stands and the line as it would
 * read. Returns segments { op: '=' | 'del' | 'ins', text }; whitespace rides
 * with the words so the renderer can print the result as a sentence.
 *
 * This is the answer to "writers can identify what was deleted, added, and
 * preserved" — the count in the ledger says how much moved, this says what.
 * Longest-common-subsequence over tokens: O(n·m) on a line of ≤ a few hundred
 * words, and it never throws on empty or identical sides.
 */
export function diffWords(before, after) {
  const tok = (t) => String(t ?? '').split(/(\s+)/).filter((x) => x !== '');
  const words = (t) => tok(t).filter((x) => !/^\s+$/.test(x));
  const A = words(before), B = words(after);
  const n = A.length, m = B.length;
  const key = (w) => w.toLowerCase();
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = key(A[i]) === key(B[j])
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out = [];
  const push = (op, text) => {
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += text;
    else out.push({ op, text });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (key(A[i]) === key(B[j])) { push('=', A[i] + ' '); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { push('del', A[i] + ' '); i++; }
    else { push('ins', B[j] + ' '); j++; }
  }
  while (i < n) { push('del', A[i] + ' '); i++; }
  while (j < m) { push('ins', B[j] + ' '); j++; }
  for (const seg of out) seg.text = seg.text.replace(/\s+$/, '');
  return out.filter((seg) => seg.text !== '');
}

/**
 * The class the desk answered with, stated as scope. A scene-level request must
 * not look like a guaranteed single-line operation: if the response carried the
 * scene's text or proposals for more than one passage, the strip says so.
 */
export function scopeOf(norm, row) {
  const takes = (norm?.takes || []).filter((t) => t && t.candidates && t.candidates.length);
  const frames = takes.reduce((n, t) => n + t.candidates.length, 0);
  const mine = row ? takes.filter((t) => takeForRow([t], { lineStart: row.lineStart, text: row.text })) : takes;
  const kind = norm?.sceneText ? 'scene' : (takes.length > 1 ? 'line' : 'passage');
  return { kind, passages: takes.length, frames, onThisLine: mine.length };
}

/** Do any two proposals rewrite overlapping text? Independence is never assumed. */
export function targetSpans(text, takes) {
  const spans = [];
  for (const t of takes || []) {
    if (!t?.oldText) continue;
    let at = String(text ?? '').indexOf(t.oldText);
    while (at >= 0) {
      spans.push({ start: at, end: at + t.oldText.length, take: t });
      at = String(text).indexOf(t.oldText, at + 1);
    }
  }
  return spans.sort((a, b) => a.start - b.start);
}
export function overlappingTargets(text, takes) {
  const spans = targetSpans(text, takes);
  // Overlap only matters between DIFFERENT proposals; repeats of one proposal are
  // the ambiguity question, not the dependency question.
  const byTake = new Map();
  for (const sp of spans) {
    const list = byTake.get(sp.take) || [];
    list.push(sp);
    byTake.set(sp.take, list);
  }
  const flat = [...byTake.values()].map((list) => list[0]);
  for (let a = 0; a < flat.length; a++) {
    for (let b = a + 1; b < flat.length; b++) {
      if (flat[a].start < flat[b].end && flat[b].start < flat[a].end) return true;
    }
  }
  return false;
}

/**
 * Direct editing of the provisional text — recomposed from the captured frame,
 * never re-framed from the mutated line. The frame is the writer's original
 * passage: whatever they type is dropped into that hole, so a typed proposal can
 * never accumulate the previous proposal.
 */
export function editProposal(frame, typed) {
  const text = String(typed ?? '').replace(/\s+/g, ' ').trim();
  if (!frame) return { ok: false, reason: 'no frame to edit' };
  if (!text) return { ok: false, reason: 'empty' };
  if (text === frame.target) return { ok: false, reason: 'unchanged' };
  return { ok: true, text, composed: composeLine(frame, text) };
}

/** Characters added and removed between two strings, as the ledger prints them. */
export function deltaOf(before, after) {
  const d = String(after ?? '').length - String(before ?? '').length;
  return { added: d > 0 ? d : 0, removed: d < 0 ? -d : 0, net: d };
}

/* ── the context filter: critique recedes, prose never does ────────────────── */

export const SCOPE_KINDS = ['all', 'scene', 'category', 'status'];
export function nextScope(scope, ctx = {}) {
  const at = SCOPE_KINDS.indexOf(scope?.kind || 'all');
  for (let step = 1; step <= SCOPE_KINDS.length; step++) {
    const kind = SCOPE_KINDS[(at + step) % SCOPE_KINDS.length];
    if (kind === 'all') return { kind: 'all', value: null };
    if (kind === 'scene' && ctx.scene != null) return { kind, value: ctx.scene };
    if (kind === 'category' && ctx.category) return { kind, value: ctx.category };
    if (kind === 'status') return { kind, value: 'open' };
  }
  return { kind: 'all', value: null };
}
export function inScope(f, scope, ctx = {}) {
  if (!scope || scope.kind === 'all') return true;
  if (scope.kind === 'scene') {
    const refs = Array.isArray(f?.scene_refs) && f.scene_refs.length ? f.scene_refs : (f?.scene != null ? [f.scene] : []);
    return refs.includes(scope.value ?? ctx.scene);
  }
  if (scope.kind === 'category') return f?.category === scope.value;
  if (scope.kind === 'status') return scope.value === 'open' ? f?.status !== 'addressed' : f?.status === scope.value;
  return true;
}
/** A row's critique is quiet when it is below the floor OR outside the filter. */
export function quietRow(row, floor, scope, ctx = {}) {
  if (!row || row.worst === 'none' || !row.finds || !row.finds.length) return false;
  if (floor > 0 && sevRank(row.worst) < floor) return true;
  return !row.finds.some((f) => inScope(f, scope, ctx));
}

/** The nearest OTHER scene a finding cites, for "visit related passage". */
export function relatedScene(f, currentScene) {
  const refs = Array.isArray(f?.scene_refs) && f.scene_refs.length ? f.scene_refs : (f?.scene != null ? [f.scene] : []);
  return refs.find((s) => s !== currentScene) ?? null;
}

/**
 * The apply response carries the recomputed findings state (contracts_UI §2.D):
 *   { scene_number, scene_text_after, findings_status: { summary, findings:[{index,status}] } }
 * So the page does not have to guess how a written edit changed the critique,
 * and does not have to make two more round trips to find out.
 */
export function statusPatch(res) {
  const fs = res && res.findings_status;
  if (!fs || typeof fs !== 'object') return null;
  const byIndex = new Map();
  for (const f of fs.findings || []) {
    if (f && f.index != null && f.status) byIndex.set(Number(f.index), String(f.status));
  }
  return { byIndex, summary: fs.summary || null };
}

/**
 * Normalise POST /rewrite into the shape the casting layer consumes.
 * Tolerant of the several plausible field names because the route map only
 * promises "replacement candidates for a scene". Anything unusable is
 * reported in `skipped` with a reason — flag, don't drop.
 */
const KNOWN_REWRITE_KEYS = ['replacements', 'targets', 'lines', 'candidates', 'takes', 'scene_text', 'note'];
const REWRITE_UNKNOWN =
  'the response carried none of the fields this desk answers with (replacements, targets, lines, candidates, scene_text, note)';

export function normalizeRewrite(payload) {
  const p = payload || {};
  /* A VALIDATED ENVELOPE, NOT AN OPTIMISTIC ONE. The tolerant reader below can
     only be safe while it is reading something it recognises; anything else is
     reported as unrecognised and the strip fails loudly, because guessing the
     structure of a reply is how a valid replacement ends up attached to the
     wrong text (Ashna's required correction). */
  const known = p && typeof p === 'object' && KNOWN_REWRITE_KEYS.some((k) => k in p);
  /* THE REAL CONTRACT, first because it is now the only thing the route sends:
       { scene_number, note, replacements: [{ old, new }], scene_text }
     A frame is not a take: it is ONE candidate for a passage, cut from the
     exact bytes it proposes to replace and applied by that match. Takes are
     therefore built by GROUPING the frames — every frame that names the same
     `old` is an alternate for the same passage, so it becomes another candidate
     in that passage's ring, and the ring keeps working exactly as the UI
     promises (J/K auditions, Enter applies one frame) while the wire stays
     one-frame-per-edit. Frames naming different passages stay separate takes.
     The legacy branches below stay: the contract was unknown when they were
     written and a tolerant reader costs nothing. */
  const frames = Array.isArray(p.replacements) ? p.replacements : null;
  if (frames && frames.some((r) => r && typeof r === 'object'
       && typeof r.old === 'string' && typeof r.new === 'string')) {
    const byOld = new Map();
    const takes = [];
    const skipped = [];
    for (const f of frames) {
      const flat = f && typeof f === 'object'
        && typeof f.old === 'string' && typeof f.new === 'string';
      if (!flat) { skipped.push({ id: skipped.length, reason: 'not an {old, new} frame' }); continue; }
      if (!f.old.trim() || !f.new.trim()) { skipped.push({ id: skipped.length, reason: 'frame has an empty side' }); continue; }
      if (f.old === f.new) { skipped.push({ id: skipped.length, reason: 'frame proposes no change' }); continue; }
      let take = byOld.get(f.old);
      if (!take) {
        take = { lineStart: f.line_start ?? null, elIndex: null, oldText: f.old,
                 findingId: f.finding_id ?? null, candidates: [], skipped: [] };
        byOld.set(f.old, take);
        takes.push(take);
      }
      if (take.candidates.some((c) => c.text === f.new)) continue;   // a repeat is not a take
      take.candidates.push({
        id: take.candidates.length, text: f.new,
        ruleId: f.rule_id ?? null, checkId: f.check_id ?? null,
        confidence: typeof f.confidence === 'number' ? f.confidence : null,
      });
    }
    return { scene: p.scene_number ?? p.scene ?? null, note: p.note ?? '',
             sceneText: p.scene_text ?? null, takes, skipped, unknown: false };
  }
  const raw = p.targets || p.lines || p.replacements || p.candidates || [];
  const list = Array.isArray(raw) ? raw : [];
  const takes = [];
  for (const r of list) {
    const cands = r.candidates || r.options || r.takes || [];
    const arr = Array.isArray(cands) ? cands : [];
    const skipped = [];
    const candidates = [];
    arr.forEach((c, i) => {
      const text = typeof c === 'string' ? c : (c.text ?? c.new_text ?? c.line ?? '');
      const reason = c.skipped_reason ?? c.reason ?? null;
      if (reason || !text) { skipped.push({ id: c.id ?? i, reason: reason || 'empty candidate' }); return; }
      candidates.push({
        id: c.id ?? c.take ?? i,
        text,
        ruleId: c.rule_id ?? r.rule_id ?? null,
        checkId: c.check_id ?? r.check_id ?? null,
        confidence: typeof c.confidence === 'number' ? c.confidence : null,
      });
    });
    takes.push({
      lineStart: r.line_start ?? r.lineStart ?? null,
      elIndex: r.el_index ?? r.elIndex ?? null,
      oldText: r.old_text ?? r.oldText ?? r.target_text ?? '',
      findingId: r.finding_id ?? r.findingId ?? null,
      candidates,
      skipped,
    });
  }
  if (!known) {
    return { scene: null, note: '', sceneText: null, takes: [], skipped: [],
             unknown: true, reason: REWRITE_UNKNOWN };
  }
  return { scene: p.scene ?? p.scene_number ?? null, takes, skipped: [], unknown: false };
}

/** Pick the take record that belongs to a row. Exact line_start first, then text. */
export function takeForRow(takes, { lineStart, text }) {
  const byLine = (takes || []).find((t) => t.lineStart != null && t.lineStart === lineStart);
  if (byLine) return byLine;
  return (takes || []).find((t) => t.oldText && text && text.includes(t.oldText)) || null;
}

/**
 * Body of the POST /edits/apply request for one cast take.
 *
 * THE REAL CONTRACT (webapp_server `apply_edits`, hardened):
 *     { scene_number, replacements: [{ old, new }] }
 * `old` is the frame's captured target — the exact bytes the take was cut from
 * — and the route refuses the WHOLE proposal with
 *     {"error": "Stale proposal: the text was modified manually.", "stale": true}
 * when those bytes are no longer what the working copy holds at the moment the
 * lock is taken. That refusal is the writer's protection, not an error to paper
 * over; `classifyApplyError` below turns it into a decision, and the DOM layer
 * answers it by putting the writer's own text back on the page.
 */
export function applyPayload({ sceneNumber, take, frame, candidate }) {
  return {
    scene_number: sceneNumber ?? null,
    replacements: [{
      old: frame ? frame.target : (take?.oldText ?? ''),
      new: candidate?.text ?? '',
    }],
  };
}

/**
 * One decision point for a failed apply. The DOM layer must never string-match
 * a server message, so the two 400 bodies the route can return are classified
 * here — they are contract, not accident:
 *   stale   the text moved under the proposal. NOTHING was written; the page is
 *           the writer's own text and asking again is the recovery.
 *   frames  a malformed replacement frame: the desk's bug, not the writer's.
 *   failed  anything else (network, 404, a dead studio).
 */
export function classifyApplyError(err) {
  const body = err && typeof err.body === 'object' && err.body ? err.body : null;
  const message = (body && (body.error || body.message)) || (err && err.message) || 'Unknown error';
  if (body && body.stale === true) return { kind: 'stale', message, recoverable: true };
  if (err && err.status === 400 && /require string fields/.test(message)) {
    return { kind: 'frames', message, recoverable: false };
  }
  return { kind: 'failed', message, recoverable: true };
}

/**
 * One shape for findings, from either envelope the desk can hand back:
 *   live   GET /findings → { items: [...], count }   (items carry `index`,
 *          `evidence_quote`, `status` ∈ addressed|still_present|unknown)
 *   demo   the offline adapter → { findings: [...] } (the shape the renderer
 *          was written against, which predates the route map being read)
 * Missing is a legitimate empty; nothing is invented for a field the server did
 * not send. `evidence_quote` is the same fact as `evidence` under the name the
 * route actually uses.
 */
export function normalizeFindings(payload) {
  const list = Array.isArray(payload) ? payload
    : (payload && (payload.findings || payload.items)) || [];
  return (Array.isArray(list) ? list : []).map((f, i) => ({
    ...f,
    index: f.index ?? i,
    evidence: f.evidence ?? f.evidence_quote ?? '',
    status: f.status ?? 'open',
  }));
}

/** A cast is only committable when nothing else is in flight. */
export function canApply(cast) {
  return !!(cast && cast.active && cast.index >= 0 && cast.candidates?.length && !cast.busy);
}

/* ══════════════════════════════════════════════════════════════════════════
   §4  ANNOUNCEMENT COPY — the only text the app speaks
   ══════════════════════════════════════════════════════════════════════════ */

export const say = {
  foldOpen: ({ lineNo, count, worst, flagged }) => {
    const bits = [`Line ${lineNo}`, `${count} finding${count === 1 ? '' : 's'}`];
    if (worst && worst !== 'none') bits.push(`worst ${worst}`);
    if (flagged) bits.push(`${flagged} unverified`);
    return bits.join(', ') + '. Press Enter to fold.';
  },
  foldClosed: () => 'Folded.',
  castReady: ({ index, count, text }) =>
    count ? `Take ${index + 1} of ${count}: ${text}` : 'No candidates for this line.',
  castApplied: ({ count, lineNo }) => `Applied. Line ${lineNo} changed. Undo with Command Z.`,
  castFailed: ({ message }) => `Apply failed. ${message}`,
  castSkipped: ({ skipped }) =>
    skipped.length ? `${skipped.length} candidate${skipped.length === 1 ? '' : 's'} skipped: ${skipped[0].reason}` : '',
  wetNone: ({ dir, filtered = false }) => filtered
    /* The walk follows the FILTER as well as the floor: a writer who narrowed the
       reading to this scene and then was walked into a line they had receded would
       reasonably conclude the filter was broken. The row is still there, still at
       full contrast, and still reachable with the arrow keys — so the sentence
       says which narrowing to undo rather than pretending the page is empty. */
    ? `No further lines speaking up ${dir < 0 ? 'above' : 'below'} — the reading is narrowed. Press F to widen the filter, or [ and ] for the ink threshold.`
    : `No further wet lines ${dir < 0 ? 'above' : 'below'}.`,
  inkFloorQuiet: ({ floor, label, quiet }) =>
    `Ink threshold ${floor} of 3 — ${label}. ${quiet} finding${quiet === 1 ? '' : 's'} receded; the manuscript stays at full contrast.`,
  inkThreshold: ({ floor, label }) => `Ink threshold ${floor} of 3 — showing ${label} and above.`,
  radar: ({ page, worst, open }) => `Page ${page}, ${open} open${worst && worst !== 'none' ? `, worst ${worst}` : ''}.`,
  castOpening: ({ count, flagged }) => (flagged
    ? `Unverified finding: no target was chosen for you. The desk answered for the passage you named — ${count} take${count === 1 ? '' : 's'}, warning kept.`
    : `${count} take${count === 1 ? '' : 's'} for this passage. J and K audition them — the line itself does not move until you commit one with Enter. E edits the wording, Escape keeps your own line.`),
  rehearseSteady: ({ count }) =>
    `Structure is compared by eye: ${count} ${count === 1 ? 'take is' : 'takes are'} listed with what each adds and removes, because a beat would hide exactly the deletion this revision is about. J and K step through them.`,
  rehearseStart: ({ mode, count }) => mode === 'temporal'
    ? `Reading ${count === 1 ? 'the take' : `all ${count} takes`} aloud, one at a time. Any key stops the reading; the take under the ledger is the one on the line.`
    : `Stacked: ${count} ${count === 1 ? 'take' : 'takes'} side by side with their size. Action and structure are compared by the eye, not the ear.`,
  rehearseStep: ({ index, count, text }) => `Take ${index + 1} of ${count}: ${text}`,
  rehearseEnd: ({ count }) => `End of the reading. ${count} ${count === 1 ? 'take' : 'takes'} heard; the last one is on the line. J and K step, Enter applies, Escape keeps your own line.`,
  rehearseStop: () => 'Reading stopped.',
  proposalEdit: () =>
    'Editing the proposal. Your words replace the passage; Enter commits the text, Escape abandons the edit and keeps the take.',
  proposalEdited: ({ text }) =>
    `Proposal edited: ${text} Enter commits, Escape keeps your original line.`,
  proposalUnchanged: () => 'The proposal is unchanged, so there is nothing to commit.',
  proposalEmpty: () =>
    'An empty proposal would delete the line, and the apply route takes a replacement — not a deletion. Nothing changed.',
  unknownShape: ({ reason }) =>
    `The desk answered in a shape this page does not know: ${reason}. Nothing was cast and nothing was written — the response is reported here rather than guessed at.`,
  ambiguousTake: ({ score, lineNo }) =>
    `The quote matches more than one line (best ${Math.round(score * 100)}%). The nearer one is shown; the proposal is kept against the warning, never silently attached.`,
  overlapping: ({ count }) =>
    `These ${count} proposals touch overlapping text on this line. Each is applied on its own and re-checked, so applying one cannot silently carry another.`,
  scopeNow: ({ kind, value, n }) => {
    if (kind === 'all') return 'Filter: every finding on the page. Press F for this scene only.';
    if (kind === 'scene') return `Filter: scene ${value} only — ${n} finding${n === 1 ? '' : 's'} speak up, the rest recede. The prose is untouched. Press F for this category only.`;
    if (kind === 'category') return `Filter: ${value} findings only. Press F to show only what is still open.`;
    return "Filter: only findings that are still open. Press F to show everything again.";
  },
  roamVisit: ({ scene, lineNo }) =>
    `Related passage: scene ${scene}, line ${lineNo ?? '—'}. Press O to come back to where you were reading.`,
  roamReturn: ({ scene, lineNo }) =>
    `Back at scene ${scene}${lineNo ? `, line ${lineNo}` : ''} — where you were reading.`,
  roamNone: () => 'This finding cites no other scene, so there is nowhere to visit.',
  ground: ({ ground, lifted }) =>
    `Ground: ${lifted ? 'lifted — the same instrument raised off black' : 'instrument — black bench, amber worklight'}. Press G for the ${lifted ? 'instrument' : 'lifted'} ground.`,
  castStale: ({ message }) =>
    `${message} The take was cut from a line that has moved since, so nothing was written — your text stands. Press J or K to ask again for a fresh take.`,
  castFrames: ({ message }) => `${message} Nothing was written. That is the desk's fault, not your text.`,
  applyReport: ({ applied, skipped }) =>
    applied ? `Applied ${applied}.${skipped ? ` ${skipped} skipped.` : ''}` : 'Nothing applied.',
};

/* ══════════════════════════════════════════════════════════════════════════
   §5  KEYMAP ARBITRATION
   Exactly one listener owns the keyboard. This table is the whole contract;
   the DOM layer only executes what it returns.
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * @param {{key:string, metaKey?:boolean, ctrlKey?:boolean, altKey?:boolean, shiftKey?:boolean}} ev
 * @param {{editing:boolean, casting:boolean, foldOpen:boolean, onHorizon:boolean}} ctx
 * @returns {string} action id
 *
 * Precedence, highest first:
 *   0. editing        — THE CARET IS ABSOLUTE. Every key passes through, including
 *                       Mod+Z: while a caret exists, undo belongs to the words the
 *                       writer is typing, not to the app's edit stack. The app's
 *                       undo stack only answers once the line is committed.
 *   1. chord          — Mod-based commands (undo/redo) survive every non-editing state
 *   2. Escape         — peels one layer: cast → fold → release focus
 *   3. casting        — j/k/Enter own the ring; a step abandons the preview.
 *                       J/K inside an OPEN fold begins casting (that is the entry
 *                       point: casting is never summoned, it grows from the line)
 *   4. horizon        — when the track has focus it is a scrollbar
 *   5. traversal      — arrows step rows, n/p step wet rows, [ ] set ink floor,
 *                       a toggles the annunciator, r requests assistance on
 *                       the selected passage (never on one chosen for you)
 */
export function routeKey(ev, ctx) {
  const k = ev.key;
  const mod = !!(ev.metaKey || ev.ctrlKey);
  const shift = !!ev.shiftKey;
  const c = ctx || {};

  /* NOBODY ELSE'S FIELD, BUT THE APP'S OWN. Enter and Escape belong to the
     proposal editor while it is open — that is the one place the caret must not
     be hijacked — and every other key is typing, including Mod+Z (the writer's
     words, not the edit stack). Checked BEFORE the `editing` guard below,
     because the editor is inside the app and the browser's caret is its own. */
  if (c.editingProposal) {
    if (mod) return 'passthrough';
    if (k === 'Enter') return 'proposal.commit';
    if (k === 'Escape') return 'proposal.abandon';
    return 'passthrough';
  }

  if (c.editing) return 'passthrough';

  if (mod && (k === 'z' || k === 'Z')) return shift ? 'edits.redo' : 'edits.undo';
  if (mod) return 'passthrough';

  if (k === 'Escape') {
    if (c.casting) return 'cast.cancel';
    if (c.foldOpen) return 'fold.close';
    if (c.onHorizon) return 'focus.release';
    return 'fold.closeAll';
  }

  if (c.casting) {
    if (k === 'j' || k === 'J' || k === 'ArrowRight') return 'cast.next';
    if (k === 'k' || k === 'K' || k === 'ArrowLeft') return 'cast.prev';
    if (k === 'v') return 'rehearse.toggle';
    if (k === 'e') return 'proposal.edit';
    if (k === 'Enter') return 'cast.apply';
    if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'PageDown' || k === 'PageUp') return 'cast.abandon';
    return 'passthrough';
  }

  if (c.onHorizon) {
    if (k === 'ArrowDown') return 'hz.next';
    if (k === 'ArrowUp') return 'hz.prev';
    if (k === 'Home') return 'hz.first';
    if (k === 'End') return 'hz.last';
    if (k === 'Enter' || k === ' ') return 'hz.jump';
    return 'passthrough';
  }

  if (k === 'ArrowDown') return 'row.next';
  if (k === 'ArrowUp') return 'row.prev';
  if (k === 'Enter') return c.foldOpen ? 'fold.close' : 'fold.toggle';
  // J/K are inert on the page and alive inside an open fold: that is how casting
  // begins. A fold that is open is a line that is asking to be rewritten.
  if (k === 'j' || k === 'J') return c.foldOpen ? 'cast.begin.next' : 'passthrough';
  if (k === 'k' || k === 'K') return c.foldOpen ? 'cast.begin.prev' : 'passthrough';
  // `r` = request assistance on the passage the writer has selected. It is the
  // escape hatch from "no target is chosen for you": automatic targeting stays
  // refused, explicit assistance is honoured, warning retained.
  if (k === 'r') return c.foldOpen ? 'cast.request' : 'passthrough';
  if (k === 'v') return c.foldOpen ? 'rehearse.toggle' : 'passthrough';
  // Visit the other scene a finding cites — and come back. The graph is deferred;
  // navigation between cited passages is the cheap version of the same need.
  /* Leaving a visit is a property of the VISIT, not of the row it landed on —
     the landing place is by definition a place with nothing on it, so O must
     still route while a return is outstanding. (While a proposal is open, the
     casting block above has already claimed the key.) */
  if (k === 'o') return (c.foldOpen || c.roaming) ? 'roam.toggle' : 'passthrough';
  // The context filter: which critique is allowed to speak up, never which prose.
  if (k === 'f') return 'scope.cycle';
  if (k === 'n') return 'wet.next';
  if (k === 'p') return 'wet.prev';
  if (k === '[') return 'ink.down';
  if (k === ']') return 'ink.up';
  if (k === 'a') return 'announce.toggle';   // the annunciator is a place you can live
  // The ground is not a theme picker: it is the same instrument on two benches,
  // and comparing them is how the register was chosen. One key, reversible, and
  // it announces which bench you are on.
  if (k === 'g') return 'ground.toggle';
  if (k === 'Home') return 'row.first';
  if (k === 'End') return 'row.last';
  return 'passthrough';
}

/** Action → the DOM layer's switch. Exported so the test can assert coverage. */
export const HANDLED = [
  'passthrough', 'edits.undo', 'edits.redo', 'cast.cancel', 'cast.next', 'cast.prev',
  'cast.apply', 'cast.abandon', 'cast.begin.next', 'cast.begin.prev', 'cast.request', 'fold.close', 'fold.toggle', 'fold.closeAll', 'focus.release',
  'row.next', 'row.prev', 'row.first', 'row.last', 'wet.next', 'wet.prev',
  'ink.up', 'ink.down', 'hz.next', 'hz.prev', 'hz.first', 'hz.last', 'hz.jump',
  'announce.toggle', 'ground.toggle', 'rehearse.toggle',
  'proposal.edit', 'proposal.commit', 'proposal.abandon', 'roam.toggle', 'scope.cycle',
];

/** Ink floor → human label, for the annunciator only. */
export const FLOOR_LABEL = ['everything', 'minor and above', 'major and above', 'critical only'];
export const stepFloor = (cur, delta) => Math.max(0, Math.min(3, cur + delta));
