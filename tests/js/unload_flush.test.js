// Gap 17 (unload leg) — the pagehide flush must not depend on a timer that
// cannot tell "saved" from "in flight".
//
// The bug, measured in the source rather than in a browser: the flush opened
// with `if (!ideaSaveTimer) return;`, and `saveIdeaContent()` clears that timer
// *before* sending its POST. So for the whole duration of an in-flight save the
// timer is null while the server does not yet have the writer's last lines —
// exactly the window in which closing the tab flushes nothing. The request that
// WAS in flight is the one a pagehide aborts (a normal fetch dies with the
// document; only `keepalive` survives), so the words were lost with no error.
//
// These tests extract the REAL `pagehide` listener from app.js and run it
// against a stub `api`, so they exercise the shipped handler — not a
// reimplementation of it. That is the closest this environment can get to the
// browser leg, which needs a Chromium binary (see the skip note at the bottom).
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const APP_JS = path.join(__dirname, "..", "..", "screenplay_studio", "webapp", "app.js");
const CORE_JS = path.join(__dirname, "..", "..", "screenplay_studio", "webapp", "core.js");

const core = require("../../screenplay_studio/webapp/core.js");

// --- extract the pagehide listener body from the shipped app.js ---------------
function pagehideHandlerSource() {
  const src = fs.readFileSync(APP_JS, "utf8");
  const start = src.indexOf('window.addEventListener("pagehide"');
  assert.ok(start > 0, "the pagehide listener must exist in app.js");
  // take the balanced-brace block that follows
  const open = src.indexOf("{", src.indexOf("=>", start));
  let depth = 0, i = open;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return src.slice(open + 1, i);
}

// Build a runnable handler with the state/functions it closes over.
function makeHandler({ editorText, savedText, pendingTimer }) {
  const calls = [];
  const listeners = {};
  const src = pagehideHandlerSource();
  const api = (url, opts) => {
    calls.push({ url, opts });
    return Promise.resolve({});
  };
  const $ = () => ({ value: editorText });
  const state = { currentIdea: { id: "idea_1", content: savedText }, inIdea: true };
  // The handler assigns `ideaSaveTimer = null`, so the timer has to live
  // somewhere the test can read afterwards. Passed as a holder, written back in
  // `finally` (the body has early `return`s; a plain write-back after the body
  // would be skipped by them).
  const holder = { value: pendingTimer };
  // eslint-disable-next-line no-new-func
  const factory = new Function(
    "api", "$", "state", "holder", "encodeURIComponent",
    "unloadFlushPayload", "unloadFlushUsesKeepalive",
    `return () => {
       let ideaSaveTimer = holder.value;
       try {${src}
       } finally { holder.value = ideaSaveTimer; }
     };`
  );
  const handler = factory(api, $, state, holder, encodeURIComponent,
    core.unloadFlushPayload, core.unloadFlushUsesKeepalive);
  return { handler, calls, state, get timer() { return holder.value; } };
}

test("gap 17: closing the tab mid-save still flushes the words (the measured bug)", () => {
  // The writer typed a third line; the debounce fired, so saveIdeaContent is
  // running: it cleared the timer and its POST is in flight. state.currentIdea
  // .content still holds the PREVIOUS text, so the new line is not confirmed.
  const h = makeHandler({
    editorText: "line one\nline two\nline three — not yet confirmed",
    savedText: "line one\nline two",
    pendingTimer: null,          // <-- cleared by saveIdeaContent on entry
  });

  h.handler();

  assert.strictEqual(h.calls.length, 1,
    "the old guard returned here and nothing was sent — the unconfirmed lines were lost");
  assert.match(h.calls[0].opts.body, /not yet confirmed/);
  assert.strictEqual(h.calls[0].opts.keepalive, true,
    "without keepalive this request is aborted as the document unloads");
});

test("gap 17: a pending debounce still flushes with keepalive", () => {
  const h = makeHandler({
    editorText: "fresh text",
    savedText: "",
    pendingTimer: 42,
  });
  h.handler();
  assert.strictEqual(h.calls.length, 1);
  assert.strictEqual(h.calls[0].opts.keepalive, true);
});

test("gap 17: nothing to say means no request at all", () => {
  // Text identical to the last confirmed save, and nothing scheduled.
  const h = makeHandler({ editorText: "same", savedText: "same", pendingTimer: null });
  h.handler();
  assert.strictEqual(h.calls.length, 0, "an identical, already-saved page must not POST");
});

test("gap 17: the flush cancels the pending debounce so it cannot double-send", () => {
  // If the timer survived pagehide it could fire later and POST the same text
  // again (harmless) — or, worse, fire with a stale value. It is cleared.
  const h = makeHandler({ editorText: "text", savedText: "", pendingTimer: 7 });
  h.handler();
  assert.strictEqual(h.timer, null, "the debounce must be cleared by the flush");
  assert.strictEqual(h.calls.length, 1, "exactly one request");
});

test("gap 17: no current idea / not in the idea room -> no request", () => {
  const h = makeHandler({ editorText: "x", savedText: "", pendingTimer: 1 });
  h.state.currentIdea = null;
  h.handler();
  assert.strictEqual(h.calls.length, 0);

  const h2 = makeHandler({ editorText: "x", savedText: "", pendingTimer: 1 });
  h2.state.inIdea = false;
  h2.handler();
  assert.strictEqual(h2.calls.length, 0);
});

// --- the pure rule, stated directly (so a future edit to app.js cannot silently
// --- reintroduce the timer dependency without failing a unit test) ------------

test("gap 17 rule: a null timer does not mean 'already saved'", () => {
  assert.strictEqual(core.unloadFlushPayload("b", "a", null), "b");
  assert.strictEqual(core.unloadFlushPayload("a", "a", null), null);
});

test("gap 17 rule: unknown saved text is treated as nothing confirmed", () => {
  assert.strictEqual(core.unloadFlushPayload("words", undefined, null), "words");
  assert.strictEqual(core.unloadFlushPayload("words", null, null), "words");
});

test("gap 17 rule: never send a non-string, never send an empty confirmation", () => {
  assert.strictEqual(core.unloadFlushPayload(undefined, "", null), null);
  assert.strictEqual(core.unloadFlushPayload(null, "a", 1), null);
  assert.strictEqual(core.unloadFlushPayload("", "", 1), null,
    "an empty page with a pending debounce has nothing to protect");
});

test("gap 17 rule: keepalive is used for exactly the flush payload", () => {
  assert.strictEqual(core.unloadFlushUsesKeepalive("x"), true);
  assert.strictEqual(core.unloadFlushUsesKeepalive(""), false);
  assert.strictEqual(core.unloadFlushUsesKeepalive(null), false);
});

test("gap 17: the browser leg is named as unverified here", () => {
  // Honesty: the extracted-handler tests above are not a browser run. The real
  // leg (tests/e2e_browser_export_flush.py) needs Chromium, whose download is
  // blocked in this environment. It is not in pytest's default collection.
  const cache = path.join(process.env.HOME || "", ".cache", "ms-playwright");
  const present = fs.existsSync(cache) && fs.readdirSync(cache).length > 0;
  assert.ok(!present || present, "recorded, not asserted: " + (present ? "browser present" : "no browser"));
  const e2e = fs.readFileSync(APP_JS, "utf8");
  assert.ok(e2e.includes("pagehide"), "the handler this file tests must still exist");
});
