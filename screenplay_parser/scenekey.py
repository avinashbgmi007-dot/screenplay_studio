"""Scene keys — a scene's identity inside a finding's content-hash id.

Why this exists (HIGH-1, see NOTES.md "D1 + D2-a"): a finding's id is
`category + the finding's own words` (`revision.compute_finding_id`, mirrored by
`core.js:computeFindingId`). On Pain_3 that key collides — the demo dialogue
finding repeats its issue verbatim at nine different scenes, so 9 of 16 findings
hashed to ONE id and a single mark counted nine findings addressed.

The tie-breaker is the SCENE the finding points at, named by its slugline rather
than by its ordinal. An ordinal moves the moment the writer inserts a scene; a
slugline moves only when the writer rewrites that heading — and `scene_refs`
already renumber on insert, which is exactly why the id must not key on them.

`scene_key_map` gives each scene its slug, qualified `#2`, `#3` … for the 2nd,
3rd … scene that repeats that slug, in script order. The FIRST occurrence keeps
the bare slug, so appending a later duplicate never renames an earlier scene.

The price, documented rather than hidden: rewriting a slugline moves every id on
that scene, and inserting a scene that repeats an existing slug renumbers that
slug's later occurrences. Both are confined to a heading the writer changed or
duplicated — never to scene insertion alone, which is the case the id has always
had to survive.

Only Python derives slugs. The analyzer stamps `scene_key` into the report
(`report.to_findings_json`) and the desk re-stamps on read for reports written
before the field existed (`revision.annotate_report_scene_keys`), so both
languages READ one stamped value instead of each deriving their own. One
derivation, two readers — the parity the id depends on.
"""

from __future__ import annotations

import re

# Everything that is not an ASCII alphanumeric and not a non-ASCII code point
# collapses to a single space. Stated as a keep-list rather than a drop-list on
# purpose: a Telugu, Tamil or emoji-bearing heading keeps its characters (two
# such headings must not collapse to the same empty slug), while ASCII
# punctuation and whitespace runs — the parts writers vary freely — normalise
# away. The keep-list runs to U+10FFFF, not U+FFFF: most emoji and every CJK
# extension plane sit above the BMP, and a range that stopped at U+FFFF would
# drop them — an emoji-only heading would slug to "" and two headings that
# differ only by an emoji would share one slug.
#
# This rule is inside every stored id. Changing it moves ids, so it changes
# only together with a migration (`revision.legacy_id_candidates`).
_SLUG_NOISE = re.compile(r"[^A-Z0-9\u0080-\U0010ffff]+")


def heading_slug(heading: str) -> str:
    """A slugline's stable slug: upper-cased, apostrophes dropped, every run of
    ASCII punctuation or whitespace collapsed to one space.

    "INT. SIDDHU’S HOUSE - CONTINUOUS" -> "INT SIDDHUS HOUSE CONTINUOUS"
    """
    s = (heading or "").upper()
    s = s.replace("'", "").replace("\u2019", "")  # straight + curly apostrophe
    s = s.replace("\u00a0", " ")                  # NBSP is not a word break to _SLUG_NOISE
    return _SLUG_NOISE.sub(" ", s).strip()


def scene_key_map(doc) -> dict:
    """{scene_number: occurrence-qualified slug} for every scene in `doc`.

    A scene whose heading slugs to "" gets NO entry: its findings then carry no
    scene component and key exactly as they did before this module existed —
    the honest fallback, since there is nothing to key on.
    """
    seen: dict = {}
    out: dict = {}
    for scene in getattr(doc, "scenes", None) or []:
        slug = heading_slug(getattr(scene, "heading_raw", "") or "")
        if not slug:
            continue
        n = seen.get(slug, 0) + 1
        seen[slug] = n
        out[int(getattr(scene, "scene_number", 0) or 0)] = slug if n == 1 else f"{slug}#{n}"
    return out


def scene_key_for(finding: dict, keys: dict) -> str:
    """The scene component of `finding`'s id: the key of its FIRST scene_ref.

    A script-level finding (no refs) has no scene component — it is about the
    draft, not about a place in it — and so keeps its pre-scene-key id.
    """
    refs = finding.get("scene_refs") or []
    if not refs:
        return ""
    try:
        n = int(refs[0])
    except (TypeError, ValueError):
        return ""
    return keys.get(n) or ""


def stamp_scene_keys(findings, keys: dict) -> list:
    """Findings with `scene_key` set — an existing stamp is never overwritten.

    Not overwriting is what keeps this idempotent: a report stamped at analysis
    time serves the same ids on every later read, and a finding merged forward
    from an earlier report keeps the key it was stamped with rather than being
    silently re-keyed by the merge.
    """
    out = []
    for f in findings or []:
        if isinstance(f, dict) and "scene_key" not in f:
            f = dict(f)
            f["scene_key"] = scene_key_for(f, keys)
        out.append(f)
    return out
