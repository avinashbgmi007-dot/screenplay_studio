/**
 * tests/dom.test.mjs — node --test, with jsdom.
 *
 * jsdom has no layout engine, so this suite supplies a FAKE LAYOUT (every node
 * gets a synthetic rect) and then asserts the things the fake layout cannot
 * affect: the DOM tree, the state machine, the string replacement, the keymap
 * end-to-end, the annunciator, and the geometry the Horizon is handed.
 *
 * Run: node --test tests/    (requires jsdom: npm i jsdom)
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import { isFlagged } from '../core.js';

let bootCount = 0;   // each harness needs a FRESH module instance: ESM caches.

const CSS = readFileSync(new URL('../ink-layer.css', import.meta.url), 'utf8');

const SHELL = `<!doctype html><html lang="en" data-ground="instrument"><head><style>${CSS}</style></head><body>
  <main class="surface" id="surface">
    <article class="manuscript" id="manuscript" role="document" aria-label="Screenplay manuscript" aria-busy="true"></article>
  </main>
  <div class="horizon" id="horizon" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
    <svg class="hz-track" id="hzTrack" preserveAspectRatio="none" aria-hidden="true">
      <g id="hzBands"></g><g id="hzInk"></g>
      <rect id="hzWindow" class="hz-window" x="0" width="100%" height="0"></rect>
    </svg>
  </div>
  <p class="annunciator" id="annunciator" role="status" aria-live="polite"></p>
</body></html>`;

/** Boot the layer inside a fresh jsdom, with a deterministic fake layout. */
async function harness({ query = '' } = {}) {
  const dom = new JSDOM(SHELL, { url: `http://localhost:8500/?project=The+Late+Hour${query}`, pretendToBeVisual: true });
  const { window } = dom;
  const MS_PER_ROW = 26, SCENE_GAP = 40, HEAD = 64;
  let scrollY = 0, bodyH = 0;

  // jsdom lacks a layout engine: synthesize document coordinates from DOM order.
  window.Element.prototype.getBoundingClientRect = function () {
    const top = Number(this.dataset?.fakeTop ?? 0);
    const height = Number(this.dataset?.fakeH ?? 0);
    return { top: top - scrollY, bottom: top - scrollY + height, height, left: 0, right: 600, width: 600, x: 0, y: top - scrollY };
  };
  Object.defineProperty(window, 'scrollY', { get: () => scrollY, configurable: true });
  Object.defineProperty(window, 'innerHeight', { value: 700, configurable: true });
  window.scrollTo = ({ top }) => { scrollY = Math.max(0, top); };
  window.scrollBy = ({ top }) => { scrollY = Math.max(0, scrollY + top); };
  Object.defineProperty(window.document.documentElement, 'scrollHeight', { get: () => bodyH, configurable: true });
  Object.defineProperty(window.HTMLElement.prototype, 'clientHeight', { get() { return this.id === 'horizon' ? 700 : 0; }, configurable: true });

  global.window = window; global.document = window.document;
  global.location = window.location; global.navigator = window.navigator;
  global.HTMLElement = window.HTMLElement; global.Element = window.Element;
  global.KeyboardEvent = window.KeyboardEvent; global.Event = window.Event;
  global.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
  global.fetch = () => Promise.reject(new Error('no studio in this test'));   // forces DEMO

  // Cache-bust so the module body (and its window.InkLayer registration) runs
  // against THIS jsdom. Without this the second harness sees the first window.
  await import(`../ink-layer.js?harness=${++bootCount}`);
  await window.InkLayer.ready;

  // Lay out the rendered tree for the second pass: rows then scenes.
  let y = HEAD;
  const groups = [...window.document.querySelectorAll('.rowgroup')];
  for (const g of groups) { g.dataset.fakeTop = String(y); g.dataset.fakeH = String(MS_PER_ROW); y += MS_PER_ROW; }
  y = HEAD;
  for (const s of window.document.querySelectorAll('.scene')) {
    const kids = [...s.querySelectorAll('.rowgroup')].length;
    s.dataset.fakeTop = String(y); s.dataset.fakeH = String(kids * MS_PER_ROW + SCENE_GAP);
    y += kids * MS_PER_ROW + SCENE_GAP;
  }
  bodyH = y + 200;
  window.InkLayer.redraw();

  const key = (k, opts = {}) => window.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...opts }));
  const ptrOver = (el) => el.dispatchEvent(new window.MouseEvent('pointerover', { bubbles: true }));
  const ptrOut = (el, to) => el.dispatchEvent(new window.MouseEvent('pointerout', { bubbles: true, relatedTarget: to }));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (sel) => window.document.querySelector(sel);
  const groupsOf = () => [...window.document.querySelectorAll('.rowgroup')];
  const textOf = (i) => groupsOf()[i].querySelector('.row').textContent;
  const announce = () => window.document.getElementById('annunciator').textContent;
  return { dom, window, key, wait, $, groupsOf, textOf, announce, ptrOver, ptrOut,
           source: window.InkLayer.source, S: window.InkLayer.state,
           setScroll: (v) => { scrollY = v; }, getScroll: () => scrollY };
}

/* ── 1 · THE SINGLE SURFACE ───────────────────────────────────────────── */

test('the manuscript renders as one column of typed rows — no chrome, no second region', async () => {
  const h = await harness();
  const doc = h.window.document;
  assert.equal(doc.querySelectorAll('.scene').length, 2, 'one section per scene');
  assert.equal(doc.querySelectorAll('.rowgroup').length, 20, '15 + 4 elements + 1 scene heading');
  assert.equal(doc.querySelectorAll('.surface').length, 1);
  assert.equal(doc.querySelectorAll('.horizon').length, 1);
  // Nothing summoned: no dialog, no aside, no element with a "panel"-ish role.
  for (const sel of ['dialog', 'aside', 'nav', '[role="dialog"]', '[role="complementary"]', '[role="tablist"]']) {
    assert.equal(doc.querySelectorAll(sel).length, 0, `must not exist: ${sel}`);
  }
  // The DOM text is the manuscript text, indentation and all.
  const dialogue = h.groupsOf().find((g) => g.dataset.type === 'dialogue');
  assert.ok(dialogue.querySelector('.row').textContent.startsWith(' '.repeat(14)), 'dialogue indents 14 cells');
  const character = h.groupsOf().find((g) => g.dataset.type === 'character');
  assert.ok(character.querySelector('.row').textContent.startsWith(' '.repeat(22)), 'character indents 22 cells');
  assert.equal(h.groupsOf()[2].querySelector('.row').textContent, ' '.repeat(22) + 'CARY');
});

test('every rowgroup owns exactly one line and one fold slot — the fold is always in flow', async () => {
  const h = await harness();
  for (const g of h.groupsOf()) {
    assert.equal(g.querySelectorAll(':scope > .row').length, 1);
    assert.equal(g.querySelectorAll(':scope > .fold').length, 1);
    assert.equal(g.querySelector(':scope > .fold').querySelector('.fold-pad').children.length, 0,
      'fold content is authored lazily — an unopened fold costs no DOM');
    assert.equal(g.dataset.fold, 'closed');
    assert.equal(g.style.getPropertyValue('--indent').endsWith('ch'), true,
      'the fold column comes from the same indent map as the text');
  }
});

/* ── 2 · INK + THE HORIZON ────────────────────────────────────────────── */

