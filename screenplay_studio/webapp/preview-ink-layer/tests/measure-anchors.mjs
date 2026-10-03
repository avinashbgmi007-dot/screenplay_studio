/**
 * measure-anchors.mjs — Q10's measurement, run against a live desk.
 *
 * NOT a unit test: it needs a running studio and a parsed/analysed project, so
 * it is never picked up by `node --test tests/` (the filename does not match
 * `*.test.mjs`). Run it by hand:
 *
 *   node tests/measure-anchors.mjs http://127.0.0.1:8500 Pain_3
 *
 * What it answers (OPEN_QUESTIONS_ANSWERS.md, Q10 step 2): over a REAL script
 * and a REAL findings payload —
 *   · how many findings carry a quote at all, and how many of those clear the
 *     0.72 in-scene gate;
 *   · the score distribution of the matches, and the loose / ambiguous rates;
 *   · how many lines the page actually inks (the premise the Ink Layer rests on).
 *
 * It mirrors ink-layer.js's dispatch (anchorFromFindings): cited-scene rows →
 * anchorFinding → row anchor if not loose; addressed/dismissed → parked or the
 * line the fix landed on; otherwise scene-anchored. The measurement must follow
 * the shipped path, not a friendlier one, or it measures nothing.
 */

import { normalizeFindings, anchorFinding, sevRank, canonSev, isFlagged, stripLead } from '../core.js';

const BASE = process.argv[2] || 'http://127.0.0.1:8500';
const PROJECT = process.argv[3] || 'Pain_3';
const api = (p) => fetch(`${BASE}/api/projects/${encodeURIComponent(PROJECT)}${p}`).then((r) => r.json());

const script = await api('/script');
const raw = await api('/findings');

/* Rows exactly as flatten()/mkRow() build them: the scene heading is a row of
   the manuscript, every element is a row, text is stripped of leading spaces. */
const rows = [];
for (const sc of script.scenes || []) {
  const elements = sc.elements || [];
  const heading = sc.heading_raw || (elements.find((e) => e.type === 'scene_heading') || {}).text || null;
  if (heading) rows.push({ type: 'scene_heading', baseText: stripLead(heading), scene: sc.scene_number, lineStart: null });
  for (const el of elements) {
    if (el.type === 'scene_heading') continue;   // the heading is already a row (flatten()'s rule)
    rows.push({ type: el.type, baseText: stripLead(el.text), scene: sc.scene_number, lineStart: el.line_start ?? null });
  }
}

const findings = normalizeFindings(raw);
const band = (s) => (s >= 1 ? '1.00 exact' : s >= 0.9 ? '0.90–0.99' : s >= 0.8 ? '0.80–0.89' : s >= 0.72 ? '0.72–0.79' : '<0.72 (loose)');

const stats = { total: findings.length, quoteBearing: 0, anchored: 0, sceneAnchor: 0, parked: 0, loose: 0, ambiguous: 0, scores: [], inkedRows: new Set() };
const lines = [];

for (const f of findings) {
  const refs = f.scene_refs?.length ? f.scene_refs : (f.scene != null ? [f.scene] : []);
  const sceneRows = rows.map((r, i) => ({ ...r, i })).filter((r) => refs.includes(r.scene));
  const hasQuote = !!(f.evidence || '').trim();
  if (hasQuote) stats.quoteBearing += 1;
  if (!sceneRows.length) { lines.push([f.index, f.severity, hasQuote ? 'quoted' : 'no_quote', '—', 'script-level: no band claims it'].join('\t')); continue; }

  const a = anchorFinding(sceneRows.map((r) => ({ ...r, scene: r.scene })), f);
  const status = (f.verification?.status) || (f.verified === false ? 'not_found' : 'ok-or-unknown');
  let placement;
  if (a.rowIndex >= 0 && !a.loose) {
    stats.anchored += 1;
    stats.scores.push(a.score);
    if (a.ambiguous) stats.ambiguous += 1;
    const row = sceneRows[a.rowIndex];
    stats.inkedRows.add(row.i);
    placement = `ROW ${row.i} (scene ${row.scene}, line ${row.lineStart ?? '—'})`;
  } else if (f.status === 'addressed' || f.dismissed) {
    stats.parked += 1;
    placement = 'parked (addressed/dismissed, fix not in this session)';
  } else {
    stats.sceneAnchor += 1;
    if (a.score < 0.72) stats.loose += 1;
    placement = `scene anchor (scene ${refs[0]})`;
  }
  lines.push([f.index, f.severity, hasQuote ? 'quoted' : 'no_quote', a.score.toFixed(3), `${placement}${a.ambiguous ? ' AMBIGUOUS' : ''}`].join('\t'));
}

console.log(`PROJECT ${PROJECT} · script ${script.scene_count ?? (script.scenes || []).length} scenes / ${rows.length} rows`);
console.log(`findings ${stats.total} · quote-bearing ${stats.quoteBearing} · anchored-to-a-row ${stats.anchored} · scene-anchored ${stats.sceneAnchor} (of which loose ${stats.loose}) · parked ${stats.parked}`);
console.log(`ambiguous ${stats.ambiguous} · rows inked ${stats.inkedRows.size} of ${rows.length}`);
console.log('');
console.log('idx\tsev\tquote\t\tscore\tplacement');
console.log(lines.join('\n'));
console.log('');
console.log('score distribution of row-anchored matches:');
const dist = {};
for (const s of stats.scores) { const b = band(s); dist[b] = (dist[b] || 0) + 1; }
for (const [b, n] of Object.entries(dist)) console.log(`  ${b.padEnd(14)} ${n}`);
if (stats.scores.length) {
  const avg = stats.scores.reduce((x, y) => x + y, 0) / stats.scores.length;
  console.log(`  mean ${avg.toFixed(3)} · min ${Math.min(...stats.scores).toFixed(3)} · max ${Math.max(...stats.scores).toFixed(3)}`);
}
const q = stats.quoteBearing;
console.log('');
console.log(`quote-bearing findings that reached a line: ${stats.anchored}/${q}` +
  (q ? ` (${Math.round(100 * stats.anchored / q)}%)` : ''));
console.log(`findings that can never ink a line on this payload: ${stats.total - stats.anchored} of ${stats.total}` +
  ` (${Math.round(100 * (stats.total - stats.anchored) / stats.total)}%)`);
