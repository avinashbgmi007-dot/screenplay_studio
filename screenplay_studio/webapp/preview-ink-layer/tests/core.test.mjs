/**
 * tests/core.test.mjs — node --test
 * Proves the three spatial mechanisms' math before any DOM exists.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DWELL_MS, sevRank, inkPx, MAX_FINDS_PER_FOLD,
  stepIndex, nearestWet, rowForLine, clampIndex,
  sceneBands, windowRect, scrubTo,
  inkChannels, inkTotals, isFlagged, provenanceOf, normalizeSummary, reconcileInk,
  foldNext, scrollCorrection, overflowCorrection,
  frameOf, composeLine, restoreLine, stepRing,
  normalizeRewrite, takeForRow, applyPayload, canApply, classifyApplyError, normalizeFindings,
  rehearsalMode, rehearsalStep,
  routeKey, HANDLED, FLOOR_LABEL, stepFloor, say,
  INDENT, indentOf, stripLead, indentText,
  STUDIO_TOKEN_COOKIE, tokenFromCookie, writeHeaders,
  SEV_ALIAS, canonSev, sevAtLeast,
  ANCHOR_THRESHOLD, fuzzyScore, anchorFinding,
  diffWords, deltaOf, editProposal, scopeOf, targetSpans, overlappingTargets,
  SCOPE_KINDS, nextScope, inScope, quietRow, relatedScene, statusPatch,
} from '../core.js';

/* ── §1 traversal ─────────────────────────────────────────────────────── */

test('stepIndex clamps at both ends — the ends are real places, not wrap points', () => {
  assert.equal(stepIndex(0, 10, -1), 0);
  assert.equal(stepIndex(9, 10, 1), 9);
  assert.equal(stepIndex(4, 10, 1), 5);
  assert.equal(stepIndex(0, 0, 1), -1);
});

test('nearestWet steps OFF the current row before searching', () => {
  const rows = [{ wet: 0 }, { wet: 1 }, { wet: 1 }, { wet: 0 }, { wet: 1 }].map(r => ({ wet: !!r.wet }));
  assert.equal(nearestWet(rows, 1, 1), 2, 'from a wet row, n advances rather than re-fires');
  assert.equal(nearestWet(rows, 2, 1), 4);
  assert.equal(nearestWet(rows, 4, 1), -1, 'extreme returns -1 so the caller can announce it');
  assert.equal(nearestWet(rows, 2, -1), 1);
  assert.equal(nearestWet([], 0, 1), -1);
});

test('rowForLine matches exactly, else falls back to the row before it', () => {
  const rows = [{ lineStart: 4 }, { lineStart: 9 }, { lineStart: null }, { lineStart: 31 }];
  assert.equal(rowForLine(rows, 9), 1);
  assert.equal(rowForLine(rows, 20), 1);
  assert.equal(rowForLine(rows, 1), -1);
  assert.equal(rowForLine(rows, null), -1);
});

/* ── §1 horizon geometry ──────────────────────────────────────────────── */

test('sceneBands tiles the track exactly — no gaps, no overlaps, monotonic tops', () => {
  const boxes = [
    { key: 's1', top: 0, height: 400, page: 1 },
    { key: 's2', top: 400, height: 120, page: 5 },
    { key: 's3', top: 520, height: 1, page: 6 },
    { key: 's4', top: 521, height: 2479, page: 6 },
  ];
  const domain = 3000, track = 900;
  const bands = sceneBands(boxes, domain, track);
  assert.equal(bands[0].topPx, 0);
  assert.equal(bands.at(-1).topPx + bands.at(-1).hPx, track, 'last band closes the track');
  for (let i = 1; i < bands.length; i++) {
    assert.equal(bands[i].topPx, bands[i - 1].topPx + bands[i - 1].hPx, 'contiguous');
    assert.ok(bands[i].topPx >= bands[i - 1].topPx, 'monotonic');
  }
  assert.ok(bands.every(b => b.hPx >= 1), 'a one-line scene is still clickable');
  assert.ok(bands.every(b => b.hPct > 0 && b.topPct >= 0 && b.topPct < 100));
});

test('sceneBands holds its invariants on adversarial measurements', () => {
  const boxes = Array.from({ length: 40 }, (_, i) => ({ key: 's' + i, top: i * 10, height: i === 20 ? 0 : 10, page: i + 1 }));
  const bands = sceneBands(boxes, 400, 120);
  assert.equal(bands.at(-1).topPx + bands.at(-1).hPx, 120);
  let prev = -1;
  for (const b of bands) { assert.ok(b.topPx >= prev); prev = b.topPx; }
  assert.equal(sceneBands([], 400, 120).length, 0);
});

test('windowRect has an 8px floor so the window stays grabbable in a 3000px script', () => {
  const long = windowRect(1500, 900, 3000, 900);
  assert.equal(long.topPx, 450);
  assert.equal(long.hPx, 270);
  const huge = windowRect(0, 800, 40000, 800);
  assert.ok(huge.hPx >= 8, 'a 40k document still yields a draggable window');
});

test('scrubTo is the inverse of windowRect', () => {
  const track = 900, H = 3000, vh = 900;
  const st = scrubTo(450, vh, H, track);
  assert.equal(st, 1500);
  const back = windowRect(st, vh, H, track);
  assert.equal(back.topPx, 450);
  assert.equal(scrubTo(99999, vh, H, track), H - vh, 'clamped at the bottom');
  assert.equal(scrubTo(-50, vh, H, track), 0);
});

test('sceneBands and windowRect agree: the window is paint-free in track px', () => {
  const bands = sceneBands([{ key: 's1', top: 0, height: 3000, page: 1 }], 3000, 900);
  const win = windowRect(600, 900, 3000, 900);
  assert.ok(win.topPx >= bands[0].topPx && win.topPx + win.hPx <= bands[0].topPx + bands[0].hPx);
});

/* ── §1 ink channels ──────────────────────────────────────────────────── */

const F = (over = {}) => ({
  finding_id: 'x', severity: 'major', status: 'open', scene_refs: [1], rule_id: 'DIAL-114', ...over,
});

test('inkChannels buckets by scene, worst OPEN severity wins, addressed never pips', () => {
  const ch = inkChannels([
    F({ finding_id: 'a', scene_refs: [1], severity: 'minor' }),
    F({ finding_id: 'b', scene_refs: [1], severity: 'critical' }),
    F({ finding_id: 'c', scene_refs: [1], severity: 'critical', status: 'addressed' }),
    F({ finding_id: 'd', scene_refs: [2], severity: 'critical', status: 'addressed' }),
  ]);
  assert.equal(ch.get(1).worst, 'critical');
  assert.equal(ch.get(1).open, 2);
  assert.equal(ch.get(1).addressed, 1);
  assert.equal(ch.get(2).worst, 'none', 'a scene whose findings are all addressed is dry');
  assert.equal(ch.get(2).open, 0);
});

