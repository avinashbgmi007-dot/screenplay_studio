import base64, sys
b64 = sys.stdin.read().strip()
html = base64.b64decode(b64).decode('utf-8')
with open('docs/design/ux2026/wireframes/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Written {len(html)} bytes')
