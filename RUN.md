# RUN.md — 5 分钟跑起来

## 1. 环境准备

- Python 3.11+
- (可选) Anthropic API Key — 不用也能跑，内置了 mock 数据

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

**有 API Key** 可以启用 LLM 润色，报告质量更高。支持 6 种大模型，任选一个配置即可：

```bash
# Anthropic Claude (默认)
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# 或者用国产大模型 — 兼容 OpenAI API，价格更实惠
# export DEEPSEEK_API_KEY=sk-xxxxx         # DeepSeek
# export QWEN_API_KEY=sk-xxxxx             # 通义千问
# export ZHIPU_API_KEY=xxxxx.xxxxx         # 智谱 GLM
# export MOONSHOT_API_KEY=sk-xxxxx         # Moonshot Kimi
# export OPENAI_API_KEY=sk-xxxxx           # OpenAI GPT

# 切换 Provider (不设则自动检测)
export MODEL_PROVIDER=deepseek

python -m agent.main
```

---

**Docker 一键启动**（可选）：

```bash
docker compose up --build
```

> 服务端口：新闻 8001 · PDF 8002 · 价格 8003

## 4. 在 Claude Desktop / Cursor 中使用

把项目目录下的 `mcp-config.json` 合并到 Claude Desktop 的 MCP 配置中，重启即可。