test('inkChannels is tolerant of payload shape and of script-level findings', () => {
  const ch = inkChannels([
    { finding_id: 'a', scene: 7, severity: 'major', status: 'open' },
    F({ finding_id: 'b', scene_refs: [] }),
    F({ finding_id: 'c', scene_refs: [3, 4] }),
    F({ finding_id: 'd', scene_refs: [3], dismissed: true }),
  ]);
  assert.equal(ch.get(7).open, 1, 'scene scalar accepted');
  assert.ok(!ch.has(0), 'a script-level finding with no ref produces no band claim');
  assert.equal(ch.get(4).open, 1, 'multi-scene findings ink every ref');
  assert.equal(ch.get(3).open, 1, 'dismissed excluded by default');
  assert.equal(inkChannels([F({ scene_refs: [3], dismissed: true })], { includeDismissed: true }).get(3).open, 1);
});

test('flag detection survives all three verification encodings', () => {
  assert.equal(isFlagged(F({ verification: { status: 'unverified' } })), true);
  assert.equal(isFlagged(F({ verification: 'unverified' })), true);
  assert.equal(isFlagged(F({ verified: false })), true);
  assert.equal(isFlagged(F({ verification: { status: 'verified' } })), false);
  assert.equal(isFlagged(F({})), false, 'absence of a verification field is not a flag');
});

test('provenance separates attributed craft rules from mechanical passes', () => {
  assert.equal(provenanceOf(F()), 'attributed');
  assert.equal(provenanceOf(F({ rule_id: null, check_id: 'pacing_drag' })), 'measured');
  assert.equal(provenanceOf(F({ rule_id: null })), 'unknown');
});

test('inkTotals is the one counting contract, and it honours dismissals', () => {
  const t = inkTotals([
    F({}), F({ status: 'addressed' }), F({ dismissed: true }),
    F({ verified: false }), F({ dismissed: true, status: 'addressed' }),
  ]);
  assert.deepEqual(t, { open: 2, addressed: 1, flagged: 1, dismissed: 2 });
  assert.equal(inkTotals([F({ dismissed: true })], { includeDismissed: true }).dismissed, 1);
});

test('normalizeSummary never invents a number, and detects the by_scene capability', () => {
  const s = normalizeSummary({ dawn_pct: 62, totals: { open: 41, addressed: 67, flagged: 5 }, by_scene: { 1: { open: 2 } } });
  assert.equal(s.dawnPct, 62);
  assert.equal(s.open, 41);
  assert.equal(s.addressed, 67);
  assert.equal(s.flagged, 5);
  assert.equal(s.dismissed, null, 'unknown stays null');
  assert.ok(s.byScene, 'by_scene capability detected at boot');
  assert.equal(normalizeSummary({ by_severity: { critical: 3 } }).byScene, null);
  assert.equal(normalizeSummary(undefined).dawnPct, null);
});

test('reconcileInk lets the server win and reports drift instead of hiding it', () => {
  const ch = inkChannels([F({}), F({ status: 'addressed' })]);
  const r = reconcileInk(ch, { open: 1, addressed: 1, flagged: 0 });
  assert.equal(r.drift, false);
  assert.equal(r.authority, 'server');
  const d = reconcileInk(ch, { open: 9, addressed: 1, flagged: 0 });
  assert.equal(d.drift, true);
  assert.equal(d.delta.open, 8, 'delta is SERVER minus CLIENT: the cache is 8 behind, i.e. stale');
  assert.equal(d.delta.addressed, 0);
  assert.equal(reconcileInk(ch, {}).drift, false, 'unknown counts are not drift');
});

/* ── §2 fold state machine ────────────────────────────────────────────── */

test('fold lifecycle only moves along the legal edges', () => {
  assert.equal(foldNext('closed', 'arm'), 'armed');
  assert.equal(foldNext('armed', 'cancel'), 'closed');
  assert.equal(foldNext('armed', 'fire'), 'open');
  assert.equal(foldNext('open', 'close'), 'closing');
  assert.equal(foldNext('closing', 'settle'), 'closed');
  assert.equal(foldNext('closed', 'fire'), 'closed', 'the timer must not open an unarmed fold');
  assert.equal(foldNext('open', 'arm'), 'open', 're-arming an open fold is inert');
  assert.equal(DWELL_MS, 420);
});

test('the dwell is cancellable: moving attention in the armed window leaves no residue', () => {
  let s = 'closed';
  s = foldNext(s, 'arm');            // dwell timer starts
  s = foldNext(s, 'cancel');         // writer moved on before 420ms
  assert.equal(s, 'closed');
  s = foldNext(s, 'arm');
  s = foldNext(s, 'fire');
  s = foldNext(s, 'close');
  assert.equal(s, 'closing');
  assert.equal(foldNext(s, 'settle'), 'closed', 'the transitionend settles it');
});

test('closing a fold ABOVE the focused line needs a scroll correction; below does not', () => {
  const above = scrollCorrection({ closingHeightPx: 180, closingTopPx: 300, focusTopPx: 900 });
  assert.equal(above, -180, 'the line would jump down by the collapsed height');
  const below = scrollCorrection({ closingHeightPx: 180, closingTopPx: 1200, focusTopPx: 900 });
  assert.equal(below, 0, 'growth or collapse below the line never moves it');
  const enclosing = scrollCorrection({ closingHeightPx: 180, closingTopPx: 800, focusTopPx: 900 });
  assert.equal(enclosing, 0);
});

test('opening a fold moves the scroll only by the overflow — never scrollIntoView', () => {
  const v = { viewTop: 0, viewBottom: 700 };
  const fits = overflowCorrection({ rowTop: 200, rowBottom: 220, foldBottom: 600, ...v });
  assert.equal(fits, 0, 'a fold that fits must not move the page at all');
  const over = overflowCorrection({ rowTop: 600, rowBottom: 620, foldBottom: 900, ...v });
  assert.equal(over, 200);
  const occluded = overflowCorrection({ rowTop: -40, rowBottom: -20, foldBottom: 600, ...v });
  assert.equal(occluded, -40);
});

/* ── §3 take casting string math ──────────────────────────────────────── */

test('frameOf captures prefix/target/suffix and refuses a missing quote', () => {
  const f = frameOf('VERA\nIt wasn\'t.', "It wasn't.");
  assert.equal(f.prefix, 'VERA\n');
  assert.equal(f.suffix, '');
  assert.equal(f.original, "VERA\nIt wasn't.");
  assert.equal(frameOf('anything', 'not present'), null, 'uncastable, not guessed');
  assert.equal(frameOf("a cat, a cat", 'a cat').ambiguous, true);
  assert.equal(frameOf("a cat", 'a cat').ambiguous, false);
});

