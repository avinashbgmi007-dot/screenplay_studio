# screenplay_analyzer/report.py

## Purpose
Report generation for analysis results. Converts findings into human-readable formats (Markdown, JSON).

## Key Functions

### `render_markdown(results: dict) -> str`
Renders analysis results as Markdown. Includes:
- Executive summary
- Scene summaries
- Findings with evidence
- Recommendations

### `to_findings_json(results: dict) -> str`
Converts results to JSON format for programmatic consumption.

### `save_report(results: dict, path: str) -> str`
Saves the report to a file. Returns the path.

## Dependencies
- `screenplay_analyzer.pipeline` (analysis results)
- `json` (stdlib)
- `datetime` (stdlib)

## Usage Example
```python
from screenplay_analyzer.report import save_report, render_markdown

results = analyze(doc, client)
save_report(results, "report.md")
print(render_markdown(results))  # Prints to stdout
```

## Graph Notes
- `save_report` connects to `ProjectManifest` (51 edges — most connected node)
- Report output is the final artifact of the analysis pipeline
