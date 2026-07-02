# RUN.md — 5 分钟快速安装、启动和测试

## 环境要求

- Python 3.11+
- pip
- (可选) Docker Desktop 24.0+
- (可选) Anthropic API Key 或 OpenAI API Key

## 步骤 1: 进入项目目录 (0:00)

```bash
cd mining_daily_agent
```

## 步骤 2: 安装依赖 (1:00)

### Windows (Git Bash / PowerShell)

```bash
# 创建虚拟环境 (推荐)
python -m venv venv
source venv/Scripts/activate  # Git Bash
# 或: .\venv\Scripts\Activate.ps1  # PowerShell

# 安装所有依赖
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt
```

## 步骤 3: 测试 MCP 服务器 (3:00)

### 3a. 测试 LME Price MCP Server

```bash
# 使用 Python 直接调用工具函数（无需启动 MCP transport）
python -c "
from servers.lme_price_mcp.tools import get_price, get_trend
print('=== Lithium Price ===')
print(get_price('lithium'))
print()
print('=== Gold 30-Day Trend ===')
print(get_trend('gold', 30))
"
```

**预期输出**: JSON 格式的价格数据和走势统计数据。

### 3b. 测试 Mining News MCP Server

```bash
python -c "
from servers.mining_news_mcp.tools import search_mining_news
print('=== News Search: Pilbara lithium ===')
print(search_mining_news('Pilbara lithium', days=7, max_results=3))
"
```

**预期输出**: JSON 格式的新闻搜索结果（含文章标题、URL、来源等）。

### 3c. 测试 Mineral PDF MCP Server

```bash
python -c "
from servers.mineral_pdf_mcp.tools import extract_resources
print('=== NI 43-101 Resource Data ===')
# 使用一个已知的 URL，会自动 fallback 到 mock 数据
print(extract_resources('https://sedar.com/ni43-101/pilgangoora.pdf'))
"
```

**预期输出**: JSON 格式的矿产资源数据（Measured/Indicated/Inferred 储量）。

## 步骤 4: 运行 Agent 生成日报 (4:00)

### Standalone 模式（不需要 API Key，使用内置 mock 数据）

```bash
python -m agent.main --standalone "给我生成一份关于 Pilbara 锂矿的今日简报"
```

**预期输出**: 一份完整的 Markdown 日报，包括新闻摘要、储量数据、价格走势、风险提示。

### 完整模式（需要 API Key，连接 MCP 服务器）

```bash
# 设置 API Key
export ANTHROPIC_API_KEY=sk-ant-xxxxx   # macOS/Linux
# set ANTHROPIC_API_KEY=sk-ant-xxxxx    # Windows

# 运行
python -m agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"
```

## 步骤 5: Docker 一键启动 (可选)

```bash
# 启动所有服务（3 个 MCP Server + 1 个 Agent）
docker compose up --build

# 服务启动后，Agent 会自动执行默认查询并输出报告
# 服务端口:
#   - mining-news:  http://localhost:8001
#   - mineral-pdf:  http://localhost:8002
#   - lme-price:    http://localhost:8003
```

## 在 Claude Desktop 中使用

将 `mcp-config.json` 的内容合并到 Claude Desktop 的 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "mining-news": {
      "command": "python",
      "args": ["-m", "servers.mining_news_mcp.server"],
      "env": { "LOG_LEVEL": "INFO" }
    },
    "mineral-pdf": {
      "command": "python",
      "args": ["-m", "servers.mineral_pdf_mcp.server"],
      "env": { "LOG_LEVEL": "INFO" }
    },
    "lme-price": {
      "command": "python",
      "args": ["-m", "servers.lme_price_mcp.server"],
      "env": { "LME_PRICE_PROVIDER": "mock", "LOG_LEVEL": "INFO" }
    }
  }
}
```

重启 Claude Desktop 后，即可在对话中直接使用 MCP 工具。

## 常见问题

### Q: 安装 pdfplumber 报错？
```bash
# Windows: 可能需要安装 Visual C++ Build Tools
# 或使用预编译包:
pip install pdfplumber --only-binary=:all:
```

### Q: 新闻搜索返回空？
内置了 mock 数据，即使 RSS 不可用也会返回预置的矿业新闻。

### Q: API Key 哪里获取？
- Anthropic: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/

Agent 的 `--standalone` 模式不需要 API Key。

### Q: 如何切换 LLM？
```bash
# 使用 OpenAI
export MODEL_PROVIDER=openai
export MODEL_NAME=gpt-4o
export OPENAI_API_KEY=sk-xxxxx
```

## 验证清单

- [ ] `python -c "from servers.lme_price_mcp.tools import get_price; print(get_price('copper'))"` 返回 JSON
- [ ] `python -c "from servers.mining_news_mcp.tools import search_mining_news; print(search_mining_news('gold'))"` 返回 JSON
- [ ] `python -c "from servers.mineral_pdf_mcp.tools import extract_resources; print(extract_resources('https://test.com/report.pdf'))"` 返回 JSON
- [ ] `python -m agent.main --standalone` 输出完整的 Markdown 日报
- [ ] (可选) `docker compose up --build` 所有服务健康启动
