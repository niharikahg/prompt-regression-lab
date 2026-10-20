"""Evaluate Daybook's Ask My Journal HTTP endpoint with synthetic examples."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .report import write_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "daybook-golden.json"
DEFAULT_BASELINE = ROOT / "data" / "daybook-baseline.json"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_ENDPOINT = "http://localhost:3000/api/ask"
ABSTENTION = "i couldn't find that in your journal."


def validate_dataset(dataset: Any) -> list[str]:
    """Return schema errors for the hand-reviewed synthetic evaluation set."""
    errors: list[str] = []
    if not isinstance(dataset, list) or not dataset:
        return ["Dataset must be a non-empty JSON array."]
    ids: set[str] = set()
    for index, case in enumerate(dataset):
        label = f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object.")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{label}.id must be a non-empty string.")
        elif case_id in ids:
            errors.append(f"Duplicate case id: {case_id}.")
        else:
            ids.add(case_id)
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            errors.append(f"{label}.question must be a non-empty string.")
        entries = case.get("entries")
        if not isinstance(entries, list):
            errors.append(f"{label}.entries must be an array.")
        else:
            for entry_index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append(f"{label}.entries[{entry_index}] must be an object.")
                    continue
                if not isinstance(entry.get("date"), str) or not entry["date"]:
                    errors.append(f"{label}.entries[{entry_index}].date must be a non-empty string.")
                if not isinstance(entry.get("text"), str):
                    errors.append(f"{label}.entries[{entry_index}].text must be a string.")
                if not isinstance(entry.get("summary", ""), str):
                    errors.append(f"{label}.entries[{entry_index}].summary must be a string.")
                if not isinstance(entry.get("topics", []), list):
                    errors.append(f"{label}.entries[{entry_index}].topics must be an array.")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{label}.expected must be an object.")
        else:
            if not isinstance(expected.get("dates"), list) or not all(
                isinstance(date, str) for date in expected.get("dates", [])
            ):
                errors.append(f"{label}.expected.dates must be an array of strings.")
            if not isinstance(expected.get("abstain"), bool):
                errors.append(f"{label}.expected.abstain must be a boolean.")
            if expected.get("abstain") is True and expected.get("dates") != []:
                errors.append(f"{label}: abstention cases must expect an empty dates array.")
    return errors


def call_daybook(endpoint: str, question: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Send one synthetic case to a running Daybook API and measure latency."""
    request = Request(
        endpoint,
        data=json.dumps({"question": question, "entries": entries}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read()
    except HTTPError as exc:
        body = exc.read()
        raise RuntimeError(f"Daybook returned HTTP {exc.code}: {body[:300].decode('utf-8', 'replace')}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach {endpoint}: {exc}") from exc
    latency_ms = (time.perf_counter() - started) * 1000
    if status < 200 or status >= 300:
        raise RuntimeError(f"Daybook returned HTTP {status}.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Daybook response was not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
        raise RuntimeError("Daybook response must contain a string 'answer'.")
    dates = payload.get("dates")
    if not isinstance(dates, list) or not all(isinstance(date, str) for date in dates):
        raise RuntimeError("Daybook response must contain a 'dates' array of strings.")
    return {"answer": payload["answer"], "dates": dates, "latency_ms": round(latency_ms, 2)}


def score_case(case: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_dates = set(case["expected"]["dates"])
    actual_dates = set(actual["dates"])
    overlap = expected_dates & actual_dates
    precision = len(overlap) / len(actual_dates) if actual_dates else float(not expected_dates)
    recall = len(overlap) / len(expected_dates) if expected_dates else float(not actual_dates)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    expected_abstain = case["expected"]["abstain"]
    actual_abstain = ABSTENTION in actual["answer"].casefold()
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_dates": sorted(expected_dates),
        "actual_dates": actual["dates"],
        "answer": actual["answer"],
        "expected_abstain": expected_abstain,
        "actual_abstain": actual_abstain,
        "date_precision": precision,
        "date_recall": recall,
        "date_f1": f1,
        "latency_ms": actual["latency_ms"],
        "passed": expected_dates == actual_dates and expected_abstain == actual_abstain,
    }


def evaluate(dataset: list[dict[str, Any]], endpoint: str) -> dict[str, Any]:
    cases = []
    for case in dataset:
        try:
            actual = call_daybook(endpoint, case["question"], case["entries"])
            cases.append(score_case(case, actual))
        except RuntimeError as exc:
            cases.append({
                "id": case["id"],
                "question": case["question"],
                "expected_dates": sorted(case["expected"]["dates"]),
                "actual_dates": [],
                "answer": "",
                "expected_abstain": case["expected"]["abstain"],
                "actual_abstain": False,
                "date_precision": 0.0,
                "date_recall": 0.0,
                "date_f1": 0.0,
                "latency_ms": None,
                "error": str(exc),
                "passed": False,
            })
    total = len(cases)
    latencies = [case["latency_ms"] for case in cases if case.get("latency_ms") is not None]
    abstention_cases = [case for case in cases if case["expected_abstain"]]
    abstention_accuracy = (
        sum(case["actual_abstain"] == case["expected_abstain"] for case in abstention_cases)
        / len(abstention_cases)
        if abstention_cases else 1.0
    )
    return {
        "endpoint": endpoint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "accuracy": sum(case["passed"] for case in cases) / total if total else 0.0,
        "date_precision": statistics.mean(case["date_precision"] for case in cases) if cases else 0.0,
        "date_recall": statistics.mean(case["date_recall"] for case in cases) if cases else 0.0,
        "date_f1": statistics.mean(case["date_f1"] for case in cases) if cases else 0.0,
        "abstention_accuracy": abstention_accuracy,
        "mean_latency_ms": statistics.mean(latencies) if latencies else None,
        "p95_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95 + 0.999) - 1)] if latencies else None,
        "cases": cases,
    }


def compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    old = {case["id"]: case for case in baseline.get("cases", [])}
    current["regressions"] = [
        {"before": old[case["id"]].get("actual_dates", []), **case}
        for case in current["cases"]
        if case["id"] in old and old[case["id"]].get("passed") and not case["passed"]
    ]
    current["improvements"] = [
        {"before": old[case["id"]].get("actual_dates", []), **case}
        for case in current["cases"]
        if case["id"] in old and not old[case["id"]].get("passed") and case["passed"]
    ]
    current["baseline_accuracy"] = baseline.get("accuracy", 0.0)
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Daybook's Ask My Journal endpoint.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--endpoint", default=os.environ.get("DAYBOOK_ASK_URL", DEFAULT_ENDPOINT))
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help="Validate the golden-set schema without calling the app.")
    parser.add_argument("--max-accuracy-drop", type=float, default=0.03)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Cannot read dataset {args.dataset}: {exc}")
    errors = validate_dataset(dataset)
    if errors:
        print("Golden dataset is invalid:")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"Golden dataset valid: {len(dataset)} cases")
    if args.validate_only:
        return 0

    result = evaluate(dataset, args.endpoint)
    has_baseline = args.baseline.exists() and not args.save_baseline
    if has_baseline:
        result = compare(result, json.loads(args.baseline.read_text(encoding="utf-8")))
    elif args.save_baseline:
        failed_cases = [case for case in result["cases"] if not case["passed"]]
        if failed_cases:
            print(f"Baseline not saved: {len(failed_cases)} case(s) did not meet the golden expectations.")
        else:
            args.baseline.parent.mkdir(parents=True, exist_ok=True)
            args.baseline.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    args.reports.mkdir(parents=True, exist_ok=True)
    report_path = args.reports / f"daybook-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    write_report(result, report_path, args.max_accuracy_drop)
    print(f"Exact-case accuracy: {result['accuracy']:.1%} ({result['total']} cases)")
    print(f"Date precision / recall / F1: {result['date_precision']:.1%} / {result['date_recall']:.1%} / {result['date_f1']:.1%}")
    print(f"Abstention accuracy: {result['abstention_accuracy']:.1%}")
    if result["mean_latency_ms"] is not None:
        print(f"Mean latency: {result['mean_latency_ms']:.1f} ms; p95: {result['p95_latency_ms']:.1f} ms")
    if result.get("regressions"):
        print(f"Regressions: {len(result['regressions'])}")
    print(f"Report: {report_path}")
    dropped = result.get("baseline_accuracy", result["accuracy"]) - result["accuracy"]
    if has_baseline:
        return int(dropped > args.max_accuracy_drop or bool(result.get("regressions")))
    return int(result["accuracy"] < 1.0)


if __name__ == "__main__":
    raise SystemExit(main())
