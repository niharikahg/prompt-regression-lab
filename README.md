# Prompt Regression Lab

Prompt Regression Lab checks whether a prompt change improves or breaks a structured LLM feature before it ships. It runs a versioned golden dataset, scores category accuracy, compares each case with a saved baseline, and writes a self-contained HTML report.

This first slice is deliberately provider-free: the included deterministic classifier makes the evaluation workflow reproducible and costs nothing. Replace `classify()` in `src/prompt_regression/runner.py` with a provider adapter when ready; keep evaluation and reporting independent of the model.

## Run locally

Requires Python 3.11+ and no third-party packages.

```sh
PYTHONPATH=src python -m prompt_regression --dataset data/golden.json --prompt-version v1 --save-baseline
PYTHONPATH=src python -m prompt_regression --dataset data/golden.json --prompt-version v2
```

Reports are written to `reports/`. The first command saves a baseline to `data/baseline.json`; the second compares against it and exits with status 1 if regressions exceed the configured threshold.

## What it measures

- Exact category accuracy and per-category accuracy
- Case-level regressions and improvements against a baseline
- A configurable warning/critical accuracy drop threshold
- A portable HTML report with run metadata and output diffs

## Layout

```text
data/golden.json                 Human-reviewed examples and expected labels
src/prompt_regression/runner.py  Inference adapter and evaluation logic
src/prompt_regression/report.py  HTML report generation
.github/workflows/evaluate.yml   Pull request evaluation workflow
```

## Next steps

1. Expand the hand-labeled dataset to cover ambiguous, malformed, and multilingual inputs.
2. Add a provider interface and structured-output validation.
3. Persist run metadata and scores in SQLite for trend queries.
4. Add confidence intervals and a clearer distinction between statistical signal and a configurable policy threshold.
5. Add a PR summary and optional notification integration.

Dataset examples are synthetic and contain no personal information. Never commit real customer messages or API keys.
