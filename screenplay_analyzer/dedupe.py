"""Cross-rule finding dedup (§5 item 3).

The same defect reaches the report more than once when the model files it under
several related rules. Measured on a real report (`gun_pen_2`, scene 2), one
on-the-nose exposition problem arrived as THREE findings:

    On-the-Nose Dialogue vs. Subtext   "Dialogue is on-the-nose, explicitly stating..."
    Say the Opposite                   "Dialogue contains multiple on-the-nose statements..."
    Exposition as Ammunition           "Dialogue is purely functional exposition..."

and a fourth dialogue finding in the same scene — `Distinct Character Voice` — is a
genuinely different defect that must NOT be merged with them.

Two measured facts shaped this module, and both rule out the obvious approach:

**1. The duplication is not textually detectable.** Those three issues share almost
no wording (across the whole 36-finding report, no pair of findings reached 0.19
text similarity). A text-similarity dedup finds nothing; a scene-only dedup merges
the voice finding too.

**2. The transitive closure of `related_rules` is far too coarse.** The KB writes
related-ness one-directionally, so it is symmetrised here — but chaining those edges
collapses 271 rules into clusters of up to **61 members**, with `cast_polarization`
alone holding **49**. `distinct_character_voice` and `on_the_nose_vs_subtext` land in
the SAME one. A closure-based merge therefore merged 36 findings down to 10 and
swallowed the voice finding — the exact error this module exists to avoid. (That was
this module's first implementation; the real report caught it.)

So the merge predicate is a **direct edge**, evaluated only between findings that are
both present and in the same scene:

    merge(A, B)  iff  A and B share a scene
                 and  B's rule is in A's related_rules (or vice versa)

That is precise where the closure is not: the exposition trio are pairwise linked
through `on_the_nose_vs_subtext`, while `distinct_character_voice` has no direct edge
to any of them.

Two consequences, both deliberate:

- **A finding with no scene is never merged.** Script-level findings carry no
  `scene_refs`; relating them by rule alone would merge observations from different
  parts of the script. The rule is "we merge only when both findings point at the
  same page".
- **Nothing is dropped.** The survivor keeps its own text and gains a
  `merged_rule_ids` list plus a stated clause, because a dedup that quietly deletes a
  finding is the same failure as the one it exists to fix. Same "flag, don't
  silently drop" policy as the verifier.
"""

from __future__ import annotations

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


def directly_related(adj: dict[str, set[str]], a: str | None, b: str | None) -> bool:
    """True when the KB links these two rules in one hop (either direction)."""
    if not a or not b or a == b:
        return False
    return b in adj.get(a, ())


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


def dedupe_related_findings(findings: list[dict], kb=None) -> list[dict]:
    """Merge findings that report the same defect under directly-related rules in
    the same scene. Returns a new list; the input dicts are copied, not mutated.

    With no KB available the input is returned unchanged — a dedup that cannot read
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
                # The same rule twice in the same scene is a duplicate by
                # definition, so it merges whether or not the KB relates the rule
                # to itself. (directly_related excludes a == b.)
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
            out.append(dict(findings[members[0]]))
            continue
        # Highest severity survives; the earliest wins a tie so the report order is
        # stable across runs.
        survivor_idx = min(
            members,
            key=lambda i: (SEVERITY_ORDER.get(findings[i].get("severity"), 3), i),
        )
        survivor = dict(findings[survivor_idx])
        others = [findings[i] for i in members if i != survivor_idx]

        merged_refs = [o.get("rule_id") for o in others if o.get("rule_id")]
        survivor["merged_rule_ids"] = merged_refs
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