test('J→K→J never accumulates text, because the frame is composed from the original', () => {
  const F0 = frameOf('VERA\nIt wasn\'t.', "It wasn't.");
  const a = composeLine(F0, 'The door was open.');
  const b = composeLine(F0, 'I heard you on the stairs.');
  const back = composeLine(F0, "It wasn't.");
  assert.equal(a, 'VERA\nThe door was open.');
  assert.equal(b, 'VERA\nI heard you on the stairs.');
  assert.equal(back, 'VERA\nIt wasn\'t.');
  assert.equal(restoreLine(F0), "VERA\nIt wasn't.", 'cancel is byte-exact');
});

test('a re-frame from the mutated text is the bug this API prevents', () => {
  const F0 = frameOf('It wasn\'t.', "It wasn't.");
  const mutated = composeLine(F0, 'The door was open.');
  assert.equal(mutated, 'The door was open.');
  // If the caller re-framed `It wasn't.` against the mutated text it would get null,
  // and a sloppy fallback would double the line. frameOf returns null instead.
  assert.equal(frameOf(mutated, "It wasn't."), null);
});

test('stepRing clamps by default; wrap is opt-in only', () => {
  assert.equal(stepRing(2, 3, 1), 2, 'no implicit wrap');
  assert.equal(stepRing(-1, 3, 1), 0, 'first press casts take 1');
  assert.equal(stepRing(0, 0, 1), -1, 'no candidates, no ring');
  // -1 is the writer's own line: the zero point of the ring, and a real place.
  assert.equal(stepRing(0, 3, -1), -1, 'back from take 1 is your own line');
  assert.equal(stepRing(-1, 3, -1), -1, 'and the ring stops there');
  assert.equal(stepRing(2, 3, 1, { wrap: true }), -1, 'wrapping past the last take lands on your line');
  assert.equal(stepRing(-1, 3, 1, { wrap: true }), 0);
  assert.equal(stepRing(0, 3, -1, { wrap: true }), -1);
  // The ring is len + 1 places wide, so every step is a step to somewhere real.
  const places = new Set([-1, 0, 1, 2]);
  for (const i of places) assert.ok(places.has(stepRing(i, 3, 1, { wrap: true })));
});

test('normalizeRewrite handles the plausible payload shapes and reports skips', () => {
  const r = normalizeRewrite({
    scene: 14,
    candidates: [{
      line_start: 9, old_text: "It wasn't.", rule_id: 'DIAL-114',
      candidates: [
        { id: 't1', text: 'The door was open.', confidence: 0.8 },
        'I heard you on the stairs.',
        { id: 't3', text: '', skipped_reason: 'line too short to rewrite' },
      ],
    }],
  });
  assert.equal(r.scene, 14);
  const t = r.takes[0];
  assert.equal(t.lineStart, 9);
  assert.equal(t.candidates.length, 2);
  assert.equal(t.candidates[1].ruleId, 'DIAL-114', 'rule id inherits from the target');
  assert.equal(t.candidates[1].text, 'I heard you on the stairs.');
  assert.deepEqual(t.skipped, [{ id: 't3', reason: 'line too short to rewrite' }], 'flag, do not drop silently');
});

test('normalizeRewrite survives junk without throwing', () => {
  assert.deepEqual(normalizeRewrite(null).takes, []);
  assert.deepEqual(normalizeRewrite({}).takes, []);
  assert.deepEqual(normalizeRewrite({ targets: 'nope' }).takes, []);
  assert.deepEqual(normalizeRewrite({ targets: [{}] }).takes[0].candidates, []);
});

test('takeForRow prefers line_start, falls back to quote containment', () => {
  const takes = [{ lineStart: null, oldText: "It wasn't." }, { lineStart: 9, oldText: 'x' }];
  assert.equal(takeForRow(takes, { lineStart: 9, text: 'anything' }).lineStart, 9);
  assert.equal(takeForRow(takes, { lineStart: undefined, text: "VERA It wasn't." }).oldText, "It wasn't.");
  assert.equal(takeForRow(takes, { lineStart: 1, text: 'no match' }), null);
});

test('applyPayload is apply-shaped and only committable when idle', () => {
  const frame = frameOf('VERA\nIt wasn\'t.', "It wasn't.");
  const body = applyPayload({
    sceneNumber: 15,
    take: { oldText: "It wasn't." },
    frame,
    candidate: { text: 'The door was open.' },
  });
  // The route's shape, verbatim: scene_number + one {old, new} frame per edit.
  assert.equal(body.scene_number, 15);
  assert.equal(body.replacements.length, 1);
  assert.equal(body.replacements[0].old, "It wasn't.");
  assert.equal(body.replacements[0].new, 'The door was open.');
  assert.ok(!body.hasOwnProperty('edits'), 'no legacy envelope survives on the wire');
  assert.ok(!body.hasOwnProperty('candidates'), 'the wire shape stays apply-shaped');
  // `old` is the frame's own target, so a proposal can never be built from text
  // the writer never saw.
  assert.equal(body.replacements[0].old, frame.target);

  assert.equal(canApply({ active: true, index: 0, candidates: [{}], busy: false }), true);
  assert.equal(canApply({ active: true, index: 0, candidates: [{}], busy: true }), false, 're-entrancy guard');
  assert.equal(canApply({ active: true, index: -1, candidates: [{}] }), false);
  assert.equal(canApply(null), false);
});

test('a refused proposal is classified from the body, never from the message', () => {
  // The stale refusal, byte for byte as the hardened route sends it. Nothing was
  // written, and the page must be able to say so without matching on prose.
  const err = new Error('Stale proposal: the text was modified manually.');
  err.status = 400;
  err.body = { error: 'Stale proposal: the text was modified manually.', stale: true };
  const stale = classifyApplyError(err);
  assert.equal(stale.kind, 'stale');
  assert.equal(stale.recoverable, true);

  const frames = new Error("replacements require string fields 'old' and 'new'");
  frames.status = 400; frames.body = { error: frames.message };
  assert.equal(classifyApplyError(frames).kind, 'frames', 'a malformed frame is the desk\'s bug');

  const dead = new Error('Failed to fetch');
  assert.equal(classifyApplyError(dead).kind, 'failed');
  assert.equal(classifyApplyError(null).kind, 'failed', 'an unknown failure is still a failure');

  // A 400 with no stale flag is NOT the stale refusal, however it is worded.
  const lookalike = new Error('Stale proposal: the text was modified manually.');
  lookalike.status = 400; lookalike.body = { error: lookalike.message };
  assert.equal(classifyApplyError(lookalike).kind, 'failed', 'the flag is the contract, the sentence is not');
});

