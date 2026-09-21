// Unit tests for screenplay_studio/webapp/core.js — the pure helpers the
// browser loads as globals before app.js. Run with:  node --test tests/js/
// Zero dependencies by design (node:test) to match the no-build-step app.
const { test } = require("node:test");
const assert = require("node:assert");
const {
  fuzzyScore,
  formatMessageContent,
  escapeHtml,
  truncate,
  formatElapsed,
  fmtDuration,
  shortModelId,
  computeFindingId,
  _strHash,
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

// ---- escapeHtml: the ONE helper every innerHTML sink must route through ----
// Regression origin: a finding whose `issue` carried <img src=x onerror=...>
// executed in the app origin on project open (the Problem Board sink).

test("escapeHtml: neutralises the exact payload that was exploited", () => {
  const payload = '<img src=x onerror="window.__XSS_FIRED=1">';
  const out = escapeHtml(payload);
  assert.ok(!out.includes("<img"), "the tag must not survive as markup");
  assert.ok(!out.includes("onerror=\""), "no bare quote may survive");
  assert.ok(out.includes("&lt;img"), "should be escaped");
});

test("escapeHtml: escapes all five significant characters", () => {
  assert.strictEqual(escapeHtml("&"), "&amp;");
  assert.strictEqual(escapeHtml("<"), "&lt;");
  assert.strictEqual(escapeHtml(">"), "&gt;");
  assert.strictEqual(escapeHtml('"'), "&quot;");
  assert.strictEqual(escapeHtml("'"), "&#39;");
});

test("escapeHtml: ampersand is escaped FIRST so entities cannot be double-decoded", () => {
  // If & were replaced after <, "&lt;" input would become "&amp;lt;" — correct —
  // but a naive order would let "&lt;script&gt;" round-trip back into a tag.
  assert.strictEqual(escapeHtml("&lt;script&gt;"), "&amp;lt;script&amp;gt;");
});

test("escapeHtml: attribute-context injection is contained", () => {
  // scene refs land inside onclick="fn(0, <here>)" — a quote must not break out
  const out = escapeHtml('1" onmouseover="window.__XSS_ATTR=1');
  assert.ok(!out.includes('"'), "no raw double quote may survive");
  assert.ok(out.includes("&quot;"), "quotes must be entity-encoded");
});

test("escapeHtml: is idempotent-safe on plain text and handles non-strings", () => {
  assert.strictEqual(escapeHtml("Scene 12 — a quiet beat"), "Scene 12 — a quiet beat");
  assert.strictEqual(escapeHtml(""), "");
  assert.strictEqual(escapeHtml(null), "");
  assert.strictEqual(escapeHtml(undefined), "");
  assert.strictEqual(escapeHtml(42), "42");
});

test("_stageStep: escapes an untrusted status (attribute context)", () => {
  const out = _stageStep("Parse", '" onmouseover="window.__XSS_STEP=1');
  assert.ok(!out.includes('onmouseover="window'), "attribute must not break out");
});

// ---- computeFindingId: byte-identical to revision.py's compute_finding_id ----
// Regression origin (audit F4): the JS walked UTF-16 code units (`charCodeAt`
// over `s.length`) while Python walked code points (`for ch in s`). A surrogate
// pair therefore hashed as TWO values on one side and ONE on the other, so any
// finding whose quote or issue contained a non-BMP character got a different id
// on each side. That id is the key for the writer's marks
// (finding_marks.json), their dismissals, ghost detection, and the doctor's
// case file — so every one of those silently stopped matching. ASCII and
// BMP-accented text always agreed, which is exactly why it survived.
//
// The expected values below were generated from revision.compute_finding_id.
// The AUTHORITY on this contract is tests/e2e_browser_finding_id_parity.py,
// which compares the LIVE js against the LIVE python — that is what catches
// Python drifting away from this table, and it is what proved the round trip.
const ID_VECTORS = [
  ["ascii quote", { category: "dialogue", evidence_quote: "I am angry." }, "f1yh1zgx"],
  ["empty finding", {}, "f5xnrwm"],
  ["accents (BMP)", { category: "voice", evidence_quote: "café naïve résumé" }, "f1j8tpa4"],
  ["emoji in quote", { category: "dialogue", evidence_quote: "She smiled 😀 and left." }, "f17jmr79"],
  ["emoji in issue", { category: "theme", issue: "the theme 😀 is thin" }, "fyvgmwq"],
  ["astral in issue", { category: "voice", issue: "astral probe 𝕏 in the quote" }, "f9vdpym"],
  ["zwj family emoji", { category: "voice", evidence_quote: "the family 👨‍👩‍👧‍👦 arrives" }, "f1ky8xej"],
];

test("computeFindingId: matches the Python twin on every vector", () => {
  for (const [label, finding, expected] of ID_VECTORS) {
    assert.strictEqual(computeFindingId(finding), expected, `${label} diverged`);
  }
});

test("_strHash: folds ONE code point per character, not two code units", () => {
  // 😀 is U+1F600 — one code point, two UTF-16 code units. Compute both
  // accumulations independently and pin which one the helper implements.
  const fold = (h, cp) => (((h << 5) + h + cp) | 0) >>> 0;
  const asCodePoint = fold(5381, 0x1f600);
  const asSurrogates = fold(fold(5381, 0xd83d), 0xde00);

  assert.strictEqual(_strHash("😀"), asCodePoint,
    "a surrogate pair must hash as a single code point");
  assert.notStrictEqual(asCodePoint, asSurrogates,
    "the two accumulations really do differ — the guard is not vacuous");
  assert.notStrictEqual(_strHash("😀"), asSurrogates,
    "the pre-fix implementation hashed the halves separately");
});

test("computeFindingId: the quote tier wins over the issue tier", () => {
  const withQuote = computeFindingId({ category: "dialogue", issue: "ignored",
                                       evidence_quote: "the quote wins" });
  assert.strictEqual(withQuote, computeFindingId({ category: "dialogue",
                                                   evidence_quote: "the quote wins" }));
  assert.notStrictEqual(withQuote,
    computeFindingId({ category: "dialogue", issue: "the quote wins" }));
});
