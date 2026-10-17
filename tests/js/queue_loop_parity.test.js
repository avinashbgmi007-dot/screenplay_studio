// SPEC 14.54 — the keyboard loop and the ranked queue walk ONE projection.
//
// These tests execute the SHIPPED loopList() and the SHIPPED filter/admission
// functions extracted from app.js, plus the SHIPPED queueProjection() from
// core.js. The fixture that discriminates is the 14.53 probe fixture: a
// theme observation, a hidden ungrounded note and a scene-less opinion that
// the queue never renders but the old report-order loop stepped anyway.
// On the old loopList these fail with real diffs (length 6 vs 3, order [0,1]
// vs [1,0]); they must not be satisfied by re-implementing the loop here.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const core = require('../../screenplay_studio/webapp/core.js');

const APP = readFileSync(join(__dirname, '../../screenplay_studio/webapp/app.js'), 'utf8');

function shippedFunction(name) {
  const start = APP.indexOf(`\nfunction ${name}(`) + 1;
  assert.ok(start > 0, `missing shipped function: ${name}`);
  const end = APP.indexOf('\n}', start);
  assert.ok(end > start, `missing top-level closing brace: ${name}`);
  return APP.slice(start, end + 2);
}

const finding = (category, extra = {}) => ({
  category, issue: `issue ${category}`, scene_refs: [1], severity: 'high', ...extra,
});

function fixture({ findings, items, filter = {}, marks = {}, showUngrounded = false,
                   dismissedFlags = [] }) {
  const findingIds = findings.map(core.computeFindingId);
  const state = {
    findings, findingIds,
    findingFilter: {
      severities: ['high', 'medium', 'low'], category: null, scene: null,
      showDeferred: false, showAddressed: false, ...filter,
    },
    findingMarks: marks, findingStatus: {}, ghostedIds: new Set(),
    fixQueue: {
      items: items || findings.map((f, i) => ({
        index: i, finding_id: findingIds[i], dismissed: false, ungrounded: !!f.ungrounded,
      })),
      dismissed_flags: dismissedFlags,
    },
    fixQueueShowUngrounded: showUngrounded,
  };
  const context = vm.createContext({ ...core, state });
  for (const name of ['findingDisposition', 'findingAdmitted', 'findingPassesFilter',
    'isFindingDismissed', 'queueItemFindingIndex', 'ungroundedRowVisible', 'loopList']) {
    vm.runInContext(shippedFunction(name), context, { filename: `app.js:${name}` });
  }
  return { state, list: () => context.loopList() };
}

test('the loop steps the queue\u2019s lane/rank order, not report order', () => {
  // f0 line (impact 3), f1 structure (impact 5): the queue leads with Structure.
  const h = fixture({ findings: [finding('dialogue'), finding('structure')] });
  assert.deepEqual(h.list().map((e) => e.index), [1, 0]);
});

test('observations stay out of the loop exactly as out of the queue (14.37 intact)', () => {
  const h = fixture({
    findings: [
      finding('theme', { scene_refs: [2] }),                    // observation, unconditionally
      finding('continuity', { scene_refs: [], rule_id: 'CONT-1' }), // 14.37 mechanical task
      finding('genre', { scene_refs: [1] }),                    // observation
      finding('dialogue'),                                      // task
    ],
  });
  // deterministic lane (max impact 2) after line (3); the observation rows are gone.
  assert.deepEqual(h.list().map((e) => e.index), [3, 1]);
});

test('a scene-less opinion is not walked; a scene-less mechanical check is', () => {
  const h = fixture({
    findings: [
      finding('dialogue', { scene_refs: [] }),                  // opinion with nowhere to point
      finding('dialogue'),                                      // locatable
    ],
  });
  assert.deepEqual(h.list().map((e) => e.index), [1]);
});

test('hidden ungrounded rows are stepped only when the writer asks', () => {
  const findings = [finding('dialogue', { issue: 'grounded' }),
                    finding('dialogue', { issue: 'ungrounded', ungrounded: true })];
  assert.deepEqual(fixture({ findings }).list().map((e) => e.index), [0]);
  assert.deepEqual(fixture({ findings, showUngrounded: true }).list().map((e) => e.index), [0, 1]);
});

