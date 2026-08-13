import json, re
import pdfplumber

pdf_path = 'studio_projects/Pain_FD_4_scenes/source.pdf'
parsed_path = 'studio_projects/Pain_FD_4_scenes/parsed.json'

# 1. Raw PDF text
pdf_lines = []
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        t = page.extract_text() or ''
        pdf_lines.append(t)
pdf_text = '\n'.join(pdf_lines)

# 2. Parsed text reconstructed from elements
p = json.load(open(parsed_path))
parsed_lines = []
for s in p['scenes']:
    parsed_lines.append(s['heading_raw'])
    for e in s['elements']:
        parsed_lines.append(e['text'])
parsed_text = '\n'.join(parsed_lines)

def norm(t):
    t = t.replace('\u2019', "'").replace('\u2018', "'")
    t = re.sub(r'[^\w\s.,\'-]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

pn = norm(pdf_text)
qn = norm(parsed_text)

print(f'PDF  normalized length: {len(pn)} chars')
print(f'Parsed normalized length: {len(qn)} chars')

# token-level diff (words in pdf missing from parsed, and vice versa)
from collections import Counter
pdf_words = Counter(pn.split())
parsed_words = Counter(qn.split())
missing = pdf_words - parsed_words
extra = parsed_words - pdf_words
print(f'\nwords in PDF but MISSING from parsed ({sum(missing.values())} total, {len(missing)} unique):')
for w, c in missing.most_common(40):
    print(f'  {w!r} x{c}')
print(f'\nwords in parsed but NOT in PDF ({sum(extra.values())} total, {len(extra)} unique):')
for w, c in extra.most_common(20):
    print(f'  {w!r} x{c}')
