#!/usr/bin/env python
# WCAG 2.1 contrast audit — five design directions, deterministic math.
# Usage: python directions_contrast_audit.py
# Every ratio computed with the proper relative-luminance formula (linearized sRGB).

def lum(h):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def ratio(fg, bg):
    l1, l2 = lum(fg), lum(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

# ---- pair sets per direction: (label, fg, bg, class) ----
# class: body = needs 4.5:1 | ui = needs 3:1 | large = needs 3:1
D1 = [  # Marked Proof — light paper
    ("body ink on sheet", "#1f1b16", "#faf6ea", "body"),
    ("dim graphite on sheet", "#6a655c", "#faf6ea", "body"),
    ("sticky text on sticky bg", "#4a3d20", "#f6e9b8", "body"),
    ("sticky textarea input", "#4a3d20", "#f6e9b8", "body"),
    ("red pencil on sheet", "#b3372b", "#faf6ea", "body"),
    ("blue pencil on sheet", "#3f5d8c", "#faf6ea", "body"),
    ("graphite on field (desk)", "#6a655c", "#e3ddcc", "body"),
]
D2 = [  # Night Room — dark room + light pages (two surfaces)
    ("room text on night", "#d8cbb5", "#0d0b08", "body"),
    ("room dim on night", "#8d8272", "#0d0b08", "body"),
    ("ember on night", "#e8a24f", "#0d0b08", "body"),
    ("moon on night", "#a9b7c4", "#0d0b08", "body"),
    ("page ink on page", "#292219", "#f4e9d3", "body"),
    ("page dim on page", "#6d6050", "#f4e9d3", "body"),
    ("composer text on night-2", "#d8cbb5", "#14110d", "body"),
    ("sticky hand on night-2", "#d9c9a8", "#14110d", "body"),
    ("high glow #c4563a on page", "#c4563a", "#f4e9d3", "body"),
    ("mid glow #b07a3a on page", "#b07a3a", "#f4e9d3", "body"),
    ("low glow #5a7896 on page", "#5a7896", "#f4e9d3", "body"),
    ("presence dim on night-2", "#8d8272", "#14110d", "body"),
    ("qfloat input on night", "#d8cbb5", "#0d0b08", "body"),
]
D3 = [  # The Consultation — clinical light
    ("body ink on clinic", "#22252b", "#f6f7f5", "body"),
    ("ink-2 on clinic", "#4d525e", "#f6f7f5", "body"),
    ("ink-3 on clinic", "#8a8f9c", "#f6f7f5", "body"),
    ("ink-3 on white panel", "#8a8f9c", "#ffffff", "body"),
    ("clay high on clinic", "#a4442f", "#f6f7f5", "body"),
    ("amber mid on clinic", "#8a6210", "#f6f7f5", "body"),
    ("slate low on clinic", "#3a5578", "#f6f7f5", "body"),
    ("tea resolved on clinic", "#2e6b52", "#f6f7f5", "body"),
    ("chart file mono on clinic", "#8a8f9c", "#f6f7f5", "body"),
    ("clay on clay-bg (7% on clinic)", "#a4442f", "#eee8e3", "body"),
    ("amber on amber-bg (7% on clinic)", "#8a6210", "#f1ecd8", "body"),
]
D4 = [  # Screening Room — dark booth
    ("txt on projection", "#e5e0d3", "#08090c", "body"),
    ("dim on projection", "#8f8c81", "#08090c", "body"),
    ("amber on projection", "#e0b45c", "#08090c", "body"),
    ("amber on screen-2", "#e0b45c", "#161a22", "body"),
    ("paper on screen-2 (slate)", "#f6f0e2", "#161a22", "body"),
    ("slate dim #b9b2a2 on screen-2", "#b9b2a2", "#161a22", "body"),
    ("paren #9b9182 on screen-2", "#9b9182", "#161a22", "body"),
    ("mark-red on projection", "#e2725b", "#08090c", "body"),
    ("mark-teal on projection", "#69b3a7", "#08090c", "body"),
    ("frame nm on screen", "#e5e0d3", "#101319", "body"),
    ("paper on screen (framecard)", "#f6f0e2", "#101319", "body"),
    ("amber on screen", "#e0b45c", "#101319", "body"),
    ("dim on screen", "#8f8c81", "#101319", "body"),
    ("m-low #8ea2c4 on screen", "#8ea2c4", "#101319", "body"),
]
D4V2 = [  # Screening Room v2 — warm booth + bright paper stage (two surfaces, severity never as text)
    ("room text on booth", "#d8cbb5", "#0d0b08", "body"),
    ("room dim on booth", "#8d8272", "#0d0b08", "body"),
    ("amber on booth", "#e0b45c", "#0d0b08", "body"),
    ("amber on booth-2", "#e0b45c", "#14110d", "body"),
    ("moon (sushruta) on booth", "#a9b7c4", "#0d0b08", "body"),
    ("moon on booth-2", "#a9b7c4", "#14110d", "body"),
    ("page ink on page", "#292219", "#f4e9d3", "body"),
    ("page dim on page", "#6d6050", "#f4e9d3", "body"),
    ("paper dot high on page", "#c4563a", "#f4e9d3", "ui"),
    ("paper dot mid on page", "#b07a3a", "#f4e9d3", "ui"),
    ("paper dot low on page", "#5a7896", "#f4e9d3", "ui"),
    ("rail border high on booth-2", "#e2725b", "#14110d", "ui"),
    ("rail border mid on booth-2", "#e0b45c", "#14110d", "ui"),
    ("rail border low on booth-2", "#a9b7c4", "#14110d", "ui"),
    ("dnote title on booth-2", "#d8cbb5", "#14110d", "body"),
    ("dnote body dim on booth-2", "#8d8272", "#14110d", "body"),
    ("cue text on booth-2", "#cfc8b8", "#14110d", "body"),
    ("sticky hand on booth-2", "#d9c9a8", "#14110d", "body"),
    ("status teal on booth", "#69b3a7", "#0d0b08", "body"),
    ("status teal on booth-2 (deck live)", "#69b3a7", "#14110d", "body"),
    ("status red on booth", "#e2725b", "#0d0b08", "body"),
    ("gr sam hand on booth-2", "#ead9b0", "#14110d", "body"),
    ("gr-ask input on booth-2", "#d8cbb5", "#14110d", "body"),
    ("selbar quote on booth-2", "#d8cbb5", "#14110d", "body"),
    ("deck dim on booth-2", "#8d8272", "#14110d", "body"),
]
D4V21 = [  # Screening Room v2.1 — graft surfaces (blends computed: alpha over base)
    # .dpick chip: rgba(224,180,92,.10) wash over booth-2 #14110d -> #282115
    ("pk-label amber on dpick chip", "#e0b45c", "#282115", "body"),
    ("pk-conf cue on dpick chip", "#cfc8b8", "#282115", "body"),
    # takecard on booth-2
    ("tk-head amber on takecard", "#e0b45c", "#14110d", "body"),
    ("tk-why dim on takecard", "#8d8272", "#14110d", "body"),
    ("tk old label red on old wash", "#e2725b", "#1e1611", "body"),   # rgba(226,114,91,.05) over booth-2
    ("tk new label teal on new wash", "#69b3a7", "#191b16", "body"),  # rgba(105,179,167,.06) over booth-2
    ("tk quote cue on booth-2", "#cfc8b8", "#14110d", "body"),
    ("tk-keep dim on booth-2", "#8d8272", "#14110d", "body"),
    ("tk-apply ink on amber", "#221704", "#e0b45c", "body"),
    # changestrip.on-paper: rgba(105,179,167,.10) over page #f4e9d3 -> #e6e4cf
    ("cs-title teal-ink on paper strip", "#276d63", "#e6e4cf", "body"),
    ("cs-copy page-dim on paper strip", "#6d6050", "#e6e4cf", "body"),
    ("cs-action teal-ink on paper strip", "#276d63", "#e6e4cf", "body"),
    ("strip border teal-ink on paper", "#276d63", "#f4e9d3", "ui"),
    # (the .fl.taken dot keeps its SEVERITY color after the semiotic fix — covered by the fdot pairs above)
    # lamptruth on booth-2
    ("lt-copy txt on booth-2", "#d8cbb5", "#14110d", "body"),
    ("lt small dim on booth-2", "#8d8272", "#14110d", "body"),
    ("lt state teal on booth-2", "#69b3a7", "#14110d", "body"),
    ("lt state amber (demo) on booth-2", "#e0b45c", "#14110d", "body"),
    ("lt state red (dead) on booth-2", "#e2725b", "#14110d", "body"),
    # readingseat (Sameer keeps his amber in the decision seat — moon is Sushruta's alone)
    ("rs who amber on booth-2", "#e0b45c", "#14110d", "body"),
    ("rs line txt on booth-2", "#d8cbb5", "#14110d", "body"),
    ("rs input txt on booth-2", "#d8cbb5", "#14110d", "body"),
    ("rs send amber on booth-2", "#e0b45c", "#14110d", "body"),
    # cleared / holds tags on the dnote rail surface (booth-2)
    ("cleared-tag teal on booth-2", "#69b3a7", "#14110d", "body"),
    ("holds-tag amber on booth-2", "#e0b45c", "#14110d", "body"),
    ("nacts dim on booth-2", "#8d8272", "#14110d", "body"),
    # selectfloat on booth-2
    ("selectfloat amber on booth-2", "#e0b45c", "#14110d", "body"),
    # graduation receipt on amber over booth-2: rgba(224,180,92,.10) -> #282115
    ("grad receipt amber on chip", "#e0b45c", "#282115", "body"),
    # .dnote.cleared dimmed key/h4 on booth-2
    ("cleared key dim on booth-2", "#8d8272", "#14110d", "body"),
]
D5 = [  # Atelier — warm workshop light
    ("ink on paper", "#241f18", "#fbf7ec", "body"),
    ("ink-2 on paper", "#5c5449", "#fbf7ec", "body"),
    ("ink-3 on paper", "#948a79", "#fbf7ec", "body"),
    ("ink on plaster wall", "#241f18", "#e9e4d8", "body"),
    ("ink-2 on plaster", "#5c5449", "#e9e4d8", "body"),
    ("ink-3 on plaster", "#948a79", "#e9e4d8", "body"),
    ("terracotta high on paper", "#b45a3c", "#fbf7ec", "body"),
    ("brass mid on paper", "#96712a", "#fbf7ec", "body"),
    ("patina resolved on paper", "#5d7a5a", "#fbf7ec", "body"),
    ("toolsteel on paper", "#2e4a62", "#fbf7ec", "body"),
    ("sameer hand #5c4a22 on plaster", "#5c4a22", "#e9e4d8", "body"),
    ("alc-ask textarea ink on plaster", "#241f18", "#e9e4d8", "body"),
    ("benchcard ink on paper", "#241f18", "#fbf7ec", "body"),
]

def verdict(r, cls):
    need = 4.5 if cls == "body" else 3.0
    return "PASS" if r >= need else ("PASS-large-only" if r >= 3.0 else "FAIL")

FILES = [
    ("D1 Marked Proof", D1),
    ("D2 Night Room", D2),
    ("D3 Consultation", D3),
    ("D4 Screening Room", D4),
    ("D4v2 Screening Room", D4V2),
    ("D4v2.1 Graft Surfaces", D4V21),
    ("D5 Atelier", D5),
]

for name, pairs in FILES:
    print(f"\n========== {name} ==========")
    fails = []
    for label, fg, bg, cls in pairs:
        r = ratio(fg, bg)
        v = verdict(r, cls)
        mark = "" if v == "PASS" else "  <<< " + v
        print(f"  {label:42s} {fg} on {bg}  {r:5.2f}:1 {v}{mark}")
        if v != "PASS":
            fails.append((label, fg, bg, r, v))
    if fails:
        print(f"  -- {len(fails)} flagged pair(s)")
    else:
        print("  -- all pairs pass")

print("\n================ SUMMARY ================")
for name, pairs in FILES:
    fl = [(l, f, b, ratio(f, b)) for l, f, b, c in pairs if verdict(ratio(f, b), c) != "PASS"]
    print(f"{name}: {len(fl)} failing/flaged of {len(pairs)}")
    for l, f, b, r in fl:
        print(f"    - {l}: {r:.2f}:1")
