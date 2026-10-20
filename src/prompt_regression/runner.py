"""Validate and run prompt regression evaluations."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .classifier import Classification, PromptConfig, classify_email
from .report import write_report

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"billing", "technical", "account", "general"}


def validate_dataset(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Dataset must be a JSON object."]
    if not isinstance(data.get("dataset_version"), str) or not data["dataset_version"]:
        errors.append("dataset_version must be a non-empty string")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty array"]
    seen: set[str] = set()
    for i, case in enumerate(cases):
        label = f"cases[{i}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = case.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append(f"{label}.id must be a non-empty string")
        elif cid in seen:
            errors.append(f"duplicate case id: {cid}")
        else:
            seen.add(cid)
        for field in ("input", "notes"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{label}.{field} must be a non-empty string")
        difficulty = case.get("expected_difficulty")
        if not isinstance(difficulty, str) or difficulty not in {"easy", "medium", "ambiguous", "hard"}:
            errors.append(f"{label}.expected_difficulty must be easy, medium, ambiguous, or hard")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{label}.expected must be an object")
        else:
            category = expected.get("category")
            if not isinstance(category, str) or category not in CATEGORIES:
                errors.append(f"{label}.expected.category must be one of {sorted(CATEGORIES)}")
            if not isinstance(expected.get("summary"), str) or not expected["summary"].strip():
                errors.append(f"{label}.expected.summary must be a non-empty string")
    return errors


def tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"[\w']+", text.casefold()))


def summary_f1(expected: str, actual: str) -> float:
    left, right = tokens(expected), tokens(actual)
    if not left or not right:
        return float(left == right)
    common = sum((left & right).values())
    precision, recall = common / sum(right.values()), common / sum(left.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate(dataset: dict[str, Any], prompt: PromptConfig, model: str) -> dict[str, Any]:
    results = []
    for case in dataset["cases"]:
        try:
            output: Classification = classify_email(case["input"], prompt, model)
            actual = output.model_dump()
            err = None
        except Exception as exc:  # Capture a per-case model/API failure in the report.
            actual = {"category": "ERROR", "summary": ""}
            err = f"{type(exc).__name__}: {exc}"
        category_ok = actual["category"] == case["expected"]["category"]
        sf1 = summary_f1(case["expected"]["summary"], actual["summary"])
        results.append({
            "id": case["id"], "input": case["input"],
            "expected_category": case["expected"]["category"], "actual_category": actual["category"],
            "expected_summary": case["expected"]["summary"], "actual_summary": actual["summary"],
            "expected_difficulty": case["expected_difficulty"], "notes": case["notes"],
            "category_passed": category_ok, "summary_f1": sf1,
            "passed": category_ok and sf1 >= 0.25, "error": err,
        })
    total = len(results)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(), "prompt_version": prompt.version,
        "dataset_version": dataset["dataset_version"], "model": model, "total": total,
        "passed": sum(row["passed"] for row in results),
        "accuracy": sum(row["passed"] for row in results) / total,
        "category_accuracy": sum(row["category_passed"] for row in results) / total,
        "mean_summary_f1": sum(row["summary_f1"] for row in results) / total,
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a support-email prompt against a versioned golden set.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/email-golden-v1.json")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts/v1.yaml")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/email-evaluation.html")
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--save-result", type=Path, default=None, help="Write machine-readable evaluation JSON to this path")
    args = parser.parse_args()
    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        prompt = PromptConfig.load(args.prompt)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    errors = validate_dataset(dataset)
    if errors:
        print("Golden dataset is invalid:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2
    print(f"Golden dataset valid: {len(dataset['cases'])} cases ({dataset['dataset_version']}); prompt {prompt.version}")
    if args.validate_only:
        return 0
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required to run model evaluations (schema validation succeeded).", file=sys.stderr)
        return 2
    result = evaluate(dataset, prompt, args.model)
    write_report(result, args.report)
    if args.save_result:
        args.save_result.parent.mkdir(parents=True, exist_ok=True)
        args.save_result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Exact pass rate: {result['accuracy']:.1%}; category accuracy: {result['category_accuracy']:.1%}; mean summary token-F1: {result['mean_summary_f1']:.1%}")
    print(f"Report: {args.report}")
    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        if result["accuracy"] < baseline.get("accuracy", 0):
            print("Regression detected: exact pass rate dropped below baseline.")
            return 1
    return int(result["passed"] != result["total"])


if __name__ == "__main__":
    raise SystemExit(main())
