// Gap 20: a stale board used to render identically to a current one -- the desk
// was told `saved: true` and drew a board the writer no longer had. The notice
// is the fix's visible half: without it the server draws the natural order and
// the saved arrangement silently disappears from view.
const { test } = require("node:test");
const assert = require("node:assert");
const { beatboardStaleNotice } = require("../../screenplay_studio/webapp/core.js");

test("gap 20: a current board says nothing at all", () => {
  assert.equal(beatboardStaleNotice({ stale: false, saved: true }), "");
  assert.equal(beatboardStaleNotice(null), "");
});

test("gap 20: a stale board says why, and names the scenes", () => {
  const text = beatboardStaleNotice({
    stale: true,
    stale_reason: "scene 3 is a different scene now",
    changed_scenes: [3, 5],
  });
  assert.match(text, /no longer fits this script/);
  assert.match(text, /scene 3 is a different scene now/);
  assert.match(text, /Scenes affected: 3, 5/);
});

test("gap 20: it says the saved arrangement is KEPT, not lost", () => {
  const text = beatboardStaleNotice({ stale: true, stale_reason: "x" });
  assert.match(text, /kept and has not been changed/,
    "the notice must not imply the writer's arrangement was thrown away");
  assert.match(text, /Re-arrange and save to reconcile/,
    "the notice says the board is stale without saying what to do");
});

test("gap 20: it does not invent a scene list or a reason", () => {
  const text = beatboardStaleNotice({ stale: true });
  assert.doesNotMatch(text, /Scenes affected/);
  assert.match(text, /the script changed since this board was saved/);
});

test("gap 20: a long changed list is truncated, never dumped raw", () => {
  const text = beatboardStaleNotice({
    stale: true, stale_reason: "x",
    changed_scenes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  });
  assert.match(text, /Scenes affected: 1, 2, 3, 4, 5, 6, 7, 8\u2026/);
});
