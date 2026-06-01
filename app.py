import sqlite3
from pathlib import Path

import streamlit as st
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.agents.agent_types import AgentType
from langchain.callbacks import StreamlitCallbackHandler
from langchain.llms.openai import OpenAI
from langchain.sql_database import SQLDatabase
from sqlalchemy import create_engine

st.set_page_config(page_title="智能销售数据查询助手", page_icon="📊")
st.title("📊 智能销售数据查询助手")
st.caption("通过自然语言查询销售数据，演示从提问到 SQL 生成再到结果解释的完整 AI 应用链路。")

INJECTION_WARNING = """
SQL Agent 可能受到提示词注入影响。连接真实数据库时建议使用只读账号，并限制可访问权限。
"""
LOCALDB = "USE_LOCAL_SALES_DB"

radio_opt = ["使用本地销售示例库 sales_demo.db", "连接你自己的 SQL 数据库"]
selected_opt = st.sidebar.radio(label="请选择数据源", options=radio_opt)
if radio_opt.index(selected_opt) == 1:
    st.sidebar.warning(INJECTION_WARNING, icon="⚠️")
    db_uri = st.sidebar.text_input(
        label="数据库连接 URI", placeholder="mysql://user:pass@hostname:port/db"
    )
else:
    db_uri = LOCALDB

openai_api_key = st.sidebar.text_input(label="OpenAI API Key", type="password")

st.sidebar.markdown("### 示例问题")
st.sidebar.markdown("- 哪个客户累计消费最高？")
st.sidebar.markdown("- 哪类产品销售额最高？")
st.sidebar.markdown("- 2026年3月的总销售额是多少？")

if not db_uri:
    st.info("请输入数据库连接 URI。")
    st.stop()

if not openai_api_key:
    st.info("请先填写 OpenAI API Key。")
    st.stop()

llm = OpenAI(openai_api_key=openai_api_key, temperature=0, streaming=True)


@st.cache_resource(ttl="2h")
def configure_db(db_uri):
    if db_uri == LOCALDB:
        db_filepath = (Path(__file__).parent / "sales_demo.db").absolute()
        creator = lambda: sqlite3.connect(f"file:{db_filepath}?mode=ro", uri=True)
        return SQLDatabase(create_engine("sqlite:///", creator=creator))
    return SQLDatabase.from_uri(database_uri=db_uri)


db = configure_db(db_uri)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

agent = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
)

if "messages" not in st.session_state or st.sidebar.button("清空对话记录"):
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "你好，我是你的销售数据查询助手。你可以直接问我客户、产品、订单和销售额相关问题。",
        }
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

user_query = st.chat_input(placeholder="例如：哪个客户累计消费最高？")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    st.chat_message("user").write(user_query)

    with st.chat_message("assistant"):
        st_cb = StreamlitCallbackHandler(st.container())
        response = agent.run(user_query, callbacks=[st_cb])
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.write(response)
