# RUN.md — 5 分钟跑起来

## 1. 环境准备

- Python 3.11+
- (可选) API Key — 不用也能跑，内置了 mock 数据

## 2. 安装

```bash
cd mining_daily_agent
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt
```

## 3. 运行

**不需要 API Key**，直接用 mock 数据生成日报：

```bash
python -m agent.main --standalone
```

输出就是一份完整的 Markdown 日报（新闻 + 储量 + 价格 + 风险提示）。

---

**有 API Key** 启用 LLM 润色。创建 `.env` 文件放入项目根目录即可，**不用区分 Windows/Mac/Linux**：

```bash
# .env — 项目根目录下新建这个文件，填入你要用的 API Key (一个就够了)
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

国产大模型也支持：

```bash
# 用 DeepSeek
DEEPSEEK_API_KEY=sk-xxxxx
MODEL_PROVIDER=deepseek

# 用通义千问
QWEN_API_KEY=sk-xxxxx
MODEL_PROVIDER=qwen

# 用智谱 GLM
ZHIPU_API_KEY=xxxxx.xxxxxxxxxxxxxx
MODEL_PROVIDER=zhipu
```

然后运行：

```bash
python -m agent.main
```

Agent 会自动读取 `.env` 文件，不用手动 `export` / `set`。

> 可用 `python -m agent.main --list-models` 查看支持的模型列表。

---

**Docker 一键启动**（可选）：

```bash
docker compose up --build
```

> 服务端口：新闻 8001 · PDF 8002 · 价格 8003

## 4. 在 Claude Desktop / Cursor 中使用

把项目目录下的 `mcp-config.json` 合并到 Claude Desktop 的 MCP 配置中，重启即可。
