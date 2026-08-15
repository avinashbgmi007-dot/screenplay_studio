"""
GBNF grammars for llama.cpp's `grammar` request field. Constraining output
at generation time (rather than just asking nicely in the prompt and hoping)
is what makes the findings schema reliable enough to parse and citation-check
programmatically.

Compatibility note: these are written to parse on BOTH the classic GBNF
parser AND the PEG-era grammar parser shipped in newer llama.cpp builds
(the "peg-native" / turboquant line). The PEG parser is stricter in two
specific ways that the app's older grammars violated:

  1. Rule bodies must be on a single line. A multi-line rule body
     (`finding ::= "{" ws` + indented continuation) makes the PEG parser
     report "expecting name" at the first token of the continuation line —
     the server then silently drops the grammar and runs unconstrained.
  2. Inside character classes, `\\x00-\\x1f` hex ranges and backslash
     escapes (`[\\\\]`, `[\\\\/bfnrt]`) are rejected by the PEG parser,
     and so are the JSON escape literals `\\/`, `\\b`, `\\f`, and `\\u`.
     This grammar uses only the constructs this build accepts: printable
     ASCII expressed as ranges that skip the characters a JSON string must
     not contain raw (quote 0x22, backslash 0x5C, and the class-closing
     `]` 0x5D), all non-ASCII via `[\\x80-\\u10FFFF]`, and the two escape
     literals the parser does accept (`\\\"` and `\\\\`). Control
     characters stay excluded, so raw newlines can't break JSON parsing.

     The escape forms that are NOT included (\\/, \\b, \\f, \\uXXXX) are
     rejected by the PEG parser outright; a model that needs to write a
     slash or unicode escape does so as a plain character instead, which is
     valid JSON anyway.

If your llama-server rejects a grammar string outright, the pipeline still
works with `grammar=None`, just with a bit less reliability on schema
conformance (see `chat_json()` in llm_client.py, which always defensively
re-parses whatever comes back).
"""

_WS = r'ws ::= [ \t\n]*'

_STRING = r'''string ::= "\"" char* "\""
char ::= [\x20-\x21] | [\x23-\x5B] | [\x5E-\x7E] | [\x80-\u10FFFF] | "\\\"" | "\\\\"'''

_INT_ARRAY = r'''int-array ::= "[" ws (integer (ws "," ws integer)*)? ws "]"
integer ::= "-"? [0-9]+'''

FINDING_CATEGORIES = [
    "theme", "character", "structure", "dialogue", "scene_function", "plot_thread", "genre",
    "continuity",
]

SEVERITIES = ["low", "medium", "high"]


def findings_grammar() -> str:
    """Grammar for: {"findings": [ {category, issue, why_it_matters, severity,
    scene_refs, evidence_quote, rule_id}, ... ]}

    'issue' and 'why_it_matters' replace what used to be a single prose
    'finding' string — this is the structured-diagnosis schema: a short
    label of what's wrong, separated from the causal explanation of why it's
    a problem. This is what lets a UI render the two consistently without
    parsing prose, and keeps every category's output shape identical whether
    it's a scene-level, script-level, or Principles Engine finding.

    'rule_id' ties a finding back to the specific knowledge-base rule it was
    judged against, where applicable (null for findings that aren't grounded
    in one specific named rule).
    """
    category_alt = " | ".join(f'"\\"{c}\\""' for c in FINDING_CATEGORIES)
    severity_alt = " | ".join(f'"\\"{s}\\""' for s in SEVERITIES)

    return f'''root ::= ws "{{" ws "\\"findings\\"" ws ":" ws findings-array ws "}}" ws
findings-array ::= "[" ws (finding (ws "," ws finding)*)? ws "]"
finding ::= "{{" ws "\\"category\\"" ws ":" ws category ws "," ws "\\"issue\\"" ws ":" ws string ws "," ws "\\"why_it_matters\\"" ws ":" ws string ws "," ws "\\"severity\\"" ws ":" ws severity ws "," ws "\\"scene_refs\\"" ws ":" ws int-array ws "," ws "\\"evidence_quote\\"" ws ":" ws (string | "null") ws "," ws "\\"rule_id\\"" ws ":" ws (string | "null") ws "}}"
category ::= {category_alt}
severity ::= {severity_alt}
{_INT_ARRAY}
{_STRING}
{_WS}
'''


