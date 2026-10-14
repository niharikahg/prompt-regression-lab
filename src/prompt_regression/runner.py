"""Deterministic starter classifier and golden-set evaluation runner."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import write_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "golden.json"
DEFAULT_BASELINE = ROOT / "data" / "baseline.json"
DEFAULT_REPORTS = ROOT / "reports"

RULES = {
    "billing": ("charge", "charged", "invoice", "refund", "payment", "price", "tax"),
    "technical": ("crash", "error", "bug", "upload", "502", "broken", "fail"),
    "account": ("account", "password", "email", "sign in", "login", "close my"),
}


def classify(message: str, prompt_version: str) -> dict[str, str]:
    """Local stand-in for an LLM adapter; v2 intentionally introduces a regression."""
    text = message.casefold()
    scores = {category: sum(term in text for term in terms) for category, terms in RULES.items()}
    category = max(scores, key=scores.get) if max(scores.values(), default=0) else "general"
    if prompt_version == "v2" and "invoice" in text:
        category = "general"  # Deliberate fault for demonstrating regression detection.
    compact = re.sub(r"\s+", " ", message).strip().rstrip(".!?")
    summary = compact[:110] + ("…" if len(compact) > 110 else "")
    return {"category": category, "summary": summary}


def evaluate(dataset: list[dict[str, Any]], prompt_version: str) -> dict[str, Any]:
    cases = []
    by_category: dict[str, list[bool]] = defaultdict(list)
    for item in dataset:
        prediction = classify(item["input"], prompt_version)
        expected = item["expected"]
        passed = prediction["category"] == expected["category"]
        by_category[expected["category"]].append(passed)
        cases.append({
            "id": item["id"],
            "input": item["input"],
            "expected": expected,
            "actual": prediction,
            "passed": passed,
        })
    total = len(cases)
    return {
        "prompt_version": prompt_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "accuracy": sum(case["passed"] for case in cases) / total if total else 0,
        "by_category": {
            category: sum(values) / len(values) for category, values in sorted(by_category.items())
        },
        "cases": cases,
    }


def compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    old = {case["id"]: case for case in baseline.get("cases", [])}
    current["regressions"] = [
        {"before": old[case["id"]]["actual"], "after": case["actual"], **case}
        for case in current["cases"]
        if case["id"] in old and old[case["id"]]["passed"] and not case["passed"]
    ]
    current["improvements"] = [
        {"before": old[case["id"]]["actual"], "after": case["actual"], **case}
        for case in current["cases"]
        if case["id"] in old and not old[case["id"]]["passed"] and case["passed"]
    ]
    current["baseline_accuracy"] = baseline.get("accuracy", 0)
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a prompt version against a golden dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--max-accuracy-drop", type=float, default=0.03)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = evaluate(dataset, args.prompt_version)
    if args.baseline.exists() and not args.save_baseline:
        result = compare(result, json.loads(args.baseline.read_text(encoding="utf-8")))
    elif args.save_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    args.reports.mkdir(parents=True, exist_ok=True)
    report_path = args.reports / f"{args.prompt_version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    write_report(result, report_path, args.max_accuracy_drop)
    print(f"Accuracy: {result['accuracy']:.1%} ({result['total']} cases)")
    print(f"Report: {report_path}")
    if result.get("regressions"):
        print(f"Regressions: {len(result['regressions'])}")
    dropped = result.get("baseline_accuracy", result["accuracy"]) - result["accuracy"]
    return 1 if dropped > args.max_accuracy_drop else 0


if __name__ == "__main__":
    raise SystemExit(main())
