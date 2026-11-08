"""Conservative cross-rule finding deduplication.

A rule relation is only a candidate signal, not proof that two findings make
one claim. Two findings in the same scene may quote different lines, contradict
each other, or make independently reviewable judgments. This module merges only
when all of the following hold: same scene, same or directly-related rules,
non-empty evidence quotes that match exactly after trimming outer whitespace,
and matching category, scene key, and normalized issue/observation. Claims use
case/spacing/punctuation normalization only; there is no fuzzy or semantic
similarity threshold. Exact quote identity is intentional because writer verdict
IDs hash quote case and punctuation. If the evidence or claim is absent or differs,
both findings remain separate. Rule relations remain one-hop and symmetric, not
transitive: the historical KB closure put the unrelated voice rule in the same
large component and swallowed an independently reviewable finding.

A qualifying merge still keeps the complete absorbed finding in
`merged_findings` and discloses the additional rule attribution. Exact whole-row
deduplication is a separate pass (`collapse_exact_duplicates`).
"""

from __future__ import annotations

import json
import re

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def related_map(kb) -> dict[str, set[str]]:
    """The KB's related_rules graph, symmetrised.

    Symmetrised because the data is written one-directionally
    (`exposition_as_ammunition -> [on_the_nose_vs_subtext]` with no back-reference):
    a one-way read would make the merge depend on which rule happened to fire.

    Deliberately NOT closed transitively — see the module docstring.
    """
    adj: dict[str, set[str]] = {}
    for rule in kb.all():
        adj.setdefault(rule.id, set())
        for other in (rule.related_rules or []):
            adj.setdefault(rule.id, set()).add(other)
            adj.setdefault(other, set()).add(rule.id)
    return adj


def _by_name(kb) -> dict[str, str]:
    """Display name (lowercased) -> rule id.

    The passes are not consistent about what they put in `rule_id`: the
    deterministic ones write a snake_case id (`unmarked_time_flip`), the
    model-driven ones write the rule's display NAME ("On-the-Nose Dialogue vs.
    Subtext"). Accepting either is what lets one dedup cover both.
    """
    return {(rule.name or "").strip().lower(): rule.id for rule in kb.all() if rule.name}


def resolve_rule_key(rule_ref, by_name: dict[str, str], known: set[str]) -> str | None:
    """Resolve a finding's rule reference to a KB rule id, or None if it isn't one."""
    if not rule_ref:
        return None
    ref = str(rule_ref).strip()
    if ref in known:
        return ref
    return by_name.get(ref.lower())


def canonical_rule_id(rule_ref, kb=None):
    """A finding's rule reference -> that rule's knowledge-base id, or None.

    `Rule.to_prompt_fragment` prints each principle as `### <name> (source:
    <attribution>)` and never its id, so a model that cites one faithfully
    copies that whole line. Both shapes are the same grounded claim, and every
    consumer that answers "says who?" — the desk's rule button, the co-writer's
    craft block, the report's rule list — looks up by id, so resolve here once
    rather than each of them learning to accept names.

    Exact-match only, deliberately: the `character` pass is shown 83 rules, and
    promoting a near-miss would print an authority the finding does not have.
    """
    if not rule_ref:
        return None
    if kb is None:
        try:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
        except Exception:
            return None
    ref = str(rule_ref).strip()
    known = {r.id for r in kb.all()}
    by_name = _by_name(kb)
    # Cut the attribution at the prompt's own marker, not at a bracket: an
    # attribution can itself contain parentheses.
    return (resolve_rule_key(ref, by_name, known)
            or resolve_rule_key(ref.split(" (source:", 1)[0].strip(), by_name, known))


def directly_related(adj: dict[str, set[str]], a: str | None, b: str | None) -> bool:
    """True when the KB links these two rules in one hop (either direction)."""
    if not a or not b or a == b:
        return False
    return b in adj.get(a, ())


def _normalized_identity_text(value) -> str:
    """Case/spacing/punctuation normalization, deliberately not fuzzy matching."""
    return " ".join(re.findall(r"\w+", str(value or "").casefold(), flags=re.UNICODE))


def _same_claim_and_evidence(a: dict, b: dict) -> bool:
    """Whether two rows carry the same explicit claim and verdict-addressed quote.

    The quote comparison intentionally stays exact (apart from outer whitespace):
    `revision.compute_finding_id` hashes quote case and punctuation as-is. Merging
    quote variants could therefore collapse two independently addressable writer
    verdicts. A related rule or shared scene alone is not enough; missing evidence
    or an empty issue cannot establish correspondence.
    """
    quote_a = str(a.get("evidence_quote") or "").strip()
    quote_b = str(b.get("evidence_quote") or "").strip()
    issue_a = _normalized_identity_text(a.get("issue"))
    issue_b = _normalized_identity_text(b.get("issue"))
    if not quote_a or not issue_a:
        return False
    return (
        quote_a == quote_b
        and issue_a == issue_b
        and _normalized_identity_text(a.get("observation"))
        == _normalized_identity_text(b.get("observation"))
        and (a.get("category") or "other") == (b.get("category") or "other")
        and str(a.get("scene_key") or "").strip()
        == str(b.get("scene_key") or "").strip()
    )


