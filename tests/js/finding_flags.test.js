// Kit-A/identity flags are part of the finding, including the ONE HOME deep
// queue card. Execute the SHIPPED card, queue, filter and binding functions;
// stub only unrelated progress, refresh and reload services. jsdom proves DOM and
// callbacks, NOT fold geometry, browser contrast, or native hit targets.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const { JSDOM } = require('jsdom');
const core = require('../../screenplay_studio/webapp/core.js');

const WEBAPP = join(__dirname, '../../screenplay_studio/webapp');
const APP = readFileSync(join(WEBAPP, 'app.js'), 'utf8');
const CSS = readFileSync(join(WEBAPP, 'style.css'), 'utf8');

function shippedFunction(name) {
  const start = APP.indexOf(`\nfunction ${name}(`) + 1;
  assert.ok(start > 0, `missing shipped function: ${name}`);
  const end = APP.indexOf('\n}', start);
  assert.ok(end > start, `missing top-level closing brace: ${name}`);
  return APP.slice(start, end + 2);
}

const finding = (issue, extra = {}) => ({
  category: 'dialogue', issue, scene_refs: [1], severity: 'high',
  why_it_matters: 'The consequence on the page.',
  observation: 'A checkable observation.', evidence_quote: `Quote for ${issue}`,
  verification: { status: 'verified', confidence: 1, matched_scene: 1 },
  ...extra,
});

function harness(findings, { showUngrounded = true, order, marks = {} } = {}) {
  const dom = new JSDOM('<!doctype html><html><head></head><body><main></main></body></html>');
  const { document } = dom.window;
  const style = document.createElement('style');
  style.textContent = CSS;
  document.head.appendChild(style);
  const container = document.querySelector('main');
  const ids = findings.map(core.computeFindingId);
  const items = (order || findings.map((_, i) => i)).map((index) => ({
    ...findings[index], index, finding_id: ids[index], dismissed: false,
  }));
  const state = {
    currentProject: 'finding-flags-test', findings, findingIds: ids,
    findingMarks: marks, findingStatus: {}, findingVerdicts: {},
    ghostedIds: new Set(), notes: [],
    findingFilter: { severities: ['high', 'medium', 'low'], category: null,
      scene: null, showDeferred: false, showAddressed: false },
    fixQueue: { items, dismissed_flags: [], dismissed_count: 0 },
    fixQueueShowDismissed: false, fixQueueShowUngrounded: showUngrounded,
  };
  const context = vm.createContext({ ...core, document, state,
    CATEGORY_LABELS: {}, SEVERITY_CLASS: {} });
  const functions = ['el', 'addPanel', 'verificationBadge', 'evidenceScopeLabel',
    'sharedMarkSiblings', 'noteCoversFinding', 'paintPinState', 'findingDisposition',
    'findingStatusOf', 'isAddressed', 'isFindingDismissed', 'queueItemFindingIndex', 'ungroundedRowVisible',
    'findingOnScene', 'inFindingFilter', 'queueCounts', 'findingNoteEl', 'renderFixQueuePanel'];
  // Load a helper if the shipped revision has it; on the BROKEN revision the
  // inline flat builder still runs, so failures identify absent DEEP flags,
  // not a loader error. No feature assertion is optional.
  if (APP.includes('\nfunction findingRowFlags(')) functions.push('findingRowFlags');
  for (const name of functions) {
    vm.runInContext(shippedFunction(name), context, { filename: `app.js:${name}` });
  }
  context.updateDawnMeter = () => 0;
  context.reloadFixQueue = async () => {};
  context.refreshAllFindingSurfaces = () => draw();
  context.renderManuscript = () => draw();
  function draw(lanes = true) {
    container.replaceChildren();
    context.renderFixQueuePanel(container, { lanes });
  }
  draw();
  return { dom, document, container, context, state, draw,
    card: (index) => container.querySelector(`.finding-note[data-finding-index="${index}"]`) };
}

const flags = [
  ['contested', 'row-flag-contested', 'contested', /observation.*against/i],
  ['identity_uncertain', 'row-flag-identity', 'identity?', /does not settle.*identity/i],
  ['ungrounded', 'row-flag-ungrounded', 'ungrounded', /no quote or checkable observation/i],
];

for (const [field, cls, text, reason] of flags) {
  test(`the real deep queue card displays its ${field} flag and reason`, () => {
    const h = harness([finding(`Only ${field}`, { [field]: true })]);
    const card = h.card(0);
    assert.ok(card, 'the task must reach the actual lane renderer');
    const badge = card.querySelector(`.${cls}`);
    assert.ok(badge, `${field} is delivered but has no badge on the primary deep card`);
    assert.equal(badge.textContent, text);
    assert.match(badge.title, reason);
    assert.equal(card.querySelectorAll('.row-flag').length, 1,
      'a flag must not invent the other two diagnoses');
    assert.ok(card.querySelector('.finding-deep').contains(badge));
    assert.equal(badge.closest('details, .finding-note-actions'), null,
      'the reason must be visible before an action/disclosure, not behind marks');
    assert.notEqual(h.dom.window.getComputedStyle(badge).display, 'none');
    assert.notEqual(h.dom.window.getComputedStyle(badge).visibility, 'hidden');
    assert.notEqual(h.dom.window.getComputedStyle(badge.parentElement).display, 'none');
  });
}

