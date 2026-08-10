# screenplay_analyzer/verifier.py

## Purpose
Evidence verification for LLM-generated findings. The single biggest trust problem with LLM-generated scripts is verifying claims against source text. This module solves that.

## Key Functions

### `verify_finding(finding: dict, doc: ScriptDocument) -> dict`
Verifies a finding against the source screenplay text. Mutates the finding dict with a `verification` block:
```python
{
    "status": "verified" | "refuted" | "uncertain",
    "evidence": "quote from source",
    "confidence": 0.85
}
```

### `_normalize(text: str) -> str`
Normalizes text for comparison (lowercase, strip whitespace, collapse spaces).

### `_best_fuzzy_match(haystack: str, needle: str, threshold: float = 0.72) -> str | None`
Sliding-window fuzzy match: compares the quote against windows of the haystack text. Uses a 0.72 similarity threshold.

## Dependencies
- `screenplay_parser.models` (ScriptDocument)
- `re` (regex)
- `difflib` (stdlib for fuzzy matching)

## Usage Example
```python
from screenplay_analyzer.verifier import verify_finding

finding = {"title": "Too much exposition", "category": "pacing", ...}
verified = verify_finding(finding, doc)
# verified["verification"] = {"status": "verified", "evidence": "...", "confidence": 0.85}
```

## Graph Notes
- `ScriptDocument` is the target of evidence verification (2 references)
- `Wires the craft knowledge base into analyzer prompts` — inferred connection to KnowledgeBase
- Evidence verification is the core trust mechanism