test('the real rewrite contract is read as frames, and takeForRow still finds them', () => {
  const payload = {
    scene_number: 14,
    note: 'voice',
    replacements: [
      { old: "You're late.", new: "You're late. The stairs gave you away." },
      { old: "You're late.", new: '' },                       // skipped, empty side
      { old: "You're late.", new: "You're late." },           // skipped, no change
    ],
    scene_text: null,
  };
  const norm = normalizeRewrite(payload);
  assert.equal(norm.scene, 14);
  assert.equal(norm.takes.length, 1, 'only the real proposal becomes a take');
  assert.equal(norm.skipped.length, 2, 'and both refusals are reported, not hidden');
  assert.equal(norm.takes[0].candidates.length, 1, 'a frame is one candidate, not a ring');
  assert.equal(norm.takes[0].oldText, "You're late.");
  const take = takeForRow(norm.takes, { lineStart: 414, text: 'VERA\nYou\'re late.' });
  assert.ok(take, 'the frame is matched by the text the route quoted, not by a line number it never sent');
  assert.equal(take.candidates[0].text, "You're late. The stairs gave you away.");
  assert.deepEqual(normalizeRewrite(null).takes, [], 'junk still does not throw');

  // Grouping: two frames naming the SAME passage are two takes on it, so the
  // ring still auditions; frames naming different passages stay apart.
  const ring = normalizeRewrite({ replacements: [
    { old: "It wasn't.", new: 'The door was open.' },
    { old: "It wasn't.", new: 'I heard you on the stairs.' },
    { old: "It wasn't.", new: 'The door was open.' },        // a repeat is not a take
    { old: 'You read the note.', new: 'You read it, then.' },
  ] });
  assert.equal(ring.takes.length, 2);
  assert.equal(ring.takes[0].candidates.length, 2, 'alternates for one passage form one ring');
  assert.deepEqual(ring.takes[0].candidates.map((c) => c.text),
    ['The door was open.', 'I heard you on the stairs.']);
  assert.equal(ring.takes[1].candidates.length, 1);
  // Every candidate in a ring is applied against the same captured bytes, which
  // is the only way a swap can be free of accumulation.
  assert.equal(ring.takes[0].oldText, "It wasn't.");
});

test('findings arrive whole, whichever envelope carried them', () => {
  const live = normalizeFindings({ items: [{ index: 7, finding_id: 'x', evidence_quote: 'the third take',
                                             status: 'still_present', severity: 'major' }], count: 1 });
  assert.equal(live[0].index, 7);
  assert.equal(live[0].evidence, 'the third take', 'evidence_quote is the same fact under the route\'s name');
  assert.equal(live[0].severity, 'major');
  const demo = normalizeFindings({ findings: [{ finding_id: 'd1' }] });
  assert.equal(demo[0].index, 0, 'a missing index is filled by position, not invented');
  assert.equal(demo[0].evidence, '');
  assert.deepEqual(normalizeFindings(null), []);
  assert.deepEqual(normalizeFindings([]), []);
});

/* ── §3b rehearsal ────────────────────────────────────────────────────── */

test('the comparison mechanic is chosen by the material, never by preference', () => {
  // voice is judged in time
  assert.equal(rehearsalMode('dialogue'), 'temporal');
  assert.equal(rehearsalMode('character'), 'temporal');
  assert.equal(rehearsalMode('parenthetical'), 'temporal');
  // structure is judged by eye, because its question is size
  assert.equal(rehearsalMode('action'), 'spatial');
  assert.equal(rehearsalMode('scene_heading'), 'spatial');
  assert.equal(rehearsalMode('shot'), 'spatial');
  assert.equal(rehearsalMode('transition'), 'spatial');
  // an unknown element type is NEVER timed: time is the mechanic that hides a
  // deletion, so it is only spent on material whose question is rhythm.
  assert.equal(rehearsalMode('library_montage'), 'spatial');
  assert.equal(rehearsalMode(undefined), 'spatial');
});

test('a reading starts at take 1, ends once, and is not the same state as never started', () => {
  assert.equal(rehearsalStep({ ring: -1, count: 3 }), 0, 'the first beat is take 1');
  assert.equal(rehearsalStep({ ring: 0, count: 3 }), 1);
  assert.equal(rehearsalStep({ ring: 2, count: 3 }), -1, 'the end is a sentinel, not a clamp');
  assert.equal(rehearsalStep({ ring: -1, count: 0 }), -1, 'nothing to read');
  // The reading terminates for every count, and always at the end — never
  // looping, never resting on a take it has not read.
  for (let count = 1; count <= 6; count++) {
    let ring = -1, beats = 0;
    while (true) {
      const next = rehearsalStep({ ring, count });
      if (next < 0) break;
      assert.equal(next, ring + 1);
      ring = next; beats++;
    }
    assert.equal(beats, count, `every take is read exactly once, all ${count}`);
    assert.equal(ring, count - 1, 'and the last beat leaves the last take on the line');
  }
});

/* ── §4 keymap arbitration ────────────────────────────────────────────── */

const ctx = (o = {}) => ({ editing: false, casting: false, foldOpen: false, onHorizon: false, ...o });
const key = (k, m = {}) => ({ key: k, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...m });

test('editing swallows everything — the caret is never hijacked mid-sentence', () => {
  for (const k of ['ArrowDown', 'Enter', 'n', 'p', 'j', 'Escape', '[']) {
    assert.equal(routeKey(key(k), ctx({ editing: true })), 'passthrough', `${k} must pass through while editing`);
  }
});

test('the caret is absolute: Mod+Z belongs to the words being typed, not the edit stack', () => {
  // While a caret exists, ⌘Z must undo typing in the browser's own stack.
  // The app's /edits/undo only answers to a committed line.
  assert.equal(routeKey(key('z', { metaKey: true }), ctx({ editing: true })), 'passthrough');
  assert.equal(routeKey(key('z', { ctrlKey: true, shiftKey: true }), ctx({ editing: true })), 'passthrough');
  assert.equal(routeKey(key('ArrowDown', { metaKey: true }), ctx({ editing: true })), 'passthrough');
});

test('outside the caret, Mod+Z is the app edit stack and survives every layer', () => {
  for (const c of [ctx(), ctx({ foldOpen: true }), ctx({ casting: true }), ctx({ onHorizon: true })]) {
    assert.equal(routeKey(key('z', { metaKey: true }), c), 'edits.undo');
    assert.equal(routeKey(key('z', { metaKey: true, shiftKey: true }), c), 'edits.redo');
    assert.equal(routeKey(key('Z', { ctrlKey: true }), c), 'edits.undo');
  }
});

test('Escape peels exactly one layer, innermost first', () => {
  assert.equal(routeKey(key('Escape'), ctx({ casting: true, foldOpen: true, onHorizon: true })), 'cast.cancel');
  assert.equal(routeKey(key('Escape'), ctx({ foldOpen: true, onHorizon: true })), 'fold.close');
  assert.equal(routeKey(key('Escape'), ctx({ onHorizon: true })), 'focus.release');
  assert.equal(routeKey(key('Escape'), ctx()), 'fold.closeAll');
});

