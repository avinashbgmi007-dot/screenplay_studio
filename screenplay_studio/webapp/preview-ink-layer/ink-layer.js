/**
 * ink-layer.js — Architecture I: The Ink Layer.
 * The DOM layer. Everything structural is in ink-layer.css; everything
 * computable is in core.js (unit-tested, no DOM). This file is deliberately
 * thin: it renders, it listens, it executes what core.js returns.
 *
 * Rules this file obeys:
 *   • ONE keyboard listener owns the whole document (window keydown → routeKey).
 *   • The manuscript scroller is the page. Nothing else scrolls.
 *   • The Horizon is absolutely positioned and takes no flow space.
 *   • Nothing is summoned. The fold grows out of the line; candidates are
 *     written into the line's own text node by string replacement.
 *   • The annunciator is the only text outside the manuscript.
 */
import * as C from './core.js';

/* ══════════════════════════════════════════════════════════════════════════
   1 · SOURCES — the only place the network exists
   Two adapters, one interface. The spatial code below never knows which is
   live; swapping adapters changes no layout, no key, no geometry.
   ══════════════════════════════════════════════════════════════════════════ */

const LIVE = {
  name: 'live',
  async _get(path, timeout = 4000) {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), timeout);
    try {
      const r = await fetch(path, { signal: ac.signal, headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText || path}`);
      return await r.json();
    } finally { clearTimeout(t); }
  },
  async _post(path, body, timeout = 60000) {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), timeout);
    try {
      const r = await fetch(path, {
        method: 'POST', signal: ac.signal,
        // The page's licence to write, echoed from the cookie the server issued
        // to this very document (see core.writeHeaders). Reads never need it.
        headers: C.writeHeaders(document.cookie), body: JSON.stringify(body || {}),
      });
      if (!r.ok) {
        // The body is the contract: the route's refusals carry a machine-
        // readable flag (`stale: true`) and its own sentence. Both ride the
        // error object, so callers decide from fields and never by matching a
        // message string.
        let body = null, msg = `${r.status}`;
        try { body = await r.json(); msg = body.error || body.message || msg; } catch { /* body was not json */ }
        const err = new Error(msg);
        err.status = r.status; err.body = body; err.stale = !!(body && body.stale === true);
        throw err;
      }
      return await r.json();
    } finally { clearTimeout(t); }
  },
  ping() { return this._get('/api/health', 900); },
  script(p) { return this._get(`/api/projects/${encodeURIComponent(p)}/script`); },
  findings(p, opts = {}) {
    const q = new URLSearchParams({ include_dismissed: '1' });
    if (opts.scene != null) q.set('scene', String(opts.scene));
    return this._get(`/api/projects/${encodeURIComponent(p)}/findings?${q}`);
  },
  summary(p) { return this._get(`/api/projects/${encodeURIComponent(p)}/findings/summary`); },
  rewrite(p, body) { return this._post(`/api/projects/${encodeURIComponent(p)}/rewrite`, body); },
  apply(p, body) { return this._post(`/api/projects/${encodeURIComponent(p)}/edits/apply`, body); },
  undo(p) { return this._post(`/api/projects/${encodeURIComponent(p)}/edits/undo`, {}); },
  dismiss(p, i) { return this._post(`/api/projects/${encodeURIComponent(p)}/findings/${i}/dismiss`, {}); },
};

/** Same test the renderer uses for "the quote was not located" — in one place. */
function isFlaggedFinding(f) {
  return (f.verification && typeof f.verification === 'object' && f.verification.status
    ? f.verification.status !== 'verified'
    : (f.verified === false));
}

/** The demo's refusal: an Error carrying the same body the route sends. */
function demoErr(status, message, stale = false) {
  const err = new Error(message);
  err.status = status;
  err.stale = stale;                                  // same shape the live POST throws
  err.body = stale ? { error: message, stale: true } : { error: message };
  return err;
}

/** Demo craft adapter. Same shapes; no server, no network. Honest about itself. */
const DEMO = {
  name: 'demo',
  _findings: [
    { index: 0, finding_id: 'd1', category: 'dialogue', severity: 'critical', status: 'open', scene_refs: [14],
      issue: 'Cary and Vera answer each other before the question lands.',
      why_it_matters: 'Neither character needs anything, so the scene has momentum without desire.',
      evidence: "You're late.", rule_id: 'DIAL-114', verified: true, verification: { status: 'verified', score: 0.94 },
      intent: null, dismissed: false },
    { index: 1, finding_id: 'd2', category: 'principles', severity: 'major', status: 'open', scene_refs: [14],
      issue: 'The note is set up in scene 6 and paid three times inside two pages.',
      why_it_matters: 'Two of the three payoffs are the same beat in different words: the writer is circling.',
      evidence: 'So you read the note.', rule_id: 'STRC-041', verified: true, verification: { status: 'verified', score: 0.88 },
      intent: null, dismissed: false },
    { index: 2, finding_id: 'd3', category: 'dialogue', severity: 'major', status: 'open', scene_refs: [14],
      issue: 'A reference to "the third take" has no antecedent on this page.',
      why_it_matters: 'Unverifiable claim: the quote could not be matched to the text, so treat it as unproven.',
      evidence: 'the third take', rule_id: null, verified: false, verification: { status: 'unverified', score: 0.41 },
      intent: null, dismissed: false },
    { index: 3, finding_id: 'd4', category: 'pacing', severity: 'minor', status: 'open', scene_refs: [14],
      issue: 'Action density rising while action share falls; slowest decile in the act.',
      why_it_matters: 'Mechanical measure of pace, not an opinion about the writing.',
      evidence: 'The ON AIR sign is dark', check_id: 'pacing_drag', rule_id: null, verified: true,
      verification: { status: 'verified', score: 1 }, intent: null, dismissed: false },
    /* A finding that cites TWO scenes with its quote in one of them: the shape
       the roam is built for, and the reason "where else does this matter?" does
       not need a graph to be useful. Its severity is spelled `high` on purpose —
       the desk's word for it, aliased in core.severityAlias. */
    { index: 5, finding_id: 'd6', category: 'principles', severity: 'high', status: 'open', scene_refs: [14, 15],
      issue: 'The cut lands before the door has been closed on the page: the corridor answers a beat the booth never lands.',
      why_it_matters: 'The quote is in scene 14; the scene it argues with is scene 15.',
      evidence: 'A long beat. Somewhere below, a door closes.', rule_id: 'STRC-052', verified: true,
      verification: { status: 'verified', score: 0.9 }, intent: null, dismissed: false },
    /* The corridor carries one of its own: without it the scene filter has one
       scene to filter, and the filter's whole claim — that a reading can be
       narrowed to the scene in front of the writer — cannot be exercised. Its
       severity is spelled `medium` on purpose: the desk's word for the middle. */
    { index: 6, finding_id: 'd7', category: 'dialogue', severity: 'medium', status: 'open', scene_refs: [15],
      issue: 'The refusal is the scene\'s last word and it is carrying the whole beat alone.',
      why_it_matters: 'A line this load-bearing reads better when the silence answers it.',
      evidence: "I'm not doing this tonight.", rule_id: 'DIAL-131', verified: true,
      verification: { status: 'verified', score: 0.86 }, intent: null, dismissed: false },
    { index: 4, finding_id: 'd5', category: 'character', severity: 'minor', status: 'addressed', scene_refs: [15],
      issue: 'Vera concedes the frame Cary sets without ever naming what she wants.',
      why_it_matters: 'Already fixed on the page.',
      evidence: 'Twice.', rule_id: 'CHAR-207', verified: true, verification: { status: 'verified', score: 0.91 },
      intent: 'done', dismissed: false },
  ],
  _script: {
    title: 'The Late Hour', author: 'Demo', source_format: 'fountain', parse_confidence: 'high',
    scenes: [
      { scene_number: 14, heading_raw: 'INT. RADIO STATION - BOOTH - NIGHT', int_ext: 'INT',
        location: 'RADIO STATION - BOOTH', time_of_day: 'NIGHT', page_start: 22.1, page_end: 23.4,
        characters_present: ['CARY', 'VERA'], elements: [
          { type: 'action', text: 'Dust turns in the light above a mixing desk that has not been touched in days.', line_start: 411 },
          { type: 'character', text: 'CARY', line_start: 413 },
          { type: 'dialogue', text: "You're late.", line_start: 414 },
          { type: 'character', text: 'VERA', line_start: 416 },
          { type: 'dialogue', text: "It wasn't.", line_start: 417 },
          { type: 'action', text: 'VERA crosses to the console. Her hand stops short of the fader.', line_start: 419 },
          { type: 'character', text: 'CARY', line_start: 421 },
          { type: 'dialogue', text: 'So you read the note.', line_start: 422 },
          { type: 'character', text: 'VERA', line_start: 424 },
          { type: 'dialogue', text: 'Twice.', line_start: 425 },
          { type: 'action', text: 'The ON AIR sign is dark, and has been dark for a while.', line_start: 427 },
          { type: 'general', text: 'A long beat. Somewhere below, a door closes.', line_start: 428 },
          { type: 'character', text: 'VERA', line_start: 430 },
          { type: 'dialogue', text: 'Say the thing you came here to say.', line_start: 431 },
          { type: 'transition', text: 'CUT TO:', line_start: 433 },
        ] },
      { scene_number: 15, heading_raw: null, int_ext: 'INT', location: 'CORRIDOR', time_of_day: 'CONTINUOUS',
        page_start: 23.4, page_end: 23.9, characters_present: ['CARY'], elements: [
          { type: 'action', text: 'Cary stands in the corridor with the door closed behind him.', line_start: 435 },
          { type: 'character', text: 'CARY', line_start: 437 },
          { type: 'dialogue', text: "I'm not doing this tonight.", line_start: 438 },
          { type: 'action', text: 'He does not move.', line_start: 440 },
        ] },
    ],
    properties: { scene_count: 2, estimated_page_count: 96 },
    warnings: [],
  },
  async ping() { return { ok: true, model: 'demo craft model' }; },
  async script() { return this._script; },
  async findings() { return { findings: this._findings.map((f) => ({ ...f })) }; },
  async summary() {
    const t = C.inkTotals(this._findings);
    const total = t.open + t.addressed;
    /* by_severity is QUOTED FROM THE DESK — the desk's own words, counted as it
       spells them, exactly as /findings/summary reports them. Re-deriving it here
       would hide the very mismatch canonSev exists to absorb (the desk says
       `high`, a finding says `critical`, the page has one mark for both). */
    const bySeverity = DEMO._findings.reduce((a, f) => {
      const k = String(f.severity || 'none');
      a[k] = (a[k] || 0) + 1;
      return a;
    }, {});
    return { dawn_pct: Math.round((t.addressed / Math.max(1, total)) * 100), totals: t,
             open_count: t.open, done_count: t.addressed, dismissed_count: t.dismissed,
             by_status: { addressed: t.addressed, still_present: t.open, unknown: 0 },
             by_severity: bySeverity, by_scene: null };
  },
  /* ── THE DEMO MIRRORS THE ROUTE, REFUSALS INCLUDED ────────────────────────
     `rewrite` answers the flat frame list the real route answers; `apply` runs
     the SAME verbatim check the hardened route runs, so the offline build is
     never a softer world than the product: a proposal whose `old` no longer
     stands in the scene is refused with the same 400 body and nothing is
     written. The `#drift` seam simulates the one situation that guard exists
     for — the writer typing into the line while the desk is still thinking —
     so the refusal is demonstrable, and checkable, without a second pair of
     hands. It changes nothing else in the adapter. */
  async rewrite(_p, body) {
    const line = body && body.line_start != null ? Number(body.line_start) : null;
    const table = {
      414: { note: 'voice — the apology precedes the accusation; the line announces its own subtext.',
             frames: [
               { old: "You're late.", new: "You're late. The stairs gave you away." },
               { old: "You're late.", new: 'I heard you on the stairs twenty minutes ago.' },
               { old: "You're late.", new: 'The door was open.' },
             ] },
      /* An ACTION line, so the structural branch of Rehearsal is exercisable:
         two takes whose only real difference is size — one of them deletes
         eleven characters from the beat. A timed audition would hide that; the
         stack prints it. */
      427: { note: 'pace — the sign is the scene\'s clock; the take that keeps the repetition is the slower one.',
             frames: [
               { old: 'The ON AIR sign is dark, and has been dark for a while.', new: 'The ON AIR sign is dark.' },
               { old: 'The ON AIR sign is dark, and has been dark for a while.', new: 'The ON AIR sign has been dark all night.' },
             ] },
      422: { note: 'setup/payoff — the note pays before it is set.', frames: [
               { old: 'So you read the note.', new: 'So you read it, then.' },
               { old: 'So you read the note.', new: 'You read it. Once is a mistake.' },
             ] },
    };
    const row = table[line] || null;
    return {
      scene_number: (body && body.scene_number) ?? 14,
      note: row ? row.note : '',
      replacements: row ? row.frames.map((f) => ({ ...f })) : [],
      scene_text: null,
    };
  },
  _has(old) {
    for (const sc of DEMO._script.scenes) for (const el of sc.elements) if (el.text === old) return true;
    return false;
  },
  _replace(old, next) {
    for (const sc of DEMO._script.scenes) for (const el of sc.elements) {
      if (el.text === old) { el.text = next; return true; }
    }
    return false;
  },
  async apply(_p, body) {
    const reps = body && body.replacements;
    if (!Array.isArray(reps) || !reps.length) throw demoErr(400, 'replacements list is required.');
    for (const r of reps) {
      if (!r || typeof r.old !== 'string' || typeof r.new !== 'string') {
        throw demoErr(400, "replacements require string fields 'old' and 'new'");
      }
    }
    for (const r of reps) {
      if (!DEMO._has(r.old)) throw demoErr(400, 'Stale proposal: the text was modified manually.', true);
    }
    for (const r of reps) DEMO._replace(r.old, r.new);
    /* The fix landed on the passage a finding pointed at, so that finding is no
       longer open — the same conclusion a real studio draws when it re-runs its
       passes over the written scene. Only findings whose located quote sits
       inside the frame are closed: an unverified finding is never retired by an
       edit that did not address it. */
    for (const f of DEMO._findings) {
      if (f.dismissed || f.status === 'addressed' || !f.evidence) continue;
      if (isFlaggedFinding(f)) continue;
      if (reps.some((r) => r.old.includes(f.evidence))) f.status = 'addressed';
    }
    return { scene_number: (body && body.scene_number) ?? null, applied: reps.length, scene_text_after: null };
  },
  async undo() { return { ok: true }; },
  /* A decision is a state change on the desk, not a local gesture: the demo
     records it so the next /findings read is the truth, exactly as the route's
     own `dismiss` writes the finding's intent server-side. */
  async dismiss(_p, index) {
    const f = DEMO._findings.find((x) => x.index === Number(index));
    if (!f) throw demoErr(404, `no finding at index ${index}`);
    f.dismissed = true;
    f.intent = 'kept_by_writer';
    return { ok: true, finding_id: f.finding_id, dismissed: true };
  },
};

/* ══════════════════════════════════════════════════════════════════════════
   2 · STATE
   ══════════════════════════════════════════════════════════════════════════ */

const S = {
  source: DEMO,
  project: 'The Late Hour',
  el: {},                      // cached nodes
  rows: [],                    // one entry per screenplay element
  scenes: [],                  // { number, heading, rowIndex, band }
  findings: [],
  findingsByRow: new Map(),    // rowIndex → finding[]
  summary: null,
  channels: new Map(),
  floor: 0,                    // ink threshold 0..3
  focus: -1,                   // row index under the reading caret
  casting: null,               // see §7
  rehearsal: null,             // { index, timer, mode } while the strip is reading
  editingProposal: null,       // { index, el } while the writer is typing a proposal
  roam: null,                  // { rowIndex, scene, lineStart } — where to come back to
  scope: { kind: 'all', value: null },   // which critique speaks up (never which prose)
  beat: null,                  // overridable beat, for tests; null = the constant
  applied: [],                 // local log for demo undo
  resolved: new Map(),         // rowIndex → 'evidence' | 'choice'; how a line went dry
  fixedOn: new Map(),          // finding_id → rowIndex: where a landed fix put a finding
  hz: { bands: [], focus: -1, domain: 0, trackH: 0, dragging: false },
  announceVisible: false,
  reduced: false,
};

/* one keyboard listener, one affordance per action */
const KEYMAP_ACTIONS = new Set(C.HANDLED);
const preventDefaultFor = (a) => a !== 'passthrough';

/* ══════════════════════════════════════════════════════════════════════════
   3 · ANNOUNCER — the load-bearing channel
   ══════════════════════════════════════════════════════════════════════════ */

function announce(text) {
  const el = S.el.annunciator;
  if (!el || !text) return;
  el.textContent = text;
  if (S.announceVisible) console.debug('[ink]', text);
}

function toggleAnnunciator() {
  S.announceVisible = !S.announceVisible;
  S.el.annunciator.dataset.show = String(S.announceVisible);
  announce(S.announceVisible ? 'Annunciator visible. Press A to hide.' : '');
}

/* ══════════════════════════════════════════════════════════════════════════
   4 · RENDER — the surface
   Row text is written as ONE text node so casting can replace it byte-exactly.
   ══════════════════════════════════════════════════════════════════════════ */

function flatten(script) {
  const rows = [];
  const scenes = [];
  for (const sc of script.scenes || []) {
    const scene = { number: sc.scene_number, heading: sc.heading_raw, elements: [], rowIndex: rows.length, band: null };
    // The scene heading is a row of the manuscript, not chrome.
    if (sc.heading_raw) {
      rows.push(mkRow(sc, { type: 'scene_heading', text: sc.heading_raw, line_start: null }, scene));
      scene.elements.push(rows.length - 1);
    }
    for (const el of sc.elements || []) {
      rows.push(mkRow(sc, el, scene));
      scene.elements.push(rows.length - 1);
    }
    scenes.push(scene);
  }
  return { rows, scenes };
}

function mkRow(scene, el, sceneRef) {
  return {
    scene, sceneRef, type: el.type, baseText: C.stripLead(el.text),
    text: C.indentText(el.type, el.text),
    lineStart: el.line_start ?? null,
    wet: false, worst: 'none', flagged: 0, finds: [], addressed: false,
    el: null, group: null, fold: null, foldBuilt: false,
  };
}

function render() {
  const frag = document.createDocumentFragment();
  let currentScene = null;
  S.rows.forEach((row, i) => {
    if (row.sceneRef !== currentScene) {
      currentScene = row.sceneRef;
      const section = document.createElement('section');
      section.className = 'scene';
      section.dataset.scene = String(row.scene.scene_number);
      section.setAttribute('aria-label', `Scene ${row.scene.scene_number}${row.scene.heading ? ': ' + row.scene.heading : ''}`);
      row.sceneRef.sectionEl = section;
      frag.appendChild(section);
    }
    const group = document.createElement('div');
    group.className = 'rowgroup';
    group.dataset.index = String(i);
    group.dataset.type = row.type;
    group.dataset.fold = 'closed';
    group.dataset.ink = 'dry';
    group.style.setProperty('--indent', C.indentOf(row.type) + 'ch');
    group.tabIndex = -1;                       // the reading caret can land anywhere

    const line = document.createElement('div');
    line.className = 'row';
    line.dataset.type = row.type;
    line.textContent = row.text;               // ONE text node. Byte-exact casts depend on it.
    line.setAttribute('aria-hidden', 'false');

    const fold = document.createElement('div');
    fold.className = 'fold';
    const pad = document.createElement('div');
    pad.className = 'fold-pad';
    fold.appendChild(pad);

    group.append(line, fold);
    row.sceneRef.sectionEl.appendChild(group);
    row.el = line; row.group = group; row.fold = pad;
  });
  S.el.manuscript.appendChild(frag);
  S.el.manuscript.setAttribute('aria-busy', 'false');
}

/* ══════════════════════════════════════════════════════════════════════════
   5 · INK — decoration from findings + summary
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Re-read the desk's findings state. The shape adapter, not a filter: the live
 * desk sends `evidence_quote` where the demo sends `evidence`, and
 * /findings/summary has two vocabularies. Reading only one of them made the
 * drift check silently blind — a reconciliation that can never disagree is not
 * a check. Called at boot, after an apply, and after a decision.
 */
async function loadFindings() {
  try {
    attachFindings(C.normalizeFindings(await S.source.findings(S.project, {})));
    return true;
  } catch (e) {
    announce(`Could not read findings. ${e.message}`);
    return false;
  }
}

function attachFindings(findings) {
  S.findings = findings;
  S.findingsByRow = new Map();
  // finding_id → report index. /rewrite grounds on the INDEX (`finding_index`)
  // while the page holds ids; without this map the request would be ungrounded
  // and the fold would show a critique it did not use.
  S.findingIndex = new Map();
  for (const f of findings) {
    if (f.finding_id != null && f.index != null && !S.findingIndex.has(f.finding_id)) {
      S.findingIndex.set(f.finding_id, f.index);
    }
  }
  const push = (i, f) => {
    const arr = S.findingsByRow.get(i) || [];
    if (!arr.includes(f)) arr.push(f);
    S.findingsByRow.set(i, arr);
  };
  S.parked = [];
  for (const f of findings) {
    const refs = f.scene_refs?.length ? f.scene_refs : (f.scene != null ? [f.scene] : []);
    const rowsOfScene = S.rows.filter((r) => refs.includes(r.scene.scene_number));
    if (!rowsOfScene.length) continue;                       // script-level: no band claims it
    /* THE QUOTE CLAIMS THE LINE, not the line number: line_start is documented as
       an unstable parameter that drifts between edits, so placement is a fuzzy
       match (threshold 0.72) against the quote, with line_start used only to break
       a genuine tie — and the tie is then reported, never silently resolved.
       A quote that reaches nothing stays SCENE-anchored: shown, never dropped,
       over-claimed nowhere, and casting refuses with the real reason. */
    const anchor = C.anchorFinding(S.rows.filter((r) => refs.includes(r.scene.scene_number))
      .map((r) => ({ ...r, scene: r.scene.scene_number })), f);
    if (anchor.rowIndex >= 0 && !anchor.loose) {
      const global = S.rows.indexOf(rowsOfScene[anchor.rowIndex]);
      f.anchor = { ...anchor, rowIndex: global };
      push(global, f);
      continue;
    }
    /* THE QUOTE IS GONE. A written fix replaces the passage it was about, so an
       ADDRESSED finding's quote is often no longer in the script — and anchoring
       it to the scene's head then would re-mark a heading with a critique that
       has already been answered. Two honest answers, in order:
         · this session watched the fix land (fixedOn) → the row the fix was
           written on is where the finding belongs, and that is a fact the page
           holds, not a guess;
         · otherwise it is PARKED: the desk still counts it, the page does not
           invent a line for it. Nothing is dropped — an answered finding simply
           has nothing to say on the page, and the annunciator says so.
       An OPEN finding that cannot be located still lands scene-anchored, flagged,
       and casting refuses it with the real reason. */
    if (f.status === 'addressed' || f.dismissed) {
      const known = S.fixedOn.get(f.finding_id);
      if (known != null && S.rows[known]) {
        f.anchor = { rowIndex: known, score: anchor.score, exact: false, ambiguous: false, loose: true, placed: 'the line this fix was written on' };
        push(known, f);
      } else {
        f.anchor = { rowIndex: -1, score: anchor.score, exact: false, ambiguous: false, loose: true, placed: 'parked' };
        S.parked.push(f);
      }
      continue;
    }
    const global = S.rows.indexOf(rowsOfScene[0]);
    f.anchor = { rowIndex: global, score: anchor.score, exact: false, ambiguous: false, loose: true, placed: 'scene anchor' };
    push(global, f);
  }
  decorate();
}

function decorate() {
  S.channels = C.inkChannels(S.findings, { includeDismissed: false });
  const floor = S.floor;
  S.rows.forEach((row, i) => {
    const finds = S.findingsByRow.get(i) || [];
    const open = finds.filter((f) => f.status !== 'addressed' && !f.dismissed);
    const addressed = finds.filter((f) => f.status === 'addressed');
    row.finds = open.slice().sort((a, b) => C.sevRank(b.severity) - C.sevRank(a.severity));
    /* The word the DOM carries is CANONICAL. sevRank() was always alias-aware,
       so ordering never changed — but the attribute did: a finding the desk
       spells `high` used to land as data-worst="high", which no rule matches, so
       the line lost its severity border entirely. The desk's own spelling is
       still shown, and the collapse is stated there (see the signature line). */
    row.worst = row.finds.reduce((w, f) => (C.sevRank(f.severity) > C.sevRank(w) ? C.canonSev(f.severity) : w), 'none');
    row.flagged = row.finds.filter(C.isFlagged).length;
    row.addressed = addressed.length > 0 && row.finds.length === 0;
    row.wet = row.finds.length > 0;

    const g = row.group;
    if (!g) return;
    /* ONE PLACE DECIDES THE INK STATE, and one place decides WHY.
       dry is not one state: a line is dry by EVIDENCE when the desk closed the
       finding because the fix landed (row.addressed), and dry by CHOICE when the
       writer looked at a take, kept their own line, and the desk recorded the
       decision (S.resolved — written only after the dismiss is confirmed, so the
       page never claims a decision the studio does not hold). A row with open
       findings is wet; a row with nothing on it has no ink. Evidence outranks
       choice on a row where both happened, because it is the stronger claim. */
    const choice = S.resolved.get(i) === 'choice' && row.finds.length === 0;
    const evidence = S.resolved.get(i) === 'evidence' || row.addressed;
    if (row.wet) {
      g.dataset.ink = 'wet';
      delete g.dataset.dry;
    } else if (evidence || choice) {
      g.dataset.ink = 'dry';
      g.dataset.dry = evidence ? 'evidence' : 'choice';
    } else {
      g.dataset.ink = 'none';
      delete g.dataset.dry;
    }
    g.dataset.worst = row.worst;
    g.dataset.flagged = String(row.flagged > 0);
    /* Quiet ≠ hidden and ≠ faded prose. Two things can recede a CRITIQUE and
       neither of them is the manuscript: the ink threshold (severity) and the
       context filter (scene · category · still-open). Prose is never filtered —
       the filter is a reading of the critique, and the page keeps every line. */
    const quiet = C.quietRow({ worst: row.worst, finds: row.finds }, floor, S.scope,
                             { scene: row.scene.scene_number });
    g.dataset.quiet = String(quiet);
    row.quiet = quiet;
    if (row.wet) {
      g.setAttribute('role', 'button');
      g.setAttribute('aria-expanded', String(g.dataset.fold === 'open' || g.dataset.fold === 'pinned'));
      // Quiet to the eye, explicit to assistive tech: the count lives in the
      // accessible name and in the annunciator, never as a numeral on the sentence.
      g.setAttribute('aria-label', C.say.foldOpen({
        lineNo: row.lineStart ?? i + 1, count: row.finds.length, worst: row.worst,
        flagged: row.flagged, quiet,
      }));
    } else {
      g.removeAttribute('role');
      g.removeAttribute('aria-expanded');
      g.removeAttribute('aria-label');
      if (g.dataset.fold !== 'closed') closeFold(i, { settle: true });
    }
  });
  horizon.paint();
}

/** Reconcile with the server's own count; the server is authority (§core). */
async function refreshSummary() {
  try {
    S.summary = C.normalizeSummary(await S.source.summary(S.project));
  } catch (e) {
    announce('Could not read findings summary. ' + e.message);
    return;
  }
  const r = C.reconcileInk(S.channels, S.summary);
  if (r.drift) announce(`Counts updated. ${r.server.open ?? '?'} open.`);
  S.el.horizon.dataset.capability = S.summary.byScene ? 'by_scene' : 'by_scene_absent';
  horizon.paint();
}

/* ══════════════════════════════════════════════════════════════════════════
   6 · THE HORIZON
   Absolute, out of flow, 12px. True proportion: bands tile the whole document.
   ══════════════════════════════════════════════════════════════════════════ */

const horizon = {
  /** Measure the document once per geometry change, then delegate all math. */
  measure() {
    const trackH = S.el.horizon.clientHeight || window.innerHeight;
    const domain = Math.max(1, document.documentElement.scrollHeight);
    const boxes = S.scenes.filter((sc) => sc.sectionEl).map((sc) => {
      const el = sc.sectionEl;
      const rect = el.getBoundingClientRect();
      return { key: String(sc.number), top: rect.top + window.scrollY, height: Math.max(1, rect.height), page: sc.page };
    }).filter((b) => b.height > 0);
    S.hz.trackH = trackH;
    S.hz.domain = domain;
    S.hz.bands = C.sceneBands(boxes, domain, trackH, { minBandPx: 1 });
    S.hz.boxes = boxes;
  },

  paint() {
    const { bands, trackH } = S.hz;
    if (!bands.length) return;
    const bandsG = S.el.hzBands, inkG = S.el.hzInk;
    bandsG.textContent = '';
    inkG.textContent = '';
    for (const b of bands) {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('class', 'hz-band');
      rect.setAttribute('x', '0'); rect.setAttribute('width', '100%');
      rect.setAttribute('y', String(b.topPct) + '%');
      rect.setAttribute('height', String(Math.max(0.1, b.hPct)) + '%');
      rect.dataset.scene = b.key;
      bandsG.appendChild(rect);
      const ch = S.channels.get(Number(b.key));
      if (!ch || (!ch.open && !ch.addressed)) continue;
      const w = C.inkPx(ch.worst);
      const pip = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      pip.setAttribute('class', 'hz-ink');
      pip.setAttribute('x', String(12 - Math.max(2, w)));       // flush to the outer edge
      pip.setAttribute('width', String(Math.max(2, w)));
      pip.setAttribute('y', String(b.topPct + b.hPct / 2) + '%');
      pip.setAttribute('height', '2');
      pip.dataset.scene = b.key;
      pip.dataset.severity = ch.worst;
      pip.dataset.flagged = String(ch.flagged > 0);
      inkG.appendChild(pip);
    }
    this.paintWindow();
  },

  paintWindow() {
    const { domain, trackH } = S.hz;
    if (!trackH) return;
    const w = C.windowRect(window.scrollY, window.innerHeight, domain, trackH);
    const r = S.el.hzWindow;
    r.setAttribute('y', String((w.topPx / trackH) * 100) + '%');
    r.setAttribute('height', String(Math.max(0.5, (w.hPx / trackH) * 100)) + '%');
    const pct = Math.round(((window.scrollY + window.innerHeight) / Math.max(1, domain)) * 100);
    S.el.horizon.setAttribute('aria-valuenow', String(Math.max(0, Math.min(100, pct))));
    S.el.horizon.setAttribute('aria-valuetext', `${pct}% through the script${S.summary?.open != null ? `, ${S.summary.open} open findings` : ''}`);
  },

  scrubToClientY(clientY) {
    const rect = S.el.horizon.getBoundingClientRect();
    const y = clientY - rect.top;
    window.scrollTo({ top: C.scrubTo(y, window.innerHeight, S.hz.domain, S.hz.trackH), behavior: 'auto' });
  },

  /** hz.* actions: the track is a scrollbar when it has focus. */
  step(delta) {
    const n = S.hz.bands.length;
    if (!n) return;
    S.hz.focus = S.hz.focus < 0 ? (delta > 0 ? 0 : n - 1) : C.stepIndex(S.hz.focus, n, delta);
    const b = S.hz.bands[S.hz.focus];
    S.el.horizon.setAttribute('aria-valuenow', String(Math.round(b.topPct)));
    const ch = S.channels.get(Number(b.key)) || { worst: 'none', open: 0 };
    announce(C.say.radar({ page: b.page ?? b.key, worst: ch.worst, open: ch.open }));
  },

  jump() {
    if (S.hz.focus < 0) return;
    const b = S.hz.bands[S.hz.focus];
    const top = S.hz.boxes.find((x) => x.key === b.key)?.top ?? 0;
    window.scrollTo({ top: Math.max(0, top - 24), behavior: S.reduced ? 'auto' : 'smooth' });
    announce(`Scene ${b.key}.`);
  },
};

/* ══════════════════════════════════════════════════════════════════════════
   7 · FOLD — dwell, focus, push
   ══════════════════════════════════════════════════════════════════════════ */

let dwellTimer = 0;
let measureTimer = 0;

/**
 * The silhouette follows the page. A fold opening pushes everything below it
 * down, which changes scene positions in document coordinates, so the track is
 * re-measured — but only after the transition has settled and only once per
 * burst, because measure() reads layout and reading layout is the expensive drug.
 */
function scheduleMeasure() {
  if (S.hz.dragging) return;                  // never re-measure under a scrub
  clearTimeout(measureTimer);
  measureTimer = setTimeout(() => { horizon.measure(); horizon.paint(); }, C.FOLD_MS + 120);
}

function setFold(i, state) {
  const g = S.rows[i]?.group;
  if (!g) return;
  g.dataset.fold = state;
  if (g.getAttribute('role') === 'button') {
    g.setAttribute('aria-expanded', String(state === 'open' || state === 'pinned'));
  }
}

function buildFold(i) {
  const row = S.rows[i];
  if (!row || row.foldBuilt) return;
  row.foldBuilt = true;
  const ol = document.createElement('ol');
  ol.className = 'finds';
  const list = row.finds.slice(0, C.MAX_FINDS_PER_FOLD);
  for (const f of list) {
    const li = document.createElement('li');
    li.className = 'find';
    li.dataset.verified = String(!C.isFlagged(f));
    li.dataset.provenance = C.provenanceOf(f);
    // The ▪ blocks are a severity channel, and they key off a CANONICAL word:
    // detent.css has no rule for `high`, so the desk's own spelling would leave
    // the heaviest finding in the fold marked with nothing at all.
    li.dataset.severity = C.canonSev(f.severity);
    const issue = document.createElement('p');
    issue.className = 'find-issue';
    issue.textContent = f.issue || f.why_it_matters || '(no issue text)';
    const ev = document.createElement('p');
    ev.className = 'find-evidence';
    ev.textContent = f.evidence || '';
    if (C.isFlagged(f)) ev.textContent += '  (unverified — could not be matched to the text)';
    const sig = document.createElement('span');
    sig.className = 'find-sig';
    const parts = [];
    // The desk's own word, and the page's word for it when they differ. A
    // collapsed vocabulary that is never stated is a vocabulary that lies.
    if (f.severity) parts.push(f.severity === C.canonSev(f.severity)
      ? f.severity : `${f.severity} → ${C.canonSev(f.severity)}`);
    if (f.rule_id) parts.push(f.rule_id);
    else if (f.check_id) parts.push(`measured: ${f.check_id}`);
    if (f.verification?.score != null) parts.push(`match ${Math.round(f.verification.score * 100)}%`);
    sig.textContent = parts.join(' · ');
    li.append(issue, ev, sig);
    ol.appendChild(li);
  }
  const more = row.finds.length - list.length;
  if (more > 0) {
    const p = document.createElement('p');
    p.className = 'find-overflow';
    p.textContent = `${more} more finding${more === 1 ? '' : 's'} on this line — press Enter to keep the fold open while you work.`;
    ol.appendChild(p);
  }
  row.fold.appendChild(ol);
}

/** openFold — the fold grows out of the line and PUSHES the page. */
function openFold(i, { pinned = false, reason = 'focus' } = {}) {
  const row = S.rows[i];
  if (!row || !row.wet) return;
  buildFold(i);
  setFold(i, pinned ? 'pinned' : 'open');
  announce(C.say.foldOpen({ lineNo: row.lineStart ?? i + 1, count: row.finds.length, worst: row.worst, flagged: row.flagged }));
  requestAnimationFrame(() => {
    const r = row.group.getBoundingClientRect();
    const over = C.overflowCorrection({
      rowTop: r.top, rowBottom: row.el.getBoundingClientRect().bottom, foldBottom: r.bottom,
      viewTop: 0, viewBottom: window.innerHeight,
    });
    if (over) window.scrollBy({ top: over, behavior: S.reduced ? 'auto' : 'smooth' });
    scheduleMeasure();
  });
}

/** closeFold — collapse, and hold the focused LINE perfectly still if the fold
 *  sat above it (that is the only case where a line can jump). */
function closeFold(i, { settle = false, speak = false } = {}) {
  const row = S.rows[i];
  if (!row || !row.group || row.group.dataset.fold === 'closed') return;
  const groupRect = row.group.getBoundingClientRect();
  const focusRow = S.rows[S.focus];
  const focusTop = focusRow ? focusRow.group.getBoundingClientRect().top : null;
  const h = groupRect.height;
  setFold(i, 'closing');
  // Announce on INTENT, not on transitionend: a keystroke must be acknowledged
  // in the same frame, and with reduced motion there is no transition to wait for.
  if (speak) announce(C.say.foldClosed());
  if (focusTop != null && S.focus !== i) {
    const fix = C.scrollCorrection({ closingHeightPx: h, closingTopPx: groupRect.top, focusTopPx: focusTop });
    if (fix) window.scrollBy({ top: fix, behavior: 'auto' });
  }
  const done = () => { setFold(i, 'closed'); row.group.dataset.fold = 'closed'; scheduleMeasure(); };
  if (settle || S.reduced) { done(); return; }
  let settled = false;
  const once = () => { if (settled) return; settled = true; done(); };
  row.group.addEventListener('transitionend', once, { once: true });
  setTimeout(once, C.FOLD_MS + 80);
}

function closeAllFolds() {
  S.rows.forEach((r, i) => { if (r.group && r.group.dataset.fold !== 'closed') closeFold(i, { settle: true }); });
  announce('');
}

/* ── focus + the two walks ─────────────────────────────────────────────── */

function focusRow(i, { speak = true } = {}) {
  const row = S.rows[i];
  if (!row) return;
  S.rows.forEach((r) => r.group?.removeAttribute('data-focus'));
  S.focus = i;
  row.group.setAttribute('data-focus', 'true');
  row.group.focus({ preventScroll: true });
  // Reveal only if the line is outside the comfortable band; never re-center
  // a line the writer is already reading.
  const r = row.group.getBoundingClientRect();
  const top = window.innerHeight * 0.18, bottom = window.innerHeight * 0.82;
  if (r.top < top || r.bottom > bottom) {
    const delta = r.top < top ? r.top - top : Math.min(r.bottom - bottom, r.top - window.innerHeight * 0.5);
    window.scrollBy({ top: delta, behavior: 'auto' });
  }
  if (speak && row.wet) {
    announce(C.say.foldOpen({ lineNo: row.lineStart ?? i + 1, count: row.finds.length, worst: row.worst, flagged: row.flagged }));
  } else if (speak) {
    announce(row.baseText.slice(0, 80));
  }
}

function stepRow(delta) {
  const next = C.stepIndex(S.focus, S.rows.length, delta);
  if (next === S.focus) return;
  if (S.casting) castAbandon();
  closeFoldsExcept(next);
  focusRow(next);
}

/** A walk leaves exactly one fold behind it: the row you are on. */
function closeFoldsExcept(keep) {
  S.rows.forEach((r, i) => {
    if (i !== keep && r.group && ['open', 'pinned'].includes(r.group.dataset.fold)) closeFold(i);
  });
}

function stepWet(delta) {
  /* THE WALK FOLLOWS THE FILTER. `n` means "the next critique that is speaking
     up", so a row the filter (or the ink floor) has receded is not a stop for it —
     landing there would read as the filter having failed. Both receded rows and
     the receded prose remain on the page at full contrast, and the arrow keys
     still step through every row. */
  const rows = S.rows.map((r) => ({ wet: r.wet && !r.quiet }));
  const from = S.focus < 0 ? (delta > 0 ? -1 : S.rows.length) : S.focus;
  const next = C.nearestWet(rows, from, delta);
  const filtered = S.scope.kind !== 'all' || S.floor > 0;
  if (next < 0) { announce(C.say.wetNone({ dir: delta, filtered })); return; }
  if (S.casting) castAbandon();
  closeFoldsExcept(next);
  focusRow(next);
}

/* ══════════════════════════════════════════════════════════════════════════
   8 · TAKE-CASTING — candidates written into the live line
   ══════════════════════════════════════════════════════════════════════════ */

/** Which substring of the line is the target of the rewrite. Precedence:
 *  the take's own old_text → the verified evidence quote → the whole line. */
function frameFor(row, take) {
  const cands = [take?.oldText, row.finds.find((f) => f.evidence && !C.isFlagged(f))?.evidence, row.text];
  for (const t of cands) {
    if (!t) continue;
    const f = C.frameOf(row.text, t);
    if (f) return f;
  }
  return null;
}

/**
 * @param {number} i row index
 * @param {{explicit?: boolean}} opts
 *   explicit = the writer selected this passage and asked for a revision
 *   (key `r`). Automatic targeting is refused whenever the evidence is
 *   unverified, but an explicit request is honoured WITH the warning retained:
 *   refusing assistance outright would block legitimate work on uncertain
 *   diagnoses. The ledger then records what the rewrite was based on.
 */
async function startCast(i, { explicit = false } = {}) {
  const row = S.rows[i];
  if (!row || !row.wet) return;
  const finding = row.finds[0];
  clearVoid(i);          // a fresh ask is a fresh question; the last refusal is not this one
  S.casting = { index: i, busy: true, ring: -1, take: null, frame: null, candidates: [],
                note: '', explicit: !!explicit, visited: new Set(), voidText: null };
  S.castingFinding = finding || null;      // remembered for fixedOn when the fix lands
  row.el.dataset.cast = 'busy';
  announce('Asking for candidates…');
  let payload;
  try {
    payload = await S.source.rewrite(S.project, {
      scene_number: row.scene.scene_number,
      line_start: row.lineStart,
      finding_index: (S.findingIndex && finding && finding.finding_id != null)
        ? (S.findingIndex.get(finding.finding_id) ?? null) : null,
      finding_id: finding ? finding.finding_id : null,
      selected_text: explicit ? row.text : null,
      allow_unverified: !!explicit,
    });
  } catch (e) {
    S.casting = null; row.el.dataset.cast = 'idle';
    announce(`Rewrite failed. ${e.message}`);
    return;
  }
  const norm = C.normalizeRewrite(payload);
  if (norm.unknown) {
    /* A reply in a shape this page does not know is reported, not interpreted.
       Guessing the structure of a response is how a valid replacement ends up
       attached to the wrong text. */
    S.casting = null; row.el.dataset.cast = 'idle';
    announce(C.say.unknownShape({ reason: norm.reason }));
    return;
  }
  const take = C.takeForRow(norm.takes, { lineStart: row.lineStart, text: row.text })
            || C.takeForRow(norm.takes, { lineStart: null, text: row.baseText });
  if (!take || !take.candidates.length) {
    S.casting = null; row.el.dataset.cast = 'idle';
    const flagged = row.finds.find(C.isFlagged);
    if (flagged && !row.baseText.includes(flagged.evidence || '\u0000')) {
      announce('Unverified finding: its quote could not be matched to the text, so there is nothing here to cast. It is still shown, not dropped.');
    } else {
      announce(take?.skipped?.length ? C.say.castSkipped({ skipped: take.skipped }) : 'No candidates came back for this line.');
    }
    return;
  }
  // The basis of this proposal is recorded and shown, not implied.
  const uncertain = C.isFlagged(finding);
  const attached = uncertain && finding.evidence && row.baseText.includes(finding.evidence);
  const frame = explicit
    ? (uncertain ? C.frameOf(row.text, row.text) : frameFor(row, take))   // explicit: the writer's own passage
    : frameFor(row, take);
  if (!frame) {
    S.casting = null; row.el.dataset.cast = 'idle';
    announce('Candidates do not line up with the text on the page. Nothing cast.');
    return;
  }
  if (uncertain && !explicit) {
    S.casting = null; row.el.dataset.cast = 'idle';
    announce('Unverified finding: no target is chosen for you. Select the passage and press R to request a revision anyway — the warning will be kept.');
    return;
  }
  const scope = C.scopeOf(norm, row);
  const overlapping = norm.takes.length > 1 && C.overlappingTargets(row.text, norm.takes);
  const ambiguous = !!frame.ambiguous;
  S.casting = { index: i, busy: false, ring: -1, take, frame, candidates: take.candidates,
                note: norm.note || '', basis: uncertain ? 'writer-selected passage' : 'located quote',
                sceneNumber: row.scene.scene_number, scope,
                ambiguous, ambSaid: ambiguous,
                overlap: overlapping ? norm.takes.length : 0,
                warning: uncertain ? (attached ? 'the quote was not located at threshold 0.72'
                                               : 'the quote could not be located at all') : null };
  row.el.dataset.cast = 'active';
  row.el.dataset.delta = 'false';       // a proposal holds no change until it is committed
  renderCastStrip(i);
  // The line does not move during an audition, and saying so is the point: the
  // manuscript holds the writer's text until a take is committed.
  /* ONE SENTENCE, SPOKEN ONCE. The warning is part of the opening rather than a
     second announcement after it: the annunciator is last-write-wins, and a
     warning that a follow-up sentence can erase is not a warning. */
  announce(C.say.castOpening({ count: take.candidates.length, flagged: uncertain })
    + (ambiguous ? ' ' + C.say.ambiguousTake({ score: 1, lineNo: row.lineStart }) : ''));
}

function renderCastStrip(i) {
  const row = S.rows[i];
  const c = S.casting;
  if (!row || !c) return;
  let strip = row.fold.querySelector('.casting');
  if (!strip) {
    strip = document.createElement('div');
    strip.className = 'casting';
    row.fold.appendChild(strip);
  }
  strip.textContent = '';
  /* WHICH STATE THE STRIP IS IN, said once, in one attribute: auditioning a
     proposal, or writing into it. The keys line and the marks both read it, so
     the two states cannot look the same — a writer who cannot see that they are
     typing is a writer who will commit a sentence they did not mean. */
  strip.dataset.editing = String(!!(S.editingProposal && S.editingProposal.index === i));
  // PROGRESSIVE DISCLOSURE, enforced by order: where this take sits, then the
  // takes themselves, then the scope the desk answered with, then the reason it
  // gives, then the keys. The reasoning is never in front of the proposal.
  renderCastLedger(strip, c);
  renderTakeList(strip, c, i);
  const scope = document.createElement('p');
  scope.className = 'cast-scope';
  scope.textContent = scopeLine(c);
  strip.appendChild(scope);
  if (c.take?.skipped?.length) {
    const sk = document.createElement('p');
    sk.className = 'cast-skipped';
    sk.textContent = C.say.castSkipped({ skipped: c.take.skipped });
    strip.appendChild(sk);
  }
  const meta = [];
  if (c.note) meta.push(c.note);
  if (c.basis) meta.push(`basis: ${c.basis}`);
  if (c.warning) meta.push(c.warning);
  if (c.ambiguous) meta.push('this quote matches more than one line');
  const cand = c.ring >= 0 ? c.candidates[c.ring] : null;
  if (cand?.ruleId) meta.push(cand.ruleId);
  if (cand?.checkId) meta.push(`measured: ${cand.checkId}`);
  if (cand?.confidence != null) meta.push(`confidence ${Math.round(cand.confidence * 100)}%`);
  if (meta.length) {
    const m = document.createElement('p');
    m.className = 'cast-meta';
    m.textContent = meta.join(' · ');
    strip.appendChild(m);
  }
  if (c.overlap) {
    // Independently applied, never presented as one atomic rewrite.
    const ov = document.createElement('p');
    ov.className = 'cast-overlap';
    ov.textContent = C.say.overlapping({ count: c.overlap });
    strip.appendChild(ov);
  }
  if (c.voidText) {
    // The refusal stays visible until it is answered. It is not a toast: a
    // message that disappears is a message the writer has to remember.
    const v = document.createElement('p');
    v.className = 'cast-void';
    v.setAttribute('role', 'status');
    const b = document.createElement('b');
    b.textContent = 'Not written';
    v.append(b, document.createTextNode(' ' + c.voidText));
    strip.appendChild(v);
  }
  // Keys last, in normal flow — the strip is a stack, not a footer.
  const key = document.createElement('p');
  key.className = 'cast-keys';
  const span = (cls, text) => {
    const el2 = document.createElement('span');
    el2.className = cls;
    el2.textContent = text;
    return el2;
  };
  const editing = strip.dataset.editing === 'true';
  const parts = editing
    /* While the writer is typing, the keys are the EDITOR'S keys. Saying
       "ENTER = commit take" under an open editor is a strip that contradicts
       itself at the moment the writer is most likely to press Enter by reflex. */
    ? [span('cast-key', 'EDITING'),
       span('cast-meta', 'ENTER = commit the wording · ESC = abandon the edit')]
    : [
        span('cast-key', c.ring >= 0 ? `TAKE ${pad2(c.ring + 1)}` : 'YOUR LINE'),
        span('cast-meta', c.ring >= 0 ? 'ENTER = commit take · ESC = keep the original'
                                      : 'J = audition a take · ESC = keep the original'),
        span('cast-key', 'E = edit wording'),
      ];
  // Reading in time is offered for the material it suits; on a structural row the
  // strip says why it is not (see startRehearsal) rather than offering a dead key.
  if (!editing && c.ring >= 0 && C.rehearsalMode(row?.type) === 'temporal') parts.push(span('cast-key', 'V = read in time'));
  for (const el2 of parts) key.appendChild(el2);
  strip.appendChild(key);
}

const pad2 = (n) => String(n).padStart(2, '0');

const fmtDelta = (d) => `+${pad2(d.added)} −${pad2(d.removed)}`;

/** The scope the desk answered with — never implied as a single-line guarantee. */
function scopeLine(c) {
  const sc = c.scope || { kind: 'passage', passages: 1, frames: c.candidates.length, onThisLine: 1 };
  if (sc.kind === 'scene') {
    return `scope: scene ${c.sceneNumber ?? '—'} — ${sc.passages} passage${sc.passages === 1 ? '' : 's'} proposed, ${sc.frames} edit${sc.frames === 1 ? '' : 's'}`;
  }
  if (sc.kind === 'line') return `scope: this line — ${sc.passages} passages, each applied and re-checked on its own`;
  return 'scope: this passage';
}

/**
 * THE TAKES, AS TEXT. Every take is listed with what it would read as and what
 * it adds or removes; the one under the ledger is the one the keys are on. The
 * manuscript is not touched by any of this — auditioning is a reading, and the
 * line changes only when a take is committed (§3.2 of the blueprint, and the
 * contract's "trap frame": J/K must never mutate the document).
 */
function renderTakeList(strip, c, rowIndex) {
  const ol = document.createElement('ol');
  ol.className = 'cast-takes';
  const row = S.rows[rowIndex];
  const push = (n, text, delta, current, editable, takeIdx) => {
    const li = document.createElement('li');
    li.className = 'take';
    li.dataset.current = String(current);
    li.dataset.original = String(takeIdx < 0);
    const b = document.createElement('b');
    b.className = 'tk-n';
    b.textContent = n;
    const t = document.createElement('span');
    t.className = 'tk-text';
    t.dataset.current = String(current);
    if (current && editable) {
      /* EDITING THE PROPOSED WORDING, inside the frame it was cut from: the
         prefix and suffix are shown, read-only, and only the target slice is
         editable. Whatever is typed lands in the hole the original passage left
         — so a typed proposal can never accumulate a previous proposal. */
      const pre = document.createElement('span');
      pre.className = 'tk-fix';
      // The manuscript's indentation is the ROW's business; inside the strip it
      // would only push the proposal out of its own column.
      pre.textContent = C.stripLead(c.frame.prefix);
      const box = document.createElement('span');
      box.className = 'tk-edit';
      box.setAttribute('contenteditable', 'true');
      box.setAttribute('role', 'textbox');
      box.setAttribute('aria-label', 'proposed wording for this passage — Enter commits, Escape abandons');
      box.dataset.editing = 'true';
      box.textContent = c.candidates[c.ring]?.text ?? '';
      const suf = document.createElement('span');
      suf.className = 'tk-fix';
      suf.textContent = c.frame.suffix;
      t.append(pre, box, suf);
      S.editingProposal = { index: rowIndex, el: box };
      queueMicrotask(() => { try { box.focus(); } catch { /* jsdom has no layout focus */ } });
    } else if (current) {
      // THE CURRENT TAKE, WITH ITS CHANGES SHOWN. Deletions are struck through
      // and insertions are underlined, in the words themselves: change
      // comprehension is the point, and neither mark depends on colour.
      const composed = C.stripLead(text);
      for (const seg of C.diffWords(C.stripLead(c.frame.original), composed)) {
        if (seg.op === '=') {
          t.appendChild(document.createTextNode(seg.text + ' '));
        } else {
          const el2 = document.createElement(seg.op === 'del' ? 'del' : 'ins');
          el2.textContent = seg.text;
          t.append(el2, document.createTextNode(' '));
        }
      }
    } else {
      t.textContent = C.stripLead(text);
    }
    t.title = text;
    const em = document.createElement('em');
    em.className = 'tk-delta';
    em.textContent = delta;
    li.append(b, t, em);
    ol.appendChild(li);
  };
  // The ring's zero point is the writer's own line, so it is the first row of the
  // reading — Original first, then the proposals.
  push('ORIG', C.stripLead(c.frame.original), fmtDelta(C.deltaOf(c.frame.original, c.frame.original)),
       c.ring < 0, false, -1);
  c.candidates.forEach((k, idx) => {
    const composed = C.composeLine(c.frame, k.text);
    push(pad2(idx + 1), composed, fmtDelta(C.deltaOf(c.frame.original, composed)),
         idx === c.ring, S.editingProposal?.index === rowIndex && idx === c.ring, idx);
  });
  strip.appendChild(ol);
}

/**
 * The ledger: where this take sits among the others, as tabular text, with the
 * change it makes to the line. A writer who prints the page still gets every
 * fact, and no per-line count is ever shown — this is the take's own position.
 */
function renderCastLedger(strip, c) {
  const cand = c.ring >= 0 ? c.candidates[c.ring] : null;
  const composed = cand ? C.composeLine(c.frame, cand.text) : c.frame.original;
  const p = document.createElement('p');
  p.className = 'cast-ledger';
  const pos = document.createElement('span');
  pos.className = 'ldg-pos';
  pos.textContent = cand ? `TAKE ${pad2(c.ring + 1)} / ${pad2(c.candidates.length)}`
                         : `ORIGINAL / ${pad2(c.candidates.length)}`;
  const marks = document.createElement('span');
  marks.className = 'ldg-marks';
  marks.textContent = c.candidates.map((_, k) => (k === c.ring ? '\u25CF' : '\u25CB')).join(' ');
  marks.setAttribute('aria-hidden', 'true');
  const delta = document.createElement('span');
  delta.className = 'ldg-delta';
  delta.textContent = fmtDelta(C.deltaOf(c.frame.original, composed));
  delta.title = 'characters this take adds and removes against the line as it stands';
  p.append(pos, marks, delta);
  strip.appendChild(p);
}

/** Show the desk's refusal in the strip, and keep it there until answered. */
function showVoid(i, text) {
  const c = S.casting;
  if (!c || c.index !== i) return;
  c.voidText = text;
  renderCastStrip(i);
}

/** The void belongs to one casting session; a new ask or a kept line ends it. */
function clearVoid(i) {
  const row = S.rows[i];
  if (!row || !row.fold) return;
  const el = row.fold.querySelector('.cast-void');
  if (el) el.remove();
}

/* ── REHEARSAL: one branch of the same strip ─────────────────────────────────
   The mechanic is chosen by the ROW, never by a setting: a voice line is read in
   time, a structural line is read by eye. Both read the same takes the same cast
   produced, and neither moves the manuscript. */
function startRehearsal() {
  const c = S.casting;
  if (!c || c.busy) return;
  stopRehearsal();                     // one reading at a time, always
  const row = S.rows[c.index];
  const mode = C.rehearsalMode(row.type);
  const count = c.candidates.length;
  if (mode === 'spatial') {
    // Structure is compared by eye. The beat is not offered here, and saying why
    // is better than a key that quietly does nothing — and nothing moves: the
    // list already carries every take's size, so the writer's place is kept.
    announce(C.say.rehearseSteady({ count }));
    return;
  }
  /* A READING OPENS ON THE ORIGINAL — the writer's own line — and then walks the
     proposals. Original/Proposed is the comparison; a reading that starts at
     take 1 asks the writer to remember what they wrote. */
  const toOriginal = -1 - c.ring;
  if (toOriginal) castStep(toOriginal);
  const beat = Number(S.beat) > 0 ? Number(S.beat) : C.REHEARSAL_BEAT_MS;
  S.rehearsal = { index: c.index, mode, timer: null };
  announce(C.say.rehearseStart({ mode, count }));
  const tick = () => {
    const live = S.casting;
    if (!S.rehearsal || !live || live.index !== c.index) return;
    const next = C.rehearsalStep({ ring: live.ring, count: live.candidates.length });
    if (next < 0) { stopRehearsal(); announce(C.say.rehearseEnd({ count })); return; }
    castStep(next - live.ring);        // the same step the keys use; no second path
    const cand = live.candidates[live.ring];
    announce(C.say.rehearseStep({ index: live.ring, count: live.candidates.length, text: cand ? cand.text : '' }));
    S.rehearsal.timer = setTimeout(tick, beat);
  };
  S.rehearsal.timer = setTimeout(tick, beat);
}

function stopRehearsal(reason) {
  if (!S.rehearsal) return;
  if (S.rehearsal.timer) clearTimeout(S.rehearsal.timer);
  S.rehearsal = null;
  if (reason) announce(reason);
}

/** Any key that is not part of the reading ends it: attention is never trapped. */
function rehearsalInterrupt() {
  if (S.rehearsal) stopRehearsal(C.say.rehearseStop());
}

/**
 * castStep — the audition. It moves the CURSOR and nothing else: the manuscript
 * is not mutated, so the line under the writer's eye is always the line in the
 * file. The composed text is what the strip shows and what a commit will write.
 */
function castStep(delta) {
  const c = S.casting;
  if (!c) return;
  if (c.busy) { announce('Still waiting for candidates.'); return; }
  const next = C.stepRing(c.ring, c.candidates.length, delta, { wrap: false });
  if (next === c.ring) { announce(delta > 0 ? 'Last take.' : 'Your own line.'); return; }
  c.ring = next;
  renderCastStrip(c.index);
  const cand = c.ring >= 0 ? c.candidates[c.ring] : null;
  /* The step's own sentence, plus the ambiguity clause if this casting has not
     been told yet: stepping past the opening must not take the warning with it. */
  const said = cand
    ? C.say.castReady({ index: c.ring, count: c.candidates.length, text: cand.text })
    : 'Your own line, exactly as written. Nothing is proposed.';
  const warn = c.ambiguous && !c.ambSaid ? ' ' + C.say.ambiguousTake({ score: 1, lineNo: S.rows[c.index].lineStart }) : '';
  if (warn) c.ambSaid = true;
  announce(said + warn);
}

async function castApply() {
  const c = S.casting;
  if (!c) return;
  if (S.editingProposal) {
    announce('You are editing the wording — Enter commits the text, Escape abandons the edit.');
    return;
  }
  if (c.ring < 0) {
    // The original line is not a proposal, so there is nothing to write — and
    // nothing to apologise for. Say where the line already is.
    announce('That is your own line. Press Escape to keep it, or J to audition a take.');
    return;
  }
  if (!C.canApply({ active: true, index: c.ring, candidates: c.candidates, busy: c.busy })) {
    announce(c.busy ? 'Still waiting for candidates.' : 'Pick a take first with J or K.');
    return;
  }
  const row = S.rows[c.index];
  const cand = c.candidates[c.ring];
  stopRehearsal();
  c.busy = true;
  row.el.dataset.cast = 'busy';
  const composed = C.composeLine(c.frame, cand.text);
  const body = C.applyPayload({
    sceneNumber: row.scene ? row.scene.scene_number : null,
    take: c.take, frame: c.frame, candidate: cand,
  });
  try {
    const res = await S.source.apply(S.project, body);
    /* THE COMMIT — the only moment the manuscript changes, and only to text the
       desk accepted. Anything the writer auditioned and did not commit was never
       in the document, so there is nothing to undo, and nothing to take back. */
    const node = row.el.firstChild;
    if (node && node.nodeType === 3) node.nodeValue = composed;
    else row.el.textContent = composed;
    row.text = composed;
    row.baseText = C.stripLead(composed);
    row.el.dataset.delta = String(composed !== c.frame.original);
    row.el.dataset.cast = 'applied';
    S.applied.push({ index: c.index, frame: c.frame, text: cand.text, composed });
    S.resolved.set(c.index, c.basis === 'located quote' ? 'evidence' : 'choice');
    const castFor = S.castingFinding;
    if (castFor && castFor.finding_id != null) S.fixedOn.set(castFor.finding_id, c.index);
    closeFold(c.index);
    /* THE FRAME IS SPENT. The strip was a diff against a line that no longer
       holds that text, so it goes with the commit — a picture of the past that
       looked live is worse than no picture. The record that a change happened
       lives on the row (data-cast="applied", data-delta="true") and in undo. */
    const spent = row.fold.querySelector('.casting');
    if (spent) spent.remove();
    scheduleMeasure();
    const applied = { index: c.index, frame: c.frame };
    S.casting = null;
    /* The apply response already carries the recomputed findings state
       (findings_status). Read it when it is there; ask the desk again only when
       it is not — the page should never have to guess how a written edit
       changed the critique, and should not make two extra round trips to find
       out. The summary is still taken fresh, because the meter is the desk's. */
    const patch = C.statusPatch(res);
    if (patch) patchFindingsStatus(patch);
    else await loadFindings();
    decorate();
    horizon.paint();
    await refreshSummary();
    announce(C.say.castApplied({ count: res?.applied ?? 1, lineNo: row.lineStart ?? applied.index + 1 })
      + ' ' + C.say.applyReport(res || {}));
  } catch (e) {
    const verdict = C.classifyApplyError(e);
    if (verdict.kind === 'stale') { refuseStale(c.index, verdict); return; }
    c.busy = false;
    row.el.dataset.cast = 'active';
    showVoid(c.index, C.say.castFailed({ message: verdict.message }));
    announce(C.say.castFailed({ message: verdict.message }));
  }
}

/** Take the desk's own account of what a written edit did to the findings. */
function patchFindingsStatus(patch) {
  for (const f of S.findings) {
    if (f.index == null) continue;
    const status = patch.byIndex.get(Number(f.index));
    if (status) f.status = status;
  }
}

/**
 * THE REFUSAL, ANSWERED. The server would not write, so the page must not
 * pretend it did. With the trap frame nothing was ever on the page, so the whole
 * answer is state: the proposal is marked stale, the frame is re-cut against the
 * text as it now stands, and the refusal stays printed under the line.
 */
function refuseStale(i, verdict) {
  const c = S.casting;
  if (!c) return;
  const row = S.rows[i];
  row.el.dataset.cast = 'stale';
  c.busy = false;
  c.ring = -1;                                       // the reading returns to the writer's own line
  const live = C.frameOf(row.text, c.frame.target);
  let extra = '';
  if (live) c.frame = live;                          // re-cut against the text as it now stands
  else extra = ' The passage this take was cut from is no longer on the line at all, so there is nothing here to re-cut — ask again with J.';
  showVoid(i, C.say.castStale({ message: verdict.message }) + extra);
  announce(C.say.castStale({ message: verdict.message }) + extra);
}

function castAbandon() {
  const c = S.casting;
  if (!c) return;
  stopRehearsal();
  S.editingProposal = null;
  const row = S.rows[c.index];
  const strip = row.fold.querySelector('.casting');
  if (strip) strip.remove();
  row.el.dataset.cast = 'idle';
  row.el.dataset.delta = 'false';
  S.casting = null;
}

function castCancel() {
  const c = S.casting;
  if (!c) return;
  const index = c.index;
  const row = S.rows[index];
  const finding = row ? row.finds[0] : null;
  castAbandon();
  keepByChoice(index, finding);
}

/**
 * RESOLVED BY CHOICE — and recorded as such, on the desk.
 *
 * Keeping a line is a decision, not a non-event: it closes the finding. The
 * route for that already exists (POST /findings/:index/dismiss), so the page
 * makes no private claim about state the studio does not hold. Until the desk
 * answers, nothing is marked: if the call fails, the row stays OPEN on the page
 * because it is still open on the server, and the failure is said out loud.
 */
async function keepByChoice(index, finding) {
  const row = S.rows[index];
  const ask = finding && finding.finding_id != null && S.findingIndex
    ? S.findingIndex.get(finding.finding_id) : null;
  if (ask == null) {
    announce('Kept your line. No edit was written. That finding carries no index, so there was nothing to close on the desk.');
    return;
  }
  announce('Kept your line — no edit written. Telling the desk the decision is yours…');
  try {
    await S.source.dismiss(S.project, ask);
    S.resolved.set(index, 'choice');
    await loadFindings();
    decorate();
    horizon.paint();
    announce('Kept your line. Nothing was written; the finding is closed by your decision, not by the desk.');
  } catch (e) {
    if (row) delete row.group.dataset.dry;
    announce(`Kept your line, but the desk could not be told: ${e.message} Nothing was written, and this finding is still open.`);
  }
}

/* ── DIRECT EDITING OF THE PROVISIONAL TEXT ──────────────────────────────────
   The writer must not be an accept/reject operator for generated text. E opens
   the current take for typing, inside the frame it was cut from; Enter commits
   the typed wording as this take, Escape abandons the edit and leaves the take
   as it was. Nothing here reaches the manuscript — committing the take is still
   the only write. */
function beginProposalEdit() {
  const c = S.casting;
  if (!c || c.busy) return;
  if (c.ring < 0) {
    announce('Nothing to edit yet — press J to bring a take up, then E to edit its wording.');
    return;
  }
  stopRehearsal();
  S.editingProposal = { index: c.index, el: null };
  S.rows[c.index].el.dataset.cast = 'editing';
  renderCastStrip(c.index);
  announce(C.say.proposalEdit());
}

function commitProposalEdit() {
  const ed = S.editingProposal;
  const c = S.casting;
  if (!ed || !c) return;
  const typed = ed.el ? ed.el.textContent : '';
  S.editingProposal = null;
  S.rows[c.index].el.dataset.cast = 'active';
  const verdict = C.editProposal(c.frame, typed);
  if (!verdict.ok) {
    renderCastStrip(c.index);
    announce(verdict.reason === 'empty' ? C.say.proposalEmpty() : C.say.proposalUnchanged());
    return;
  }
  const cand = c.candidates[c.ring];
  c.candidates[c.ring] = { ...cand, text: verdict.text, edited: true };
  renderCastStrip(c.index);
  announce(C.say.proposalEdited({ text: verdict.text }));
}

function abandonProposalEdit() {
  const ed = S.editingProposal;
  const c = S.casting;
  S.editingProposal = null;
  if (!ed || !c) return;
  S.rows[c.index].el.dataset.cast = 'active';
  renderCastStrip(c.index);
  announce('Edit abandoned — this take stands as the desk wrote it.');
}

/* ── VISIT A CITED PASSAGE, AND COME BACK ────────────────────────────────────
   The cheap version of "where else does this matter?": navigation between cited
   passages, with a return. No graph, and no edge that the payload does not
   assert — the landing place is the row whose text matches the same quote, and
   the scene's own head when there is no such row. */
function roamToggle() {
  const i = S.focus;
  const row = S.rows[i];
  /* THE WAY BACK IS CHECKED FIRST. The place a visit lands is by definition a
     place with nothing on it — the other scene's head, or a passage the finding
     only points at — so asking the landing row to justify the return would make
     the return unreachable. Leaving is a property of the visit, not of the row. */
  if (S.roam && S.roam.scene != null) {
    const back = S.roam;
    S.roam = null;
    closeFoldsExcept(back.rowIndex);
    focusRow(back.rowIndex);
    announce(C.say.roamReturn({ scene: back.scene, lineNo: back.lineStart }));
    return;
  }
  if (!row || !row.finds.length) { announce(C.say.roamNone()); return; }
  const f = row.finds[0];
  const other = C.relatedScene(f, row.scene.scene_number);
  if (other == null) { announce(C.say.roamNone()); return; }
  let target = f.evidence
    ? S.rows.findIndex((r) => r.scene.scene_number === other && r.baseText.includes(f.evidence))
    : -1;
  if (target < 0) target = S.scenes.find((sc) => sc.number === other)?.rowIndex ?? -1;
  if (target < 0) { announce(C.say.roamNone()); return; }
  S.roam = { rowIndex: i, scene: row.scene.scene_number, lineStart: row.lineStart };
  closeFoldsExcept(target);
  focusRow(target);
  announce(C.say.roamVisit({ scene: other, lineNo: S.rows[target].lineStart }));
}

/* ── THE CONTEXT FILTER ──────────────────────────────────────────────────────
   Which critique is allowed to speak up, never which prose is allowed to be
   read: receding is the same state the ink threshold already uses, so nothing
   here can dim the manuscript. */
function cycleScope() {
  const row = S.rows[S.focus] || null;
  const category = row && row.finds.length ? row.finds[0].category : null;
  const scene = row ? row.scene.scene_number : null;
  S.scope = C.nextScope(S.scope, { scene, category });
  decorate();
  const n = S.rows.filter((r) => r.wet && !r.quiet).length;
  announce(C.say.scopeNow({ kind: S.scope.kind, value: S.scope.value, n }));
}

/* ══════════════════════════════════════════════════════════════════════════
   9 · THE SINGLE KEYBOARD OWNER
   ══════════════════════════════════════════════════════════════════════════ */

function isEditing() {
  const a = document.activeElement;
  if (!a) return false;
  return a.isContentEditable || a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.tagName === 'SELECT';
}

function foldOpenAt(i) {
  const g = S.rows[i]?.group;
  return !!g && ['open', 'pinned'].includes(g.dataset.fold);
}

async function onKeydown(e) {
  const i = S.focus;
  const action = C.routeKey(e, {
    editing: isEditing(),
    editingProposal: !!S.editingProposal,
    casting: !!S.casting,
    roaming: !!S.roam,
    foldOpen: i >= 0 && foldOpenAt(i),
    onHorizon: document.activeElement === S.el.horizon,
  });
  if (!KEYMAP_ACTIONS.has(action) || action === 'passthrough') return;
  // A reading that survives an unrelated keystroke is a reading that keeps
  // moving the writer's line while they are doing something else.
  if (S.rehearsal && action !== 'rehearse.toggle') rehearsalInterrupt();
  if (preventDefaultFor(action)) e.preventDefault();

  switch (action) {
    /* focus / traversal */
    case 'row.next': stepRow(1); break;
    case 'row.prev': stepRow(-1); break;
    case 'row.first': stepRow(-S.rows.length); break;
    case 'row.last': stepRow(S.rows.length); break;
    case 'wet.next': stepWet(1); break;
    case 'wet.prev': stepWet(-1); break;

    /* the fold */
    case 'fold.toggle':
      if (i < 0) { stepWet(1); break; }
      openFold(i, { pinned: true, reason: 'key' });
      break;
    case 'fold.close':
      if (i >= 0) closeFold(i, { speak: true });
      break;
    case 'fold.closeAll': closeAllFolds(); break;

    /* casting */
    case 'cast.begin.next': {
      if (S.casting) { castStep(1); break; }
      if (i < 0) break;
      await startCast(i);
      if (S.casting && !S.casting.busy) {
        // The step's sentence is about to overwrite the opening, so an ambiguity
        // warning that rode with the opening has to ride with the step instead.
        S.casting.ambSaid = false;
        castStep(1);                                   // the first J casts take 1
      }
      break;
    }
    case 'cast.request': {
      if (S.casting) { castStep(1); break; }
      if (i < 0) break;
      await startCast(i, { explicit: true });
      break;
    }
    case 'cast.begin.prev': {
      if (S.casting) { castStep(-1); break; }
      if (i < 0) break;
      await startCast(i);
      break;
    }
    case 'cast.next': castStep(1); break;
    case 'cast.prev': castStep(-1); break;
    case 'cast.apply': castApply(); break;
    case 'cast.cancel': castCancel(); break;
    case 'cast.abandon': {
      const dir = (e.key === 'ArrowDown' || e.key === 'PageDown') ? 1 : -1;
      castAbandon();
      stepRow(dir);
      break;
    }

    /* ink threshold */
    case 'ink.up': case 'ink.down': {
      const next = C.stepFloor(S.floor, action === 'ink.up' ? 1 : -1);
      if (next === S.floor) break;
      S.floor = next;
      decorate();
      announce(C.say.inkThreshold({ floor: S.floor, label: C.FLOOR_LABEL[S.floor] }));
      break;
    }

    /* horizon */
    case 'hz.next': horizon.step(1); break;
    case 'hz.prev': horizon.step(-1); break;
    case 'hz.first': S.hz.focus = -1; horizon.step(1); break;
    case 'hz.last': S.hz.focus = S.hz.bands.length; horizon.step(-1); break;
    case 'hz.jump': horizon.jump(); break;
    case 'focus.release': S.el.manuscript.focus({ preventScroll: true }); announce('Left the horizon.'); break;

    /* the edit stack (only reachable outside a caret) */
    case 'edits.undo': doUndo(); break;
    case 'edits.redo': announce('Redo: not wired in this prototype. Undo is available.'); break;

    /* the annunciator itself */
    case 'announce.toggle': toggleAnnunciator(); break;
    case 'proposal.edit': beginProposalEdit(); break;
    case 'proposal.commit': commitProposalEdit(); break;
    case 'proposal.abandon': abandonProposalEdit(); break;
    case 'roam.toggle': roamToggle(); break;
    case 'scope.cycle': cycleScope(); break;
    case 'rehearse.toggle': {
      if (!S.casting) { announce('Nothing to rehearse yet: open a line and cast a take first.'); break; }
      if (S.rehearsal || S.casting.stack) { stopRehearsal(); announce('Rehearsal off.'); break; }
      startRehearsal();
      break;
    }
    case 'ground.toggle': {
      /* TWO GROUNDS, ONE DESIGN. The lift is a comparison carry, not a mode: it
         changes six token values (detent.css §D0) and nothing else, so a writer
         who never presses G is on the bench the register was designed on. */
      const lifted = document.documentElement.dataset.ground !== 'lifted';
      document.documentElement.dataset.ground = lifted ? 'lifted' : 'instrument';
      announce(C.say.ground({ ground: lifted ? 'lifted' : 'instrument', lifted }));
      break;
    }
    default: break;
  }
}

async function doUndo() {
  try {
    await S.source.undo(S.project);
    const last = S.applied.pop();
    if (last) {
      const row = S.rows[last.index];
      const node = row.el.firstChild;
      if (node && node.nodeType === 3) node.nodeValue = last.frame.original;
      row.el.dataset.cast = 'idle';
      // an undone edit re-wets the line: the diagnosis answers back
      const f = S.findingsByRow.get(last.index)?.[0];
      if (f) { f.status = 'open'; decorate(); }
    }
    await refreshSummary();
    announce('Undone. The finding is open again.');
  } catch (e) {
    announce(`Undo failed. ${e.message}`);
  }
}

/* ── pointer: dwell, pin, scrub ────────────────────────────────────────── */

function onPointerOver(e) {
  const g = e.target.closest?.('.rowgroup');
  if (!g) return;
  const i = Number(g.dataset.index);
  const row = S.rows[i];
  clearTimeout(dwellTimer);
  if (!row?.wet || row.quiet || foldOpenAt(i) || S.casting?.index === i) return;
  dwellTimer = setTimeout(() => {
    if (S.focus !== i) focusRow(i, { speak: false });
    openFold(i, { pinned: false, reason: 'dwell' });
  }, C.DWELL_MS);
}

function onPointerOut(e) {
  const g = e.target.closest?.('.rowgroup');
  if (!g) return;
  const to = e.relatedTarget?.closest?.('.rowgroup');
  if (to === g) return;                      // line → its own fold is not leaving
  clearTimeout(dwellTimer);
  const i = Number(g.dataset.index);
  // An unpinned fold closes when attention leaves it. A pinned fold never does.
  if (S.rows[i]?.group?.dataset.fold === 'open') closeFold(i);
}

function onRowClick(e) {
  const g = e.target.closest?.('.rowgroup');
  if (!g) return;
  const i = Number(g.dataset.index);
  const row = S.rows[i];
  if (!row) return;
  if (isEditing()) return;
  focusRow(i, { speak: false });
  if (!row.wet) return;
  if (foldOpenAt(i)) closeFold(i);
  else openFold(i, { pinned: true, reason: 'click' });
}

/* ══════════════════════════════════════════════════════════════════════════
   10 · BOOT
   ══════════════════════════════════════════════════════════════════════════ */

async function boot() {
  S.reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  S.el.surface = document.getElementById('surface');
  S.el.manuscript = document.getElementById('manuscript');
  S.el.horizon = document.getElementById('horizon');
  S.el.hzTrack = document.getElementById('hzTrack');
  S.el.hzBands = document.getElementById('hzBands');
  S.el.hzInk = document.getElementById('hzInk');
  S.el.hzWindow = document.getElementById('hzWindow');
  S.el.annunciator = document.getElementById('annunciator');
  if (!S.el.manuscript) return;

  const params = new URLSearchParams(location.search);
  S.project = params.get('project') || S.project;

  /* live if a local studio is answering, demo otherwise — never a third state.
     A single-file build opened from disk has no studio to ask and cannot reach
     one: the probe is skipped rather than thrown, so the deliverable's console
     carries no error it can do nothing about. The announcement is the same one
     either way, because the state is the same one. */
  const offline = location.protocol === 'file:';
  try {
    if (offline) throw new Error('offline build');
    await LIVE.ping(); S.source = LIVE;
  } catch { S.source = DEMO; }
  announce(S.source === LIVE ? `Connected to your studio. Project ${S.project}.` : 'No local studio answering. Running the demo craft model.');

  let script;
  try { script = await S.source.script(S.project); }
  catch (e) {
    S.el.manuscript.textContent = `Could not read the manuscript. ${e.message}`;
    return;
  }
  const flat = flatten(script);
  S.rows = flat.rows; S.scenes = flat.scenes;
  S.scenes.forEach((sc) => { const r = S.rows[sc.rowIndex]; sc.page = r?.lineStart ?? null; });
  render();

  /* normalizeFindings is the shape adapter, not a filter: the live desk sends
     `evidence_quote` where the demo sends `evidence`, and /findings/summary has
     two vocabularies. Reading only one of them made the drift check silently
     blind — a reconciliation that can never disagree is not a check. */
  await loadFindings();

  horizon.measure();
  horizon.paint();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { horizon.measure(); horizon.paint(); });
  await refreshSummary();

  window.addEventListener('keydown', onKeydown);   // the only keyboard owner
  window.addEventListener('scroll', () => requestAnimationFrame(() => horizon.paintWindow()), { passive: true });
  window.addEventListener('resize', () => { horizon.measure(); horizon.paint(); }, { passive: true });
  document.addEventListener('pointerover', onPointerOver);
  document.addEventListener('pointerout', onPointerOut);
  document.addEventListener('click', onRowClick);
  // A reading is interrupted by ATTENTION moving, and the pointer is attention.
  // Without this, clicking somewhere during a reading left the line stepping
  // under the writer's hand — the one thing the beat must never do.
  document.addEventListener('pointerdown', rehearsalInterrupt, { capture: true });
  document.addEventListener('scroll', () => clearTimeout(dwellTimer), { passive: true, capture: true });

  // the horizon: drag anywhere on the 12px track to scrub; it is a scrollbar
  S.el.horizon.addEventListener('pointerdown', (e) => {
    S.el.horizon.setPointerCapture(e.pointerId);
    S.hz.dragging = true;
    horizon.scrubToClientY(e.clientY);
  });
  S.el.horizon.addEventListener('pointermove', (e) => { if (S.hz.dragging) horizon.scrubToClientY(e.clientY); });
  S.el.horizon.addEventListener('pointerup', (e) => {
    S.hz.dragging = false;
    try { S.el.horizon.releasePointerCapture(e.pointerId); } catch { /* already released */ }
  });
  S.el.horizon.addEventListener('focus', () => announce('Horizon. Arrow keys to step scenes, Enter to jump.'));

  const wet = S.rows.filter((r) => r.wet).length;
  announce(`${wet} wet lines. Press N to walk to the first.`);
}

/* Public surface. `ready` is what a host page (or a test) awaits; nothing else
   about the layer is meant to be reached into from outside. */
const ready = document.readyState === 'loading'
  ? new Promise((resolve) => document.addEventListener('DOMContentLoaded', () => boot().then(resolve), { once: true }))
  : boot();
window.InkLayer = {
  ready,
  state: S,
  /* The adapter in use, exposed for the test suite only: the refusal path cannot
     be exercised through the UI without the ability to make the studio refuse.
     Nothing in the app reads this back, and no test-only branch exists in the
     adapter itself — the suite stubs this object, the demo owns no seams. */
  source: S.source,
  redraw: () => { horizon.measure(); horizon.paint(); decorate(); },
};
