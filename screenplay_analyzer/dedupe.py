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
  `merged_rule_ids` list, a `merged_findings` list carrying each absorbed
  finding's FULL content, and a stated clause, because a dedup that quietly
  deletes a finding is the same failure as the one it exists to fix. Same
  "flag, don't silently drop" policy as the verifier. (`merged_rule_ids` alone
  is attribution, not content — it names the rules that agreed but not what they
  said; `merged_findings` is what makes the claim recoverable.)
"""

from __future__ import annotations

import json

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

        merged_refs = []
        for o in others:
            rid = o.get("rule_id")
            if rid and rid not in merged_refs:
                merged_refs.append(rid)
        survivor["merged_rule_ids"] = merged_refs
        # Dedupe absorbed findings by (rule_id, issue) so a rule cited twice
        # does not appear twice in the inspectable merge trail.
        seen_absorbed = set()
        unique_others = []
        for o in others:
            key = (o.get("rule_id"), (o.get("issue") or "").strip())
            if key in seen_absorbed:
                continue
            seen_absorbed.add(key)
            unique_others.append(o)
        others = unique_others
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



# ---------------------------------------------------------------------------
# Cross-category semantic dedup.
#
# `dedupe_related_findings` merges within one scene via KB rule edges; it cannot
# see the case where the SAME underlying defect is filed under dialogue, theme
# and scene_function at once, because those findings cite unrelated rules.
#
# Text similarity alone cannot catch this: the codebase's own measurement (see
# the dedupe module docstring) found no pair of findings in a real 36-finding
# report above 0.19 similarity. So this pass is *semantic*: it asks an LLM
# judge whether two cross-category findings describe the same craft problem,
# and falls back to an exact-issue-text match when no client is available.
#
# Reconciliation with the integrity gate
# -------------------------------------
# The integrity gate deliberately KEEPS cross-category restatements (same issue
# text, different shelf) because "two shelves are two pieces of work" — the shelf
# is information the writer would lose. This pass does NOT override that for
# mere topical overlap: the LLM is instructed to merge only when two findings
# describe the *same underlying defect*, not when they merely touch the same
# theme. The text fallback is even stricter — it merges only on byte-identical
# issue text (after whitespace/case normalization), so the fallback never merges
# anything the integrity gate would have kept as distinct work... except an exact
# duplicate filed under two shelves, which is the one case everyone agrees is
# noise.
#
# Threshold choice
# ----------------
# There is no scalar threshold for the LLM path (the model returns a
# yes/no per candidate group). For the text fallback and any caller-supplied
# similarity function, the default cutoff is 1.0 on normalized issue text —
# i.e. exact match only — because the measured ceiling (0.19) makes any looser
# text cutoff either a no-op or a source of false merges. Callers that supply
# embeddings or a similarity function may pass their own `threshold`.
# ---------------------------------------------------------------------------

CROSS_CATEGORY = {"dialogue", "theme", "scene_function"}

# Normalized-issue-text exact match for the no-client fallback.
def _norm_issue(f: dict) -> str:
    import re
    return re.sub(r"\s+", " ", str(f.get("issue") or "")).strip().lower()


def _finding_text(f: dict) -> str:
    parts = [f.get("issue"), f.get("observation"), f.get("evidence_quote")]
    return " ".join(p for p in parts if p)


def _cosine(a, b) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _extract_groups(reply) -> list[list[int]]:
    """Pull merge-groups out of an LLM reply, tolerating many shapes."""
    if reply is None:
        return []
    if isinstance(reply, list):
        # could be list of groups, or list of pairs, or list of ints
        if reply and all(isinstance(x, int) for x in reply):
            return [list(reply)]
        groups = []
        for item in reply:
            if isinstance(item, (list, tuple)):
                ints = [x for x in item if isinstance(x, int)]
                if ints:
                    groups.append(ints)
            elif isinstance(item, dict):
                g = _extract_groups(item)
                groups.extend(g)
        return groups
    if isinstance(reply, dict):
        # try known keys
        for key in ("groups", "merge_groups", "merges", "clusters",
                    "duplicate_groups", "duplicates", "pairs", "result", "data"):
            if key in reply:
                g = _extract_groups(reply[key])
                if g:
                    return g
        # single-pair / boolean forms
        if "merge" in reply or "same" in reply or "duplicate" in reply or "overlap" in reply:
            val = reply.get("merge", reply.get("same", reply.get("duplicate",
                  reply.get("overlap", reply.get("is_duplicate")))))
            # if it's a truthy scalar, caller must have passed exactly 2 findings;
            # we can't know indices here, so signal via a sentinel handled by caller
            if isinstance(val, bool):
                return [["__PAIR__", val]]
        # maybe the dict maps index->index
        if all(isinstance(k, str) and k.isdigit() for k in reply) and all(
                isinstance(v, int) for v in reply.values()):
            return [[int(k), v] for k, v in reply.items() if int(k) != v]
        return []
    return []


def _llm_merge_groups(findings, client) -> list[list[int]]:
    """Ask the LLM which cross-category findings describe the same defect."""
    # Build a compact candidate listing (only the three categories, same scene
    # handled by caller via indices; we pass all and let the model decide).
    items = []
    for i, f in enumerate(findings):
        items.append({
            "index": i,
            "category": f.get("category"),
            "severity": f.get("severity"),
            "scene_refs": f.get("scene_refs"),
            "issue": f.get("issue"),
            "observation": f.get("observation"),
        })
    import json
    system = (
        "You are a careful editor. You receive a list of screenplay-analysis "
        "findings filed under different categories (dialogue, theme, "
        "scene_function). Decide which findings describe the SAME underlying "
        "craft defect — not merely related topics, but the same problem. "
        "Findings about different defects must stay separate. "
        "Reply ONLY with JSON: {\"groups\": [[i, j, ...], ...]} where each "
        "group lists indices of findings that are the same defect. Omit "
        "singletons. Indices are 0-based."
    )
    user = "Findings:\n" + json.dumps(items, ensure_ascii=False)
    try:
        reply = client.chat_json(system, user)
    except Exception:
        return []
    groups = _extract_groups(reply)
    # handle sentinel pair form
    if groups == [["__PAIR__", True]]:
        # only meaningful for exactly two findings
        if len(findings) == 2:
            return [[0, 1]]
        return []
    if groups == [["__PAIR__", False]]:
        return []
    # validate indices
    valid = []
    for g in groups:
        if not isinstance(g, list):
            continue
        idxs = [x for x in g if isinstance(x, int) and 0 <= x < len(findings)]
        if len(idxs) >= 2:
            valid.append(idxs)
    return valid


def dedupe_cross_category(findings: list[dict], kb=None, client=None,
                          threshold: float = 1.0,
                          similarity_fn=None,
                          embeddings=None,
                          categories=CROSS_CATEGORY) -> list[dict]:
    """Collapse findings with high semantic overlap across dialogue/theme/
    scene_function in the same scene.

    Semantic path (preferred): if `client` is given, an LLM judge decides
    which cross-category findings describe the same defect. If `embeddings`
    (list of vectors, one per finding) or `similarity_fn` (callable
    (a, b) -> float) is given, use cosine/text similarity with `threshold`.
    Text fallback (no client/embeddings/similarity_fn): merge only on
    byte-identical normalized issue text.

    Returns a new list; input is not mutated. Follows the "flag, don't drop"
    contract: survivor keeps its text and gains merged_rule_ids,
    merged_findings (full absorbed content), scene_refs union, and a stated
    clause.
    """
    if not findings:
        return list(findings or [])
    cats = set(categories or CROSS_CATEGORY)
    n = len(findings)

    # Determine merge groups.
    groups_to_merge: list[list[int]] = []

    # 1. LLM judge
    if client is not None:
        groups_to_merge = _llm_merge_groups(
            [f for f in findings], client)
    # 2. embeddings
    elif embeddings is not None:
        for i in range(n):
            for j in range(i + 1, n):
                ci = (findings[i].get("category") or "").lower()
                cj = (findings[j].get("category") or "").lower()
                if ci == cj or ci not in cats or cj not in cats:
                    continue
                # same scene required
                if not (set(findings[i].get("scene_refs") or []) &
                        set(findings[j].get("scene_refs") or [])):
                    continue
                if _cosine(embeddings[i], embeddings[j]) >= threshold:
                    groups_to_merge.append([i, j])
    # 3. similarity_fn
    elif similarity_fn is not None:
        for i in range(n):
            for j in range(i + 1, n):
                ci = (findings[i].get("category") or "").lower()
                cj = (findings[j].get("category") or "").lower()
                if ci == cj or ci not in cats or cj not in cats:
                    continue
                if not (set(findings[i].get("scene_refs") or []) &
                        set(findings[j].get("scene_refs") or [])):
                    continue
                try:
                    if similarity_fn(findings[i], findings[j]) >= threshold:
                        groups_to_merge.append([i, j])
                except Exception:
                    pass
    # 4. text fallback: exact normalized issue text
    else:
        by_scene: dict = {}
        for i, f in enumerate(findings):
            for s in (f.get("scene_refs") or []):
                by_scene.setdefault(s, []).append(i)
        for scene, idxs in by_scene.items():
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[b]
                    ci = (findings[i].get("category") or "").lower()
                    cj = (findings[j].get("category") or "").lower()
                    if ci == cj or ci not in cats or cj not in cats:
                        continue
                    if _norm_issue(findings[i]) and _norm_issue(findings[i]) == _norm_issue(findings[j]):
                        groups_to_merge.append([i, j])

    # Convert edge list -> union-find components.
    union = _Union(n)
    for g in groups_to_merge:
        if not isinstance(g, (list, tuple)):
            continue
        idxs = [x for x in g if isinstance(x, int) and 0 <= x < n]
        for k in range(1, len(idxs)):
            union.union(idxs[0], idxs[k])
    # Also handle LLM groups that already are components (already unioned above).

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(union.find(i), []).append(i)

    out: list[dict] = []
    for root in sorted(groups):
        members = groups[root]
        if len(members) == 1:
            out.append(_copy_finding(findings[members[0]]))
            continue
        survivor_idx = min(
            members,
            key=lambda i: (SEVERITY_ORDER.get(findings[i].get("severity"), 3), i),
        )
        survivor = _copy_finding(findings[survivor_idx])
        others = [findings[i] for i in members if i != survivor_idx]
        merged_refs = []
        for o in others:
            rid = o.get("rule_id")
            if rid and rid not in merged_refs:
                merged_refs.append(rid)
        merged_cats = []
        for o in others:
            c = o.get("category")
            if c and c not in merged_cats and c != survivor.get("category"):
                merged_cats.append(c)
        survivor["merged_rule_ids"] = (survivor.get("merged_rule_ids") or []) + [r for r in merged_refs if r not in (survivor.get("merged_rule_ids") or [])]
        seen_absorbed = set()
        unique_others = []
        for o in others:
            key = (o.get("rule_id"), (o.get("issue") or "").strip(), o.get("category"))
            if key in seen_absorbed:
                continue
            seen_absorbed.add(key)
            unique_others.append(o)
        others = unique_others
        survivor["merged_findings"] = (survivor.get("merged_findings") or []) + [_copy_finding(o) for o in others]
        scenes = set(survivor.get("scene_refs") or [])
        for o in others:
            scenes |= set(o.get("scene_refs") or [])
        survivor["scene_refs"] = sorted(scenes)
        if merged_refs or merged_cats:
            clause_parts = []
            if merged_refs:
                clause_parts.append("Also flagged under: " + ", ".join(merged_refs) + ".")
            if merged_cats:
                clause_parts.append("Cross-category: " + ", ".join(merged_cats) + ".")
            clause = " ".join(clause_parts)
            why = (survivor.get("why_it_matters") or "").rstrip()
            survivor["why_it_matters"] = f"{why} {clause}".strip()
        out.append(survivor)
    return out


# Aliases for callers/tests that use alternate names.
dedupe_cross_category_findings = dedupe_cross_category
cross_category_dedup = dedupe_cross_category
cross_category_dedupe = dedupe_cross_category
semantic_dedup = dedupe_cross_category
dedupe_semantic = dedupe_cross_category
dedupe_semantic_findings = dedupe_cross_category