test('casting owns j/k/Enter, and a traversal key abandons the preview', () => {
  const c = ctx({ casting: true, foldOpen: true });
  assert.equal(routeKey(key('j'), c), 'cast.next');
  assert.equal(routeKey(key('K'), c), 'cast.prev');
  assert.equal(routeKey(key('Enter'), c), 'cast.apply');
  assert.equal(routeKey(key('ArrowDown'), c), 'cast.abandon', 'leaving the line restores the original');
  assert.equal(routeKey(key('PageDown'), c), 'cast.abandon');
  assert.equal(routeKey(key('n'), c), 'passthrough', 'n is not a casting key');
});

test('the horizon behaves like a scrollbar when focused, and like a row walker when not', () => {
  const h = ctx({ onHorizon: true });
  assert.equal(routeKey(key('ArrowDown'), h), 'hz.next');
  assert.equal(routeKey(key('ArrowUp'), h), 'hz.prev');
  assert.equal(routeKey(key('Home'), h), 'hz.first');
  assert.equal(routeKey(key('End'), h), 'hz.last');
  assert.equal(routeKey(key('Enter'), h), 'hz.jump');
  assert.equal(routeKey(key('ArrowDown'), ctx()), 'row.next');
  assert.equal(routeKey(key('Enter'), ctx({ foldOpen: true })), 'fold.close');
  assert.equal(routeKey(key('Enter'), ctx()), 'fold.toggle');
});

test('J and K begin casting ONLY inside an open fold — casting is never summoned', () => {
  assert.equal(routeKey(key('j'), ctx()), 'passthrough', 'j on a bare page is inert');
  assert.equal(routeKey(key('J'), ctx({ foldOpen: true })), 'cast.begin.next');
  assert.equal(routeKey(key('k'), ctx({ foldOpen: true })), 'cast.begin.prev');
  assert.equal(routeKey(key('j'), ctx({ casting: true, foldOpen: true })), 'cast.next',
    'once casting, j steps the ring rather than re-beginning');
});

test('r requests assistance on the selected passage; automatic targeting stays refused', () => {
  assert.equal(routeKey(key('r'), ctx()), 'passthrough', 'r on a bare page is inert');
  assert.equal(routeKey(key('r'), ctx({ foldOpen: true })), 'cast.request');
  assert.equal(routeKey(key('r'), ctx({ casting: true })), 'passthrough', 'while casting, r is inert');
});

test('traversal keys are stable and the ink floor steps are bounded', () => {
  assert.equal(routeKey(key('n'), ctx()), 'wet.next');
  assert.equal(routeKey(key('p'), ctx()), 'wet.prev');
  assert.equal(routeKey(key('['), ctx()), 'ink.down');
  assert.equal(routeKey(key(']'), ctx()), 'ink.up');
  assert.equal(routeKey(key('q'), ctx()), 'passthrough');
  assert.equal(routeKey(key('a'), ctx()), 'announce.toggle');
  assert.equal(routeKey(key('g'), ctx()), 'ground.toggle', 'the second ground is one reversible key away');
  assert.equal(stepFloor(0, -1), 0);
  assert.equal(stepFloor(3, 1), 3);
  assert.equal(stepFloor(1, 1), 2);
  assert.equal(FLOOR_LABEL.length, 4);
});

test('every action the router can emit is in HANDLED — no dead switch arms', () => {
  const emitted = new Set();
  const keys = ['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Enter', ' ', 'Escape', 'j', 'K', 'n', 'p', '[', ']', 'Home', 'End', 'z', 'q'];
  const flags = [0, 1];
  for (const k of keys) for (const e of flags) for (const c of flags) for (const f of flags) for (const h of flags) {
    emitted.add(routeKey(key(k, { metaKey: e === 1, shiftKey: f === 1 }), ctx({ casting: !!c, foldOpen: !!f, onHorizon: !!h })));
  }
  for (const a of emitted) assert.ok(HANDLED.includes(a), `${a} missing from HANDLED`);
});

test('announcements carry the load, so no visual channel is load-bearing', () => {
  assert.match(say.foldOpen({ lineNo: 9, count: 3, worst: 'critical', flagged: 1 }), /Line 9, 3 findings, worst critical, 1 unverified/);
  assert.match(say.castReady({ index: 1, count: 3, text: 'The door was open.' }), /Take 2 of 3: The door was open\./);
  assert.match(say.wetNone({ dir: 1 }), /below/);
  assert.match(say.inkThreshold({ floor: 2, label: 'major and above' }), /major and above/);
  assert.match(say.applyReport({ applied: 2, skipped: 1 }), /Applied 2\. 1 skipped\./);
  assert.equal(say.castSkipped({ skipped: [] }), '');
});

/* ── integration: one writer session, no DOM ──────────────────────────── */

test('a full session: walk wet → arm → open → cast → apply → dry, with server authority', () => {
  // 1. rows hydrate; two are wet
  const findings = [
    F({ finding_id: 'a', scene_refs: [1], severity: 'critical' }),
    F({ finding_id: 'b', scene_refs: [1], severity: 'minor' }),
    F({ finding_id: 'c', scene_refs: [2], severity: 'major' }),
  ];
  const ch = inkChannels(findings);
  const rows = [
    { lineStart: 4, scene: 1 }, { lineStart: 9, scene: 1 },
    { lineStart: 12, scene: 1 }, { lineStart: 31, scene: 2 },
  ].map(r => ({ ...r, wet: (ch.get(r.scene)?.open || 0) > 0 }));
  assert.deepEqual(rows.map(r => r.wet), [true, true, true, true]);

  // 2. n walks to the first wet row, then off it
  assert.equal(nearestWet(rows, -1, 1), 0);
  assert.equal(nearestWet(rows, 0, 1), 1);
  assert.equal(nearestWet(rows, 3, 1), -1);

  // 3. dwell arms and fires
  let s = foldNext('closed', 'arm');
  s = foldNext(s, 'fire');
  assert.equal(s, 'open');

  // 4. cast take 2, then back to take 1, then commit
  const frame = frameOf('VERA\nIt wasn\'t.', "It wasn't.");
  const takes = normalizeRewrite({ candidates: [{ line_start: 9, old_text: "It wasn't.", candidates: ['The door was open.', 'I heard you on the stairs.'] }] }).takes;
  const take = takeForRow(takes, { lineStart: 9, text: 'VERA\nIt wasn\'t.' });
  assert.ok(take);
  assert.equal(composeLine(frame, take.candidates[1].text), 'VERA\nI heard you on the stairs.');
  assert.equal(composeLine(frame, take.candidates[0].text), 'VERA\nThe door was open.');
  const body = applyPayload({ sceneNumber: 14, take, frame, candidate: take.candidates[0] });
  assert.equal(body.replacements[0].new, 'The door was open.');
  assert.equal(body.replacements[0].old, "It wasn't.", 'the frame carries the exact bytes it was cut from');

  // 5. the server re-reports: one fewer open, dawn up
  const after = reconcileInk(inkChannels(findings.map(f => f.finding_id === 'a' ? { ...f, status: 'addressed' } : f)),
    { open: 2, addressed: 1, flagged: 0 });
  assert.equal(after.drift, false);
  assert.equal(after.server.open, 2);
});