class _Union:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _copy_finding(f: dict) -> dict:
    """A copy that does not alias the input's CONTAINERS.

    `dict(f)` is a shallow copy, so `scene_refs` (and any other list/dict value)
    stays the SAME object as the caller's. The merge below rebinds `scene_refs`
    on the survivor, which hid this on the common path — but the pass-through
    copy for an unmerged finding, and every entry in `merged_findings`, still
    handed the caller's own lists back. Anyone appending to a returned finding's
    scene list would then have edited the input they passed in, which is the
    opposite of this function's documented contract.

    One level is enough for this schema: findings are flat dicts whose only
    containers are lists of scalars and `merged_findings` (which this function
    builds itself, so its inner dicts are already private).
    """
    return {
        k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
        for k, v in f.items()
    }


def dedupe_related_findings(findings: list[dict], kb=None) -> list[dict]:
    """Merge only same-claim, same-evidence findings under related rules in one scene.

    Returns a new list; input dicts and containers are copied, not mutated. With
    no KB available the input is returned unchanged — a dedup that cannot read
    the relation map must not guess at what is related.
    """
    if not findings:
        return list(findings or [])
    if kb is None:
        try:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
        except Exception:
            return list(findings)

    adj = related_map(kb)
    by_name = _by_name(kb)
    keys = [resolve_rule_key(f.get("rule_id"), by_name, set(adj)) for f in findings]

    # Union only WITHIN a scene, and only across a direct edge. Restricting the
    # closure to the findings actually present is what keeps this local: the KB's
    # global closure would reach half the dialogue rules from here.
    union = _Union(len(findings))
    by_scene: dict = {}
    for i, f in enumerate(findings):
        for s in (f.get("scene_refs") or []):
            by_scene.setdefault(s, []).append(i)
    for scene, idxs in by_scene.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                # Rule identity/relation is only a candidate signal. Same-rule
                # rows can be independent claims too; require the identical
                # non-empty quote and normalized claim before any pair is united.
                if not _same_claim_and_evidence(findings[i], findings[j]):
                    continue
                if keys[i] and keys[i] == keys[j]:
                    union.union(i, j)
                elif directly_related(adj, keys[i], keys[j]):
                    union.union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(findings)):
        groups.setdefault(union.find(i), []).append(i)

    out: list[dict] = []
    for root in sorted(groups):
        members = groups[root]
        if len(members) == 1:
            out.append(_copy_finding(findings[members[0]]))
            continue
        # Highest severity survives; the earliest wins a tie so the report order is
        # stable across runs.
        survivor_idx = min(
            members,
            key=lambda i: (SEVERITY_ORDER.get(findings[i].get("severity"), 3), i),
        )
        survivor = _copy_finding(findings[survivor_idx])
        others = [findings[i] for i in members if i != survivor_idx]

        merged_refs = [o.get("rule_id") for o in others if o.get("rule_id")]
        survivor["merged_rule_ids"] = merged_refs
        # The absorbed findings' FULL content, not only their rule names. A rule
        # id says "another rule agreed"; it does not say WHAT that rule said —
        # and the absorbed `issue`, `observation`, `evidence_quote` and `severity`
        # were previously retained NOWHERE (measured: 23 findings on Pain_3, 6 on
        # gun_pen). `merged_rule_ids` alone was cited as proof that a merge
        # preserved content, and it does not: it preserves the attribution, not
        # the claim. The integrity gate already keeps every finding it removes
        # whole (finding_integrity.py, `withdrawals`); this makes the dedupe
        # honour the same contract, so "nothing lost" is true here too.
        survivor["merged_findings"] = [_copy_finding(o) for o in others]
        scenes = set(survivor.get("scene_refs") or [])
        for o in others:
            scenes |= set(o.get("scene_refs") or [])
        survivor["scene_refs"] = sorted(scenes)
        if merged_refs:
            # Stated on the finding itself, not only in a side field: a writer
            # reading one card must be able to see that other rules agreed.
            clause = "Also flagged under: " + ", ".join(merged_refs) + "."
            why = (survivor.get("why_it_matters") or "").rstrip()
            survivor["why_it_matters"] = f"{why} {clause}".strip()
        out.append(survivor)
    return out

def collapse_exact_duplicates(findings: list[dict]) -> list[dict]:
    """Drop a row that is word-for-word another row, keeping first-seen order.

    This is NOT the merge above. `dedupe_related_findings` unites two different
    notes that share a page, so it has to choose which text survives; this one
    removes a row that carries nothing the survivor does not, so it chooses
    nothing and loses nothing. The key is the WHOLE row: a difference in severity,
    rule id, reasoning, suggestion or scene order keeps both rows, because that
    difference is information the writer would lose. Two different craft judgments
    about one quoted line stay two notes with two marks.

    The set of distinct content ids is provably unchanged — `compute_finding_id`
    reads only category, quote and issue, all three inside this key — so the
    strip's fixed/new arithmetic cannot move.
    """
    seen: set = set()
    out: list[dict] = []
    for f in findings:
        key = json.dumps(f, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
