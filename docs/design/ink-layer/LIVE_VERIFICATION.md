# Live verification — the audit's claims, observed against a running studio

> A dated record (2026-10-03). The ids quoted below are the ids of that day: since D1 (#8) a finding that points at a scene also carries that scene's slugline in its id, so the same finding now has a different one. See `DECISION_RECORD.md`.

**What was run.** The repo's own demo entrypoint, unmodified:

```
python3 -m screenplay_studio.webapp_demo --port 8500 --projects-dir <fresh dir> --no-token
# then: POST /api/sample   → project "The_Late_Hour"
#       POST /api/projects/The_Late_Hour/analyze   → complete in 0.17 s (in-process demo model)
```

`GET /api/health` answered `{"demo_model": true, "status": "ok"}`. The demo model is an in-process
stand-in for llama-server, so **every response below is the real route, the real pipeline and the
real stores** — only the craft model is synthetic, and the report's own text says so
(`"[demo] Sample theme finding — demo model, not a real analysis."`).

---

## 1 · `/findings` — the item shape, observed

```json
{
  "act": 2, "act_name": "Act 2", "category": "plot_thread", "dismissed": false,
  "evidence_quote": null, "finding_id": "f1gahqi6", "index": 3,
  "issue": "Setup left dangling: \"The revolver\"",
  "scene_heading": "INT. WRITER'S ROOM - NIGHT", "scene_refs": [1, 2],
  "severity": "medium", "status": "unknown",
  "verification": { "confidence": null, "matched_scene": null, "status": "no_quote" },
  "why_it_matters": "Never used."
}
```

Confirms, in one response: the **`evidence_quote`** field name; the served **`verification`**
block (with `matched_scene` and a nullable `confidence`); the **content-hash** `finding_id` shape;
**`severity: "medium"`** in the closed three-member domain (across all five rows: `low`×4,
`medium`×1 — no `critical`, no `major`); and — new from this pass — **`dismissed` rides the row**.
The `plot_thread` row also settles Q9 the hard way: the dangling setup's `scene_refs` are `[1, 2]`,
and **no `payoff_scenes` or ledger `status` rides the finding**.

## 2 · Which verification state is normal

All five findings: **`no_quote`**, `evidence_quote: null`, `status: "unknown"`. The published
`report.md` contains **zero** "unverified" badges — exactly what `report.py` does with a quoteless
state — while the summary counts it: `{'verified': 0, 'not_found': 0, 'no_quote': 5,
'scene_not_found': 0, 'quote_bearing': 0, 'verified_pct_of_quoted': None}`.

Two fields here were **not in the read-only audit**: `quote_bearing` and `verified_pct_of_quoted`.
The latter is `None` when nothing quote-bearing exists — **no denominator, no number** — rather than
a misleading `0%`. Same honesty pattern as the rest of the desk.

Under the predicate this build shipped *before* the audit, this report would have been described as
**"5 unverified"**: every finding flagged, against a published report that names none.

## 3 · The writer's intent, written and cleared

```
POST /findings/intent  {"finding_id": "f1gahqi6", "intent": "addressed"}
→ {"finding_id": "f1gahqi6", "intent": "addressed", "ok": true}
   finding_marks.json on disk:  { "f1gahqi6": "addressed" }

POST /findings/intent  {"finding_id": "f1gahqi6", "intent": null}
→ {"ok": true}
   finding_marks.json on disk:  {}
```

The vocabulary (`addressed`, `deferred`, `null` clears), the content-hash key, and the durable store
are now **observed**, not inferred. `GET /edits` likewise returned
`finding_intents: {}` alongside `findings_status`, `can_undo`, `can_redo`, `edits[]`, `last_pass` —
the payload shape the page reads on load.

## 4 · What this does NOT establish

* **Craft quality.** The findings are `[demo]` fixtures from the demo model. Nothing here measures
  the analyzer, and nothing here tests a real `llama-server`.
* **The 83 % figure.** `docs/CRITICAL_REVIEW_2026-09-18.md:399` (19/23 `no_quote`) is a real-script
  measurement; the sample agrees in kind (5/5) but is five findings, not twenty-three.
* **The page in a browser.** These are route-level observations; no human or Playwright session
  looked at the prototype rendering this data.
* **Anything outside the findings path.** Parser, co-writer, knowledge base and the desk's own test
  suite remain unread (see the audit's scope note).