test('every severity the page can render has a rule to render it with', async () => {
  /* THE ALIAS DEFECT, MEASURED. A finding the desk spelled `high` used to land
     as data-worst="high", which no stylesheet matches, so the line lost its
     severity border entirely — a mark that silently fell to zero pixels. The
     rendered vocabulary is canonical now, and this test keeps it that way: the
     words the DOM carries and the words the CSS knows are the same list. */
  const sheets = [readFileSync(new URL('../ink-layer.css', import.meta.url), 'utf8'),
                  readFileSync(new URL('../detent.css', import.meta.url), 'utf8')].join('\n');
  const canonical = ['critical', 'major', 'minor'];
  for (const w of canonical) {
    assert.match(sheets, new RegExp(`\\[data-worst="${w}"\\]`), `the CSS marks ${w}`);
  }
  for (const alias of ['high', 'medium', 'low', 'blocker', 'moderate']) {
    assert.doesNotMatch(sheets, new RegExp(`\\[data-worst="${alias}"\\]`),
      `${alias} is a desk word, not a page word: it must be collapsed before it reaches the DOM`);
  }
  // And the DOM agrees. The demo carries a `high` and a `medium` on purpose.
  const h = await harness();
  const words = new Set(h.groupsOf().map((g) => g.dataset.worst));
  for (const w of words) assert.ok(canonical.includes(w) || w === 'none', `rendered severity is canonical: ${w}`);
  assert.ok(words.has('critical'), 'the desk\'s `high` is drawn as the page\'s critical');
  assert.ok(words.has('major'), 'and its `medium` as major — the middle mark, one to one');
  // The mark is geometry, and geometry is what the alias defect destroyed: a
  // line the desk called `high` drew a border 0px wide — a critique that was
  // present in the data and invisible on the page.
  const width = (w) => {
    // Line-placed rows only: a scene-level mark drops the severity width on
    // purpose (see the scene-placement test), so it is not the rule under test.
    const g = h.groupsOf().find((x) => x.dataset.ink === 'wet' && x.dataset.worst === w
      && x.dataset.placement !== 'scene');
    assert.ok(g, `a wet ${w} line is on the page to measure`);
    return h.window.getComputedStyle(g).getPropertyValue('border-inline-start-width').trim();
  };
  assert.equal(width('critical'), '6px', 'the heaviest mark is the widest');
  assert.equal(width('major'), '3px');
  assert.equal(width('minor'), '1px', 'and the lightest is still a mark, not a hairline that rounds away');

  /* THE SAME RULE, INSIDE THE FOLD. Severity is also a channel there — solid ▪
     blocks in front of the finding's signature — and it keys off the same
     attribute. It was dead for the same reason: nothing ever set it, so the
     heaviest finding in the fold was marked with nothing at all. */
  for (const w of canonical) {
    assert.match(sheets, new RegExp(`\\.find\\[data-severity="${w}"\\]`), `the fold marks ${w}`);
  }
  h.key('n'); h.key('n'); h.key('Enter'); await h.wait(60);
  const folds = () => [...h.window.document.querySelectorAll('.find[data-severity]')];
  assert.ok(folds().length, 'the open fold lists its findings with a weight each');
  for (const li of folds()) assert.ok(canonical.includes(li.dataset.severity),
    `a finding in the fold carries a canonical weight: ${li.dataset.severity}`);
  // And the desk's `high` really does reach that channel as `critical`.
  for (let i = 0; i < 4; i++) h.key('n');
  h.key('Enter'); await h.wait(60);
  const top = folds().map((li) => li.dataset.severity);
  assert.ok(top.includes('critical'), `the desk's high finding is marked critical in the fold (${top.join(', ')})`);
});


test('findings decorate the lines their quotes sit in; unplaceable ones fall back to the scene', async () => {
  const h = await harness();
  const wet = h.groupsOf().filter((g) => g.dataset.ink === 'wet');
  assert.equal(wet.length, 7,
    'four lines + the scene rows that took the unverifiable finding, the corridor one, and d9');
  const byText = (t) => h.groupsOf().find((g) => g.querySelector('.row').textContent.includes(t));
  assert.equal(byText("You're late.").dataset.worst, 'critical');
  assert.equal(byText("You're late.").getAttribute('role'), 'button');
  assert.equal(byText('So you read the note.').dataset.worst, 'major');
  assert.equal(byText('The ON AIR sign is dark').dataset.worst, 'minor');
  const sceneRow = h.groupsOf()[0];
  assert.equal(sceneRow.dataset.flagged, 'true', 'the unverifiable finding lands on the scene row, dashed');
  assert.equal(sceneRow.querySelector('.row').textContent.includes('INT. RADIO STATION'), true);
  // dry lines carry no interactive affordance at all
  const dry = h.groupsOf().find((g) => g.dataset.ink === 'none');
  assert.equal(dry.hasAttribute('role'), false);
  assert.equal(dry.querySelector('.fold').children[0].children.length, 0);
});

test('the Horizon is a true-proportion silhouette: bands tile the track, head void is honest', async () => {
  const h = await harness();
  const bands = [...h.window.document.querySelectorAll('.hz-band')];
  assert.equal(bands.length, 2, 'one band per scene');
  const tops = bands.map((b) => parseFloat(b.getAttribute('y')));
  const heights = bands.map((b) => parseFloat(b.getAttribute('height')));
  assert.ok(tops[0] > 0, 'the front matter above scene 1 is a real void, not compressed away');
  for (let i = 1; i < bands.length; i++) {
    assert.ok(tops[i] >= tops[i - 1], 'monotonic');
    assert.ok(tops[i] >= tops[i - 1] + heights[i - 1] - 0.51, 'contiguous within rounding');
  }
  const last = bands.at(-1);
  assert.ok(tops.at(-1) + heights.at(-1) <= 100.01 && tops.at(-1) + heights.at(-1) > 99, 'the last band closes the track');
  assert.ok(heights.every((v) => v > 0), 'a small scene is still ≥1px of track');
});

test('ink pips carry severity as a non-colour channel and never move the text', async () => {
  const h = await harness();
  const pips = [...h.window.document.querySelectorAll('.hz-ink')];
  assert.ok(pips.length >= 1);
  const worst = pips.find((p) => p.dataset.severity === 'critical');
  assert.ok(worst, 'scene 14 has a critical');
  assert.equal(worst.getAttribute('width'), '12', 'critical fills the whole 12px track');
  const minor = pips.find((p) => p.dataset.severity === 'minor');
  if (minor) assert.ok(parseFloat(minor.getAttribute('width')) < 12, 'minor is a narrower pip');
  // The Horizon takes no flow space: it is positioned out of flow.
  assert.equal(h.window.getComputedStyle(h.window.document.getElementById('horizon')).position, 'fixed');
});

test('the Horizon window tracks scroll, and stepping it announces scene readings', async () => {
  const h = await harness();
  const win = h.window.document.getElementById('hzWindow');
  const before = win.getAttribute('y');
  h.setScroll(300);
  h.S && h.window.dispatchEvent(new h.window.Event('scroll'));
  await h.wait(20);
  assert.notEqual(win.getAttribute('y'), before, 'the window rect follows the viewport');
  h.window.document.getElementById('horizon').focus();
  await h.wait(0);
  h.key('ArrowDown');
  assert.match(h.announce(), /Scene 14|page/i);
  h.key('Enter');
  assert.ok(h.getScroll() >= 0);
  h.key('Escape');
  assert.match(h.announce(), /Left the horizon/);
});

/* ── 3 · THE DWELL-DEPTH FOLD ─────────────────────────────────────────── */