/* ── §0 column geometry ───────────────────────────────────────────────── */

test('indentation comes from one map, and leading whitespace is owned by the renderer', () => {
  assert.equal(indentOf('dialogue'), 14);
  assert.equal(indentOf('character'), 22);
  assert.equal(indentOf('action'), 0);
  assert.equal(indentOf('unknown_type'), 0, 'unknown types are flush, never guessed');
  assert.equal(stripLead('    It wasn\'t.'), "It wasn\'t.");
  assert.equal(indentText('dialogue', '   It wasn\'t.'), ' '.repeat(14) + "It wasn\'t.");
  assert.equal(indentText('action', 'Dust turns.'), 'Dust turns.');
  assert.equal(Object.keys(INDENT).length, 8);
});

test('the same number drives the text AND the fold column — they cannot drift', () => {
  for (const type of Object.keys(INDENT)) {
    const rendered = indentText(type, 'x');
    const leading = rendered.length - rendered.trimStart().length;
    assert.equal(leading, indentOf(type), `${type}: text indent must equal the fold indent`);
  }
});

/* ── §3a identity is not location: the alias table and the 0.72 gate ─────── */

test("the desk's three tiers map one-to-one onto the page's three marks", () => {
  // Read from the producer, not from a document: `screenplay_analyzer/grammar.py:50`
  // compiles SEVERITIES = ["low", "medium", "high"] into the findings grammar, and
  // the findings route tallies `by_severity` from those same strings — so the desk
  // has three tiers and no fourth. Three tiers, three marks, no collapse: every rung
  // of the ladder is reachable from real data, which is what the pip geometry
  // (4 / 8 / 12 px) and the three-step ink threshold were sized for.
  assert.equal(canonSev('high'), 'critical');
  assert.equal(canonSev('medium'), 'major');
  assert.equal(canonSev('low'), 'minor');
  const rungs = new Set(['low', 'medium', 'high'].map(canonSev));
  assert.equal(rungs.size, 3, 'no two desk tiers collapse onto one mark');
  // The page's own names read, and so do the legacy spellings in cached payloads.
  assert.equal(canonSev('critical'), 'critical');
  assert.equal(canonSev('major'), 'major');
  assert.equal(canonSev('minor'), 'minor');
  assert.equal(canonSev('blocker'), 'critical');
  assert.equal(canonSev('moderate'), 'major');
  assert.equal(canonSev('  HIGH '), 'critical', 'the word arrives as text and is read as text');
  assert.equal(canonSev(undefined), 'none');
  assert.equal(canonSev('whatever'), 'none', 'an unknown weight is no mark, never a guess');
  for (const w of Object.keys(SEV_ALIAS)) assert.equal(canonSev(SEV_ALIAS[w]), SEV_ALIAS[w], `${w} is idempotent`);
  // The mark a desk word produces is the mark the page has — all three widths live.
  assert.equal(inkPx('high'), 12);
  assert.equal(inkPx('medium'), 8, 'the middle width is reachable, not decorative');
  assert.equal(inkPx('low'), 4);
  assert.equal(inkPx('high'), inkPx('critical'));
  assert.equal(inkPx('medium'), inkPx('major'));
  // Aliasing only renames: the ordering the filter and the threshold read is unchanged.
  assert.equal(sevRank('high'), sevRank('critical'));
  assert.equal(sevRank('medium'), 2);
  assert.equal(sevAtLeast('low', sevRank('major')), false);
  assert.equal(sevAtLeast('medium', 2), true, 'the middle tier clears the middle threshold step');
});

test('only a failed SEARCH is flagged: a quoteless finding is quiet, not unverified', () => {
  // `report.py:37` prints a warning for exactly two of the desk's four verification
  // states — `not_found` and `scene_not_found` — and leaves `no_quote` blank. A
  // finding that never offered a quote has nothing to verify, so calling it
  // unverified reports a failure that never happened. The page mirrors the
  // published report rather than the summary's arithmetic.
  assert.equal(isFlagged({ verification: { status: 'not_found' } }), true);
  assert.equal(isFlagged({ verification: { status: 'scene_not_found' } }), true);
  assert.equal(isFlagged({ verification: { status: 'no_quote' } }), false);
  assert.equal(isFlagged({ verification: { status: 'verified' } }), false);
  assert.equal(isFlagged({ verification: 'not_found' }), true, 'the string form is tolerated');
  assert.equal(isFlagged({ verification: 'no_quote' }), false);
  assert.equal(isFlagged({ verified: false }), true, 'the legacy boolean still reads');
  assert.equal(isFlagged({ verified: true }), false);
  assert.equal(isFlagged({}), false, 'silence is not a failure');
  assert.equal(isFlagged({ verification: { status: 'NOT_FOUND' } }), true, 'read as text, case-folded');
});

test('inkChannels reports the canonical word, because the geometry reads it', () => {
  const f = (id, sev, scene, extra = {}) => ({ finding_id: id, severity: sev, status: 'open', scene_refs: [scene], ...extra });
  const ch = inkChannels([f('a', 'minor', 1), f('b', 'high', 1), f('c', 'major', 1), f('d', 'high', 1)]);
  const one = ch.get(1);
  assert.equal(one.worst, 'critical', 'a channel that saw `high` carries `critical`, the word the ink is drawn from');
  assert.equal(one.open, 4);
  assert.equal(ch.get(1).flagged, 0);
});

test('fuzzyScore: containment is a match, rewording is measured, nothing throws', () => {
  assert.equal(fuzzyScore("You're late.", "You're late."), 1);
  assert.equal(fuzzyScore('late', "You're late."), 1, 'a contained fragment is a located quote');
  assert.equal(fuzzyScore("You're late.", ''), 0);
  assert.equal(fuzzyScore('', "You're late."), 0);
  assert.equal(fuzzyScore(null, null), 0);
  const near = fuzzyScore("You're late. The stairs gave you away.", "You're late. The stairs told on you.");
  assert.ok(near > 0.72 && near < 1, `a rewording inside the threshold is a match (${near})`);
  // A quote that lost a whole clause is NOT located, and must not be: this is
  // the case the 0.72 gate exists to refuse, and it refuses by measurement, not
  // by taste.
  const clauseLost = fuzzyScore('The ON AIR sign is dark', 'The ON AIR sign has been dark for a while');
  assert.ok(clauseLost < 0.72, `a quote that lost a clause falls below the gate (${clauseLost})`);
  assert.ok(fuzzyScore('Totally unrelated sentence here', 'The ON AIR sign is dark') < 0.4);
  assert.equal(fuzzyScore('a', 'b'), 0, 'too short to measure is not a match');
  // Case and punctuation are not the writer's problem.
  assert.equal(fuzzyScore('THE ON AIR SIGN IS DARK', 'The ON AIR sign is dark.'), 1);
});

