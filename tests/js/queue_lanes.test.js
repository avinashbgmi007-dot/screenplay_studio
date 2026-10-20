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
    const lane = core.findingLane(f(cat, [1, 2]));
    const label = core.LANE_LABELS[lane] || cat;
    assert.ok(text.startsWith(label),
      `${cat} printed ${JSON.stringify(text)}, expected the ${label} lane`);
    assert.ok(text.length > label.length, `${cat} printed an empty reason`);
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

// ---------------------------------------------------------------------------
// Spec 14.35: the queue's id join, pinned by the ONLY mutation that can tell it
// apart from positional binding.
//
// The 14.29 join was inline in the render path and contained
// `at = item._seen == null ? -1`. `seen` starts at 0, so 0 never equalled -1,
// `hit` stayed -1, `_seen` was never written, and EVERY row fell back to
// positional binding on every render. The suite was green the whole time,
// including a shared-mark seed whose clone "passed", because the code under
// test never executed. A guard that cannot distinguish the new code from the
// old code certifies the old code.
//
// So these run against core.js bindQueueItems, and the reorder case below is
// the one that positional binding cannot pass.
const item = (index, finding_id) => ({ index, finding_id });
const fid = (f) => core.computeFindingId(f);

test('id binding survives a re-run that reorders findings', () => {
  const A = { category: 'dialogue', issue: 'A', scene_refs: [1] };
  const B = { category: 'structure', issue: 'B', scene_refs: [2] };
  const findings = [A, B];
  const ids = findings.map(fid);

  // POSITIONAL binding answers [0, 1] here, and that is wrong: item 0 carries
  // B's id, so it must resolve to position 1.
  const bound = core.bindQueueItems([item(0, ids[1]), item(1, ids[0])], findings, ids);
  assert.deepEqual(bound, [1, 0],
    'items must follow their finding_id, not their .index');
});

test('two items sharing one content id get two different findings', () => {
  // The same quote judged by two rules is real and shipped: Rain_C courier_7
  // and gun_pen_2 both do it. computeFindingId keys on category + quote +
  // scene_key, so identical evidence collapses to one id on purpose.
  const shared = { category: 'dialogue', evidence_quote: 'the courier never blinks', scene_key: 'INT', issue: 'one' };
  const dup = { category: 'dialogue', evidence_quote: 'the courier never blinks', scene_key: 'INT', issue: 'two' };
  const findings = [shared, dup];
  const id = fid(shared);
  assert.equal(fid(dup), id, 'the fixture must actually collide, or this proves nothing');

  // indexOf() sends BOTH items to findings[0] and renders the same card twice.
  const bound = core.bindQueueItems([item(0, id), item(1, id)], findings, [id, id]);
  assert.deepEqual(bound, [0, 1],
    'the Nth item with an id must get the Nth finding carrying it');
});

test('an item with no finding_id still binds positionally', () => {
  // Older server payloads carry no id. That path must keep working.
  const findings = [{ category: 'dialogue', issue: 'A' }, { category: 'structure', issue: 'B' }];
  assert.deepEqual(core.bindQueueItems([{ index: 1 }], findings, ['nope', 'nada']), [1]);
});

test('an id that matches nothing falls back instead of dropping the row', () => {
  const findings = [{ category: 'dialogue', issue: 'A' }];
  assert.deepEqual(core.bindQueueItems([item(3, 'f-unknown')], findings, ['f-other']), [3],
    'a row must never disappear because its id could not be resolved');
});

// ---------------------------------------------------------------------------
// Spec 14.37: the membership ruling. Scene-less findings split on provenance.
test('a mechanical check with no scene is a TASK and is queued', () => {
  // "This clock jump has no slugline" cannot cite a slugline. The old rule made
  // the scene requirement circular and the row reached no card surface at all.
  assert.equal(core.findingLane({ category: 'continuity', rule_id: 'timeline_consistency' }), 'deterministic');
  assert.equal(core.findingLane({ category: 'continuity', check_id: 'unmarked_time_flip' }), 'deterministic');
  // No provenance and no scene: an opinion with nowhere to point. Not a task.
  assert.equal(core.findingLane({ category: 'dialogue' }), 'observation');
  assert.equal(core.findingLane({ category: 'continuity' }), 'observation',
    'a scene-less finding with no rule/check is still an observation');
});

test('theme and genre stay observations even WITH a scene', () => {
  assert.equal(core.findingLane({ category: 'theme', scene_refs: [1] }), 'observation');
  assert.equal(core.findingLane({ category: 'genre', scene_refs: [1] }), 'observation');
});

test('a scene-less mechanical check never becomes a silent demotion', () => {
  // It must be weighted, not parked at impact 0 like an unknown category.
  const f = { category: 'continuity', rule_id: 'timeline_consistency' };
  assert.ok(core.IMPACT.continuity > 0, 'continuity is weighed');
  assert.ok(core.rankScore(f) >= core.IMPACT.continuity * 10,
    `a queued scene-less check scores ${core.rankScore(f)}, below its own impact floor`);
});

test('a scene-less mechanical check still reaches the queue, not just a lane', () => {
  // findingLane returning a real lane is necessary but not sufficient: the
  // grouping step drops `observation` entries. This is the check that would
  // have caught the original "shown outside the queue" claim being false.
  const cut = core.groupByLane([
    { f: { category: 'continuity', rule_id: 'r' }, index: 0 },
    { f: { category: 'dialogue' }, index: 1 },
  ]);
  assert.deepEqual(cut.order, ['deterministic'],
    'the queued check is grouped; the scene-less opinion is not');
  assert.equal((cut.groups.deterministic || []).length, 1);
});
