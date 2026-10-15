// Track B: lanes, rank v0, and the auditable reason string.
//
// The load-bearing property is COVERAGE, not the values. An absent IMPACT entry
// makes IMPACT[category] undefined, undefined * 10 is NaN, and NaN in a sort
// comparator is unspecified behaviour - which is exactly how `voice` and
// `subtext` were about to ship (spec section 13).

import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const core = require('../../screenplay_studio/webapp/core.js');

const f = (category, scene_refs = [1], over = {}) =>
  ({ category, scene_refs, ...over });

test('every IMPACT value is a finite positive number', () => {
  for (const [cat, v] of Object.entries(core.IMPACT)) {
    assert.ok(Number.isFinite(v), `IMPACT[${cat}] is ${v}`);
    assert.ok(v > 0, `IMPACT[${cat}] is ${v}`);
  }
});

test('voice and subtext are laned to Line (Track B requirement 1)', () => {
  assert.equal(core.LANE_OF.voice, 'line');
  assert.equal(core.LANE_OF.subtext, 'line');
});

test('a finding with no scene_refs is an observation, not a task', () => {
  assert.equal(core.findingLane(f('dialogue', [])), 'observation');
  assert.equal(core.findingLane(f('continuity', [])), 'observation');
  // ...and with scene refs it IS queued. Membership requires a scene AND a verb
  // (spec 1.1); this is the half that keeps a locatable note from being waved
  // away. AGENTS.md:66, "Flag, don't drop".
  assert.notEqual(core.findingLane(f('dialogue', [2])), 'observation');
});

test('theme and genre are observations even when they carry scene refs', () => {
  // Spec 1.2 puts theme and genre in the Observation lane unconditionally: a
  // thesis or a conformance note is not a task, and a scene anchor does not turn
  // one into a task. My first draft of this file asserted the opposite and was
  // wrong — the implementation follows the spec.
  assert.equal(core.findingLane(f('theme', [])), 'observation');
  assert.equal(core.findingLane(f('theme', [2])), 'observation');
  assert.equal(core.findingLane(f('genre', [1, 2, 3])), 'observation');
  // They are therefore deliberately absent from LANE_OF, and the Python guard
  // allows the same exception.
  assert.equal(core.LANE_OF.theme, undefined);
  assert.equal(core.LANE_OF.genre, undefined);
});

test('the deterministic lane is a lane, not a demotion', () => {
  assert.equal(core.findingLane(f('continuity', [1, 2])), 'deterministic');
  // And it is NOT ranked below the others by default - lanes are separate
  // groups, so this is about lane identity, never about sort position.
  assert.notEqual(core.findingLane(f('continuity', [1])), 'observation');
});

test('sceneRefCount tolerates numeric and string refs alike', () => {
  assert.equal(core.sceneRefCount(f('dialogue', [1, '2', 3])), 3);
  assert.equal(core.sceneRefCount(f('dialogue', [])), 0);
  assert.equal(core.sceneRefCount({ category: 'dialogue' }), 0);
  assert.equal(core.sceneRefCount(null), 0);
});

test('rankScore never returns NaN, for any category at all', () => {
  const categories = [...Object.keys(core.IMPACT), 'brand_new_category', ''];
  for (const cat of categories) {
    const s = core.rankScore(f(cat, [1, 2, 3]));
    assert.ok(Number.isFinite(s), `rankScore(${cat}) is ${s} — NaN breaks the sort`);
  }
  assert.equal(core.rankScore(null), 0);
  assert.equal(core.rankScore(undefined), 0);
});

test('verified outranks unverified at equal impact', () => {
  const plain = core.rankScore(f('dialogue', [1]));
  const verified = core.rankScore(f('dialogue', [1], { verification: { status: 'verified' } }));
  assert.equal(verified - plain, 3);
});

test('span rewards multi-scene findings, capped at three', () => {
  assert.equal(core.rankScore(f('dialogue', [1, 2])) - core.rankScore(f('dialogue', [1])), 1);
  assert.equal(
    core.rankScore(f('dialogue', [1, 2, 3, 4])) - core.rankScore(f('dialogue', [1])),
    2,
  );
});

test('impact dominates every other term (weights are uncalibrated but ordered)', () => {
  // A structure note with one scene, unverified and unaddressed, must still
  // outrank a subtext note spanning three scenes and marked addressed. If this
  // ever inverts, the weights stopped being a hierarchy and became a shuffle.
  assert.ok(
    core.rankScore(f('structure', [1])) > core.rankScore(f('subtext', [1, 2, 3])),
  );
});

test('an unknown category gets its own lane, not a demotion', () => {
  // The failure this prevents: unknown -> "line" with IMPACT 0 scores at most 5,
  // against a known `dialogue` floor of 30. That is a 30-point demotion, which
  // is the silent demotion spec 1.3 ruled out.
  assert.equal(core.findingLane(f('brand_new_category', [1])), 'uncategorised');
  const unknownBest = core.rankScore(
    f('brand_new_category', [1, 2, 3], { verification: { status: 'verified' } }),
  );
  const knownFloor = core.rankScore(f('dialogue', [1]));
  assert.ok(
    unknownBest < knownFloor,
    'the point is that unknown CANNOT compete in Line, which is why it needs its '
      + 'own lane — this assertion documents the gap, not a desired ranking',
  );
  // ...and it is not dropped either. AGENTS.md:66.
  assert.notEqual(core.findingLane(f('brand_new_category', [1])), 'observation');
});

