# SQL Sales Chatbot

一个面向销售场景的自然语言数据查询助手。用户可以直接输入中文问题，系统会完成 `schema 过滤 -> SQL 生成 -> SELECT 校验 -> 查询执行 -> 结果回答` 的完整链路。

## 项目亮点

- 支持中文自然语言转 SQL 查询
- 内置本地 `SQLite` 销售示例数据库
- 接入讯飞 `Spark API` 作为大模型后端
- 增加 `schema 过滤 / 表选择`，缩小 SQL 生成上下文
- 增加 `SELECT-only guardrail`，拦截非查询类 SQL
- 增加 `执行失败后的自动修正重试`
- 增加 `query trace`，记录用户问题、生成 SQL、执行结果和最终回答
- 增加离线评测集，可统计 SQL 可执行率和结果正确率

## 技术栈

- Python
- Streamlit
- LangChain Core
- iFLYTEK Spark API
- SQLite
- SQLAlchemy

## 项目结构

- `app.py`: Streamlit 交互界面
- `project_core.py`: Spark 模型与数据库初始化
- `sql_workflow.py`: SQL workflow、guardrail、retry、trace
- `evaluate.py`: 评测脚本
- `eval_cases.json`: 评测样例集
- `sales_demo.db`: 本地示例数据库

## 核心流程

1. 根据用户问题做表选择，缩小候选 schema
2. 基于候选表 schema 生成 SQL
3. 在执行前进行 `SELECT-only` 校验
4. 执行 SQL 查询
5. 如果 SQL 执行失败，基于报错自动修正并重试
6. 基于查询结果生成最终中文回答
7. 将完整 trace 输出到前端，便于排查 bad case

## 本地运行

### 1. 创建并激活虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

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

### 4. 启动应用

```bash
streamlit run app.py
```

## 评测

运行下面的命令可以基于 `eval_cases.json` 评估当前 SQL workflow：

```bash
python evaluate.py
```

默认运行 `core` 核心业务场景评测。你也可以显式指定：

```bash
python evaluate.py --suite core
python evaluate.py --suite challenge
python evaluate.py --suite all
```

输出会包含：

- `suite`: 当前运行的评测集
- `case_count`: 当前评测样例数量
- `sql_executable_rate`: SQL 可执行率
- `result_correct_rate`: 结果正确率
- `retry_success_count`: 经过自动修正后成功的数量
- `category_summary`: 按 `aggregation / filtering / join / ranking / robustness` 分类统计的结果

## 当前工程化能力

- `Guardrail`: 仅允许执行单条 `SELECT` 语句
- `Retry`: SQL 执行失败后自动基于报错修正一次
- `Trace`: 输出问题、选表、SQL、执行结果、最终回答
- `Evaluation`: 使用离线评测集验证效果

## 后续可扩展方向

- 更细粒度的 schema 检索与列级过滤
- 多轮上下文支持
- fallback 模型与错误降级
- 更系统的 bad case 分类和指标看板
