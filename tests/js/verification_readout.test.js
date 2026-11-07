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
    "10 of 16 quotes found in the script (63%) \u00B7 26 carried no quote"
  );
});

test("rounds half down the way Math.round does, never invents digits", () => {
  // 13/14 = 92.857 -> 93%; the quote-less findings still ride as a clause.
  assert.strictEqual(
    verificationReadoutText({ verified: 13, not_found: 1, no_quote: 29 }),
    "13 of 14 quotes found in the script (93%) \u00B7 29 carried no quote"
  );
});

test("scene_not_found is a failure, not a denominator exclusion", () => {
  // 1 verified of 2 checkable (one citation pointed at scenes that do not exist)
  assert.strictEqual(
    verificationReadoutText({ verified: 1, not_found: 0, scene_not_found: 1, no_quote: 0 }),
    "1 of 2 quotes found in the script (50%)"
  );
});

test("all-clear prints 100% without a no_quote clause", () => {
  assert.strictEqual(
    verificationReadoutText({ verified: 2, not_found: 0, scene_not_found: 0, no_quote: 13 }),
    "2 of 2 quotes found in the script (100%) \u00B7 13 carried no quote"
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
    "2 of 2 quotes found in the script (100%)"
  );
});

// ---- Gap 93: the falsifiability count rides in the same breath ----
//
// The filed case: 16 findings, 3 quoted and verified, 0 with an observation.
// The old line said "3 of 3 quotes found in the script (100%) · 13 carried no quote" —
// every number true, and the sentence a writer quotes back is "100%", which is
// not what the run showed. Observation coverage is the number that corrects it.

test("observation coverage is stated beside the quote rate", () => {
  assert.strictEqual(
    verificationReadoutText({
      verified: 3, not_found: 0, scene_not_found: 0, no_quote: 13,
      observation_bearing: 0, observation_pct: 0.0,
    }),
    "3 of 3 quotes found in the script (100%) \u00B7 13 carried no quote"
      + " \u00B7 0 carried a checkable observation"
  );
});

test("a report analysed before the field existed invents no zero", () => {
  // Older reports have no observation_bearing. Printing "0 carried" for them
  // would accuse the run of a defect it was never measured for.
  const text = verificationReadoutText({ verified: 2, not_found: 0, no_quote: 4 });
  assert.strictEqual(text, "2 of 2 quotes found in the script (100%) \u00B7 4 carried no quote");
  assert.ok(text.indexOf("observation") === -1);
});

test("the nothing-checkable case still counts findings and can carry observations", () => {
  assert.strictEqual(
    verificationReadoutText({ no_quote: 16, observation_bearing: 5 }),
    "16 findings carried no quote to verify \u00B7 5 carried a checkable observation"
  );
});

test("an observation count of zero is printed, not suppressed", () => {
  // Zero is the whole point of the gap: it is a fact about falsifiability, and
  // falsy-zero handling would hide exactly the case that matters most.
  const text = verificationReadoutText({
    verified: 1, not_found: 0, no_quote: 0, observation_bearing: 0,
  });
  assert.ok(text.indexOf("0 carried a checkable observation") !== -1);
});

// Gap 10: a located quote is not necessarily the script's own words. The
// readout said "quotes verified" for both, so a reworded line counted as
// evidence of the same strength as an exact quotation.

test("gap 10: says how many of the located quotes were the script's own words", () => {
    const text = verificationReadoutText({
      verified: 3, not_found: 0, no_quote: 0, scene_not_found: 0,
      exact: 2, approximate: 1,
    });
    assert.match(text, /3 of 3 quotes found in the script/);
    assert.match(text, /2 exact/);
    assert.match(text, /1 reworded/);
});

test("gap 10: does not say 'verified' without saying what verified means", () => {
    const text = verificationReadoutText({
      verified: 1, not_found: 0, no_quote: 2, scene_not_found: 0,
      exact: 1, approximate: 0,
    });
    assert.doesNotMatch(text, /quotes verified/);
});

test("gap 10: invents no split for a report produced before the split existed", () => {
    const text = verificationReadoutText({
      verified: 2, not_found: 0, no_quote: 1, scene_not_found: 0,
    });
    assert.doesNotMatch(text, /exact/);
    assert.match(text, /2 of 2 quotes found in the script/);
});

test("gap 10: says nothing when there are no findings at all", () => {
    assert.equal(verificationReadoutText({
      verified: 0, not_found: 0, no_quote: 0, scene_not_found: 0,
      exact: 0, approximate: 0,
    }), null);
});