test('combined flags occur once each; an unflagged control spends no flag row', () => {
  const h = harness([
    finding('All reasons', { contested: true, identity_uncertain: true, ungrounded: true }),
    finding('No reasons', { contested: false, identity_uncertain: false, ungrounded: false }),
  ]);
  assert.equal(h.card(0).querySelectorAll('.row-flag').length, 3);
  for (const [, cls] of flags) assert.equal(h.card(0).querySelectorAll(`.${cls}`).length, 1);
  assert.equal(h.card(1).querySelectorAll('.row-flag, .finding-row-flags').length, 0,
    'ordinary cards must not pay another Tier 1 row for absent flags');
});

test('the actual ungrounded toggle returns a marked card, then hides it again', async () => {
  const h = harness([
    finding('Grounded control'), finding('Hidden task', { ungrounded: true }),
  ], { showUngrounded: false });
  assert.ok(h.card(0));
  assert.equal(h.card(1), null);
  h.container.querySelector('.fq-toggle-ungrounded').click();
  await new Promise(setImmediate);
  assert.equal(h.state.fixQueueShowUngrounded, true);
  assert.ok(h.card(1).querySelector('.row-flag-ungrounded'),
    'a returned ungrounded finding must state why it was hidden');
  h.container.querySelector('.fq-toggle-ungrounded').click();
  await new Promise(setImmediate);
  assert.equal(h.state.fixQueueShowUngrounded, false);
  assert.equal(h.card(1), null);
});

test('rank-reordered wire items do not exchange their card flags', () => {
  const h = harness([
    finding('Contested task', { contested: true }),
    finding('Identity task', { identity_uncertain: true }),
    finding('Ungrounded task', { ungrounded: true }),
  ], { order: [2, 0, 1] });
  for (const [index, [, cls]] of flags.entries()) {
    const card = h.card(index);
    assert.equal(card.querySelectorAll('.row-flag').length, 1);
    assert.ok(card.querySelector(`.${cls}`), `row ${index} borrowed another finding's flag`);
  }
});

test('flags preserve evidence, verification, judgment, and the single closed action row', () => {
  const h = harness([finding('A disputed note', { contested: true })]);
  const card = h.card(0);
  assert.ok(card.querySelector('.row-flag-contested'));
  for (const cls of ['finding-deep-why', 'finding-deep-observation', 'finding-deep-quote',
    'finding-deep-badge', 'finding-verdict-row', 'dock-rank-reason']) {
    assert.ok(card.querySelector(`.${cls}`), `${cls} was sacrificed to make space for flags`);
  }
  assert.equal(card.querySelectorAll('.finding-note-actions').length, 1);
  assert.equal(card.querySelector('.finding-intent-disclosure').open, false);
  assert.ok(card.querySelector('.finding-note-actions .fq-dismiss'));
});

test('the flat report retains the same three badges; shallow margin pins stay unchanged', () => {
  const f = finding('All flags', { contested: true, identity_uncertain: true, ungrounded: true });
  const h = harness([f]);
  h.draw(false);
  assert.equal(h.container.querySelectorAll('.fix-row .row-flag').length, 3);
  const pin = h.context.findingNoteEl(f, 0, { pin: true });
  assert.equal(pin.querySelectorAll('.row-flag, .finding-row-flags').length, 0);
});

test('writer-addressed and server-addressed cards carry the same visible settled state', () => {
  const f = finding('Resolved by the writer');
  const id = core.computeFindingId(f);
  const h = harness([f], { marks: { [id]: 'addressed' } });
  assert.ok(h.card(0).classList.contains('addressed'),
    'writer intent updates the ledger but the primary card still looks open');
  assert.equal(h.card(0).querySelector('.finding-note-state').textContent, 'addressed');
  delete h.state.findingMarks[id];
  h.state.findingStatus[id] = 'addressed';
  h.draw();
  assert.ok(h.card(0).classList.contains('addressed'));
  assert.equal(h.card(0).querySelector('.finding-note-state').textContent, 'addressed');
});

test('flags remain visible without verification; empty ordinary cards gain no deep block', () => {
  const bare = { evidence_quote: null, observation: null, why_it_matters: null, verification: null };
  const h = harness([
    finding('No verification yet', { ...bare, ungrounded: true }),
    finding('No additional evidence', bare),
  ]);
  assert.ok(h.card(0).querySelector('.finding-deep .row-flag-ungrounded'),
    'an ungrounded reason must not depend on a verification badge existing');
  assert.equal(h.card(0).querySelector('.finding-deep-badge'), null);
  assert.equal(h.card(1).querySelector('.finding-deep'), null,
    'an empty flags wrapper must not create a new deep block');
});