test('an unweighed row says it is unweighed', () => {
  // An unknown category has no IMPACT value. Printing "impact 0" would imply a
  // judgement was made; the row must admit none was.
  const text = core.rankReasonText(f('brand_new_category', [1, 2]));
  assert.match(text, /unweighed/);
  assert.doesNotMatch(text, /impact 0/);
  // A weighed row still prints its number.
  assert.match(core.rankReasonText(f('dialogue', [1])), /impact 3/);
});

test('every row can print its own reason (spec 1.5)', () => {
  for (const cat of Object.keys(core.IMPACT)) {
    const text = core.rankReasonText(f(cat, [1, 2]));
    assert.match(text, /^ranked here: /, `${cat} printed ${JSON.stringify(text)}`);
    assert.ok(text.length > 'ranked here: '.length, `${cat} printed an empty reason`);
  }
});

test('the reason string names the lane and the impact', () => {
  const text = core.rankReasonText(f('voice', [1, 2, 3]));
  assert.match(text, /Line/);
  assert.match(text, /impact 3/);
  assert.match(text, /spans 3 scenes/);
});

test('the reason string credits verification without hiding anything', () => {
  const text = core.rankReasonText(f('dialogue', [1], { verification: { status: 'verified' } }));
  assert.match(text, /verified/);
  // A rejected verification is not a boost and must not claim to be one.
  const bad = core.rankReasonText(f('dialogue', [1], { verification: { status: 'refuted' } }));
  assert.doesNotMatch(bad, /verified/);
});

// ---------------------------------------------------------------------------
// Spec 14.20: the e2e scene-filter fixture's contract, pinned WITHOUT a browser.
//
// `tests/e2e_browser_dock_sections.py` migrates P1.7/P1.8 onto the merged Fix
// Queue, and its assertions about ORDER cannot run here — no Playwright. These
// are the same expectations against the same functions the browser will call,
// so a fixture that silently stops discriminating fails in CI instead of on the
// runner's machine.
//
// The fixture is the interesting part. Its two Line-lane rows share a category,
// so they share IMPACT, and the ONLY thing separating them is the verified
// term. The verified row is the LOW-severity one, so "highs first" and "rank
// first" order the pair in OPPOSITE directions. A first draft seeded the
// verified row as high severity; the assertions passed and proved nothing,
// because both keys agreed. This test exists so that mistake cannot recur
// unnoticed.
test('the scene-filter fixture discriminates: rank beats severity', () => {
  const mk = (cat, sev, scene, issue, ver) => Object.assign(
    { category: cat, severity: sev, scene_refs: [scene], issue }, ver ? { verification: { status: ver } } : {});
  const fixture = [
    mk('dialogue', 'low', 1, 'SEED low dialogue on 1', 'verified'),
    mk('dialogue', 'high', 1, 'SEED high dialogue on 1'),
    mk('structure', 'medium', 2, 'SEED medium structure on 2'),
    mk('structure', 'high', 2, 'SEED high structure on 2'),
  ];
  const cut = core.groupByLane(fixture.map((f, index) => ({ f, index })));
  const line = cut.groups.line || [];

  assert.equal(line.length, 2, 'the Line lane must hold the fixture pair');
  assert.ok(line[0].f.issue.startsWith('SEED low'),
    'the LOW-severity row must lead the Line lane; it leads only because it is verified');
  assert.ok(line[1].f.issue.startsWith('SEED high'),
    'the HIGH-severity row must follow. If the fixture is re-seeded so severity and rank agree, these assertions stop proving anything.');
  assert.ok(core.rankScore(line[0].f) > core.rankScore(line[1].f),
    'and it must win on rankScore, not by accident of ordering');
});

test('the fixture ranks lanes by descending max IMPACT, with none forced last', () => {
  const mk = (cat, scene) => ({ category: cat, severity: 'low', scene_refs: [scene], issue: cat });
  const cut = core.groupByLane([
    { f: mk('dialogue', 1), index: 0 }, { f: mk('structure', 2), index: 1 },
  ]);
  assert.deepEqual(cut.order.slice(0, 2), ['structure', 'line'],
    'structure is impact 5 and line is impact 3, so structure leads');
});

test('the fixture rows each print a reason that names the term that decided it', () => {
  const f = { category: 'dialogue', severity: 'low', scene_refs: [1],
    verification: { status: 'verified' }, issue: 'x' };
  const why = core.rankReasonText(f);
  assert.match(why, /verified/, 'the verified term is why this row leads and it must be printed');
  assert.doesNotMatch(why, /severity/i,
    'severity is an attribute, not a rank term; printing it would imply it sorted the row');
});