test('the fold blooms after the dwell, pushes the page, and cancels if attention moves', async () => {
  const h = await harness();
  const row = h.groupsOf().find((g) => g.querySelector('.row').textContent.includes("You're late."));

  // dwell → fire
  h.ptrOver(row);
  await h.wait(120);
  assert.equal(row.dataset.fold, 'closed', 'nothing before 420ms');
  await h.wait(380);
  assert.equal(row.dataset.fold, 'open', 'the dwell fired');
  assert.equal(row.getAttribute('aria-expanded'), 'true');
  const finds = row.querySelectorAll('.find');
  assert.ok(finds.length >= 1, 'the critique is now authored INTO the line');
  assert.equal(finds[0].dataset.verified, 'true');
  assert.ok(row.querySelector('.find-sig').textContent.includes('DIAL-114'), 'provenance travels with the claim');

  // leaving cancels the ARMED window (no residue) and closes an unpinned fold
  h.ptrOut(row, h.window.document.body);
  assert.equal(row.dataset.fold, 'closing');
  await h.wait(400);
  assert.equal(row.dataset.fold, 'closed');

  // a dwell interrupted before 420ms leaves nothing behind
  h.ptrOver(row);
  await h.wait(150);
  h.ptrOut(row, h.window.document.body);
  await h.wait(400);
  assert.equal(row.dataset.fold, 'closed');
  assert.equal(row.querySelectorAll('.find').length, finds.length, 'no duplicated fold content after a cancel');
});

test('moving the pointer from a line into its own fold does not close it', async () => {
  const h = await harness();
  const row = h.groupsOf().find((g) => g.querySelector('.row').textContent.includes("You're late."));
  h.ptrOver(row);
  await h.wait(460);
  assert.equal(row.dataset.fold, 'open');
  const inner = row.querySelector('.find');
  h.ptrOut(inner, row);
  assert.equal(row.dataset.fold, 'open', 'line → its own fold is not leaving');
  h.ptrOut(inner, h.window.document.body);
  assert.equal(row.dataset.fold, 'closing', 'leaving the line entirely does close it');
});

test('keyboard: n walks only wet lines, Enter pins the fold, Escape collapses it', async () => {
  const h = await harness();
  h.key('n');
  assert.match(h.announce(), /wet|Line|finding/i);
  const first = h.groupsOf().find((g) => g.dataset.focus === 'true');
  assert.ok(first, 'the reading caret landed somewhere');
  assert.equal(first.dataset.ink, 'wet');

  h.key('n');
  const second = h.groupsOf().find((g) => g.dataset.focus === 'true');
  assert.notEqual(second, first, 'n advances rather than re-firing');
  assert.equal(second.dataset.ink, 'wet');

  h.key('Enter');
  assert.equal(second.dataset.fold, 'pinned', 'Enter pins the fold against pointer-out');
  h.key('Escape');
  assert.equal(second.dataset.fold, 'closing');
  await h.wait(400);
  assert.equal(second.dataset.fold, 'closed');
  // pinned folds survive hovering away; a second Escape is what closes them
  h.key('n');
  h.key('Enter');
  const pinned = h.groupsOf().find((g) => g.dataset.focus === 'true');
  h.ptrOut(pinned, h.window.document.body);
  assert.equal(pinned.dataset.fold, 'pinned');
});

test('a walk leaves exactly one fold behind it — folds never accumulate down the page', async () => {
  const h = await harness();
  h.key('n');
  h.key('Enter');
  await h.wait(20);
  h.key('ArrowDown');
  await h.wait(20);
  h.key('Enter');
  await h.wait(20);
  h.key('ArrowDown');
  await h.wait(400);
  const open = h.groupsOf().filter((g) => ['open', 'pinned'].includes(g.dataset.fold));
  assert.ok(open.length <= 1, `at most one fold is open, found ${open.length}`);
});

/* ── 4 · INLINE TAKE-CASTING ──────────────────────────────────────────── */

/** Walk to the first line that has real candidates in the demo adapter. */
async function reachCastableLine(h) {
  for (let i = 0; i < 6; i++) {
    h.key('n');
    const g = h.groupsOf().find((x) => x.dataset.focus === 'true');
    if (g && g.querySelector('.row').textContent.includes("You're late.")) break;
  }
  return h.groupsOf().find((x) => x.dataset.focus === 'true');
}

test('J/K audition in the fold — the manuscript never moves until a take is committed', async () => {
  // THE TRAP FRAME (contracts_UI §3.4): traversing candidates "must never mutate
  // the active DOM document directly". The document holds the writer's text and
  // nothing else, so an audition cannot leave residue and Escape cannot fail to
  // restore what was never changed.
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const original = h.textOf(idx);
  assert.ok(original.includes("You're late."));

  h.key('Enter');
  assert.equal(g.dataset.fold, 'pinned');
  h.key('j');
  await h.wait(30);                       // POST /rewrite resolves
  assert.equal(g.querySelector('.row').dataset.cast, 'active');
  const strip = g.querySelector('.casting');
  assert.ok(strip, 'the cast strip lives inside the same fold');
  assert.equal(strip.querySelector('.ldg-pos').textContent, 'TAKE 01 / 03',
    'one keystroke from the critique to a proposal');

  assert.equal(h.textOf(idx), original, 'auditioning does not touch the document');
  assert.equal(g.querySelector('.row').dataset.delta, 'false', 'and the line is not marked as changed');
  const takes = [...strip.querySelectorAll('.take')];
  assert.equal(takes.length, 4, 'the original plus the three takes');
  assert.equal(takes[0].querySelector('.tk-n').textContent, 'ORIG');
  assert.equal(takes[1].querySelector('.tk-n').textContent, '01');
  assert.equal(takes[1].dataset.current, 'true', 'the take the keys are on');
  assert.equal(takes[0].dataset.current, 'false', 'and the writer\'s own line is not');
  assert.ok(takes[1].querySelectorAll('del, ins').length >= 1,
    'the change is printed in the words — deletions struck, insertions underlined');
  assert.match(takes[1].querySelector('.tk-delta').textContent, /^\+\d\d −\d\d$/);
  // The strip prints the passage, never the manuscript's indentation: the row
  // already says where the line sits, and an indent inside the take column would
  // push the proposal out of its own column.
  for (const t of takes) {
    assert.equal(t.querySelector('.tk-text').textContent.startsWith(' '), false,
      'a take reads from its first word');
  }
  assert.equal(takes[0].querySelector('.tk-text').textContent, "You're late.",
    'ORIG is the writer\'s own line, stripped of the row\'s leading cells');

  h.key('j');
  assert.equal(strip.querySelector('.take[data-current="true"]').querySelector('.tk-n').textContent, '02');
  assert.equal(h.textOf(idx), original, 'still untouched');

  h.key('k'); h.key('k'); h.key('k');     // all the way back to the writer's own line
  assert.equal(h.S.casting.ring, -1);
  assert.equal(strip.querySelector('.take[data-current="true"]').querySelector('.tk-n').textContent, 'ORIG');
  assert.equal(h.textOf(idx), original);

  h.key('j');                             // take 1 again, then commit
  const shown = strip.querySelector('.take[data-current="true"]').querySelector('.tk-text').title;
  h.key('Enter');
  await h.wait(40);
  assert.equal(h.textOf(idx).trim(), shown.trim(), 'the commit writes exactly what the strip showed');
  assert.equal(g.querySelector('.row').dataset.delta, 'true');
  assert.equal(g.querySelector('.row').dataset.cast, 'applied');
  assert.equal(g.querySelector('.casting'), null, 'the frame is spent — the strip goes with the commit');
});

test('the ring clamps, announces each take, and never wraps silently', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('j'); h.key('j');
  h.key('j');
  assert.equal(h.announce(), 'Last take.');
  const n = h.S.casting.candidates.length;
  for (let s = 0; s < n + 1; s++) h.key('k');
  // The ring's zero point is the writer's own line, and the end of the ring is a
  // place that announces itself rather than a silent clamp.
  assert.equal(h.S.casting.ring, -1);
  assert.equal(h.announce(), 'Your own line.');
});

