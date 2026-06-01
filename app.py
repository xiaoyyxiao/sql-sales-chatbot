import os
import sqlite3
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_classic.agents.agent_types import AgentType
from langchain_core.language_models.llms import LLM
from sqlalchemy import create_engine
from dotenv import load_dotenv


load_dotenv()


class SparkLLM(LLM):
    api_key: str
    api_secret: str
    api_url: str = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    model: str = "lite"
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "spark"

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.exceptions.RequestException as exc:
            raise ValueError(f"Failed to reach Spark API: {exc}") from exc

        if response.status_code != 200:
            raise ValueError(f"Spark API error {response.status_code}: {response.text}")

        result = response.json()
        if result.get("error"):
            raise ValueError(str(result["error"]))

        choices = result.get("choices", [])
        if not choices:
            raise ValueError("Spark API returned no choices.")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("Spark API returned an empty answer.")

        if stop:
            for token in stop:
                if token in content:
                    content = content.split(token)[0]

        return content


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

spark_api_key = st.sidebar.text_input(
    label="讯飞 Spark API Key",
    value=os.getenv("XF_APIKey", ""),
    type="password",
)
spark_api_secret = st.sidebar.text_input(
    label="讯飞 Spark API Secret",
    value=os.getenv("XF_APISecret", ""),
    type="password",
)
spark_model = st.sidebar.text_input(
    label="Spark 模型名称",
    value=os.getenv("XF_MODEL", "lite"),
)
spark_api_url = st.sidebar.text_input(
    label="Spark 接口地址",
    value=os.getenv("XF_URL", "https://spark-api-open.xf-yun.com/v1/chat/completions"),
)

st.sidebar.markdown("### 示例问题")
st.sidebar.markdown("- 哪个客户累计消费最高？")
st.sidebar.markdown("- 哪类产品销售额最高？")
st.sidebar.markdown("- 2026年3月的总销售额是多少？")

if not db_uri:
    st.info("请输入数据库连接 URI。")
    st.stop()

if not spark_api_key or not spark_api_secret:
    st.info("请先填写 Spark API Key 和 API Secret。")
    st.stop()

llm = SparkLLM(
    api_key=spark_api_key,
    api_secret=spark_api_secret,
    api_url=spark_api_url,
    model=spark_model,
    temperature=0.0,
)


@st.cache_resource(ttl="2h")
def configure_db(db_uri: str) -> SQLDatabase:
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
        try:
            response = agent.run(user_query, callbacks=[st_cb])
        except Exception as exc:
            response = f"查询失败：{exc}"
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.write(response)
