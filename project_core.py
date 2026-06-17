import os
import sqlite3
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.language_models.llms import LLM
from sqlalchemy import create_engine


load_dotenv()

LOCALDB = "USE_LOCAL_SALES_DB"


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


def build_spark_llm(
    api_key: str,
    api_secret: str,
    api_url: str,
    model: str,
    temperature: float = 0.0,
) -> SparkLLM:
    return SparkLLM(
        api_key=api_key,
        api_secret=api_secret,
        api_url=api_url,
        model=model,
        temperature=temperature,
    )


def build_sql_database(db_uri: str) -> SQLDatabase:
    if db_uri == LOCALDB:
        db_filepath = (Path(__file__).parent / "sales_demo.db").absolute()

        def creator() -> sqlite3.Connection:
            return sqlite3.connect(f"file:{db_filepath}?mode=ro", uri=True)

        return SQLDatabase(create_engine("sqlite:///", creator=creator))

    return SQLDatabase.from_uri(database_uri=db_uri)


def get_default_spark_settings() -> dict[str, str]:
    return {
        "api_key": os.getenv("XF_APIKey", ""),
        "api_secret": os.getenv("XF_APISecret", ""),
        "model": os.getenv("XF_MODEL", "lite"),
        "api_url": os.getenv("XF_URL", "https://spark-api-open.xf-yun.com/v1/chat/completions"),
    }
