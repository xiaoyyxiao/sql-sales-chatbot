# SQL Sales Chatbot

???????????????????????????????????????? SQL ??????????????????

## Project Overview

This project is a lightweight AI application for structured data Q&A.
Users can ask questions in natural language such as:

- ???????????
- ??????????
- 2026?3??????????

The system will:
1. understand the database schema,
2. generate SQL from the user question,
3. execute the SQL query,
4. return the result in natural language.

## Features

- Natural language to SQL
- Local SQLite sales demo database
- Chinese UI for business demo scenarios
- Streamlit interactive interface
- Read-only local database connection

## Tech Stack

- Python
- Streamlit
- LangChain
- OpenAI
- SQLite
- SQLAlchemy

## Run Locally

### 1. Create virtual environment

```bash
python -m venv .venv
```

### 2. Activate environment

Windows PowerShell:

```powershell
.\.venv\Scriptsctivate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment

Create a `.env` file or export your OpenAI API key locally.

Example:

```env
OPENAI_API_KEY=your_api_key_here
```

### 5. Start the app

```bash
streamlit run app.py
```

## Demo Database

The repository includes a local SQLite database `sales_demo.db` with sample data for:

- customers
- products
- orders

## My Customizations

This project was adapted for interview/demo use with the following changes:

- Reworked the original English UI into a Chinese business-style interface
- Replaced the original sample database with a local sales demo database
- Adjusted example questions for sales analytics scenarios

## Acknowledgement

This project is adapted from the open-source example below:

- Repository: https://github.com/langchain-ai/streamlit-agent
- Original example: `chat_with_sql_db.py`

The original project provided the base SQL agent demo, and this version focuses on localized business scenario customization and structured data query presentation.
