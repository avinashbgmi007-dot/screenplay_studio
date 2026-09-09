import os
outpath = os.path.join("docs", "design", "ux2026", "wireframes", "index.html")
os.makedirs(os.path.dirname(outpath), exist_ok=True)

css = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,sans-serif;background:#111;color:#ccc;font-size:13px}
.tabs{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;background:#1a1a1a;border-bottom:1px solid #333;padding:0 16px}
.tab{padding:10px 18px;cursor:pointer;color:#888;border-bottom:2px solid transparent;font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.tab:hover{color:#bbb}.tab.active{color:#e0e0e0;border-bottom-color:#7e6bff}
.pg{display:none;padding-top:44px;height:100vh}.pg.on{display:block}
.w{border:1px dashed #444;background:#1a1a1a;border-radius:6px;padding:8px;position:relative}
.lb{position:absolute;top:-10px;left:8px;background:#111;padding:0 4px;font-size:10px;color:#666;text-transform:uppercase;letter-spacing:.08em}
.bt{display:inline-block;border:1px solid #555;border-radius:4px;padding:4px 10px;font-size:11px;color:#999;background:#222}
.bt.pr{border-color:#7e6bff;color:#7e6bff}
.inp{border:1px solid #444;border-radius:4px;padding:5px 8px;background:#1a1a1a;color:#888;font-size:11px;width:100%}
.tx{color:#555;font-size:11px;line-height:1.5}.hd{color:#999;font-size:14px;font-weight:600}
.se{font-family:Georgia,serif;color:#888;font-style:italic}
.mo{font-family:Courier New,monospace;font-size:11px;color:#777}
.dt{display:inline-block;width:6px;height:6px;border-radius:50%;background:#444}
.dg{background:#4ade80}.da{background:#fbbf24}
.sp{border:none;border-top:1px dashed #333;margin:6px 0}
.nt{font-size:10px;color:#555;font-style:italic;margin-top:4px}
.fl{display:flex}.ac{align-items:center}.jb{justify-content:space-between}
.g4{gap:4px}.g8{gap:8px}.g16{gap:16px}.f1{flex:1}
"""

# Read the HTML template
with open("_wf_template.html", "r") as f:
    html = f.read()

with open(outpath, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written {len(html)} bytes to {outpath}")