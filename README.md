# Prompt Regression Lab

A CI-oriented evaluation project for a customer support email classifier. The classifier maps each email to `billing`, `technical`, `account`, or `general` and returns a one-sentence summary. Prompts are versioned YAML configuration; evaluation uses a versioned, manually authored synthetic golden dataset.

## Current scope

- `src/prompt_regression/classifier.py`: typed Pydantic `PromptConfig` and `Classification` contracts plus an OpenAI structured-output classifier.
- `prompts/v1.yaml`: versioned prompt with metadata and few-shot examples.
- `data/email-golden-v1.json`: 51 synthetic cases with expected category, reference summary, difficulty, and notes. Includes short, ambiguous, typo-containing, sarcastic, and Spanish-language cases. Labels are manually authored rather than model-generated; please review them before describing them as human-verified ground truth.
- `src/prompt_regression/runner.py`: schema validation, model evaluation, category accuracy, summary token-F1, regression comparison, and HTML reporting.
- `.github/workflows/evaluate.yml`: validates the prompt and dataset on pull requests without requiring API credentials.

The examples are synthetic and must not be replaced with real customer emails or personal data.

## Setup

Requires Python 3.11+ and an OpenAI API key for live evaluation.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Validate configuration without making a model call:

```sh
PYTHONPATH=src python -m prompt_regression --validate-only
```

Run the model evaluation:

```sh
export OPENAI_API_KEY="your-key"
PYTHONPATH=src python -m prompt_regression
```

Select another prompt/model/dataset with `--prompt`, `--model`, and `--dataset`. The default report is written to `reports/email-evaluation.html` (reports are ignored by git).

## Scoring and regression checks

Category accuracy is exact. Summary comparison uses token-level F1 as a lightweight signal; it is not a semantic or factuality judge. A case passes when its category is correct and summary token-F1 is at least 0.25. Tune this threshold and the examples based on reviewed failure cases before relying on it as a release gate. Optional `--baseline PATH` fails if the exact pass rate is below the saved baseline. The baseline format is the JSON evaluation result; create one by saving/copying a reviewed run result intentionally.

The pull request workflow currently validates schema only. Running paid model calls in GitHub Actions requires configuring a secret and deciding whether each PR should make live calls; that is not enabled by default.

## Project layout

```text
prompts/v1.yaml                          Versioned prompt configuration
data/email-golden-v1.json               Versioned synthetic golden dataset
src/prompt_regression/classifier.py      Typed interface and model call
src/prompt_regression/runner.py           Validation, evaluation, and regression check
src/prompt_regression/report.py           Standalone HTML report
.github/workflows/evaluate.yml            Pull request configuration validation
```
