// Readiness guards, not a browser contrast/layout test. Pointer opacity uses
// the SHIPPED CSS. The severity tests execute the browser suite's actual probe
// with SHIPPED severity mapping; jsdom geometry/paint values are explicit test
// doubles. Native contrast and visible-card acceptance remain browser gates.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const { JSDOM } = require('jsdom');

const ROOT = join(__dirname, '../..');
const CSS = readFileSync(join(ROOT, 'screenplay_studio/webapp/style.css'), 'utf8');
const APP = readFileSync(join(ROOT, 'screenplay_studio/webapp/app.js'), 'utf8');
const READINESS = readFileSync(join(ROOT, 'tests/e2e_browser_readiness_gate.py'), 'utf8');
const mapping = APP.match(/^const SEVERITY_CLASS = (\{[^\n]+\});$/m);
assert.ok(mapping, 'the shipped severity mapping disappeared');
const SEVERITY_CLASS = vm.runInNewContext(`(${mapping[1]})`);

for (const theme of ['night', 'dawn']) {
  test(`${theme}: pointer text does not composite a semantic text token through alpha`, () => {
    const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>');
    const { document } = dom.window;
    document.body.className = theme === 'dawn' ? 'dawn' : '';
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
    const pointer = document.createElement('p');
    pointer.className = 'dock-pointer-line';
    pointer.textContent = 'The findings are in the Fix queue.';
    document.body.appendChild(pointer);
    assert.equal(dom.window.getComputedStyle(pointer).opacity, '1',
      'semantic text colour is dimmed a second time by pointer opacity');
  });
}

function probeHarness(levels = ['high', 'medium', 'low']) {
  const source = READINESS.match(/^SEVERITY_CUES_JS = r?"""([\s\S]*?)"""/m);
  assert.ok(source, 'missing the browser suite\'s severity-cue probe');
  const dom = new JSDOM('<!doctype html><body><div class="dock-lens" data-lens="evidence">'
    + '<div class="dock-section-fixqueue"></div></div></body>');
  const { document } = dom.window;
  const container = document.querySelector('.dock-section-fixqueue');
  const rows = levels.map((severity, index) => {
    const row = document.createElement('div');
    row.className = 'finding-note queue-row' + (SEVERITY_CLASS[severity] || '');
    row.dataset.findingIndex = String(index);
    // A browser supplies these computed paint/geometry values. jsdom cannot.
    row.style.borderLeft = '3px solid rgb(180, 60, 40)';
    row.getClientRects = () => [{ width: 320, height: 100 }];
    row.getBoundingClientRect = () => ({ width: 320, height: 100 });
    container.appendChild(row);
    return row;
  });
  const context = vm.createContext({
    document, SEVERITY_CLASS, state: { findings: levels.map((severity) => ({ severity })) },
    getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
  });
  const run = () => JSON.parse(JSON.stringify(vm.runInContext(`(${source[1]})()`, context)));
  return { document, container, rows, run };
}

test('the actual probe accepts all three severities, including high with no modifier', () => {
  const h = probeHarness();
  assert.equal(h.rows[0].classList.contains('sev-high'), false,
    'the shipped high-severity class is intentionally empty');
  const result = h.run();
  assert.equal(result.total, 3);
  assert.deepEqual(result.invalid, []);
  assert.deepEqual(result.levels, ['high', 'medium', 'low']);
});

test('one valid card cannot mask a wrong severity class on another', () => {
  const h = probeHarness();
  h.rows[1].classList.remove('sev-medium');
  const result = h.run();
  assert.equal(result.total, 3);
  assert.deepEqual(result.invalid.map((e) => e.index), [1]);
});

test('an absent or transparent rim cannot pass as a visible severity cue', () => {
  for (const border of ['0px solid red', '3px none red', '3px solid transparent',
    '3px solid rgba(200, 60, 40, 0)']) {
    const h = probeHarness();
    h.rows[2].style.borderLeft = border;
    assert.deepEqual(h.run().invalid.map((e) => e.index), [2], border);
  }
});

test('retired flat severity badges alone cannot satisfy the primary-card check', () => {
  const h = probeHarness([]);
  h.container.innerHTML = '<div class="fix-row"><span class="sev-badge sev-high">HIGH</span></div>';
  assert.equal(h.run().total, 0);
});

test('unknown report severity is diagnosed rather than silently blessed as high', () => {
  const h = probeHarness(['unexpected']);
  const result = h.run();
  assert.equal(result.total, 1);
  assert.deepEqual(result.invalid.map((e) => e.index), [0]);
});

test('hidden or fully faded ancestors do not supply on-screen cues', () => {
  for (const hide of [n => { n.style.display = 'none'; },
    n => { n.style.visibility = 'hidden'; }, n => { n.style.opacity = '0'; }]) {
    const h = probeHarness();
    hide(h.container);
    assert.equal(h.run().total, 0);
  }
});

test('an off-layout primary card cannot satisfy the cue check', () => {
  const h = probeHarness(['high']);
  h.rows[0].getClientRects = () => [];
  assert.equal(h.run().total, 0);
});
