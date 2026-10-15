// Unit tests for verificationReadoutText — the words the dock's trust line
// prints in both orientation strips. Lives in core.js so node --test can pin
// the denominator rule WITHOUT booting a browser; app.js's
// verificationReadout() delegates to it.
//
// The rule (UI audit 2026-09-20, defect #10): only quote-bearing findings sit
// in the denominator — `no_quote` rows have nothing checkable, and counting
// them manufactured "0 of 6 verified (0%)" on demo reports. A percentage over
// nothing is a lie, so the nothing case prints a count instead.
const { test } = require("node:test");
const assert = require("node:assert");
const { verificationReadoutText } =
  require("../../screenplay_studio/webapp/core.js");

test("verified + not_found share the denominator; no_quote rides beside", () => {
  assert.strictEqual(
    verificationReadoutText({ verified: 10, not_found: 3, scene_not_found: 3, no_quote: 26 }),
    "10 of 16 quotes verified (63%) \u00B7 26 carried no quote"
  );
});

test("rounds half down the way Math.round does, never invents digits", () => {
  // 13/14 = 92.857 -> 93%; the quote-less findings still ride as a clause.
  assert.strictEqual(
    verificationReadoutText({ verified: 13, not_found: 1, no_quote: 29 }),
    "13 of 14 quotes verified (93%) \u00B7 29 carried no quote"
  );
});

test("scene_not_found is a failure, not a denominator exclusion", () => {
  // 1 verified of 2 checkable (one citation pointed at scenes that do not exist)
  assert.strictEqual(
    verificationReadoutText({ verified: 1, not_found: 0, scene_not_found: 1, no_quote: 0 }),
    "1 of 2 quotes verified (50%)"
  );
});

test("all-clear prints 100% without a no_quote clause", () => {
  assert.strictEqual(
    verificationReadoutText({ verified: 2, not_found: 0, scene_not_found: 0, no_quote: 13 }),
    "2 of 2 quotes verified (100%) \u00B7 13 carried no quote"
  );
});

test("nothing checkable prints the no-quote count — never 0%", () => {
  assert.strictEqual(
    verificationReadoutText({ verified: 0, not_found: 0, scene_not_found: 0, no_quote: 6 }),
    "6 findings carried no quote to verify"
  );
  assert.strictEqual(
    verificationReadoutText({ verified: 0, not_found: 0, scene_not_found: 0, no_quote: 1 }),
    "1 finding carried no quote to verify"
  );
});

test("empty and missing blocks render nothing at all", () => {
  assert.strictEqual(verificationReadoutText(null), null);
  assert.strictEqual(verificationReadoutText(undefined), null);
  assert.strictEqual(verificationReadoutText({}), null);
  assert.strictEqual(verificationReadoutText({ verified: 0, not_found: 0 }), null);
});

test("missing fields default to 0 instead of NaN", () => {
  assert.strictEqual(
    verificationReadoutText({ verified: 2 }),
    "2 of 2 quotes verified (100%)"
  );
});
