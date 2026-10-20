"""Render a self-contained HTML classifier evaluation report."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def write_report(result: dict[str, Any], destination: Path) -> None:
    esc = lambda value: html.escape(str(value))
    rows = []
    for case in result["cases"]:
        state = "PASS" if case["passed"] else "FAIL"
        rows.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in (
            case["id"], state, case["expected_category"], case["actual_category"],
            case["expected_difficulty"], case["input"], case["expected_summary"], case["actual_summary"],
        )) + "</tr>")
    body = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Prompt Regression Lab report</title><style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:1500px;margin:32px auto;padding:0 18px;color:#172033;background:#f5f7fb}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}.card{{background:white;border:1px solid #dce3ef;border-radius:10px;padding:12px 18px}}
.value{{display:block;font-size:1.4rem;font-weight:700}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:9px;text-align:left;vertical-align:top;border-bottom:1px solid #e5eaf2}}th{{background:#eaf0f8}}
</style><body><h1>Prompt Regression Lab</h1><p>Prompt: {esc(result['prompt_version'])} · Model: {esc(result['model'])} · Dataset: {esc(result['dataset_version'])}</p>
<section class="cards"><div class="card">Exact case accuracy<span class="value">{result['accuracy']:.1%}</span></div>
<div class="card">Category accuracy<span class="value">{result['category_accuracy']:.1%}</span></div>
<div class="card">Summary similarity (token F1)<span class="value">{result['mean_summary_f1']:.1%}</span></div>
<div class="card">Passes<span class="value">{result['passed']}/{result['total']}</span></div></section>
<h2>Case results</h2><div style="overflow-x:auto"><table><thead><tr><th>ID</th><th>Result</th><th>Expected category</th><th>Actual category</th><th>Difficulty</th><th>Email</th><th>Expected summary</th><th>Actual summary</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></body></html>"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body, encoding="utf-8")
