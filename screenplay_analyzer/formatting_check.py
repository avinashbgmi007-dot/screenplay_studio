"""
Formatting & industry-standard compliance checks — deterministic, no model
call. These are rule checks against the parsed structure, not subjective
judgment calls, so there's no reason to spend model tokens or risk
hallucination on them.
"""

import re

from screenplay_parser.models import ElementType, ScriptDocument


def check_formatting(doc: ScriptDocument) -> list[dict]:
    findings = []

    # 1. Scene headings missing INT/EXT or time-of-day
    for scene in doc.scenes:
        if not scene.int_ext:
            findings.append({
                "rule": "scene_heading_missing_int_ext",
                "severity": "medium",
                "scene_refs": [scene.scene_number],
                "message": f"Scene {scene.scene_number} heading (\"{scene.heading_raw}\") doesn't "
                            f"clearly start with INT./EXT./EST. — may confuse shooting-schedule tools.",
            })
        if not scene.time_of_day:
            findings.append({
                "rule": "scene_heading_missing_time_of_day",
                "severity": "low",
                "scene_refs": [scene.scene_number],
                "message": f"Scene {scene.scene_number} heading (\"{scene.heading_raw}\") has no "
                            f"time-of-day (DAY/NIGHT/etc.) after the location.",
            })

    # 2. Character introduced in dialogue before appearing in ALL CAPS in an action line
    #    (industry convention: a character's name should appear in caps in action
    #    text on their first appearance, not just as a dialogue-cue debut).
    #    Skipped when the script doesn't follow Hollywood caps conventions (e.g.
    #    Tenglish/non-English scripts where characters are introduced in dialogue
    #    and action lines use mixed case) — detected by checking whether ANY
    #    character is introduced in ALL CAPS in action text.
    introduced_in_action = set()
    # Language-aware: the ALL-CAPS introduction convention is a Hollywood
    # (English) formatting rule. If NO character is ever introduced in ALL
    # CAPS in action text, the script doesn't follow this convention (e.g.
    # Tenglish, Hindi, Tamil scripts) — skip the check entirely. If at least
    # one character IS introduced in caps, the script follows the convention
    # and we flag the rest.
    caps_introduced = set()
    for scene in doc.scenes:
        for el in scene.elements:
            if el.type == ElementType.ACTION:
                for name in doc.all_characters:
                    if name in caps_introduced:
                        continue
                    if re.search(rf"\b{re.escape(name)}\b", el.text):
                        caps_introduced.add(name)
    # Only apply the check if the script demonstrates the convention
    if len(caps_introduced) > 0:
        for scene in doc.scenes:
            for el in scene.elements:
                if el.type == ElementType.ACTION:
                    for name in doc.all_characters:
                        if name in introduced_in_action:
                            continue
                        if re.search(rf"\b{re.escape(name)}\b", el.text):
                            introduced_in_action.add(name)
                elif el.type == ElementType.CHARACTER and el.character:
                    if el.character not in introduced_in_action:
                        findings.append({
                            "rule": "character_not_capitalized_on_first_appearance",
                            "severity": "low",
                            "scene_refs": [scene.scene_number],
                            "message": f"'{el.character}' speaks in Scene {scene.scene_number} before "
                                        f"appearing in ALL CAPS in any action line — convention is to "
                                        f"introduce a character in caps in action text on first appearance.",
                        })
                        introduced_in_action.add(el.character)  # only flag once per character

    # 3. Heavy parenthetical usage per character (potential over-directing of actors)
    paren_counts = {}
    dialogue_counts = {}
    for scene in doc.scenes:
        for el in scene.elements:
            if el.character:
                if el.type == ElementType.PARENTHETICAL:
                    paren_counts[el.character] = paren_counts.get(el.character, 0) + 1
                elif el.type == ElementType.DIALOGUE:
                    dialogue_counts[el.character] = dialogue_counts.get(el.character, 0) + 1
    for name, p_count in paren_counts.items():
        d_count = dialogue_counts.get(name, 0)
        if d_count >= 5 and p_count / d_count > 0.4:
            findings.append({
                "rule": "heavy_parenthetical_usage",
                "severity": "low",
                "scene_refs": [],
                "message": f"'{name}' has parentheticals on {p_count}/{d_count} dialogue lines "
                            f"({round(100*p_count/d_count)}%) — worth checking these are earning "
                            f"their place rather than over-directing line readings.",
            })

    # 4. Very long unbroken action paragraphs (a soft proxy for "overwritten action" —
    #    the LLM-based check does the qualitative judgment; this just flags candidates)
    for scene in doc.scenes:
        for el in scene.elements:
            if el.type == ElementType.ACTION and len(el.text.split()) > 60:
                findings.append({
                    "rule": "long_action_block",
                    "severity": "low",
                    "scene_refs": [scene.scene_number],
                    "message": f"Scene {scene.scene_number} has an action line of "
                                f"{len(el.text.split())} words — worth a look for trimming.",
                })

    return findings