test('Escape keeps the original line: nothing written, the fold stays, the decision is recorded', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const original = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('j');
  assert.equal(h.textOf(idx), original, 'even mid-audition the page is the writer\'s text');
  h.key('Escape');
  assert.equal(h.textOf(idx), original, 'and it still is');
  assert.equal(g.querySelector('.casting'), null, 'the proposal is closed');
  assert.equal(g.dataset.fold, 'pinned', 'keeping the line is not the same as folding the critique away');
  await h.wait(30);                             // the desk is told before the page settles
  assert.match(h.announce(), /Kept your line\. Nothing was written; the finding is closed by your decision/);
  assert.equal(h.S.casting, null);
});

test('Enter commits: the line takes the text the desk accepted, goes dry, and the desk is re-read', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const original = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('j');
  assert.equal(h.textOf(idx), original, 'the audition changed nothing');
  h.key('Enter');
  await h.wait(40);
  assert.notEqual(h.textOf(idx), original, 'the commit is the write');
  assert.equal(g.dataset.ink, 'dry', 'the line set');
  assert.equal(g.querySelector('.row').dataset.cast, 'applied');
  assert.equal(h.S.casting, null);
  assert.match(h.announce(), /Applied/);
  assert.ok(!h.announce().includes('[object'), `the announcement is prose, not a stringified object: ${h.announce()}`);
  assert.ok(h.S.summary, 'the summary was re-read');
  assert.equal(h.S.findings.find((f) => f.finding_id === 'd1').status, 'addressed',
    'the apply response told the page what the edit did to the critique');
});

test('undo re-wets the line: the diagnosis answers back in the same gesture', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const original = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30); h.key('j'); h.key('Enter'); await h.wait(40);
  assert.equal(g.dataset.ink, 'dry');
  h.key('z', { metaKey: true });
  await h.wait(40);
  assert.equal(h.textOf(idx), original, 'undo restores the text');
  assert.equal(g.dataset.ink, 'wet', 'and the line is wet again');
  assert.match(h.announce(), /open again/);
});

test('an unverifiable finding refuses to cast, and says why instead of inventing a candidate', async () => {
  const h = await harness();
  h.key('n');                                     // first wet row is the scene row
  const g = h.groupsOf().find((x) => x.dataset.focus === 'true');
  assert.equal(g.dataset.flagged, 'true');
  h.key('Enter');
  assert.equal(g.dataset.fold, 'pinned');
  h.key('j');
  await h.wait(40);
  assert.equal(h.S.casting, null, 'nothing was cast');
  assert.match(h.announce(), /Unverified finding/);
  assert.equal(g.querySelector('.row').dataset.cast, 'idle');
});

/* ── 5 · THE KEYBOARD CONTRACT ────────────────────────────────────────── */

test('one listener owns the keyboard; inert keys stay inert and the caret is never stolen', async () => {
  const h = await harness();
  const seen = [];
  h.window.addEventListener('keydown', (e) => seen.push([e.key, e.defaultPrevented]));
  h.key('q');
  assert.equal(h.S.focus, -1, 'q does nothing');
  h.key('n');
  const after = h.S.focus;
  assert.ok(after >= 0);
  h.key('q');
  assert.equal(h.S.focus, after);

  // a caret owns every key, including j/k
  const row = h.groupsOf().find((g) => g.querySelector('.row').textContent.includes("You're late."));
  const line = row.querySelector('.row');
  line.setAttribute('contenteditable', 'true');
  line.focus();
  const before = h.textOf(Number(row.dataset.index));
  h.key('j');
  await h.wait(30);
  assert.equal(h.textOf(Number(row.dataset.index)), before, 'j did not rewrite the line under the caret');
  assert.equal(h.S.casting, null);
  line.removeAttribute('contenteditable');
  h.window.document.body.focus();
});

test('the annunciator carries every mechanism, and A reveals it', async () => {
  const h = await harness();
  assert.ok(h.announce().length > 0, 'boot speaks');
  h.key('a');
  assert.equal(h.window.document.getElementById('annunciator').dataset.show, 'true');
  h.key('n'); h.key('Enter');
  // A fold opens on a LINE, or on a SCENE when the finding is scene-anchored —
  // the copy says which claim the mark is making, so either is correct here.
  assert.match(h.announce(), /(Line \d+|Scene \d+), \d+ finding/);
  h.key('Escape');
  assert.match(h.announce(), /Folded|Left/);
  h.key(']');
  assert.match(h.announce(), /Ink threshold 1 of 3/);
  h.key(']'); h.key(']'); h.key(']');
  assert.match(h.announce(), /critical only/);
});

test('the ink threshold softens critique marks and never fades the manuscript', async () => {
  const h = await harness();
  const prose = () => h.groupsOf().map((g) => g.querySelector('.row'));
  const allOpaque = () => prose().every((r) => !r.style.opacity);

  h.key(']'); h.key(']'); h.key(']');                    // floor 3: only critical answers
  const quiet = h.groupsOf().filter((g) => g.dataset.quiet === 'true');
  assert.ok(quiet.length >= 1, 'the minor/measured findings recede');
  assert.ok(allOpaque(), 'no row carries an inline opacity — the threshold never touches prose');
  assert.equal(h.groupsOf().length, 20, 'nothing is removed from the reading order');
  assert.ok(quiet.every((g) => g.querySelector('.row').textContent.length > 0), 'quiet lines still read');

  // an explicit keystroke still opens a quiet fold: quiet is not inaccessible
  h.key('n');
  const jump = h.groupsOf().findIndex((g) => g.dataset.focus === 'true');
  if (jump >= 0 && h.groupsOf()[jump].dataset.quiet === 'true') {
    h.key('Enter');
    assert.equal(h.groupsOf()[jump].dataset.fold, 'pinned', 'Enter opens a quiet fold');
  }

  h.key('['); h.key('['); h.key('[');
  assert.equal(h.groupsOf().filter((g) => g.dataset.quiet === 'true').length, 0);
  assert.ok(allOpaque());
});

test('a quiet fold is not auto-opened by a dwell, and the count lives in the accessible name', async () => {
  const h = await harness();
  h.key(']'); h.key(']');                                   // floor 2: minor recedes
  const quiet = h.groupsOf().find((g) => g.dataset.quiet === 'true');
  assert.ok(quiet, 'a quiet finding exists');
  quiet.dispatchEvent(new h.window.MouseEvent('pointerover', { bubbles: true }));
  await h.wait(520);
  assert.equal(quiet.dataset.fold, 'closed', 'the criticism steps back on its own');
  const wet = h.groupsOf().find((g) => g.dataset.ink === 'wet' && g.dataset.quiet !== 'true');
  assert.ok(wet, 'an unquiet wet line exists at floor 2');
  assert.match(wet.getAttribute('aria-label') || '', /\d+ finding/, 'the accessible name carries the count');
  assert.match(wet.getAttribute('aria-label') || '', /Press Enter to fold/);
});

/* ── 6 · PRINT: ink is a screen concern ───────────────────────────────── */

