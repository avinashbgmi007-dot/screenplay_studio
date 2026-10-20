// G5 preamble regressions, not a pixel/fold test. jsdom has no layout engine.
// Execute the SHIPPED queue renderer with real binding/grouping/ranking. Only
// the deep card and unrelated application services are stubs; card anatomy and
// the <900px gate remain the anchored browser runner's responsibility.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const { JSDOM, VirtualConsole } = require('jsdom');
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

const finding = (category, issue, extra = {}) => ({
  category, issue, scene_refs: [1], severity: 'high', ...extra,
});

function harness(findings, { lanes = true, filter = () => true, dismissed = 0 } = {}) {
  const cssErrors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => cssErrors.push(err.message));
  const dom = new JSDOM('<!doctype html><html><head></head><body>'
    + '<div class="dock-section"><div class="dock-section-fixqueue"></div></div>'
    + '</body></html>', { virtualConsole });
  const { document } = dom.window;
  const style = document.createElement('style');
  style.textContent = CSS;
  document.head.appendChild(style);
  assert.deepEqual(cssErrors, [], 'the shipped stylesheet must parse');
  assert.ok(style.sheet, 'stylesheet absent');
  const container = document.querySelector('.dock-section-fixqueue');
  const items = findings.map((f, index) => ({
    ...f, index, finding_id: core.computeFindingId(f), dismissed: false,
  }));
  const state = {
    findings, findingIds: findings.map(core.computeFindingId), findingMarks: {},
    fixQueue: { items, dismissed_count: dismissed },
    findingFilter: { category: null }, fixQueueShowDismissed: false,
    currentProject: 'queue-preamble-test',
  };
  const cards = [];
  let refreshes = 0;
  const context = vm.createContext({
    ...core, document, state, CATEGORY_LABELS: {},
    // These are services outside the preamble. No test below claims to verify
    // their arithmetic, card anatomy, persistence, or network behavior.
    queueCounts: (scope = items) => ({ open: scope.length, total: scope.length }),
    updateDawnMeter: () => 25,
    inFindingFilter: (item) => filter(item)
      && (!state.findingFilter.category || state.findingFilter.category === item.category),
    queueItemFindingIndex: (item) => item.index,
    findingDisposition: () => 'open', isAddressed: () => false,
    findingNoteEl: (f, index, opts) => {
      cards.push({ f, index, opts });
      const row = document.createElement('div');
      row.className = 'finding-note';
      row.dataset.findingIndex = String(index);
      row.textContent = f.issue;
      const actions = document.createElement('div');
      actions.className = 'finding-note-actions';
      row.appendChild(actions);
      return row;
    },
    refreshAllFindingSurfaces: () => { refreshes += 1; draw(); },
  });
  for (const name of ['el', 'addPanel', 'verificationBadge', 'findingRowFlags', 'renderFixQueuePanel']) {
    vm.runInContext(shippedFunction(name), context, { filename: `app.js:${name}` });
  }
  function draw() {
    container.replaceChildren();
    context.renderFixQueuePanel(container, { lanes });
  }
  draw();
  return {
    dom, document, container, state, cards,
    css: (node) => dom.window.getComputedStyle(node),
    refreshes: () => refreshes,
    panel: () => container.querySelector('.fix-queue'),
  };
}

test('ranked compaction reaches populated AND filtered-empty queues, never the flat report', () => {
  const findings = [finding('dialogue', 'A line note')];
  for (const filter of [() => true, () => false]) {
    const h = harness(findings, { filter });
    assert.ok(h.panel().classList.contains('fix-queue-ranked'),
      'the actual ranked render path did not opt in to compaction');
  }
  const flat = harness(findings, { lanes: false });
  assert.ok(!flat.panel().classList.contains('fix-queue-ranked'));
  assert.equal(flat.css(flat.panel().querySelector('.craft-panel-head')).display, 'flex');
  assert.match(flat.panel().querySelector('.craft-panel-title').textContent, /^Fix queue/);
  assert.equal(flat.panel().querySelectorAll('.fix-row').length, 1);
});

test('ranked preamble retains counts, visible caveat, progress, both toggles and Dismiss explanation', () => {
  const h = harness([
    finding('dialogue', 'A grounded note'),
    finding('voice', 'An ungrounded note', { ungrounded: true }),
  ], { dismissed: 3 });
  const head = h.panel().querySelector('.craft-panel-head');
  assert.equal(head.querySelector('.craft-panel-title').textContent,
    '2 open / 2 shown / 2 total');
  const caveat = head.querySelector('.dock-section-hint');
  assert.equal(caveat.textContent, 'impact weights uncalibrated');
  assert.notEqual(h.css(caveat).display, 'none');
  assert.notEqual(h.css(caveat).visibility, 'hidden');
  assert.equal(head.querySelector('.dawn-pct').textContent, '25%');
  assert.equal(head.querySelector('.dawn-fill').style.width, '25%');
  const toggles = head.querySelector('.fix-queue-toggles');
  assert.ok(toggles, 'toggles must share one wrapping row, not two grid rows');
  assert.equal(toggles.querySelectorAll('button').length, 2);
  assert.match(toggles.querySelector('.fq-toggle-dismissed').textContent, /3/);
  assert.match(toggles.querySelector('.fq-toggle-ungrounded').textContent, /1/);
  assert.match(h.panel().querySelector(':scope > .finding-intent-hint').textContent,
    /Dismiss.*to-do.*report/);
  for (const { opts } of h.cards) {
    assert.equal(opts.deep, true, 'compaction must not substitute a shallow card');
    assert.equal(opts.collapseIntents, true);
  }
});

