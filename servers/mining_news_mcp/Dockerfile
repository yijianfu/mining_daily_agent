FROM python:3.11-slim

WORKDIR /app

COPY servers/mining_news_mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY servers/shared /app/servers/shared
COPY servers/mining_news_mcp /app/servers/mining_news_mcp

ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "servers.mining_news_mcp.server"]
