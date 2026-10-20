"""Small dependency-free HTML report renderer for Daybook evaluations."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_report(result: dict[str, Any], destination: Path, max_accuracy_drop: float) -> None:
    escape = lambda value: html.escape(str(value))
    rows = []
    for case in result["cases"]:
        state = "PASS" if case["passed"] else "FAIL"
        error = f"<br><strong>Error:</strong> {escape(case['error'])}" if case.get("error") else ""
        rows.append(
            "<tr>"
            f"<td>{escape(case['id'])}</td><td>{state}</td>"
            f"<td>{escape(', '.join(case['expected_dates']) or 'No dates')}</td>"
            f"<td>{escape(', '.join(case['actual_dates']) or 'No dates')}</td>"
            f"<td>{escape(case['question'])}{error}</td>"
            f"<td>{escape(case['answer'])}</td>"
            f"<td>{case['date_f1']:.0%}</td>"
            f"<td>{case['latency_ms'] if case['latency_ms'] is not None else '—'}</td>"
            "</tr>"
        )
    baseline = result.get("baseline_accuracy")
    baseline_label = f"{baseline:.1%}" if baseline is not None else "Not set"
    regressions = len(result.get("regressions", []))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Daybook Ask My Journal evaluation</title>
<style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:1200px;margin:36px auto;padding:0 20px;color:#172033;background:#f5f7fb}}
h1{{margin-bottom:4px}}.muted{{color:#617089;overflow-wrap:anywhere}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}
.card{{background:white;border:1px solid #dce3ef;border-radius:12px;padding:14px 18px;min-width:130px}}
.value{{display:block;font-size:1.5rem;font-weight:700}}table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid #e5eaf2;vertical-align:top}}th{{background:#eaf0f8}}
pre{{white-space:pre-wrap;background:white;padding:16px;border-radius:12px;overflow:auto}}.wrap{{overflow-wrap:anywhere}}
</style><body><h1>Daybook Ask My Journal evaluation</h1>
<div class="muted">{escape(result['timestamp'])} · endpoint {escape(result['endpoint'])}</div>
<section class="cards"><div class="card">Exact-case accuracy<span class="value">{result['accuracy']:.1%}</span></div>
<div class="card">Date precision<span class="value">{result['date_precision']:.1%}</span></div>
<div class="card">Date recall<span class="value">{result['date_recall']:.1%}</span></div>
<div class="card">Date F1<span class="value">{result['date_f1']:.1%}</span></div>
<div class="card">Abstention accuracy<span class="value">{result['abstention_accuracy']:.1%}</span></div>
<div class="card">Baseline accuracy<span class="value">{baseline_label}</span></div>
<div class="card">Regressions<span class="value">{regressions}</span></div></section>
<p class="muted">Configured accuracy-drop threshold: {max_accuracy_drop:.1%}. Latency excludes client/network setup and reflects this run's endpoint response time.</p>
<h2>Case results</h2><div class="wrap"><table><thead><tr><th>Case</th><th>Result</th><th>Expected dates</th><th>Returned dates</th><th>Question</th><th>Answer</th><th>Date F1</th><th>Latency ms</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>Machine-readable run</h2><details><summary>Show JSON</summary><pre>{escape(payload)}</pre></details>
</body></html>"""
    destination.write_text(document, encoding="utf-8")