test('every populated lane shares its heading with its first category, later categories stay beside their rows', () => {
  const h = harness([
    finding('voice', 'Voice note'), finding('subtext', 'Subtext note'),
    finding('structure', 'Structure note'),
  ]);
  const groups = [...h.panel().querySelectorAll('.dock-lane-group')];
  assert.deepEqual(groups.map((g) => g.dataset.lane), ['structure', 'line']);
  for (const group of groups) {
    const heading = group.querySelector(':scope > .dock-lane-head');
    assert.ok(heading, 'lane title/category still spend separate pre-card rows');
    assert.ok(heading.querySelector('.dock-lane-title'));
    assert.equal(heading.querySelectorAll('.dock-lane-cat').length, 1);
    assert.ok(group.querySelector('.finding-note'));
  }
  const line = groups[1];
  assert.equal(line.querySelector('.dock-lane-head .dock-lane-cat').dataset.category, 'voice');
  assert.deepEqual([...line.querySelector('.dock-finding-list').children].map((n) =>
    n.classList.contains('finding-note') ? n.textContent : n.dataset.category),
  ['Voice noteDismissLine, impact 3', 'subtext',
    'Subtext noteDismissLine, impact 3']);
});

test('relocated category chips still narrow AND widen through the shared refresh entry point', () => {
  const h = harness([
    finding('structure', 'Structure note'), finding('dialogue', 'Line note'),
  ]);
  const chip = () => h.panel().querySelector('.dock-lane-cat[data-category="structure"]');
  chip().click();
  assert.equal(h.state.findingFilter.category, 'structure');
  assert.equal(h.refreshes(), 1);
  assert.equal(h.panel().querySelectorAll('.finding-note').length, 1);
  chip().click();
  assert.equal(h.state.findingFilter.category, null);
  assert.equal(h.refreshes(), 2);
  assert.equal(h.panel().querySelectorAll('.finding-note').length, 2);
});

test('filtered-out lanes and observations do not leave empty headers ahead of the admitted row', () => {
  const h = harness([
    finding('structure', 'Hidden by severity', { severity: 'low' }),
    finding('theme', 'Observation with scene refs'),
    finding('dialogue', 'The sole admitted note'),
    finding('continuity', 'Scene-less opinion', { scene_refs: [] }),
  ], { filter: (item) => item.severity === 'high' });
  const groups = [...h.panel().querySelectorAll('.dock-lane-group')];
  assert.deepEqual(groups.map((g) => g.dataset.lane), ['line']);
  assert.equal(groups[0].querySelectorAll('.finding-note').length, 1);
});

test('compaction CSS matches the real first lane, preserves later separation, and leaves card width alone', () => {
  const h = harness([
    finding('structure', 'Structure note'), finding('dialogue', 'Line note'),
  ]);
  const panel = h.panel();
  const head = panel.querySelector('.craft-panel-head');
  const headCSS = h.css(head);
  assert.equal(headCSS.display, 'grid', 'the ranked header still stacks three flex rows');
  assert.equal(headCSS.gridTemplateColumns, 'minmax(0, 1fr) auto');
  assert.equal(headCSS.paddingBottom, '0px');
  assert.equal(headCSS.borderBottomWidth, '0px');
  assert.equal(h.css(head.querySelector('.craft-panel-title')).gridColumn, '1 / -1');
  assert.equal(h.css(head.querySelector('.dock-section-hint')).paddingLeft, '0px');
  assert.equal(h.css(head.querySelector('.dawn-track')).width, '44px');
  const groups = panel.querySelectorAll('.dock-lane-group');
  assert.equal(h.css(groups[0]).marginTop, '0px',
    ':first-of-type misses the lane because the panel header is an earlier div');
  assert.equal(h.css(groups[0]).paddingTop, '0px');
  assert.equal(h.css(groups[0]).borderTopWidth, '0px');
  assert.equal(h.css(groups[1]).marginTop, '14px');
  assert.equal(h.css(groups[1]).paddingTop, '10px');
  for (const group of groups) {
    const heading = group.querySelector('.dock-lane-head');
    assert.equal(h.css(heading).display, 'flex');
    assert.equal(h.css(heading).position, 'sticky', 'lane identity must still follow its rows');
    assert.equal(h.css(heading.querySelector('.dock-lane-title')).marginBottom, '0px');
  }
  const flat = harness([finding('dialogue', 'Flat note')], { lanes: false });
  assert.equal(h.css(panel).paddingLeft, flat.css(flat.panel()).paddingLeft,
    'horizontal padding is the already-green card/verb width budget');
  assert.equal(h.css(panel).paddingRight, flat.css(flat.panel()).paddingRight);
});
