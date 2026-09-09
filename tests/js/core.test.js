// Unit tests for screenplay_studio/webapp/core.js — the pure helpers the
// browser loads as globals before app.js. Run with:  node --test tests/js/
// Zero dependencies by design (node:test) to match the no-build-step app.
const { test } = require("node:test");
const assert = require("node:assert");
const {
  fuzzyScore,
  formatMessageContent,
  truncate,
  formatElapsed,
  fmtDuration,
  shortModelId,
  _stageStep,
} = require("../../screenplay_studio/webapp/core.js");

test("fuzzyScore: empty query matches everything equally", () => {
  assert.strictEqual(fuzzyScore("", "Anything"), 1);
});

test("fuzzyScore: exact substring outranks scattered subsequence", () => {
  const exact = fuzzyScore("revision", "Open the Revision view");
  const scattered = fuzzyScore("rvsn", "Revision view");
  assert.ok(exact >= 100, `expected substring rank >=100, got ${exact}`);
  assert.ok(scattered > 0 && scattered < exact, "subsequence should score but lose to substring");
});

test("fuzzyScore: word-start bonus outranks mid-word subsequence", () => {
  // neither label contains "bb" as a substring — pure subsequence contest
  const wordStart = fuzzyScore("bb", "Beat Board");   // both b's start words
  const midWord = fuzzyScore("bb", "alababa");        // both b's buried mid-word
  assert.ok(wordStart > midWord, `word-start ${wordStart} should beat mid-word ${midWord}`);
});

test("fuzzyScore: non-match returns 0", () => {
  assert.strictEqual(fuzzyScore("zzz", "Beat Board"), 0);
});

test("formatMessageContent: escapes HTML injection attempts", () => {
  const out = formatMessageContent('<script>alert(1)</script>');
  assert.ok(!out.includes("<script>"), "raw script tag must not survive");
  assert.ok(out.includes("&lt;script&gt;"), "should be escaped");
});

test("formatMessageContent: bold and bullets render, list wraps once", () => {
  const out = formatMessageContent("**Note**\n- one\n- two\n\nDone.");
  assert.ok(out.includes("<strong>Note</strong>"));
  assert.ok(out.includes("<ul><li>one</li><li>two</li></ul>"));
  assert.ok(out.includes("<p>Done.</p>"));
  assert.match(out, /<br>/); // blank line becomes <br>
});

test("truncate: short text untouched, long text ellipsized and whitespace-collapsed", () => {
  assert.strictEqual(truncate("short", 10), "short");
  const out = truncate("a  b\nc", 4);
  assert.strictEqual(out, "a b…"); // collapsed to "a bc"(3)? no: "a b c" -> slice
});
