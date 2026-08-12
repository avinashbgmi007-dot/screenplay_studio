"""Crash-safe grammar probe against the live llama-server on :8080.

Run ONE variant per invocation (index arg) so that if a grammar crashes
the server process, we know exactly which variant killed it. Health-check
first; never send the next request while the server is down.

Usage:  python tests/_grammar_bisect.py [variant-index]
        0 = current app grammar (the one in the failure log)
        1 = ws rule swapped to upstream form
        2 = + char class matching upstream
        3 = + bounded hex repetition
        4 = full upstream-dialect rewrite
        5 = llama.cpp reference json.gbnf (sanity)
"""
import sys
import requests

URL = "http://localhost:8080/v1/chat/completions"
HEALTH = "http://localhost:8080/health"
# n_predict=1: grammar must PARSE before any generation; one token is trivial
PAYLOAD = {
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1,
    "temperature": 0,
}


def build_variants():
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from screenplay_analyzer.grammar import findings_grammar
    v0 = findings_grammar()
    variants = []

    variants.append(("V0 current app grammar (the one from your failure log)", v0))

    v1 = v0.replace('ws ::= [ \\t\\n]*', 'ws ::= | " " | "\\n" [ \\t]{0,20}')
    variants.append(("V1 only-ws swap to upstream form", v1))

    v2 = v1.replace('[^"\\\\\\x00-\\x1f]', '[^"\\\\\\x7F\\x00-\\x1F]')
    variants.append(("V2 V1 + upstream char class", v2))

    v3 = v2.replace(
        '"u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]',
        '"u" [0-9a-fA-F]{4}')
    variants.append(("V3 V2 + bounded {4} hex", v3))

    v4 = '''root ::= "{" ws "\\"findings\\"" ":" ws findings-array "}" ws
findings-array ::= "[" ws (finding ("," ws finding)*)? "]" ws
finding ::= "{" ws
  "\\"category\\"" ":" ws category
  "," "\\"issue\\"" ":" ws string
  "," "\\"why_it_matters\\"" ":" ws string
  "," "\\"severity\\"" ":" ws severity
  "," "\\"scene_refs\\"" ":" ws int-array
  "," "\\"evidence_quote\\"" ":" ws (string | "null")
  "," "\\"rule_id\\"" ":" ws (string | "null")
  "}" ws
category ::= "\\"theme\\"" | "\\"character\\"" | "\\"structure\\"" | "\\"dialogue\\"" | "\\"scene_function\\"" | "\\"plot_thread\\"" | "\\"genre\\""
severity ::= "\\"low\\"" | "\\"medium\\"" | "\\"high\\""
int-array ::= "[" ws (integer ("," ws integer)*)? "]" ws
integer ::= "-"? ([0-9] | [1-9] [0-9]{0,15})
string ::= "\\"" ( [^"\\\\\\x7F\\x00-\\x1F] | "\\\\" (["\\\\bfnrt] | "u" [0-9a-fA-F]{4}) )* "\\"" ws
ws ::= | " " | "\\n" [ \\t]{0,20}'''
    variants.append(("V4 full upstream-dialect rewrite", v4))

    v5 = '''root   ::= object
value  ::= object | array | string | number | ("true" | "false" | "null") ws
object ::= "{" ws ( string ":" ws value ("," ws string ":" ws value)* )? "}" ws
array  ::= "[" ws ( value ("," ws value)* )? "]" ws
string ::= "\\"" ( [^"\\\\\\x7F\\x00-\\x1F] | "\\\\" (["\\\\bfnrt] | "u" [0-9a-fA-F]{4}) # escapes )* "\\"" ws
number ::= ("-"? ([0-9] | [1-9] [0-9]{0,15})) ("." [0-9]+)? ([eE] [-+]? [0-9] [1-9]{0,15})? ws
ws ::= | " " | "\\n" [ \\t]{0,20}'''
    variants.append(("V5 llama.cpp reference json.gbnf (sanity)", v5))
    return variants


def main():
    variants = build_variants()
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not (0 <= idx < len(variants)):
        print(f"variant index must be 0..{len(variants) - 1}")
        return 2

    try:
        requests.get(HEALTH, timeout=5)
    except Exception:
        print("SERVER IS DOWN — nothing listening on :8080. Restart llama-server first.")
        return 1

    name, grammar = variants[idx]
    print(f"testing [{idx}] {name} ...")
    try:
        r = requests.post(URL, json=dict(PAYLOAD, grammar=grammar), timeout=90)
    except requests.exceptions.ConnectionError as e:
        print(f"SERVER DIED while processing this grammar (connection error): {e}")
        return 1
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return 1

    if r.status_code == 200:
        print("PASS — grammar accepted, constrained generation started")
        return 0
    print(f"FAIL ({r.status_code}): {r.text[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
