#!/usr/bin/env python
# Compute corrected token values: nearest hue-preserving hex that passes 4.5:1 on its real bg.

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

def darken(hex_color, step=2):
    """Scale RGB toward black, preserving hue ratios."""
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    f = 1 - step / 100
    return '#%02x%02x%02x' % (int(r * f), int(g * f), int(b * f))

def find_pass(fg, bg, need=4.5, label=''):
    cur, n = fg, 0
    while ratio(cur, bg) < need and n < 40:
        cur = darken(cur, 3)
        n += 1
    print(f"{label:44s} {fg} -> {cur}  {ratio(fg,bg):.2f} -> {ratio(cur,bg):.2f}:1 (need {need})")
    return cur

# D1: graphite on field
find_pass('#6a655c', '#e3ddcc', 4.5, 'D1 graphite on field')
# D2: severity text-as-ink problem -> we restructure instead; badge chip colors on page for 3:1 UI
print('D2 severity dot/dot as UI component (3:1 on page #f4e9d3):')
for name, c in [('high #c4563a', '#c4563a'), ('mid #b07a3a', '#b07a3a'), ('low #5a7896', '#5a7896')]:
    print(f"   {name}: {ratio(c, '#f4e9d3'):.2f}:1 as UI component", "PASS" if ratio(c, '#f4e9d3') >= 3 else "FAIL")
# D3: ink-3 on clinic and panel
find_pass('#8a8f9c', '#f6f7f5', 4.5, 'D3 ink-3 on clinic')
find_pass('#8a8f9c', '#ffffff', 4.5, 'D3 ink-3 on white panel')
# D3 focus candidate: deep clinical indigo distinct from slate
for cand in ['#2c2f6e', '#33366b', '#3a3560']:
    print(f"D3 focus cand {cand} on clinic #f6f7f5: {ratio(cand, '#f6f7f5'):.2f}:1 ; vs slate #3a5578 distinct hue")
# D5: ink-3 on plaster + paper; severity ramp on paper
find_pass('#948a79', '#e9e4d8', 4.5, 'D5 ink-3 on plaster')
find_pass('#948a79', '#fbf7ec', 4.5, 'D5 ink-3 on paper')
find_pass('#b45a3c', '#fbf7ec', 4.5, 'D5 terracotta on paper')
find_pass('#96712a', '#fbf7ec', 4.5, 'D5 brass on paper')
find_pass('#5d7a5a', '#fbf7ec', 4.5, 'D5 patina on paper')
# D5 tagplates sit on paper bg (inside .ms): confirm terracotta/brass also on plaster (alcove/bench areas?)
find_pass('#b45a3c', '#e9e4d8', 4.5, 'D5 terracotta on plaster')
find_pass('#96712a', '#e9e4d8', 4.5, 'D5 brass on plaster')
find_pass('#5d7a5a', '#e9e4d8', 4.5, 'D5 patina on plaster')
# D5 sameer hand color on plaster already 6.74 pass. Sushruta label = ink-2 pass (5.87).
