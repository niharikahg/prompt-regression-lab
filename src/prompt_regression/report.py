"""Small dependency-free HTML report renderer."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_report(result: dict[str, Any], destination: Path, max_accuracy_drop: float) -> None:
    escaped = lambda value: html.escape(str(value))
    rows = []
    for case in result["cases"]:
        state = "PASS" if case["passed"] else "FAIL"
        rows.append(
            "<tr>"
            f"<td>{escaped(case['id'])}</td><td>{state}</td>"
            f"<td>{escaped(case['expected']['category'])}</td>"
            f"<td>{escaped(case['actual']['category'])}</td>"
            f"<td>{escaped(case['input'])}</td>"
            "</tr>"
        )
    baseline = result.get("baseline_accuracy")
    baseline_label = f"{baseline:.1%}" if baseline is not None else "Not set"
    regressions = result.get("regressions", [])
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Prompt Regression Lab · {escaped(result['prompt_version'])}</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#172033;background:#f5f7fb}}
h1{{margin-bottom:4px}}.muted{{color:#617089}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}
.card{{background:white;border:1px solid #dce3ef;border-radius:12px;padding:16px 20px;min-width:150px}}
.value{{display:block;font-size:1.6rem;font-weight:700}}table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:11px;border-bottom:1px solid #e5eaf2;vertical-align:top}}th{{background:#eaf0f8}}
pre{{white-space:pre-wrap;background:white;padding:16px;border-radius:12px;overflow:auto}}
</style><body><h1>Prompt Regression Lab</h1>
<div class="muted">Prompt {escaped(result['prompt_version'])} · {escaped(result['timestamp'])}</div>
<section class="cards"><div class="card">Accuracy<span class="value">{result['accuracy']:.1%}</span></div>
<div class="card">Baseline<span class="value">{baseline_label}</span></div>
<div class="card">Regressions<span class="value">{len(regressions)}</span></div>
<div class="card">Cases<span class="value">{result['total']}</span></div>
<div class="card">Allowed drop<span class="value">{max_accuracy_drop:.1%}</span></div></section>
<h2>Per-category accuracy</h2><ul>{''.join(f'<li>{escaped(k)}: {v:.1%}</li>' for k,v in result['by_category'].items())}</ul>
<h2>Case results</h2><table><thead><tr><th>Case</th><th>Result</th><th>Expected</th><th>Actual</th><th>Input</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table><h2>Machine-readable run</h2><details><summary>Show JSON</summary><pre>{escaped(payload)}</pre></details>
</body></html>"""
    destination.write_text(document, encoding="utf-8")
