"""Shared text/quote matching primitives.

WHY THIS MODULE EXISTS
Two engines ask a question about the same quote, and they must never disagree:

  * the analyzer's verifier asks *"was this quote really in the script?"* —
    leniently (0.72 fuzzy), because a small model reworded a real line;
  * the studio's status engine asks *"is this cited line still in the draft?"* —
    strictly, because a reworded line is exactly what a WRITER'S EDIT looks like.

They must share the normaliser and the way the haystack is built. They must NOT
share a threshold: unifying them would make every writer edit read as "still
present" and kill the writer-fix signal silently.

That is why this module exports no threshold. Each caller keeps its own, with a
name that says which question it answers (`FUZZY_MATCH_THRESHOLD` = verification,
`QUOTE_CHANGE_THRESHOLD` = change detection).

WHY IT LIVES IN screenplay_parser
That package is the leaf both pieces already depend on: it imports nothing from
`screenplay_analyzer` or `screenplay_studio` (only stdlib, pdfplumber, and its
own relative modules). Putting the shared code here means the studio never
reaches into the analyzer, so there is no import-failure path that could quietly
restore the old, narrower matching.

BACKGROUND (the defect this was extracted for)
`revision.quote_present` used to substring-match the raw quote against ONE
element at a time and then fuzzy-compare the whole quote against that same
element (about 35 characters). Two ordinary situations broke it, both captured
from a real report's `parsed.json`:

    element[7]  'yudhame jarguthundi... “you are the'
    element[8]  'sum of all your choices”'
    finding     '"you are the sum of all your choices"'

The quote spans two line-wrapped elements, and the model wrote straight quotes
where the script has curly ones. The verifier accepted it at confidence 1.0; the
status engine called it gone. On a script nobody had edited, the desk then
reported eight findings "addressed by you".
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_WHITESPACE = re.compile(r"\s+")

# Joiners that carry meaning inside a grapheme cluster in several Indic and
# Arabic scripts. They are category Cf, so the letter/mark/number rule below
# would otherwise drop them and could glue two distinct clusters together.
_MEANINGFUL_JOINERS = frozenset(("\u200c", "\u200d"))  # ZWNJ, ZWJ

_KEEP_CACHE: dict[str, bool] = {}


def _is_kept(ch: str) -> bool:
    """Is this character part of the text we compare, or is it punctuation?

    KEEP letters, combining marks and numbers. The marks are the whole point:
    Telugu, Devanagari and Tamil write long/ short vowels and other distinctions
    as combining characters (categories Mn and Mc), so a `\w`-based filter —
    which keeps only `str.isalnum()` characters — silently deletes them. That
    made కాల ("time") and కల ("a pen") normalise to the same string, and the
    verifier then reported a quote that is NOT in the script as `verified` with
    confidence 1.0 (gap 23). Dropping punctuation is right; dropping a vowel
    sign changes the word.
    """
    try:
        return _KEEP_CACHE[ch]
    except KeyError:
        keep = ch == "_" or ch in _MEANINGFUL_JOINERS or unicodedata.category(ch)[0] in "LMN"
        _KEEP_CACHE[ch] = keep
        return keep


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Comparison is done on NFC text: a quote typed with a decomposed vowel sign
    must match the composed form in the script, because those two are the same
    word. NFC only folds canonically EQUIVALENT sequences — it cannot merge two
    genuinely different words — which is why it is safe here where a `\w`-based
    strip was not. NFKC is deliberately NOT used: it also folds compatibility
    variants (ligatures, full-width forms), which would blur text a matcher
    should keep distinct.

    Moved from `screenplay_analyzer.verifier._normalize`, which is now a thin
    alias, so the two engines cannot normalise differently. Fixing it HERE keeps
    that guarantee: the analyzer's verifier and the studio's change detector
    both get the correction, and neither can drift back.
    """
    text = unicodedata.normalize("NFC", text.lower())
    text = "".join(ch for ch in text if ch.isspace() or _is_kept(ch))
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def scene_text(scene) -> str:
    """A scene's elements joined into one string, in document order.

    The joining is the whole point: a quote that spans a line wrap is invisible
    to any matcher that only ever sees one element at a time.
    """
    return "\n".join(e.text for e in scene.elements)


def find_scene_text(doc, scene_number: int) -> str | None:
    """Joined text of one scene, or None when that scene isn't in this document."""
    for scene in doc.scenes:
        if scene.scene_number == scene_number:
            return scene_text(scene)
    return None


def iter_scene_texts(doc):
    """Yield each scene's joined text, in document order.

    Scenes stay separate on purpose. Joining the whole document into one string
    would let a quote match across a scene boundary, which is not a quote anyone
    wrote.
    """
    for scene in doc.scenes:
        yield scene_text(scene)


def windowed_similarity(quote_norm: str, haystack_norm: str) -> float:
    """Sliding-window fuzzy match, both sides already normalised.

    Compares the quote against windows of the haystack roughly its own size
    rather than the whole haystack at once (SequenceMatcher on very
    different-length strings underestimates similarity for a short quote inside
    a long scene). Moved verbatim from
    `screenplay_analyzer.verifier._best_fuzzy_match`, which is now a thin alias,
    so a scoring change cannot land in one engine only.
    """
    words = haystack_norm.split()
    qwords = quote_norm.split()
    if not qwords:
        return 0.0
    window = max(len(qwords), 3)
    best = 0.0
    step = max(1, window // 2)
    for i in range(0, max(1, len(words) - window + 1), step):
        chunk = " ".join(words[i:i + window + 2])
        ratio = SequenceMatcher(None, quote_norm, chunk).ratio()
        best = max(best, ratio)
    if not words:
        return 0.0
    return best