test('an ungrounded row the writer addressed bypasses the kit-A clause when admitted', () => {
  const findings = [finding('dialogue', { issue: 'grounded' }),
                    finding('dialogue', { issue: 'ungrounded', ungrounded: true })];
  const marks = { [core.computeFindingId(findings[1])]: 'addressed' };
  const h = fixture({ findings, marks, filter: { showAddressed: true } });
  assert.deepEqual(h.list().map((e) => e.index), [0, 1]);
});

test('dispositions keep their chips — open always, deferred and addressed behind theirs', () => {
  const findings = [finding('dialogue', { issue: 'open one' }),
                    finding('dialogue', { issue: 'parked one' }),
                    finding('dialogue', { issue: 'done one' })];
  const ids = findings.map(core.computeFindingId);
  const marks = { [ids[1]]: 'deferred', [ids[2]]: 'addressed' };
  assert.deepEqual(fixture({ findings, marks }).list().map((e) => e.index), [0]);
  assert.deepEqual(fixture({ findings, marks, filter: { showDeferred: true } })
    .list().map((e) => e.index), [0, 1]);
  assert.deepEqual(fixture({ findings, marks, filter: { showAddressed: true } })
    .list().map((e) => e.index), [0, 2]);
  assert.deepEqual(fixture({ findings, marks, filter: { showDeferred: true, showAddressed: true } })
    .list().map((e) => e.index), [0, 1, 2]);
});

test('a dismissed row is never walked — not even addressed, not even with its chips on', () => {
  const findings = [finding('dialogue', { issue: 'open one' }),
                    finding('dialogue', { issue: 'done one' }),
                    finding('dialogue', { issue: 'done and dismissed' })];
  const ids = findings.map(core.computeFindingId);
  const items = findings.map((f, i) => ({
    index: i, finding_id: ids[i], dismissed: i === 2, ungrounded: false,
  }));
  const marks = { [ids[1]]: 'addressed', [ids[2]]: 'addressed' };
  const h = fixture({
    findings, items, marks, filter: { showAddressed: true },
    dismissedFlags: [{ finding_id: ids[2], index: 2 }],
  });
  // 0 open and 1 finished are both admitted; 2 carries the writer's mark AND
  // the dismissal — the queue's default view and the loop both refuse it.
  assert.deepEqual(h.list().map((e) => e.index), [0, 1]);
});

test('duplicate ids bind one-to-one — never collapse, and the observation sibling stays out', () => {
  // Same category + same quote + no scene_key = one content id, three rows.
  // The middle row has no scene and no rule provenance: an observation.
  const a = finding('dialogue', { issue: 'same words' });
  const b = finding('dialogue', { issue: 'same words', scene_refs: [] });
  const c = finding('dialogue', { issue: 'same words' });
  const findings = [a, b, c];
  assert.equal(core.computeFindingId(a), core.computeFindingId(b), 'fixture must share one id');
  assert.equal(core.computeFindingId(b), core.computeFindingId(c), 'fixture must share one id');
  const id = core.computeFindingId(a);
  const items = findings.map((f, i) => ({ index: i, finding_id: id, dismissed: false, ungrounded: false }));
  const h = fixture({ findings, items });
  // Consuming binding: item k keeps finding k. A queue-order walk drops the
  // observation (1) and must still reach BOTH remaining rows — not [0] twice.
  assert.deepEqual(h.list().map((e) => e.index), [0, 2]);
});

test('severity, category and scene chips constrain the loop like the queue', () => {
  const findings = [
    finding('dialogue', { severity: 'high', issue: 'a' }),
    finding('dialogue', { severity: 'medium', issue: 'b' }),
    finding('structure', { issue: 'c' }),
    finding('dialogue', { scene_refs: [7], issue: 'd' }),
  ];
  // lane order leads with Structure (impact 5) before Line (impact 3)
  assert.deepEqual(fixture({ findings, filter: { severities: ['high'] } })
    .list().map((e) => e.index), [2, 0, 3]);
  assert.deepEqual(fixture({ findings, filter: { category: 'dialogue' } })
    .list().map((e) => e.index), [0, 1, 3]);
  assert.deepEqual(fixture({ findings, filter: { scene: 7 } })
    .list().map((e) => e.index), [3]);
});

