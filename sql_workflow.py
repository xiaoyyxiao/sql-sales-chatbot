from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.language_models.llms import LLM


SQL_BLOCK_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
SQL_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "pragma",
)
SQLITE_UNSUPPORTED_FUNCTIONS = (
    "year",
    "month",
    "date_trunc",
    "extract",
    "to_char",
)


@dataclass
class QueryTrace:
    question: str
    selected_tables: list[str]
    schema_excerpt: str
    generated_sql: str | None = None
    corrected_sql: str | None = None
    executed_sql: str | None = None
    sql_result: str | None = None
    final_answer: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class QueryResult:
    answer: str
    sql: str
    raw_result: str
    trace: QueryTrace
    retries_used: int


def select_relevant_tables(question: str, table_names: list[str], max_tables: int = 2) -> list[str]:
    normalized = question.lower()
    keyword_map = {
        "customers": ["客户", "顾客", "会员", "城市", "等级", "customer"],
        "products": ["产品", "商品", "品类", "类别", "单价", "product", "rag", "ai应用"],
        "orders": ["订单", "销售", "金额", "销量", "购买", "order", "消费", "营收"],
    }

    scored_tables: list[tuple[int, str]] = []
    for table in table_names:
        score = 0
        for keyword in keyword_map.get(table, []):
            if keyword.lower() in normalized:
                score += 1
        if any(token in normalized for token in ["多少", "总", "累计", "最高", "最低", "平均", "top", "排行"]):
            if table == "orders":
                score += 1
        scored_tables.append((score, table))

    scored_tables.sort(key=lambda item: (-item[0], item[1]))
    chosen = [table for score, table in scored_tables if score > 0][:max_tables]
    if not chosen:
        chosen = table_names[:max_tables]
    if "orders" in table_names and "orders" not in chosen and len(chosen) < max_tables:
        chosen.append("orders")
    return sorted(set(chosen), key=chosen.index)


def extract_sql(text: str) -> str:
    match = SQL_BLOCK_RE.search(text)
    if match:
        candidate = match.group(1).strip()
    else:
        candidate = text.strip()

    for prefix in ("SQL:", "sql:", "最终 SQL:", "最终SQL:"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :].strip()
    return candidate.strip().rstrip(";")


def ensure_select_only(sql: str) -> str:
    normalized = sql.strip().lower()
    if not normalized:
        raise ValueError("模型没有生成 SQL。")
    if not normalized.startswith("select"):
        raise ValueError("仅允许执行 SELECT 查询。")
    if ";" in normalized:
        parts = [part.strip() for part in normalized.split(";") if part.strip()]
        if len(parts) > 1:
            raise ValueError("仅允许执行单条 SELECT 查询。")
    for keyword in SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            raise ValueError(f"检测到危险 SQL 关键字: {keyword}")
    return sql.strip().rstrip(";")


def build_dialect_rules(dialect: str) -> str:
    if dialect.lower() == "sqlite":
        return """
SQLite 约束：
- 当前数据库方言是 SQLite。
- `order_date` 是 TEXT 类型，格式固定为 `YYYY-MM-DD`。
- 不要使用 `YEAR()`、`MONTH()`、`DATE_TRUNC()`、`EXTRACT()`、`TO_CHAR()` 这类非 SQLite 写法。
- 按月筛选时，优先使用 `substr(order_date, 1, 7) = 'YYYY-MM'`。
- 按年筛选时，优先使用 `substr(order_date, 1, 4) = 'YYYY'`。
- 如果用户只问“3月”或“4月”，但没有指定年份，优先结合样例数据中的年份直接写成 `2026-03`、`2026-04` 这种完整月份条件。
""".strip()
    return f"当前数据库方言是 {dialect}，请严格使用该方言兼容的 SQL 语法。"


def validate_sql_for_dialect(sql: str, dialect: str) -> str:
    normalized = sql.strip().lower()
    if dialect.lower() == "sqlite":
        for func_name in SQLITE_UNSUPPORTED_FUNCTIONS:
            if re.search(rf"\b{func_name}\s*\(", normalized):
                raise ValueError(
                    f"SQLite 不支持 `{func_name}()` 这类写法。请改用 substr(order_date, ...) 进行日期筛选。"
                )
    return sql


def parse_sql_result(raw_result: str) -> Any:
    if raw_result.startswith("Error:"):
        return raw_result
    if raw_result == "":
        return []
    try:
        return ast.literal_eval(raw_result)
    except (ValueError, SyntaxError):
        return raw_result