def scene_summary_grammar() -> str:
    """Grammar for: {"summaries": [ {scene_number, summary}, ... ]}"""
    return f'''root ::= ws "{{" ws "\\"summaries\\"" ws ":" ws summaries-array ws "}}" ws
summaries-array ::= "[" ws (summary-item (ws "," ws summary-item)*)? ws "]"
summary-item ::= "{{" ws "\\"scene_number\\"" ws ":" ws integer ws "," ws "\\"summary\\"" ws ":" ws string ws "}}"
{_INT_ARRAY}
{_STRING}
{_WS}
'''


def principle_judgment_grammar() -> str:
    """Grammar for the Principles Engine's judge-significance stage output:
    {"significant": bool, "paid_off": bool, "reasoning": str}
    Deliberately no suggested_resolution field — Piece 2 diagnoses, it never
    prescribes. Fixes are Piece 3's job, generated conversationally and only
    when the writer asks for them."""
    return f'''root ::= ws "{{" ws "\\"significant\\"" ws ":" ws boolean ws "," ws "\\"paid_off\\"" ws ":" ws boolean ws "," ws "\\"reasoning\\"" ws ":" ws string ws "}}" ws
boolean ::= "true" | "false"
{_STRING}
{_WS}
'''


def replacements_grammar() -> str:
    """Grammar for the revision loop's rewrite suggestion output:
    {"replacements": [{"old": str, "new": str}], "note": str}.
    'old' must be an exact verbatim line from the scene, so the apply step can
    match it deterministically."""
    return f'''root ::= ws "{{" ws "\\"replacements\\"" ws ":" ws replacements-array ws "," ws "\\"note\\"" ws ":" ws string ws "}}" ws
replacements-array ::= "[" ws (replacement (ws "," ws replacement)*)? ws "]"
replacement ::= "{{" ws "\\"old\\"" ws ":" ws string ws "," ws "\\"new\\"" ws ":" ws string ws "}}"
{_STRING}
{_WS}
'''


def logline_test_grammar() -> str:
    """Grammar for the logline test: diagnoses whether the premise lands in
    one sentence. No grades — signal is strong/workable/muddled, with an
    explanation of what works, what muddles it, what element a clean logline
    needs that's missing, and one tightened example that keeps the writer's
    premise intact."""
    return f'''root ::= ws "{{" ws "\\"logline\\"" ws ":" ws string ws "," ws "\\"signal\\"" ws ":" ws signal ws "," ws "\\"what_works\\"" ws ":" ws string ws "," ws "\\"what_muddles\\"" ws ":" ws string ws "," ws "\\"missing\\"" ws ":" ws string ws "," ws "\\"tightened\\"" ws ":" ws string ws "}}" ws
signal ::= "\\"strong\\"" | "\\"workable\\"" | "\\"muddled\\""
{_STRING}
{_WS}
'''


def character_reads_grammar() -> str:
    """Grammar for the character-perception read: how each character actually
    comes across to a stranger, what the script appears to intend, and the gap
    between the two. Mirrors the findings schema (scene_refs + evidence_quote)
    so the same quote-verifier can check the evidence."""
    return f'''root ::= ws "{{" ws "\\"reads\\"" ws ":" ws reads-array ws "}}" ws
reads-array ::= "[" ws (read-item (ws "," ws read-item)*)? ws "]"
read-item ::= "{{" ws "\\"character\\"" ws ":" ws string ws "," ws "\\"how_reads\\"" ws ":" ws string ws "," ws "\\"apparent_intent\\"" ws ":" ws string ws "," ws "\\"gap\\"" ws ":" ws string ws "," ws "\\"scene_refs\\"" ws ":" ws int-array ws "," ws "\\"evidence_quote\\"" ws ":" ws (string | "null") ws "}}"
{_INT_ARRAY}
{_STRING}
{_WS}
'''


def coverage_grammar() -> str:
    """Grammar for the single-object coverage report."""
    return f'''root ::= ws "{{" ws "\\"logline\\"" ws ":" ws string ws "," ws "\\"genre\\"" ws ":" ws string ws "," ws "\\"tone\\"" ws ":" ws string ws "," ws "\\"one_page_synopsis\\"" ws ":" ws string ws "," ws "\\"strengths\\"" ws ":" ws string-array ws "," ws "\\"weaknesses\\"" ws ":" ws string-array ws "," ws "\\"comparable_films\\"" ws ":" ws string-array ws "," ws "\\"recommendation\\"" ws ":" ws recommendation ws "}}" ws
string-array ::= "[" ws (string (ws "," ws string)*)? ws "]"
recommendation ::= "\\"pass\\"" | "\\"consider\\"" | "\\"recommend\\""
{_STRING}
{_WS}
'''