test('an empty or failed queue fetch yields an empty walk, never a report-order fallback', () => {
  const findings = [finding('dialogue'), finding('structure')];
  assert.deepEqual(fixture({ findings, items: [] }).list(), []);
});

test('a rank-reordered payload binds each row to its OWN finding (14.55)', () => {
  // /fixqueue sorts its items by severity then act (webapp_server.py:2677),
  // so the payload's ARRAY POSITIONS disagree with item.index whenever the
  // sort moves a row — measured on the demo desk: [0,1,3,2,4]. bindQueueItems
  // returns one binding PER ITEM (bound[k] for items[k], queue_lanes.test.js
  // pins exactly that), so a consumer reading bound[item.index] pairs the
  // two reordered rows with EACH OTHER's findings. Caught in the browser on
  // the real payload: the row headed "Setup left dangling" carried the
  // character row's item (its verbs, flags and toggles) and vice versa.
  const findings = [
    finding('dialogue', { issue: 'dialogue row' }),
    finding('continuity', { issue: 'continuity row', rule_id: 'CONT-1' }),
    finding('character', { issue: 'character row' }),
    finding('plot_thread', { issue: 'setup row' }),
  ];
  const ids = findings.map(core.computeFindingId);
  const items = [                                  // severity/act sort moved 3 ahead of 2
    { index: 0, finding_id: ids[0], dismissed: false },
    { index: 1, finding_id: ids[1], dismissed: false },
    { index: 3, finding_id: ids[3], dismissed: false },
    { index: 2, finding_id: ids[2], dismissed: false },
  ];
  const proj = core.queueProjection(items, findings, ids, null);
  assert.deepEqual(proj.entries.map((e) => e.index).sort(), [0, 1, 2, 3],
    'every reordered row still reaches its own finding');
  for (const e of proj.entries) {
    // The render pairs the row's finding with the row's item through byIndex
    // (app.js: byIndex.get(entry.index)); the item it fetches must be the one
    // that binds to THIS finding, or the row wires another row's verbs.
    assert.equal(proj.byIndex.get(e.index).finding_id, ids[e.index],
      `row ${e.index} must carry its own item`);
  }
});

test('queueProjection: lane order, flatten order, and the byIndex lookup agree', () => {
  const findings = [finding('dialogue'), finding('structure')];
  const ids = findings.map(core.computeFindingId);
  const items = [
    { index: 0, finding_id: ids[0], dismissed: false },
    { index: 1, finding_id: ids[1], dismissed: false },
  ];
  const proj = core.queueProjection(items, findings, ids, null);
  assert.deepEqual(proj.order, ['structure', 'line']);
  assert.deepEqual(proj.entries.map((e) => e.index), [1, 0]);
  const flat = [];
  for (const lane of proj.order) for (const e of proj.groups[lane]) flat.push(e.index);
  assert.deepEqual(flat, proj.entries.map((e) => e.index),
    'the loop\u2019s flatten must be the render\u2019s walk order');
  assert.equal(proj.byIndex.get(0), items[0]);
  assert.equal(proj.byIndex.get(1), items[1]);
});

test('queueProjection: admission runs after binding over the full item list', () => {
  const a = finding('dialogue', { issue: 'same words' });
  const c = finding('dialogue', { issue: 'same words' });
  const id = core.computeFindingId(a);
  const items = [
    { index: 0, finding_id: id, dismissed: false },
    { index: 1, finding_id: id, dismissed: false, hidden: true },
  ];
  const proj = core.queueProjection(items, [a, c], [id, id],
    (item) => !item.hidden);
  // item 1 consumed the second occurrence before being admitted away: the
  // surviving row still binds to finding 0, not to a re-run of the counter.
  assert.deepEqual(proj.entries.map((e) => e.index), [0]);
});
