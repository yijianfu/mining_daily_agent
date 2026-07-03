"""FastAPI web server for the Mining Daily Agent.

Provides a REST API and serves the chat UI.
Start with: python -m agent.web_server
"""

import sys
import os
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn
import asyncio
import json

from servers.shared.logging_base import setup_logging

setup_logging("mining-agent-web", use_stderr=True)

app = FastAPI(
    title="Mining Daily Agent",
    description="MCP-based mining industry daily briefing agent",
    version="1.0.0",
)


# ── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(
        default="给我生成一份关于 Pilbara 锂矿的今日简报",
        description="Natural language briefing request",
    )


class ChatResponse(BaseModel):
    report: str = Field(description="Markdown briefing report")
    timestamp: str = Field(description="Generation timestamp")


# ── Agent Runner ─────────────────────────────────────────────────────────────

async def _run_agent(query: str) -> str:
    """Run the agent in standalone mode (no MCP subprocess overhead)."""
    from agent.main import run_standalone
    return await run_standalone(query)


# ── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Run the agent and return a briefing report."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info(f"Chat API: {query[:80]}...")
    try:
        report = await _run_agent(query)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        report=report,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream the agent report line-by-line for a real-time feel."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info(f"Chat stream: {query[:80]}...")

    async def generator():
        # Send status messages while the report is being generated
        yield f"data: {json.dumps({'type': 'status', 'message': 'Connecting to data sources...'})}\n\n"

        try:
            # Run the agent in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            report = await loop.run_in_executor(None, _run_sync, query)

            # Stream the report in chunks for visual effect
            lines = report.split("\n")
            chunk = []
            for i, line in enumerate(lines):
                chunk.append(line)
                # Send every 5 lines or at section boundaries
                if len(chunk) >= 5 or line.startswith("##") or i == len(lines) - 1:
                    text = "\n".join(chunk)
                    yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"
                    chunk = []

            yield f"data: {json.dumps({'type': 'done', 'timestamp': datetime.now().isoformat()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _run_sync(query: str) -> str:
    """Synchronous wrapper for async agent runner (used in thread pool)."""
    import asyncio as _asyncio
    from agent.main import run_standalone
    return _asyncio.run(run_standalone(query))


# ── Static Files ─────────────────────────────────────────────────────────────

static_dir = _PROJECT_ROOT / "agent" / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the chat UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Mining Daily Agent API", "docs": "/docs"}


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    """Start the web server."""
    import argparse
    parser = argparse.ArgumentParser(description="Mining Daily Agent Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    logger.info(f"Starting web server at http://{args.host}:{args.port}")
    print(f"\n  Mining Daily Agent Web UI")
    print(f"  Open: http://{args.host}:{args.port}")
    print(f"  API docs: http://{args.host}:{args.port}/docs\n")

    uvicorn.run(
        "agent.web_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
