# Mining Daily Agent — 基于 MCP 的矿权日报 Agent

基于 **Model Context Protocol (MCP)** 和 **LangGraph** 构建的矿业日报自动生成系统。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Client (LangGraph)                  │
│  plan → fetch_news → fetch_resources → fetch_prices →       │
│  synthesize → Markdown Report                               │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │ MCP (stdio/SSE)  │                  │
       ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ mining-news  │ │ mineral-pdf  │ │  lme-price   │
│    MCP       │ │    MCP       │ │    MCP       │
│              │ │              │ │              │
│ search()     │ │ extract_     │ │ get_price()  │
│ fetch_       │ │ resources()  │ │ get_trend()  │
│ article()    │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 项目结构

```
mining_daily_agent/
├── servers/
│   ├── shared/              # 共享模块 (缓存、日志、HTTP、基类)
│   ├── mining_news_mcp/     # 矿业新闻搜索 & 文章提取
│   ├── mineral_pdf_mcp/     # NI 43-101 PDF 资源量解析
│   └── lme_price_mcp/       # 金属商品价格 & 走势
├── agent/                   # LangGraph Agent (状态图 + MCP 客户端)
├── docker-compose.yml       # 一键启动
├── mcp-config.json          # Claude Desktop / Cursor MCP 配置
├── RUN.md                   # 5 分钟快速上手指南
└── README.md
```

## 快速开始

### 方式 1: 本地运行 (推荐开发使用)

```bash
# 1. 安装依赖
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt

# 2. 设置 API Key (仅 Agent LLM 需要)
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# 3. 运行 Agent (standalone 模式，不启动独立 MCP 进程)
python -m agent.main --standalone "给我生成一份关于 Pilbara 锂矿的今日简报"

# 4. 运行 Agent (完整模式，启动 MCP 子进程)
python -m agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"
```

### 方式 2: Docker 一键启动

```bash
docker compose up --build
```

### 方式 3: 在 Claude Desktop / Cursor 中使用

将 `mcp-config.json` 中的配置添加到 Claude Desktop 或 Cursor 的 MCP 配置中。

## MCP 服务器

### mining-news-mcp
| 工具 | 描述 |
|------|------|
| `search_mining_news(query, days, max_results)` | 搜索矿业新闻 (RSS + 内置数据) |
| `fetch_article(url)` | 获取新闻全文 (trafilatura 提取) |

### mineral-pdf-mcp
| 工具 | 描述 |
|------|------|
| `extract_resources(pdf_url)` | 解析 NI 43-101 PDF，提取资源量数据 |

### lme-price-mcp
| 工具 | 描述 |
|------|------|
| `get_price(commodity, date)` | 获取商品当前/历史价格 |
| `get_trend(commodity, days)` | 获取价格走势 + 统计摘要 |

## Agent 流程

```
用户输入 "Pilbara 锂矿简报"
        │
        ▼
   [plan] ─── LLM 提取主题、商品
        │
        ▼
[fetch_news] ─── 搜索 RSS + 获取文章
        │
        ▼
[fetch_resources] ─── 解析 NI 43-101 PDF
        │
        ▼
[fetch_prices] ─── 锂价 + 走势数据
        │
        ▼
[synthesize] ─── LLM 生成 Markdown 报告
        │
        ▼
    输出日报 (新闻 / 储量 / 价格 / 风险 / 引用)
```

## 技术栈

- **MCP**: `mcp` SDK (FastMCP)
- **Agent**: LangGraph + langchain-mcp-adapters
- **LLM**: Anthropic Claude / OpenAI GPT-4o
- **PDF**: PyMuPDF + pdfplumber
- **HTTP**: aiohttp
- **日志**: loguru
- **部署**: Docker Compose

## 许可证

MIT