test('anchorFinding: exact, thresholded, ambiguous-with-a-hint, or loose', () => {
  const rows = [
    { scene: 14, lineStart: 411, baseText: 'Dust turns in the light above a mixing desk.' },
    { scene: 14, lineStart: 414, baseText: "You're late." },
    { scene: 14, lineStart: 422, baseText: 'So you read the note.' },
    { scene: 15, lineStart: 435, baseText: 'Cary stands in the corridor.' },
  ];
  const anchored = anchorFinding(rows, { evidence: "You're late.", scene_refs: [14], line_start: 414 });
  assert.deepEqual(anchored, { rowIndex: 1, score: 1, exact: true, ambiguous: false, loose: false });
  // The quote sits in scene 14 but the finding cites scene 15. Identity is not
  // location: the quote is not searched outside the scenes the finding names, so
  // this is LOOSE — it stays on its own scene instead of being pointed at a line
  // in a scene it never cited.
  const elsewhere = anchorFinding(rows, { evidence: 'Dust turns in the light', scene_refs: [15] });
  assert.equal(elsewhere.rowIndex, -1);
  assert.equal(elsewhere.loose, true);

  const loose = anchorFinding(rows, { evidence: 'Nobody says this anywhere on the page', scene_refs: [14] });
  assert.equal(loose.loose, true, 'below the gate: shown, never re-pointed');
  assert.equal(loose.rowIndex, -1);
  assert.ok(loose.score < ANCHOR_THRESHOLD);

  // Two rows carry the same words. The quote cannot choose; line_start may.
  const twins = [
    { scene: 14, lineStart: 414, baseText: "You're late." },
    { scene: 14, lineStart: 436, baseText: "You're late." },
  ];
  const amb = anchorFinding(twins, { evidence: "You're late.", scene_refs: [14], line_start: 436 });
  assert.equal(amb.ambiguous, true, 'the tie is announced, not hidden');
  assert.equal(amb.rowIndex, 1, 'and line_start only breaks a tie it is told to, never predicts');
  const amb2 = anchorFinding(twins, { evidence: "You're late.", scene_refs: [14] });
  assert.equal(amb2.ambiguous, true);
  assert.equal(amb2.rowIndex, 0, 'with no hint the first row wins — deterministic, and said to be ambiguous');
  const scoped = anchorFinding(twins, { evidence: "You're late.", scene_refs: [99] });
  assert.equal(scoped.loose, true, 'a scene that owns no rows cannot host the finding');
  assert.equal(anchorFinding([], { evidence: 'x' }).rowIndex, -1);
});

/* ── §3c takes: what changed, and what the writer typed ──────────────────── */

test('diffWords prints the change in words: deletions struck, insertions added', () => {
  const d = diffWords("You're late.", "You're late. The stairs gave you away.");
  assert.deepEqual(d.map((x) => x.op), ['=', 'ins']);
  assert.equal(d[0].text, "You're late.");
  assert.ok(d[1].text.includes('stairs'));
  const back = diffWords("You're late. The stairs gave you away.", "You're late.");
  assert.deepEqual(back.map((x) => x.op), ['=', 'del']);
  // The beat that loses a clause: the diff prints the deletion AND the segment
  // that had to be re-written to close the sentence — the writer sees both sides.
  const cut = diffWords('The ON AIR sign is dark, and has been dark for a while.', 'The ON AIR sign is dark.');
  assert.deepEqual(cut.map((x) => x.op), ['=', 'del', 'ins']);
  assert.equal(cut[0].text, 'The ON AIR sign is');
  assert.match(cut[1].text, /dark, and has been dark for a while/);
  assert.equal(cut[2].text, 'dark.');
  const same = diffWords('Twice.', 'Twice.');
  assert.deepEqual(same, [{ op: '=', text: 'Twice.' }], 'an unchanged line is one run, not an empty diff');
  assert.deepEqual(diffWords('', ''), []);
  assert.deepEqual(diffWords(null, null), []);
  // Whitespace rides with the words so the renderer can print a sentence.
  assert.equal(diffWords('a b', 'a b').map((x) => x.text).join(''), 'a b');
});

test('deltaOf is the arithmetic the ledger prints, with no negative counts', () => {
  assert.deepEqual(deltaOf('abc', 'abcde'), { added: 2, removed: 0, net: 2 });
  assert.deepEqual(deltaOf('abcde', 'abc'), { added: 0, removed: 2, net: -2 });
  assert.deepEqual(deltaOf('abc', 'abc'), { added: 0, removed: 0, net: 0 });
  assert.deepEqual(deltaOf(null, 'ab'), { added: 2, removed: 0, net: 2 });
});

test('editProposal recomposes from the frame, and refuses an empty proposal', () => {
  const frame = frameOf("You're late.", "You're late.");
  const r = editProposal(frame, "  You're   late — the stairs told me first.  ");
  assert.equal(r.ok, true);
  assert.equal(r.text, "You're late — the stairs told me first.", 'whitespace is normalised, the words are the writer\'s');
  assert.equal(r.composed, r.text);
  assert.equal(editProposal(frame, '   ').ok, false);
  assert.equal(editProposal(frame, '   ').reason, 'empty', 'an empty proposal is a deletion, and deletions are not proposals');
  assert.equal(editProposal(frame, "You're late.").reason, 'unchanged');
  assert.equal(editProposal(null, 'x').reason, 'no frame to edit');
  // A frame inside a longer line keeps its prefix and suffix: the edit is a hole.
  const mid = frameOf("So you read the note.", 'read the note');
  const mid2 = editProposal(mid, 'read it once');
  assert.equal(mid2.composed, 'So you read it once.');
  assert.equal(restoreLine(mid), "So you read the note.", 'and the original is restorable byte for byte');
});

/* ── §3c scope, filter, roam: what the desk answered, and what speaks ────── */

test('scopeOf says whether the desk answered for a passage, a line, or a scene', () => {
  const norm = normalizeRewrite({ scene_number: 14, note: 'n', replacements: [{ old: "You're late.", new: 'X' }] });
  const one = scopeOf(norm, { lineStart: 414, text: "You're late." });
  assert.equal(one.kind, 'passage');
  const many = normalizeRewrite({ scene_number: 14, replacements: [
    { old: "You're late.", new: 'X' }, { old: 'So you read the note.', new: 'Y' }] });
  assert.equal(scopeOf(many, { lineStart: 414, text: "You're late." }).kind, 'line');
  const scene = scopeOf(normalizeRewrite({ scene_number: 14, scene_text: 'CARY\nYou\'re late.', replacements: [{ old: 'a', new: 'b' }] }), null);
  assert.equal(scene.kind, 'scene', 'a response that carried the scene text answered for the scene');
});