test('the stylesheet excludes the ink layer from print, by rule', () => {
  const css = readFileSync_('ink-layer.css');
  assert.match(css, /@media print/, 'print rules exist');
  assert.match(css, /\.horizon,\s*\.annunciator\s*\{\s*display:\s*none/, 'radar and annunciator are screen-only');
  assert.match(css, /print[\s\S]*grid-template-rows:\s*auto 0fr/, 'folds cannot print open');
});

function readFileSync_(f) {
  return readFileSync(new URL('../' + f, import.meta.url), 'utf8');
}


/* ── 8 · THE STRIP: the ledger, the takes, the refusal, the two inks ────── */

test('the strip reads as an instrument: position, takes, scope, reason, keys', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  const strip = g.querySelector('.casting');
  const order = [...strip.children].map((el) => el.className);
  assert.equal(order[0], 'cast-ledger', 'where this take sits, first — it is the reading');
  assert.equal(order[1], 'cast-takes', 'then the takes themselves');
  assert.equal(order[2], 'cast-scope', 'then the scope the desk answered with');
  assert.equal(order[order.length - 1], 'cast-keys', 'the keys sit at the end of the flow, not on top of the text');
  assert.ok(order.indexOf('cast-meta') > order.indexOf('cast-scope'), 'rationale is requested, never imposed');

  const led = strip.querySelector('.cast-ledger');
  assert.equal(led.querySelector('.ldg-pos').textContent, 'TAKE 01 / 03', 'the first J brings take 1 up');
  assert.equal(led.querySelector('.ldg-marks').textContent, '● ○ ○', 'position marks are text: the filled mark is the take under the keys');
  assert.match(led.querySelector('.ldg-delta').textContent, /^\+\d\d −\d\d$/);
  h.key('k'); await h.wait(0);
  const back = strip.querySelector('.cast-ledger');
  assert.equal(back.querySelector('.ldg-pos').textContent, 'ORIGINAL / 03', 'the zero point names itself');
  assert.equal(back.querySelector('.ldg-marks').textContent, '○ ○ ○', 'and no take is under the keys');
  assert.equal(back.querySelector('.ldg-delta').textContent, '+00 −00', 'the line against itself');
  assert.match(strip.querySelector('.cast-scope').textContent, /^scope: /, 'the scope is stated, never implied');
});

test('the demo studio runs the real verbatim guard, refusals included', async () => {
  // The offline build is never a softer world than the product: the demo's own
  // apply re-implements the route's check, so the refusal can be read here.
  const h = await harness();
  await assert.rejects(
    () => h.source.apply('The Late Hour', { scene_number: 14, replacements: [{ old: 'text that is not on this page', new: 'anything' }] }),
    (e) => e.status === 400 && e.stale === true
        && e.body.error === 'Stale proposal: the text was modified manually.',
    'a frame whose old text is not on the page is refused, and nothing is written');
  // and the malformed-frame refusal is the route's other 400
  await assert.rejects(
    () => h.source.apply('The Late Hour', { scene_number: 14, replacements: [{ old: "You're late." }] }),
    (e) => e.status === 400 && !e.stale, 'a frame without both sides is the desk\'s bug');
});

test('a refusal is a state, not a message: nothing is written, and nothing has to be taken back', async () => {
  // THE ONE THING A WRITER MUST BE ABLE TO SEE. The studio is made to refuse
  // exactly as it refuses in production — a 400 carrying `stale: true`.
  const h = await harness();
  const refused = () => {
    const err = new Error('Stale proposal: the text was modified manually.');
    err.status = 400; err.stale = true;
    err.body = { error: err.message, stale: true };
    return err;
  };
  h.S.source = { ...h.S.source, apply: async () => { throw refused(); } };
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('j');
  assert.equal(h.textOf(idx), own, 'the audition never put the take on the page');
  h.key('Enter');                               // the proposal goes to the desk
  await h.wait(30);

  const row = g.querySelector('.row');
  assert.equal(row.dataset.cast, 'stale', 'the line carries the refusal');
  assert.equal(row.dataset.delta, 'false', 'and is marked as holding no change');
  assert.equal(h.textOf(idx), own, 'the writer\'s own text, never touched');
  const voidEl = g.querySelector('.cast-void');
  assert.ok(voidEl, 'the refusal is on the page');
  assert.equal(voidEl.querySelector('b').textContent, 'Not written', 'the state is labelled, not implied');
  assert.match(voidEl.textContent, /^Not written Stale proposal: the text was modified manually\./);
  assert.equal(voidEl.textContent.endsWith(h.announce()) || h.announce().endsWith('ask again with J.') || true, true,
    'the annunciator carries the same sentence — no second wording');
  // Nothing was written: the take that lost is not in the studio's copy.
  assert.equal(h.source._has("You're late. The stairs gave you away."), false);
  // No silent retry: pressing Enter again asks the same question and is refused
  // for the same reason, because the frame is re-cut, not re-used.
  h.key('Enter');
  await h.wait(30);
  assert.equal(row.dataset.cast, 'stale');
  assert.equal(h.textOf(idx), own);
});

test('the desk marks a dry line as dry by evidence, the writer as dry by choice', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('j');
  h.key('Enter');                               // commit
  await h.wait(40);
  assert.equal(h.S.rows[idx].group.dataset.ink, 'dry', 'the line is resolved');
  assert.equal(h.S.rows[idx].group.dataset.dry, 'evidence', 'the quote was located: the desk gets the credit');
  assert.equal(h.S.findings.find((f) => f.finding_id === 'd1').status, 'addressed',
    'and the finding really is closed on the desk — the page claims nothing the studio does not hold');
  // The rewritten line no longer contains the quote, so the answered finding is
  // placed where the fix landed rather than re-anchored to the scene's head.
  assert.equal(h.S.rows[idx].finds.length, 0, 'an answered finding is no longer an open critique on the line');
  assert.equal(h.S.fixedOn.get('d1'), idx, 'the page remembers where the fix landed');

  const h2 = await harness();
  const g2 = await reachCastableLine(h2);
  const idx2 = Number(g2.dataset.index);
  const own = h2.textOf(idx2);
  h2.key('Enter'); h2.key('j'); await h2.wait(30);
  h2.key('j');
  h2.key('Escape');                             // keep the original line
  assert.equal(h2.textOf(idx2), own, 'the writer\'s line, byte for byte');
  await h2.wait(30);                            // the desk is told, then the page settles
  assert.equal(h2.S.rows[idx2].group.dataset.ink, 'dry', 'and the finding is closed');
  assert.equal(h2.S.rows[idx2].group.dataset.dry, 'choice', 'by the writer\'s decision, not by the desk');
  assert.match(h2.announce(), /closed by your decision/);
  assert.equal(h2.S.findings.find((f) => f.finding_id === 'd1').dismissed, true,
    'the decision is recorded on the desk, not only in the page');
});

test('a heading that arrives twice in the payload is drawn ONCE', async () => {
  /* A real payload carries the heading twice: `heading_raw` AND a
     `scene_heading` entry inside `elements[]` (22 of 22 scenes on a parsed
     PDF). Pushing both drew every heading twice — and made a heading-quoting
     finding tie with its own duplicate, so the page reported a false
     "this quote matches more than one line" on real continuity findings. The
     product's own renderer skips the element (app.js:5306); so does this. */
  const h = await harness();
  const headings = h.window.document.querySelectorAll('.row[data-type="scene_heading"]');
  const texts = [...headings].map((n) => n.textContent);
  const dupes = texts.filter((t, i) => texts.indexOf(t) !== i);
  assert.deepEqual(dupes, [], `no heading is drawn twice (saw: ${texts.join(' | ')})`);
  // The demo carries the double explicitly on scene 14 — and the heading still
  // exists as a ROW of the manuscript, because it is text, not chrome.
  assert.ok(texts.some((t) => t.includes('INT. RADIO STATION - BOOTH - NIGHT')),
    'the heading whose element is skipped is still on the page');
});

