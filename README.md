# Prompt Regression Lab

Prompt Regression Lab evaluates the real **Ask My Journal** endpoint from [Daybook AI Journal](https://github.com/niharikahg/daybook-ai-journal). It sends synthetic questions and synthetic journal entries to a running Daybook instance, then checks which entry dates the feature retrieved, whether it abstained when the answer was absent, and how long the request took.

## What this version covers

- The Daybook endpoint contract: `POST /api/ask` with `{ "question": string, "entries": Entry[] }` and `{ "answer": string, "dates": string[] }` response fields.
- Eight synthetic golden cases for relevant-entry retrieval, multiple relevant entries, summary/topic retrieval, and abstention.
- Exact case accuracy, date precision/recall/F1, abstention accuracy, mean latency, and p95 latency.
- Case-by-case HTML reports and optional baseline comparisons.
- Pull request validation of the golden-set schema.

The test cases contain fabricated journal content only. They do not read or send your personal Daybook entries. If the Daybook server has `OPENAI_API_KEY` configured, its normal answer route will send these synthetic questions and entries to OpenAI. To evaluate the local deterministic fallback, run Daybook without that key.

## Run against Daybook locally

Requires Python 3.11+ and no third-party Python packages. Start Daybook in another terminal so its API is available at `http://localhost:3000/api/ask`:

```sh
pnpm dev
```

Then, from this repository root:

```sh
PYTHONPATH=src python3 -m prompt_regression --validate-only
PYTHONPATH=src python3 -m prompt_regression --save-baseline
PYTHONPATH=src python3 -m prompt_regression
```

Set `DAYBOOK_ASK_URL` or pass `--endpoint` to point at a different running Daybook instance. `--save-baseline` writes `data/daybook-baseline.json` only when every golden case passes; later runs compare against it. Review and commit that baseline when you want it to become the comparison point for the project. HTML reports are written to `reports/`.

If the endpoint is unavailable or returns an invalid payload, affected cases fail and the report records the error. The baseline should only be saved from a successful run.

## Evaluation limits

This first integration checks retrieval evidence and abstention behavior. It does not judge whether a generated answer is semantically complete or factually correct beyond its cited dates. Token usage is not returned by Daybook's current API. The GitHub Action currently validates dataset structure only; running model evaluations in CI needs a reachable Daybook endpoint and a deliberate cross-repository setup.

## Project layout

```text
data/daybook-golden.json          Synthetic questions, journal entries, and expected evidence
src/prompt_regression/runner.py   HTTP client, dataset validation, scoring, baseline comparison
src/prompt_regression/report.py   Dependency-free HTML report
.github/workflows/evaluate.yml    Golden-set schema validation on pull requests
```

Never add real journal entries, API keys, or other personal data to this repository.
