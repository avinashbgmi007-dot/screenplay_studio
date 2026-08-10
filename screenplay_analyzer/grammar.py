"""
GBNF grammars for llama.cpp's `grammar` request field. Constraining output
at generation time (rather than just asking nicely in the prompt and hoping)
is what makes the findings schema reliable enough to parse and citation-check
programmatically.

Note: these are hand-written against the documented GBNF syntax llama.cpp
uses (https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md).
I don't have a live llama.cpp binary in this environment to compile-check
them against, so `chat_json()` in llm_client.py does NOT assume the grammar
was honored — it always defensively re-parses whatever text comes back.
If your llama-server rejects a grammar string outright (should surface as
an HTTP 400), the pipeline still works with `grammar=None`, just with a bit
less reliability on schema conformance.
"""

_WS = r'ws ::= [ \t\n]*'

_STRING = r'''string ::= "\"" char* "\""
char ::= [^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])'''

_INT_ARRAY = r'''int-array ::= "[" ws (integer (ws "," ws integer)*)? ws "]"
integer ::= "-"? [0-9]+'''

FINDING_CATEGORIES = [
    "theme", "character", "structure", "dialogue", "scene_function", "plot_thread",
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
finding ::= "{{" ws
  "\\"category\\"" ws ":" ws category ws ","  ws
  "\\"issue\\"" ws ":" ws string ws "," ws
  "\\"why_it_matters\\"" ws ":" ws string ws "," ws
  "\\"severity\\"" ws ":" ws severity ws "," ws
  "\\"scene_refs\\"" ws ":" ws int-array ws "," ws
  "\\"evidence_quote\\"" ws ":" ws (string | "null") ws "," ws
  "\\"rule_id\\"" ws ":" ws (string | "null") ws
  "}}"
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
summary-item ::= "{{" ws
  "\\"scene_number\\"" ws ":" ws integer ws "," ws
  "\\"summary\\"" ws ":" ws string ws
  "}}"
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
    return f'''root ::= ws "{{" ws
  "\\"significant\\"" ws ":" ws boolean ws "," ws
  "\\"paid_off\\"" ws ":" ws boolean ws "," ws
  "\\"reasoning\\"" ws ":" ws string ws
"}}" ws
boolean ::= "true" | "false"
{_STRING}
{_WS}
'''


def coverage_grammar() -> str:
    """Grammar for the single-object coverage report."""
    return f'''root ::= ws "{{" ws
  "\\"logline\\"" ws ":" ws string ws "," ws
  "\\"genre\\"" ws ":" ws string ws "," ws
  "\\"tone\\"" ws ":" ws string ws "," ws
  "\\"one_page_synopsis\\"" ws ":" ws string ws "," ws
  "\\"strengths\\"" ws ":" ws string-array ws "," ws
  "\\"weaknesses\\"" ws ":" ws string-array ws "," ws
  "\\"comparable_films\\"" ws ":" ws string-array ws "," ws
  "\\"recommendation\\"" ws ":" ws recommendation ws
"}}" ws
string-array ::= "[" ws (string (ws "," ws string)*)? ws "]"
recommendation ::= "\\"pass\\"" | "\\"consider\\"" | "\\"recommend\\""
{_STRING}
{_WS}
'''