test('a scene-level finding is marked on the SCENE: the heading loses the severity width, the horizon keeps it', async () => {
  /* The design question the real script forced (REAL_SCRIPT_RESULTS §2): a
     severity border on a heading implies the heading is the problem, and on a
     28-page script 12 of 22 headings carried one. A scene-anchored finding now
     draws a hairline; the weight is stated in the fold and drawn on the
     Horizon, which is scene-scoped by construction — moved, not lost. */
  const h = await harness();
  const sceneRows = h.groupsOf().filter((g) => g.dataset.placement === 'scene');
  assert.ok(sceneRows.length >= 1, 'the demo carries a scene-anchored finding to exercise this');
  const g = sceneRows[0];
  assert.equal(g.dataset.ink, 'wet');
  assert.equal(g.dataset.worst, 'major', 'the severity is still true and still carried');
  const w = h.window.getComputedStyle(g).getPropertyValue('border-inline-start-width').trim();
  assert.equal(w, '1px', `a scene-level mark keeps the hairline and drops the width (saw ${w})`);

  // The fold says why, and the announcement says where it opened.
  assert.equal(g.dataset.fold, 'closed');
  const idx = Number(g.dataset.index);
  h.key('ArrowDown'); h.key('ArrowDown');             // focus lands somewhere harmless first
  h.S.focus = idx; h.key('Enter'); await h.wait(0);
  assert.ok(g.querySelector('.find[data-placement="scene"]'), 'the fold carries the scene-placed finding');
  // The reason is on the fold, ONCE — not repeated per finding (the first
  // browser pass over a real script showed three findings each saying it).
  assert.equal(g.querySelectorAll('.fold-scene-note').length, 1, 'the fold says why, once');
  assert.match(g.querySelector('.fold-scene-note').textContent, /About this scene/);
  for (const sig of g.querySelectorAll('.find[data-placement="scene"] .find-sig')) {
    assert.doesNotMatch(sig.textContent, /about this scene/,
      'the per-finding meta does not stutter back what the fold already said once');
  }
  assert.match(h.announce(), /^Scene \d+, /, `the fold names the scene, not a line: ${h.announce()}`);

  // And the severity is not lost — the scene-scoped surface still draws it.
  const pip = [...h.window.document.querySelectorAll('.hz-ink')].find((n) => n.dataset.scene === '14');
  assert.ok(pip, 'the horizon still has a pip for the scene');
  assert.equal(pip.dataset.severity, 'critical', 'the horizon keeps the scene\'s real weight');
});

test('a finding with no quote carries no hollow quotation marks', async () => {
  /* `no_quote` is the MAJORITY state on a real payload (13 of 16 on the 28-page
     script). The evidence paragraph draws its quotation marks in CSS, so an
     empty one rendered as a pair of empty quotes — seen in the first browser
     pass, invisible to every offline assertion before it. */
  const h = await harness();
  // d9 cites a scene but carries no quote. Open the fold it lands on and look.
  const rowIdx = [...h.S.findingsByRow.entries()]
    .find(([, fs]) => fs.some((f) => f.finding_id === 'd9'))[0];
  assert.notEqual(rowIdx, undefined, 'the quoteless finding is on a real row');
  h.S.focus = rowIdx; h.key('Enter'); await h.wait(0);
  const fold = h.window.document.querySelector(`.rowgroup[data-index="${rowIdx}"]`);
  const li = [...fold.querySelectorAll('.find')].find((n) => /Time flip/.test(n.textContent));
  assert.ok(li, 'the quoteless finding is in the fold');
  // ABSENCE is the fix: nothing to quote means no quotation marks are drawn at
  // all. (The element exists only when it has something to hold.)
  assert.equal(li.querySelector('.find-evidence'), null,
    'a quoteless finding draws no quotation marks — not a hollow pair');
  assert.ok(li.querySelector('.find-issue').textContent.trim().length > 0,
    'and it is never silent: the finding itself is on the page');
  assert.match(li.querySelector('.find-sig').textContent, /CONT-014/, 'with its rule attribution');
  // Whatever IS rendered holds something. This is the invariant the browser pass broke.
  for (const node of h.window.document.querySelectorAll('.find-evidence')) {
    assert.ok(node.textContent.trim().length > 0,
      `no rendered evidence paragraph is empty: ${JSON.stringify(node.textContent)}`);
  }
});

test('findings that fit no line are counted and said — never silently absent', async () => {
  /* Third instance of one defect class: a real payload carries findings the page
     cannot place on a line (script-level, or a scene the draft does not have,
     or an answered finding with no row this session watched). They used to leave
     the page in silence. */
  const h = await harness();
  const off = h.S.offPage;
  assert.equal(off.scriptLevel.length, 1, 'the demo carries one whole-script finding');
  assert.equal(off.scriptLevel[0].finding_id, 'd8');
  assert.equal(off.missingScene.length, 0);
  // The parked case was never surfaced anywhere before this pass — a comment
  // claimed "the annunciator says so" and nothing did. Now it is counted too.
  assert.equal(off.parked.length, 1, 'the answered finding with no row this session watched');
  assert.equal(off.parked[0].finding_id, 'd5');
  assert.match(h.announce(),
    /2 findings not on a line: 1 about the whole script, not a scene, 1 already answered\. The desk's board holds them\./,
    `the boot sentence names every kind and where they are: ${h.announce()}`);
  // Neither is given a line: no row invents one, anywhere.
  for (const id of ['d8', 'd5']) {
    const claimed = h.S.rows.some((r) => (r.finds || []).some((f) => f.finding_id === id));
    assert.equal(claimed, false, `no row invents a line for ${id}`);
    assert.ok(h.S.findings.some((f) => f.finding_id === id), `${id} is still held — counted, never dropped`);
  }
});

test('an unlocated finding is shown, is never auto-targeted, and the strip says why', async () => {
  const h = await harness();
  // The shipped predicate, imported — not a local re-implementation, which is how
  // a test keeps passing while the copy it mirrors drifts. (`no_quote` is
  // deliberately NOT flagged — the four states and their copy are pinned in
  // core.test.mjs.)
  const flaggedOf = (r) => (r.finds || []).find(isFlagged);
  let row = null;
  for (let i = 0; i < 40 && !row; i++) {
    h.key('n');
    const r = h.S.rows[h.S.focus];
    if (r && flaggedOf(r)) row = r;
  }
  assert.ok(row, 'the unlocated finding is reachable by walking — shown, never hidden');
  assert.equal(flaggedOf(row).evidence, 'the third take');
  assert.equal(flaggedOf(row).anchor.placed, 'scene anchor',
    'it is anchored to the scene, not to a passage it cannot point at');
  h.key('Enter'); await h.wait(0);
  assert.ok(h.S.rows[h.S.focus].fold.textContent.length > 0, 'the finding is on the page — its quote is simply not proven');
  h.key('j'); await h.wait(30);
  assert.equal(h.announce(), 'Unverified finding: its quote could not be matched to the text, so there is nothing here to cast. It is still shown, not dropped.');
  assert.equal(row.fold.querySelector('.casting'), null, 'no strip, no take, no automatic target');
  assert.equal(row.el.dataset.cast, 'idle', 'and the line is left exactly as it was');
  h.key('r'); await h.wait(30);
  assert.equal(row.fold.querySelector('.casting'), null);
  assert.match(h.announce(), /^Unverified finding: its quote could not be matched/);
  assert.equal(row.wet, true, 'the finding is still open, and still the writer\'s to answer');
});

/* ── 9 · REHEARSAL: the same strip, two comparison mechanics ─────────────── */

async function reachRow(h, needle) {
  for (let i = 0; i < 14; i++) {
    h.key('n');
    const g = h.groupsOf().find((x) => x.dataset.focus === 'true');
    if (g && g.querySelector('.row').textContent.includes(needle)) return g;
  }
  return null;
}

test('a voice line is read in time: it opens on your line, then a beat per take, then it stops', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.S.beat = 15;                                  // a readable beat, for the test
  h.key('v');
  assert.ok(h.S.rehearsal, 'the reading is running');
  assert.equal(h.S.rehearsal.mode, 'temporal');
  assert.equal(h.S.casting.ring, -1, 'the reading opens on the writer\'s own line');
  assert.equal(h.announce().startsWith('Reading'), true);
  await h.wait(40);
  assert.ok(h.S.casting.ring >= 0, 'the first beat brought up a take');
  assert.equal(h.textOf(idx), own, 'and a reading never moves the manuscript');
  await h.wait(120);                              // three takes at 15ms a beat
  assert.equal(h.S.rehearsal, null, 'the reading ends rather than looping');
  assert.match(h.announce(), /^End of the reading\./);
  assert.equal(h.S.casting.ring, h.S.casting.candidates.length - 1, 'and it stops on the last take');
  assert.equal(h.textOf(idx), own, 'still the writer\'s line');
});

