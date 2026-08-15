"""
Setup/Payoff ledger — the end-of-pipeline whole-script audit.

The Principles Engine judges each mechanically-flagged candidate from its
own mentions alone: "was THIS object/promise significant, and was it paid
off?" It cannot see the arc. This pass is the complementary view and it runs
LAST, when the whole script's shape is available: the model gets the
scene-by-scene overview of the entire screenplay plus the mechanically
extracted candidate list, and produces a ledger — for every setup it can see
(seeded candidates AND setups the extractor missed: thematic promises,
single-scene emphasis that never pays), where it was set up, where (if
anywhere) it was paid off, and an honest status: paid / dangling / abandoned
/ red herring.

This is deliberately a diagnosis-only output: the ledger says what's set up
and what never comes back. Proposing fixes stays in the conversational
layer, where the writer can ask for it.

Dangling entries are folded back into the findings (category plot_thread,
rule setup_payoff_general) so they land in the Fix Queue — deduped against
the Principles Engine's per-candidate findings so the same promise isn't
reported twice.
"""

from __future__ import annotations

from . import prompts
from .grammar import setup_payoff_ledger_grammar

# Cap total ledger entries so a long script's overview + a greedy model can't
# blow the output budget or the grammar's patience.
MAX_LEDGER_ENTRIES = 12

_STATUS_ORDER = {"dangling": 0, "abandoned": 1, "red_herring": 2, "paid": 3}


def _seed_candidates(kg) -> list[str]:
    """Compact seed list of mechanically-flagged candidates — props and
    dialogue promises — with the scenes they appear in, straight from the
    knowledge graph (real text, no paraphrase)."""
    seeds = []
    for p in sorted(kg.prop_candidates, key=lambda c: -c.mention_count):
        scenes = ", ".join(f"S{s}" for s in p.scenes_mentioned)
        seeds.append(f"- OBJECT \"{p.name}\" — mentioned in scenes {scenes}")
    for p in kg.promise_candidates:
        text = (p.text or "").strip()[:120]
        seeds.append(f"- PROMISE (by {p.character}, scene {p.scene_number}): \"{text}\"")
    return seeds


def run_setup_payoff_ledger(
    overview: str,
    kg,
    client,
    rules_fragment: str = "",
    total_scenes: int = 0,
    language: str = "eng",
) -> tuple[list[dict], list[str]]:
    """One whole-script call producing the setup/payoff ledger.

    Returns (entries, errors). entries is a list of:
      {setup, kind, setup_scenes, payoff_scenes (list|None), status, note}
    status is one of paid | dangling | abandoned | red_herring.
    """
    seeds = _seed_candidates(kg)
    seed_block = "\n".join(seeds) if seeds else (
        "(none mechanically flagged — judge from the overview alone)"
    )
    system, user = prompts.setup_payoff_ledger_prompt(
        overview, seed_block, rules_fragment, total_scenes, language=language
    )
    try:
        data = client.chat_json(
            system, user,
            grammar=setup_payoff_ledger_grammar(),
            max_tokens=2000,
            temperature=0.3,
        )
    except Exception as e:  # LlamaServerError and any client wrapper
        return [], [f"Setup/payoff ledger failed: {e}"]

    if not isinstance(data, dict):
        return [], ["Setup/payoff ledger returned a non-object."]
    entries = data.get("ledger")
    if not isinstance(entries, list):
        return [], ["Setup/payoff ledger missing the 'ledger' list."]

    cleaned = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        setup = (e.get("setup") or "").strip()
        if not setup:
            continue
        status = e.get("status")
        if status not in ("paid", "dangling", "abandoned", "red_herring"):
            status = "dangling"  # default: flag it, don't silently drop it
        cleaned.append({
            "setup": setup[:200],
            "kind": e.get("kind") or "other",
            "setup_scenes": _int_list(e.get("setup_scenes")),
            "payoff_scenes": _int_list(e.get("payoff_scenes")) or None,
            "status": status,
            "note": (e.get("note") or "").strip()[:400],
        })
    cleaned.sort(key=lambda e: _STATUS_ORDER.get(e["status"], 9))
    return cleaned[:MAX_LEDGER_ENTRIES], []


def _int_list(value) -> list[int]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def dangling_findings(ledger: list[dict], existing_plot_thread: list[dict]) -> list[dict]:
    """Fold dangling/abandoned ledger entries into findings for the Fix Queue,
    deduped against existing plot_thread findings (e.g. the Principles
    Engine's 'Promise never fulfilled' for the same candidate)."""
    existing_texts = []
    for f in existing_plot_thread:
        issue = (f.get("issue") or "").lower()
        why = (f.get("why_it_matters") or "").lower()
        existing_texts.append(issue + " " + why)

    findings = []
    for e in ledger:
        if e.get("status") not in ("dangling", "abandoned"):
            continue
        setup = (e.get("setup") or "").strip()
        haystack = " ".join(existing_texts)
        if setup and setup.lower()[:40] in haystack:
            continue  # already reported by the Principles Engine
        label = "Setup left dangling" if e.get("status") == "dangling" else "Setup abandoned"
        findings.append({
            "category": "plot_thread",
            "rule_id": "setup_payoff_general",
            "issue": f'{label}: "{setup}"',
            "why_it_matters": e.get("note") or "Set up on the page, never paid off.",
            "severity": "medium",
            "scene_refs": e.get("setup_scenes") or [],
            "evidence_quote": None,
        })
    return findings
