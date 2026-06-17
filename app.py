import streamlit as st

from project_core import LOCALDB, build_spark_llm, build_sql_database, get_default_spark_settings
from sql_workflow import QueryResult, append_trace_log, run_sql_query_workflow, trace_to_pretty_json


st.set_page_config(page_title="智能销售数据查询助手", page_icon="📊")
st.title("📊 智能销售数据查询助手")
st.caption("通过自然语言查询销售数据，演示从提问到 SQL 生成再到结果解释的完整 AI 应用链路。")

INJECTION_WARNING = """
系统会对 SQL 执行做 SELECT-only 校验，但连接真实数据库时仍建议使用只读账号，并限制可访问权限。
"""

radio_opt = ["使用本地销售示例库 sales_demo.db", "连接你自己的 SQL 数据库"]
selected_opt = st.sidebar.radio(label="请选择数据源", options=radio_opt)
if radio_opt.index(selected_opt) == 1:
    st.sidebar.warning(INJECTION_WARNING, icon="⚠️")
    db_uri = st.sidebar.text_input(
        label="数据库连接 URI", placeholder="mysql://user:pass@hostname:port/db"
    )
else:
    db_uri = LOCALDB

defaults = get_default_spark_settings()
spark_api_key = st.sidebar.text_input(
    label="讯飞 Spark API Key",
    value=defaults["api_key"],
    type="password",
)
spark_api_secret = st.sidebar.text_input(
    label="讯飞 Spark API Secret",
    value=defaults["api_secret"],
    type="password",
)
spark_model = st.sidebar.text_input(
    label="Spark 模型名称",
    value=defaults["model"],
)
spark_api_url = st.sidebar.text_input(
    label="Spark 接口地址",
    value=defaults["api_url"],
)
show_trace = st.sidebar.checkbox("展示 query trace", value=True)
max_retries = st.sidebar.slider("SQL 自动修正重试次数", min_value=0, max_value=3, value=1)

st.sidebar.markdown("### 示例问题")
st.sidebar.markdown("- 哪个客户累计消费最高？")
st.sidebar.markdown("- 哪类产品销售额最高？")
st.sidebar.markdown("- 2026年3月的总销售额是多少？")
st.sidebar.markdown("- 4月一共有多少笔订单？")

if not db_uri:
    st.info("请输入数据库连接 URI。")
    st.stop()

if not spark_api_key or not spark_api_secret:
    st.info("请先填写 Spark API Key 和 API Secret。")
    st.stop()


@st.cache_resource(ttl="2h")
def configure_db(db_uri: str):
    return build_sql_database(db_uri)


db = configure_db(db_uri)
llm = build_spark_llm(
    api_key=spark_api_key,
    api_secret=spark_api_secret,
    api_url=spark_api_url,
    model=spark_model,
    temperature=0.0,
)

if "messages" not in st.session_state or st.sidebar.button("清空对话记录"):
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "你好，我是你的销售数据查询助手。你可以直接问我客户、产品、订单和销售额相关问题。",
        }
    ]
    st.session_state["traces"] = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

user_query = st.chat_input(placeholder="例如：哪个客户累计消费最高？")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    st.chat_message("user").write(user_query)

    with st.chat_message("assistant"):
        try:
            result: QueryResult = run_sql_query_workflow(
                question=user_query,
                llm=llm,
                db=db,
                max_retries=max_retries,
            )
            st.write(result.answer)
            st.caption(f"执行 SQL：`{result.sql}`")
            st.caption(f"自动修正重试次数：{result.retries_used}")

            trace_json = trace_to_pretty_json(result.trace)
            append_trace_log(result.trace, "logs/query_traces.jsonl")
            st.session_state["messages"].append({"role": "assistant", "content": result.answer})
            st.session_state["traces"].append(trace_json)

            if show_trace:
                with st.expander("查看 query trace", expanded=False):
                    st.code(trace_json, language="json")
        except Exception as exc:
            response = f"查询失败：{exc}"
            st.session_state["messages"].append({"role": "assistant", "content": response})
            st.write(response)

if st.session_state.get("traces"):
    with st.sidebar.expander("最近一次 trace", expanded=False):
        st.code(st.session_state["traces"][-1], language="json")