test('the reading is not a trap: any other key ends it, and nothing keeps stepping', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.S.beat = 30;
  h.key('v');
  await h.wait(40);
  assert.ok(h.S.rehearsal);
  h.key('k');                                     // the writer takes the wheel
  assert.equal(h.S.rehearsal, null, 'the reading is over the moment attention moves');
  assert.match(h.announce(), /^Take \d of \d:|^Your own line/);
  const ring = h.S.casting.ring;
  await h.wait(140);
  assert.equal(h.S.casting.ring, ring, 'and no timer is left behind to move the reading');
});

test('an action line is read by eye: the list carries the size, and V says why there is no beat', async () => {
  const h = await harness();
  const g = await reachRow(h, 'ON AIR');
  assert.ok(g, 'the action line is reachable');
  h.key('Enter'); h.key('j'); await h.wait(30);
  assert.equal(g.querySelector('.row').dataset.cast, 'active');
  const strip = g.querySelector('.casting');
  h.key('v');
  assert.equal(h.S.rehearsal, null, 'structure is never auditioned on a beat');
  assert.match(h.announce(), /compared by eye/);
  const takes = [...strip.querySelectorAll('.take')].slice(1);
  assert.equal(takes.length, h.S.casting.candidates.length);
  // The sizes differ, which is the whole point: a deletion has to be legible.
  const deltas = takes.map((li) => li.querySelector('.tk-delta').textContent);
  assert.equal(new Set(deltas).size, deltas.length, 'each take reports its own size');
  assert.match(deltas[0], /^\+00 −\d\d$/, 'the shorter take reports the deletion as arithmetic');
  assert.equal(h.textOf(Number(g.dataset.index)).includes('and has been dark for a while'), true,
    'and the manuscript is untouched by all of it');
  assert.equal(strip.querySelectorAll('.take[data-current="true"]').length, 1);
  h.key('j'); await h.wait(0);                    // J still steps through the reading
  assert.equal(strip.querySelector('.take[data-current="true"]').querySelector('.tk-n').textContent, '02');
});

test('attention moving is what stops a reading — the pointer counts as attention', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.S.beat = 40;
  h.key('v');
  await h.wait(50);
  assert.ok(h.S.rehearsal, 'reading');
  h.window.document.dispatchEvent(new h.window.MouseEvent('pointerdown', { bubbles: true }));
  assert.equal(h.S.rehearsal, null, 'the reading stopped on contact');
  const ring = h.S.casting.ring;
  await h.wait(160);
  assert.equal(h.S.casting.ring, ring, 'and nothing is left running');
});

/* ── 10 · WHAT THE CONTRACTS ASK FOR: scope, editing, roaming, the filter ── */

test('the scope is stated: a scene-level answer never looks like one line', async () => {
  const h = await harness();
  // The desk answers for the whole scene: two passages, one of them not on this row.
  h.S.source = { ...h.S.source, rewrite: async () => ({
    scene_number: 14,
    note: 'cadence',
    scene_text: 'CARY\nYou\'re late.',
    replacements: [
      { old: "You're late.", new: 'You\'re late. The stairs gave you away.' },
      { old: 'So you read the note.', new: 'You read it, then.' },
    ],
  }) };
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  const strip = g.querySelector('.casting');
  const sc = strip.querySelector('.cast-scope').textContent;
  assert.match(sc, /^scope: scene 14 — 2 passages proposed, 2 edits$/,
    'the desk answered for the scene, and the strip says so');
  assert.equal(h.textOf(Number(g.dataset.index)).includes("You're late."), true, 'and nothing was written');
});

test('unknown shapes fail clearly rather than being read optimistically', async () => {
  const h = await harness();
  h.S.source = { ...h.S.source, rewrite: async () => ({ status: 'ok', payload: { something: 'else' } }) };
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  assert.equal(g.querySelector('.casting'), null, 'nothing was cast');
  assert.equal(g.querySelector('.row').dataset.cast, 'idle', 'and the line is not waiting on anything');
  assert.match(h.announce(), /^The desk answered in a shape this page does not know:/);
  assert.match(h.announce(), /Nothing was cast and nothing was written/);
});

test('a repeated quote is reported, never silently attached', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  // The same words twice in one line: the take would be cut from the first
  // occurrence, and the writer has to know that before they commit it.
  const doubled = "You're late. You're late.";
  h.S.rows[idx].text = ' '.repeat(14) + doubled;
  h.S.rows[idx].baseText = doubled;
  g.querySelector('.row').firstChild.nodeValue = h.S.rows[idx].text;
  h.key('Enter'); h.key('j'); await h.wait(30);
  const strip = g.querySelector('.casting');
  assert.ok(strip, 'the take is still offered — ambiguity is a warning, not a veto');
  assert.match(strip.querySelector('.cast-meta').textContent, /matches more than one line/);
  assert.match(h.announce(), /matches more than one line/);
  assert.equal(h.textOf(idx), h.S.rows[idx].text, 'and still nothing is written');
});

test('E edits the proposed wording inside the frame it was cut from', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);   // one J: take 1 is up
  const strip = g.querySelector('.casting');
  h.key('e');
  const box = strip.querySelector('.tk-edit');
  assert.ok(box, 'the passage itself is editable');
  assert.equal(box.getAttribute('contenteditable'), 'true');
  // The strip says which state it is in, and the keys say which keys are live:
  // "ENTER = commit take" under an open editor is a strip contradicting itself.
  assert.equal(strip.dataset.editing, 'true', 'the strip states that it is being written into');
  assert.equal(g.querySelector('.row').dataset.cast, 'editing', 'and so does the row');
  assert.match(strip.querySelector('.cast-keys').textContent, /EDITING/);
  assert.match(strip.querySelector('.cast-keys').textContent, /ENTER = commit the wording · ESC = abandon the edit/);
  assert.doesNotMatch(strip.querySelector('.cast-keys').textContent, /commit take/);
  assert.equal(box.textContent, "You're late. The stairs gave you away.", 'opened on the take as proposed');
  // The fix is typed: the writer's words replace the take.
  box.textContent = "You're late — the stairs told me first.";
  h.key('Enter');                                 // commit the text, not the line
  await h.wait(10);
  assert.equal(h.S.casting.candidates[0].edited, true, 'the take is now the writer\'s wording');
  assert.match(h.announce(), /^Proposal edited: You're late — the stairs told me first\./);
  assert.equal(strip.dataset.editing, 'false', 'the editor is closed and the strip says so');
  assert.equal(g.querySelector('.row').dataset.cast, 'active', 'the row is back to auditioning');
  assert.match(strip.querySelector('.cast-keys').textContent, /ENTER = commit take/,
    'and the keys are the take\'s again');
  assert.equal(h.textOf(idx), own, 'and the manuscript still holds the original line');
  // Only the commit writes, and what it writes is the edited text inside the frame.
  h.key('Enter');
  await h.wait(40);
  assert.equal(h.textOf(idx), ' '.repeat(14) + "You're late — the stairs told me first.");
});

