"use strict";

const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

const source = readFileSync(
  path.join(__dirname, "../../screenplay_studio/webapp/app.js"), "utf8",
);
const start = source.indexOf("function graduationTransferMessage(transfer) {");
const end = source.indexOf("\n}\n\nfunction appendGraduationTransferNote", start);
assert.notEqual(start, -1, "graduation status formatter exists");
assert.notEqual(end, -1, "graduation status formatter has a clear boundary");
const graduationTransferMessage = new Function(
  `${source.slice(start, end + 2)}; return graduationTransferMessage;`,
)();

test("graduation UI never reports failed transfer as a success", () => {
  const text = graduationTransferMessage({
    complete: false,
    premise: { status: "copied" },
    sessions: { status: "partial", expected: 2, copied: ["one"], failed: [{ id: "two" }] },
    session_pin: { status: "deferred" },
  });
  assert.match(text, /Graduation is incomplete/);
  assert.match(text, /Premise card: carried/);
  assert.match(text, /1 of 2 carried/);
  assert.match(text, /Not carried: two/);
  assert.match(text, /original idea remains available/);
  assert.doesNotMatch(text, /Graduation transfer complete/);
});

test("graduation UI distinguishes no conversation from a missing transfer", () => {
  const text = graduationTransferMessage({
    complete: true,
    premise: { status: "already_present" },
    sessions: { status: "empty", expected: 0 },
    session_pin: { status: "not_needed" },
  });
  assert.match(text, /Graduation transfer complete/);
  assert.match(text, /Saved conversation: none existed/);
  assert.doesNotMatch(text, /incomplete/);
});
