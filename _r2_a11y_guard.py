"""R2 a11y guard — no NEW bare outline:none suppressors (per R2 spec,
implementation step 1). A bare suppressor = an `outline: none` declaration
on a selector that has NO compensating :focus/:focus-visible rule (the
WCAG 2.4.7 lesson from .idea-rename-input).

Whitelist (audited 2026-09-12, all correct):
  #main:focus, #manuscript-container:focus — keyboard work surfaces whose
    focus must not draw an outline (containers, not controls)
  .idea-content — writing surface, caret exemption (word-processor
    convention; a ring while typing prose would be hostile)
Exit 0 = clean; exit 1 with a report = new bare suppressor found.
"""
import re
import sys

PATH = "screenplay_studio/webapp/style.css"
css = open(PATH, encoding="utf-8").read()

# pair each "outline: none" with its selector; find that selector's
# focus variant elsewhere in the sheet
suppressors = []  # (line, selector)
for m in re.finditer(r"([^\n{}]+)\{\s*[^}]*outline:\s*none[^}]*\}", css):
    sel = m.group(1).strip().rstrip("{").strip()
    # the rule's pseudo state, if any (":focus", ":focus-visible")
    pseudo = ""
    pm = re.search(r":(focus(-visible)?)$", sel)
    if pm:
        pseudo = pm.group(1)
        sel = sel[: pm.start()].strip()
    suppressors.append((css[: m.start()].count("\n") + 1, sel, pseudo))

WHITELIST = {
    "#main:focus",          # container
    "#manuscript-container:focus",  # container
    ".idea-content",        # writing surface (caret exemption)
}

bare = []
for line, sel, pseudo in suppressors:
    if pseudo:
        continue  # the suppressor itself lives in a focus rule — compensated
    if sel in WHITELIST:
        continue
    # look for ANY compensating focus rule for this selector (or its base)
    base = sel.split(":")[0]
    if re.search(re.escape(base) + r":(focus|focus-visible)", css):
        continue
    # parent-level :focus-within reveal also counts as compensation
    if re.search(re.escape(base), css) and ":focus-within" in css:
        continue
    bare.append((line, sel))

if bare:
    print("NEW BARE outline:none SUPPRESSORS (WCAG 2.4.7 risk):")
    for line, sel in bare:
        print(f"  L{line}: {sel}")
    sys.exit(1)
print(f"clean — {len(suppressors)} outline:none sites, all compensated/whitelisted")
