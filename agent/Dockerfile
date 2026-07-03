FROM python:3.11-slim

WORKDIR /app

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY servers /app/servers
COPY agent /app/agent

ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Default: start the web server
CMD ["python", "-m", "agent.web_server", "--host", "0.0.0.0", "--port", "8080"]
EXPOSE 8080