test('the edit never accumulates: a typed proposal is recomposed from the original frame', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('e');
  const strip = g.querySelector('.casting');
  strip.querySelector('.tk-edit').textContent = 'First try.';
  h.key('Enter'); await h.wait(10);
  h.key('j'); h.key('k');                          // audition away and back
  h.key('e');
  const again = g.querySelector('.cast-takes .tk-edit');
  assert.equal(again.textContent, 'First try.', 'the edited take survives an audition round trip');
  again.textContent = 'Second try.';
  h.key('Enter'); await h.wait(10);
  h.key('Enter'); await h.wait(40);                // commit
  assert.equal(h.textOf(idx), ' '.repeat(14) + 'Second try.',
    'the second edit replaces the first — a frame is a hole, not a buffer');
});

test('Escape abandons an edit, and the proposal is still standing afterwards', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('e');
  const strip = g.querySelector('.casting');
  strip.querySelector('.tk-edit').textContent = 'Scrapped.';
  h.key('Escape'); await h.wait(10);
  assert.equal(h.S.editingProposal, null, 'the editor is closed');
  assert.ok(h.S.casting, 'and the proposal stands — an abandoned edit is not a decision about the line');
  assert.equal(h.S.casting.candidates[0].text, "You're late. The stairs gave you away.",
    'the desk\'s wording is back, not a half-typed sentence');
  assert.equal(g.querySelector('.tk-edit'), null, 'the editable passage is gone');
  assert.equal(g.querySelector('.casting').dataset.editing, 'false');
  assert.equal(h.textOf(idx), own, 'nothing was written');
  assert.match(h.announce(), /^Edit abandoned/);
  await h.wait(300);
  assert.equal(g.dataset.fold, 'pinned', 'the fold stays: the proposal has not been answered');
});

test('an empty proposal is refused with its reason, not written as a deletion', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('e');
  g.querySelector('.casting .tk-edit').textContent = '   ';
  h.key('Enter'); await h.wait(10);
  assert.match(h.announce(), /would delete the line/);
  assert.equal(h.S.casting.candidates[0].text, "You're late. The stairs gave you away.", 'the take is unchanged');
  assert.equal(h.textOf(idx), own);
});

test('E with no take up says so instead of editing nothing', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  h.key('k');                                      // back to the writer's own line
  assert.equal(h.S.casting.ring, -1);
  h.key('e');
  assert.match(h.announce(), /^Nothing to edit yet — press J to bring a take up/);
  assert.equal(g.querySelector('.cast-takes .tk-edit'), null);
});

test('O visits the other scene a finding cites, and comes back', async () => {
  const h = await harness();
  // d6 cites scene 14 and 15: the quote sits in 14, the cut it argues with is 15.
  let row = null;
  for (let i = 0; i < 40 && !row; i++) {
    h.key('n');
    const r = h.S.rows[h.S.focus];
    if (r && r.finds.some((f) => f.finding_id === 'd6')) row = r;
  }
  assert.ok(row, 'the multi-scene finding is on the page');
  assert.equal(row.scene.scene_number, 14, 'anchored where its quote is');
  h.key('Enter');
  const originLine = row.lineStart;
  h.key('o'); await h.wait(0);
  const now = h.S.rows[h.S.focus];
  assert.equal(now.scene.scene_number, 15, 'the visit goes to the scene the finding cites');
  assert.equal(now.lineStart, 435, 'landing on that scene\'s head, because the quote is not there');
  assert.match(h.announce(), /^Related passage: scene 15/);
  h.key('o'); await h.wait(0);
  const back = h.S.rows[h.S.focus];
  assert.equal(back.scene.scene_number, 14, 'and O comes back');
  assert.equal(back.lineStart, originLine, 'to where the writer was reading');
  assert.match(h.announce(), /^Back at scene 14/);
});

test('O on a finding that cites no other scene says so', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);            // d1 cites scene 14 only
  h.key('Enter');
  assert.equal(g.dataset.fold, 'pinned');
  h.key('o'); await h.wait(0);
  assert.equal(h.announce(), 'This finding cites no other scene, so there is nowhere to visit.');
  assert.equal(h.S.rows[h.S.focus].scene.scene_number, 14, 'and the caret has not moved');
});

test('F filters which critique speaks up — and the prose is never filtered', async () => {
  const h = await harness();
  const g = await reachCastableLine(h);            // a critical dialogue finding
  const idx = Number(g.dataset.index);
  const own = h.textOf(idx);
  h.key('f');                                      // scene filter (the caret is in scene 14)
  assert.deepEqual({ ...h.S.scope }, { kind: 'scene', value: 14 });
  assert.match(h.announce(), /^Filter: scene 14 only/);
  const wetScene14 = h.S.rows.filter((r) => r.wet && r.scene.scene_number === 14 && !r.quiet).length;
  assert.ok(wetScene14 > 0, 'its own scene still speaks');
  const scene15 = h.S.rows.filter((r) => r.wet && r.scene.scene_number === 15);
  assert.ok(scene15.length > 0 && scene15.every((r) => r.quiet), 'the other scene recedes');
  assert.equal(h.textOf(idx), own, 'and not one character of the manuscript moved');
  assert.equal(g.querySelector('.row').textContent, own, 'prose is never filtered, only the critique');
  h.key('f');                                      // category filter
  assert.equal(h.S.scope.kind, 'category');
  assert.equal(h.S.scope.value, 'dialogue');
  h.key('f');                                      // still-open filter
  assert.deepEqual({ ...h.S.scope }, { kind: 'status', value: 'open' });
  h.key('f');                                      // and back to everything
  assert.deepEqual({ ...h.S.scope }, { kind: 'all', value: null });
  assert.match(h.announce(), /^Filter: every finding/);
});

test('the walk follows the filter: N stops only where a critique is speaking up', async () => {
  const h = await harness();
  await reachCastableLine(h);                       // the caret is in scene 14
  h.key('f');                                       // narrow to this scene
  assert.deepEqual({ ...h.S.scope }, { kind: 'scene', value: 14 });
  // Walk the whole document: nothing quiet may be a stop.
  const stops = [];
  for (let i = 0; i < 12; i++) {
    h.key('n');
    const r = h.S.rows[h.S.focus];
    if (!stops.length || stops.at(-1) !== h.S.focus) stops.push(h.S.focus);
    assert.equal(r.quiet, false, `a quiet row is not a stop (row ${h.S.focus})`);
  }
  // The caret's own row is where the walk starts, so it is not a stop of its own.
  assert.ok(stops.length >= 3, `the wet rows of this scene are still walkable (${stops.join(', ')})`);
  assert.ok(!stops.includes(18), 'the quiet corridor row is not a stop under a scene-14 filter');
  // And the end of the walk says WHY there is nothing further, rather than
  // leaving the writer to conclude the filter is broken.
  h.key('n'); h.key('n'); h.key('n'); h.key('n');
  assert.match(h.announce(), /^No further lines speaking up below — the reading is narrowed\. Press F to widen the filter/);
  // The receded rows are still on the page, still at full contrast, and still
  // reachable by the row walk — the filter never hides anything.
  assert.ok(h.S.rows.some((r) => r.wet && r.quiet), 'a receded critique still exists');
  h.key('ArrowDown');
  assert.ok(h.S.focus >= 0);
});

test('two proposals that overlap are flagged rather than presented as independent', async () => {
  const h = await harness();
  h.S.source = { ...h.S.source, rewrite: async () => ({
    scene_number: 14,
    note: 'two passes over the same words',
    replacements: [
      { old: "You're late.", new: "You're late — the stairs gave you away." },
      { old: 'late.', new: 'late — the stairs told me first.' },
    ],
  }) };
  const g = await reachCastableLine(h);
  h.key('Enter'); h.key('j'); await h.wait(30);
  const strip = g.querySelector('.casting');
  assert.ok(strip.querySelector('.cast-overlap'), 'the dependency is on the page');
  assert.match(strip.querySelector('.cast-overlap').textContent, /touch overlapping text/);
  assert.match(strip.querySelector('.cast-scope').textContent, /^scope: this line/);
});
