# SQL Sales Chatbot

一个基于大模型的自然语言销售数据查询助手，支持用户直接用自然语言提问，系统自动生成 SQL 查询本地销售数据库，并返回结果说明。

## 项目简介

这是一个面向结构化数据问答的轻量级 AI 应用。  
用户可以直接输入自然语言问题，例如：

- 哪个客户累计消费最高？
- 哪类产品销售额最高？
- 2026 年 3 月的总销售额是多少？

系统的核心流程如下：

1. 读取数据库表结构信息
2. 根据用户问题生成 SQL
3. 执行 SQL 查询
4. 将结果转换为自然语言返回

## 功能特点

- 支持自然语言转 SQL
- 内置本地 SQLite 销售示例数据库
- 中文业务化界面，便于演示销售数据问答场景
- 基于 Streamlit 的交互式聊天界面
- 对接讯飞 Spark 作为大模型后端
- 本地数据库采用只读连接，降低误操作风险

## 技术栈

- Python
- Streamlit
- LangChain
- iFLYTEK Spark API
- SQLite
- SQLAlchemy

## 本地运行

### 1. 创建虚拟环境

```bash
python -m venv .venv
```

### 2. 激活虚拟环境

Windows PowerShell:

```powershell
.\.venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env`，并填写讯飞 Spark 配置：

```powershell
Copy-Item .env.example .env
```

`.env` 示例：

```env
XF_APIKey=your_api_key_here
XF_APISecret=your_api_secret_here
XF_MODEL=lite
XF_URL=https://spark-api-open.xf-yun.com/v1/chat/completions
```

### 5. 启动应用

```bash
streamlit run app.py
```

## 示例数据库

仓库内置 `sales_demo.db`，包含以下示例表：

- `customers`
- `products`
- `orders`

适合用于演示客户、产品、订单、销售额等典型销售数据查询场景。

## 我的改动

这个项目基于开源 SQL Agent 示例做了本地复现和轻量改造，主要包括：

- 将原始英文界面改成中文业务化界面
- 将默认示例数据库替换为本地销售数据示例库
- 调整示例问题，使其更贴近销售分析场景
- 将默认 OpenAI 模型调用改造成讯飞 Spark 模型后端

## 致谢

本项目基于以下开源示例改造：

- 原始仓库：<https://github.com/langchain-ai/streamlit-agent>
- 原始示例文件：`chat_with_sql_db.py`

原项目提供了基础的 SQL Agent 演示能力，本版本重点放在中文业务场景改造、讯飞 Spark 接入和结构化数据问答展示。
