FROM python:3.11-slim

WORKDIR /app

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY servers /app/servers
COPY agent /app/agent

ENV PYTHONPATH=/app
ENV MCP_CLIENT_TRANSPORT=sse
ENV MCP_NEWS_URL=http://mining-news-mcp:8000/sse
ENV MCP_PDF_URL=http://mineral-pdf-mcp:8000/sse
ENV MCP_LME_URL=http://lme-price-mcp:8000/sse
ENV LOG_LEVEL=INFO

ENTRYPOINT ["python", "-m", "agent.main"]
CMD ["给我生成一份关于 Pilbara 锂矿的今日简报"]