def build_sql_prompt(question: str, schema_info: str, dialect: str) -> str:
    return f"""
你是一个负责结构化数据查询的 SQL 助手。请基于给定 schema 只生成一条可执行的 {dialect} SELECT 语句。

要求：
1. 只能输出一条 SELECT 语句，不要输出解释。
2. 不允许出现 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE 等写操作。
3. 字段名和表名必须严格来自 schema。
4. 如果涉及聚合、排序或日期筛选，请显式写出逻辑。
5. 优先返回能直接回答用户问题的最小结果集。
6. 必须遵守下面的数据库方言规则，不要使用其他数据库的函数。

{build_dialect_rules(dialect)}

用户问题：
{question}

可用 schema：
{schema_info}
""".strip()


def build_retry_prompt(
    question: str,
    schema_info: str,
    failed_sql: str,
    error_message: str,
    dialect: str,
) -> str:
    return f"""
你上一次生成的 SQL 执行失败了。请根据报错信息修正 SQL，并只输出一条新的 {dialect} SELECT 语句。

你必须特别遵守下面的数据库方言规则：
{build_dialect_rules(dialect)}

用户问题：
{question}

可用 schema：
{schema_info}

失败 SQL：
{failed_sql}

报错信息：
{error_message}
""".strip()


def build_answer_prompt(question: str, sql: str, sql_result: str) -> str:
    return f"""
你是销售数据分析助手。请基于查询结果回答用户问题。

要求：
1. 回答使用简洁中文。
2. 明确指出关键结论。
3. 如果结果为空，直接说明没有查到相关数据。
4. 不要编造数据库中没有的信息。

用户问题：
{question}

执行 SQL：
{sql}

查询结果：
{sql_result}
""".strip()


def run_sql_query_workflow(
    question: str,
    llm: LLM,
    db: SQLDatabase,
    max_retries: int = 1,
) -> QueryResult:
    table_names = list(db.get_usable_table_names())
    selected_tables = select_relevant_tables(question, table_names)
    schema_info = db.get_table_info_no_throw(selected_tables)
    trace = QueryTrace(
        question=question,
        selected_tables=selected_tables,
        schema_excerpt=schema_info,
    )

    sql_prompt = build_sql_prompt(question=question, schema_info=schema_info, dialect=db.dialect)
    sql_candidate = extract_sql(llm.invoke(sql_prompt))
    trace.generated_sql = sql_candidate

    current_sql = ensure_select_only(sql_candidate)
    raw_result = ""
    retries_used = 0

    for attempt in range(max_retries + 1):
        trace.attempts.append({"attempt": attempt + 1, "sql": current_sql})

        try:
            validated_sql = validate_sql_for_dialect(current_sql, db.dialect)
            trace.executed_sql = validated_sql
            raw_result = str(db.run_no_throw(validated_sql))
        except ValueError as exc:
            raw_result = f"Error: {exc}"
        trace.attempts[-1]["result"] = raw_result

        if not raw_result.startswith("Error:"):
            current_sql = trace.executed_sql or current_sql
            break

        if attempt >= max_retries:
            trace.error = raw_result
            raise ValueError(f"SQL 执行失败：{raw_result}")

        retries_used += 1
        retry_prompt = build_retry_prompt(
            question=question,
            schema_info=schema_info,
            failed_sql=current_sql,
            error_message=raw_result,
            dialect=db.dialect,
        )
        corrected_sql = extract_sql(llm.invoke(retry_prompt))
        current_sql = ensure_select_only(corrected_sql)
        trace.corrected_sql = current_sql

    trace.sql_result = raw_result
    answer_prompt = build_answer_prompt(question=question, sql=current_sql, sql_result=raw_result)
    final_answer = llm.invoke(answer_prompt).strip()
    trace.final_answer = final_answer

    return QueryResult(
        answer=final_answer,
        sql=current_sql,
        raw_result=raw_result,
        trace=trace,
        retries_used=retries_used,
    )


def trace_to_pretty_json(trace: QueryTrace) -> str:
    return json.dumps(
        {
            "question": trace.question,
            "selected_tables": trace.selected_tables,
            "generated_sql": trace.generated_sql,
            "corrected_sql": trace.corrected_sql,
            "executed_sql": trace.executed_sql,
            "sql_result": parse_sql_result(trace.sql_result or ""),
            "final_answer": trace.final_answer,
            "attempts": trace.attempts,
            "error": trace.error,
        },
        ensure_ascii=False,
        indent=2,
    )


def trace_to_dict(trace: QueryTrace) -> dict[str, Any]:
    return {
        "question": trace.question,
        "selected_tables": trace.selected_tables,
        "generated_sql": trace.generated_sql,
        "corrected_sql": trace.corrected_sql,
        "executed_sql": trace.executed_sql,
        "sql_result": parse_sql_result(trace.sql_result or ""),
        "final_answer": trace.final_answer,
        "attempts": trace.attempts,
        "error": trace.error,
    }


def append_trace_log(trace: QueryTrace, log_path: str | Path) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(trace_to_dict(trace), ensure_ascii=False) + "\n")
