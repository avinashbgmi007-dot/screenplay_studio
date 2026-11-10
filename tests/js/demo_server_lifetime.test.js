// Gap 90: switching back to a real provider does not stop the in-process demo
// server, because tabs may still be using it. The connection card must disclose
// that process lifetime instead of implying the listener ended with demo mode.
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

const source = readFileSync(
  path.join(__dirname, "../../screenplay_studio/webapp/app.js"), "utf8",
);
const start = source.indexOf("function renderConnCard() {");
const end = source.indexOf("\n}\n\n// ---------- projects", start);
assert.notEqual(start, -1, "connection card renderer exists");
assert.notEqual(end, -1, "connection card renderer has a clear boundary");
const makeRenderConnCard = new Function(
  "$", "state", "escapeHtml",
  `${source.slice(start, end + 2)}; return renderConnCard;`,
);

function render(demo) {
  const card = { hidden: true, innerHTML: "" };
  const state = {
    config: { demo_model: demo, server_url: "http://127.0.0.1:8099" },
    connState: { ok: true, models: [] },
  };
  makeRenderConnCard((selector) => selector === "#conn-card" ? card : null,
    state, (value) => String(value))();
  return card.innerHTML;
}

test("demo connection card discloses the server outlives a model switch", () => {
  const html = render(true);
  assert.match(html, /Switching models does not stop this in-process demo server/);
  assert.match(html, /until this Studio process exits/);
});

test("real-provider card does not show a demo-server lifetime notice", () => {
  assert.doesNotMatch(render(false), /demo server|Studio process exits/);
});