test('overlappingTargets reports a dependency between proposals, never within one', () => {
  const a = { oldText: "You're late." }, b = { oldText: 'late.' };
  assert.equal(overlappingTargets("You're late.", [a, b]), true, 'two proposals over the same words are not independent');
  assert.equal(overlappingTargets("You're late.", [a]), false, 'one proposal, however long, is one proposal');
  assert.equal(overlappingTargets("You're late.", [a, a]), false, 'a repeat is the ambiguity question, not a dependency');
  assert.equal(overlappingTargets("You're late.", [{ oldText: "You're late." }, { oldText: 'nothing here' }]), false);
  assert.deepEqual(targetSpans("You're late. You're late.", [{ oldText: "You're late." }]).map((s) => s.start), [0, 13],
    'every occurrence of a target is a span, not just the first');
  assert.equal(overlappingTargets('', [a]), false);
});

test('nextScope cycles in context and skips what the row cannot offer', () => {
  assert.deepEqual(nextScope({ kind: 'all' }, { scene: 14, category: 'dialogue' }), { kind: 'scene', value: 14 });
  assert.deepEqual(nextScope({ kind: 'scene' }, { scene: 14, category: 'dialogue' }), { kind: 'category', value: 'dialogue' });
  assert.deepEqual(nextScope({ kind: 'category' }, {}), { kind: 'status', value: 'open' });
  assert.deepEqual(nextScope({ kind: 'status' }, {}), { kind: 'all', value: null });
  assert.deepEqual(nextScope(null, { scene: 14 }), { kind: 'scene', value: 14 }, 'a missing scope reads as all');
  assert.deepEqual(nextScope({ kind: 'all' }, {}), { kind: 'status', value: 'open' },
    'no scene and no category: the cycle skips to what it can offer');
  assert.deepEqual(SCOPE_KINDS, ['all', 'scene', 'category', 'status']);
});

test('inScope and quietRow recede critique, and can never touch prose', () => {
  const f = { severity: 'major', status: 'open', category: 'dialogue', scene_refs: [14] };
  assert.equal(inScope(f, { kind: 'all' }), true);
  assert.equal(inScope({ ...f, status: 'addressed' }, { kind: 'status', value: 'open' }), false);
  assert.equal(inScope({ ...f, category: 'pacing' }, { kind: 'category', value: 'dialogue' }), false);
  assert.equal(inScope({ ...f, scene_refs: [15] }, { kind: 'scene', value: 14 }), false);
  assert.equal(inScope({ scene: 15 }, { kind: 'scene', value: 15 }), true, 'a bare `scene` is a refs list of one');
  const row = { worst: 'major', finds: [f] };
  assert.equal(quietRow(row, 0, { kind: 'all' }), false);
  assert.equal(quietRow(row, sevRank('critical'), { kind: 'all' }), true, 'below the floor: the critique recedes');
  assert.equal(quietRow(row, 0, { kind: 'scene', value: 15 }), true, 'outside the filter: the critique recedes');
  assert.equal(quietRow({ worst: 'none', finds: [] }, 0, { kind: 'scene', value: 15 }), false,
    'a row with no critique has nothing to recede — and its prose is never a filter subject');
});

test('relatedScene names the other scene a finding cites, or nothing', () => {
  assert.equal(relatedScene({ scene_refs: [14, 15] }, 14), 15);
  assert.equal(relatedScene({ scene_refs: [14, 15] }, 15), 14);
  assert.equal(relatedScene({ scene_refs: [14] }, 14), null);
  assert.equal(relatedScene({ scene: 15 }, 14), 15, 'a single-scene finding still names its scene');
  assert.equal(relatedScene({}, 14), null);
});

test('statusPatch reads the apply response, and reports nothing when it is not there', () => {
  const patch = statusPatch({ applied: 1, findings_status: { summary: { open_count: 3 }, findings: [
    { index: 0, status: 'addressed' }, { index: 2, status: 'still_present' }, { index: 3, status: null }] } });
  assert.equal(patch.byIndex.get(0), 'addressed');
  assert.equal(patch.byIndex.get(2), 'still_present');
  assert.equal(patch.byIndex.has(3), false, 'a finding with no status is not patched to a guess');
  assert.deepEqual(patch.summary, { open_count: 3 });
  assert.equal(statusPatch({ applied: 1 }), null, 'no patch: the caller asks the desk instead');
  assert.equal(statusPatch(null), null);
  assert.equal(statusPatch({ findings_status: 'yes' }), null);
});

test('normalizeRewrite refuses a shape it does not know instead of reading it optimistically', () => {
  const unknown = normalizeRewrite({ status: 'ok', payload: { something: 'else' } });
  assert.equal(unknown.unknown, true);
  assert.equal(typeof unknown.reason, 'string');
  assert.match(unknown.reason, /none of the fields/);
  assert.deepEqual(unknown.takes, [], 'nothing is cast from a shape that was not recognised');
  // A non-object, or an empty one, is unknown too — and never throws.
  assert.equal(normalizeRewrite(null).unknown, true);
  assert.equal(normalizeRewrite([]).unknown, true);
  // A known key is enough to read, even when the list is empty: the desk answered.
  assert.equal(normalizeRewrite({ replacements: [] }).unknown, false);
  assert.equal(normalizeRewrite({ note: 'cadence' }).unknown, false);
});

/* ── §0b the capability token ─────────────────────────────────────────── */

test('the page echoes the studio token it was issued, and only on writes', () => {
  assert.equal(STUDIO_TOKEN_COOKIE, 'studio_token');
  const jar = 'theme=dark; studio_token=secret-token-123; other=1';
  assert.equal(tokenFromCookie(jar), 'secret-token-123');
  assert.deepEqual(writeHeaders(jar), {
    'Content-Type': 'application/json', 'X-Studio-Token': 'secret-token-123' });
  // No token configured is a legal world: the server's guard is inert then, and
  // sending an empty header would be worse than sending none.
  assert.deepEqual(writeHeaders('theme=dark'), { 'Content-Type': 'application/json' });
  assert.deepEqual(writeHeaders(''), { 'Content-Type': 'application/json' });
  assert.deepEqual(writeHeaders(undefined), { 'Content-Type': 'application/json' });
  // A prefix match must not pass for the cookie: `studio_token_x` is another cookie.
  assert.equal(tokenFromCookie('studio_token_x=nope'), null);
  assert.equal(tokenFromCookie('studio_token='), null, 'an empty value is no licence');
  assert.equal(tokenFromCookie('studio_token=a%2Fb'), 'a/b', 'cookie values are URL-encoded');
});
