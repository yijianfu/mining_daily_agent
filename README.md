# Mining Daily Agent — MCP 矿权日报 Agent

基于 **MCP** + **LangGraph** 的矿业日报自动生成系统。输入自然语言查询，自动搜索新闻、提取 NI 43-101 储量数据、追踪金属价格，生成专业 Markdown 日报。

## 项目结构 (54 files)

```
mining_daily_agent/
│
├── agent/                          # Agent 层
│   ├── main.py                     # CLI 入口 (交互式对话 / 单次模式)
│   ├── web_server.py               # Web 入口 (FastAPI + Chat UI)
│   ├── graph.py                    # LangGraph 5 节点 pipeline
│   ├── nodes.py                    # plan → fetch_news → fetch_resources → fetch_prices → synthesize
│   ├── mcp_clients.py              # MultiServerMCPClient (stdio/SSE)
│   ├── llm.py                      # 多 Provider LLM 工厂 (6 种模型)
│   ├── prompts.py                  # 系统提示词 (中英双语)
│   ├── state.py                    # AgentState TypedDict
│   ├── config.py                   # Agent 配置
│   ├── static/index.html           # Web Chat UI (深色主题)
│   ├── Dockerfile                  # Agent 镜像
│   └── requirements.txt            # fastapi, uvicorn, langgraph, mcp, ...
│
├── servers/                        # MCP Server 层
│   ├── shared/                     # 共享基础设施
│   │   ├── cache_base.py           # TTL 缓存
│   │   ├── http_client.py          # 异步 HTTP (重试 + SSRF 防护)
│   │   ├── base_server.py          # FastMCP 包装 (stdio/SSE 双传输)
│   │   ├── async_utils.py          # 协程自适应 (sync/async)
│   │   └── logging_base.py         # loguru 日志
│   │
│   ├── mining_news_mcp/            # MCP Server 1: 矿业新闻
│   │   ├── fetchers/rss_fetcher.py   # Google News RSS 聚合
│   │   ├── fetchers/article_fetcher.py # trafilatura 正文提取
│   │   ├── tools.py                # search_mining_news + fetch_article
│   │   ├── server.py               # FastMCP 入口
│   │   └── models.py               # NewsArticle, SearchResult, ArticleBody
│   │
│   ├── mineral_pdf_mcp/            # MCP Server 2: NI 43-101 PDF 解析
│   │   ├── extractors/pdf_parser.py    # PyMuPDF 文本块
│   │   ├── extractors/table_extractor.py # pdfplumber 表格检测
│   │   ├── extractors/resource_parser.py # 资源量解析 + Mock 数据
│   │   ├── schemas.py              # NI 43-101 数据模型
│   │   ├── tools.py                # extract_resources
│   │   └── server.py
│   │
│   └── lme_price_mcp/              # MCP Server 3: 金属价格
│       ├── providers/base.py       # PriceProvider 抽象基类
│       ├── providers/mock_provider.py # 随机游走模拟价格
│       ├── tools.py                # get_price + get_trend (+ 30日统计)
│       ├── models.py               # CommodityPrice, PriceTrend, TrendSummary
│       └── server.py
│
├── docker-compose.yml              # 4 服务一键启动 (3 MCP + Web UI)
├── mcp-config.json                 # Claude Desktop / Cursor MCP 配置
├── .env.example                    # 环境变量模板
├── .gitignore
├── README.md
└── RUN.md                          # 5 分钟快速上手
```

## 运行方式

### 1. Web 界面 (推荐)

```bash
pip install -r agent/requirements.txt
python -m agent.web_server
# 浏览器打开 http://127.0.0.1:8080
```

### 2. CLI 交互式对话

```bash
python -m agent.main
# Mining> 给我生成一份关于 Pilbara 锂矿的今日简报
# /help  /models  /quit  /save <path>
```

### 3. CLI 单次模式

```bash
python -m agent.main "Copper market analysis"
```

### 4. Docker 一键启动

```bash
docker compose up --build
# Web UI: http://localhost:8080
```

## 支持的 LLM

| Provider | 环境变量 | 默认模型 |
|----------|---------|---------|
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| 通义千问 | `QWEN_API_KEY` | qwen-max |
| 智谱 GLM | `ZHIPU_API_KEY` | glm-4-plus |
| Moonshot | `MOONSHOT_API_KEY` | moonshot-v1-128k |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |

```bash
cp .env.example .env   # 填入任意一个 API Key 即可
python -m agent.main --list-models  # 查看状态
```

## MCP 工具清单

| Server | Tool | 描述 |
|--------|------|------|
| mining-news | `search_mining_news(query, days)` | RSS 搜索 + Mock 回退 |
| mining-news | `fetch_article(url)` | trafilatura 正文提取 |
| mineral-pdf | `extract_resources(pdf_url)` | NI 43-101 资源量解析 |
| lme-price | `get_price(commodity, date)` | 当前/历史价格 |
| lme-price | `get_trend(commodity, days)` | 30日走势 + 统计摘要 |

## Agent Pipeline

```
用户输入 → [plan: LLM提取主题] → [fetch_news: RSS+文章]
         → [fetch_resources: NI 43-101] → [fetch_prices: 价格走势]
         → [synthesize: LLM生成日报] → Markdown 报告
```

## 技术栈

`MCP` `LangGraph` `FastAPI` `Anthropic/OpenAI/DeepSeek` `PyMuPDF` `pdfplumber` `trafilatura` `aiohttp` `Docker`
