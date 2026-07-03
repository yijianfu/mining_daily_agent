# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Install all dependencies at once
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt

# Web UI (primary dev entry point)
python -m agent.web_server              # → http://127.0.0.1:8080

# CLI — interactive dialogue
python -m agent.main                    # /help /models /quit /save

# CLI — one-shot
python -m agent.main "Pilbara lithium briefing"

# CLI — standalone (no MCP subprocesses, no API key)
python -m agent.main --standalone "铜矿市场分析"

# List configured LLM providers and their API key status
python -m agent.main --list-models

# Docker
docker compose up --build               # 3 MCP servers + Web UI → :8080
docker compose --profile cli up agent   # CLI mode instead of Web UI
```

## Architecture

The project has two layers: **MCP Servers** (data fetching) and **Agent** (orchestration + presentation).

### MCP Servers (`servers/`)

Three independent FastMCP servers, each runnable standalone via `python -m servers.<name>.server`. They share a `servers/shared/` module for caching (`TTLCache`), HTTP (`HTTPClient`), and server boilerplate (`BaseMCPServer`).

Each server auto-detects transport from `MCP_TRANSPORT` env var: `stdio` (local dev) or `sse` (Docker). Every server has built-in mock data fallback — the system works with zero API keys.

Key shared utility: `servers/shared/async_utils.py` → `run_async()` — safely calls async code from both sync and async contexts. MCP tool functions are sync, but internally call async HTTP/IO via this helper.

### Agent (`agent/`)

**LLM layer** (`llm.py`): Unified factory with 6 providers (DeepSeek, Qwen, Zhipu, Moonshot, Anthropic, OpenAI). `_env()` helper strips inline `#` comments from `.env` values (a trap: `KEY=value  # comment` gets parsed as the full string by python-dotenv). The factory auto-detects which provider has a configured API key.

**Pipeline** (`graph.py` + `nodes.py`): 5-node LangGraph StateGraph: `plan → fetch_news → fetch_resources → fetch_prices → synthesize`. Each fetch node receives MCP tools via closure injection in `build_graph()`. Nodes degrade gracefully — if MCP tools are unavailable or a call fails, that section is marked as "no data" rather than crashing.

**MCP Client** (`mcp_clients.py`): Uses `langchain-mcp-adapters.MultiServerMCPClient`. Two transport configs: `build_stdio_config()` spawns subprocesses (local dev), `build_sse_config()` connects via HTTP (Docker). The web server and CLI both reuse MCP connections across queries in interactive mode.

**Web Server** (`web_server.py`): FastAPI app serving the chat UI at `/` and a REST API at `/api/chat`. Auto-detects Docker mode via `MCP_CLIENT_TRANSPORT=sse` to switch between standalone and MCP-connected agent runs. Static files at `agent/static/index.html`.

### Key Design Patterns

- **Mock-everywhere**: All 3 servers work without API keys. Mock data is clearly labeled in output.
- **.env auto-loading**: `main.py` and `web_server.py` both call `load_dotenv()` at startup. No shell export needed.
- **Graceful degradation**: If a data source fails, the pipeline continues and marks that section "no data".
- **Chinese-first prompts**: Synthesis prompt defaults to Chinese output. Commodity aliases in `_fallback_extract()` handle both English and Chinese keywords.
- **Cache TTLs**: News search 300s, article body 3600s, current price 60s, price history 300s, PDF extraction 86400s.
