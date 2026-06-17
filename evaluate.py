from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_core import LOCALDB, build_spark_llm, build_sql_database, get_default_spark_settings
from sql_workflow import parse_sql_result, run_sql_query_workflow


def normalize_result(value: Any) -> Any:
    if isinstance(value, list):
        normalized_rows = []
        for row in value:
            if isinstance(row, tuple):
                normalized_rows.append(list(row))
            else:
                normalized_rows.append(row)
        return normalized_rows
    return value


def load_cases() -> list[dict[str, Any]]:
    eval_path = Path(__file__).with_name("eval_cases.json")
    return json.loads(eval_path.read_text(encoding="utf-8"))


def build_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the SQL workflow.")
    parser.add_argument(
        "--suite",
        choices=["core", "challenge", "all"],
        default="core",
        help="Which evaluation suite to run. Defaults to core.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    defaults = get_default_spark_settings()
    if not defaults["api_key"] or not defaults["api_secret"]:
        raise SystemExit("缺少 Spark 配置，请先在 .env 中设置 XF_APIKey 和 XF_APISecret。")

    llm = build_spark_llm(
        api_key=defaults["api_key"],
        api_secret=defaults["api_secret"],
        api_url=defaults["api_url"],
        model=defaults["model"],
        temperature=0.0,
    )
    db = build_sql_database(LOCALDB)
    all_cases = load_cases()
    if args.suite == "all":
        cases = all_cases
    else:
        cases = [case for case in all_cases if case.get("difficulty", "core") == args.suite]

    sql_executable = 0
    result_correct = 0
    retry_success = 0
    outputs: list[dict[str, Any]] = []
    category_stats: dict[str, dict[str, int]] = {}

    for case in cases:
        category = case.get("category", "uncategorized")
        category_stats.setdefault(
            category,
            {
                "case_count": 0,
                "sql_executable_count": 0,
                "result_correct_count": 0,
                "retry_success_count": 0,
            },
        )
        category_stats[category]["case_count"] += 1

        item: dict[str, Any] = {
            "id": case.get("id"),
            "category": category,
            "question": case["question"],
        }
        try:
            result = run_sql_query_workflow(
                question=case["question"],
                llm=llm,
                db=db,
                max_retries=1,
            )
            sql_executable += 1
            category_stats[category]["sql_executable_count"] += 1
            parsed_result = normalize_result(parse_sql_result(result.raw_result))
            expected_result = normalize_result(case["expected_result"])
            if parsed_result == expected_result:
                result_correct += 1
                category_stats[category]["result_correct_count"] += 1
            if result.retries_used > 0:
                retry_success += 1
                category_stats[category]["retry_success_count"] += 1

            item.update(
                {
                    "status": "ok",
                    "generated_sql": result.sql,
                    "raw_result": parsed_result,
                    "expected_result": expected_result,
                    "answer": result.answer,
                    "retries_used": result.retries_used,
                    "result_match": parsed_result == expected_result,
                }
            )
        except Exception as exc:
            item.update({"status": "error", "error": str(exc)})
        outputs.append(item)

    summary = {
        "suite": args.suite,
        "case_count": len(cases),
        "sql_executable_rate": build_rate(sql_executable, len(cases)),
        "result_correct_rate": build_rate(result_correct, len(cases)),
        "retry_success_count": retry_success,
    }

    category_summary = {
        category: {
            **stats,
            "sql_executable_rate": build_rate(stats["sql_executable_count"], stats["case_count"]),
            "result_correct_rate": build_rate(stats["result_correct_count"], stats["case_count"]),
        }
        for category, stats in category_stats.items()
    }

    print(
        json.dumps(
            {"summary": summary, "category_summary": category_summary, "details": outputs},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
