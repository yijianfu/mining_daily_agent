# RUN.md — 5 步跑起来

```bash
# 1. 克隆项目
git clone https://github.com/yijianfu/mining_daily_agent.git
cd mining_daily_agent

# 2. 配置 API Key (不配也能跑，内置了 mock 数据)
cp .env.example .env

# 3. 安装依赖
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt

# 4. 运行 (三选一)
#    Web 界面 (推荐)
python -m agent.web_server
#    打开 http://127.0.0.1:8080

#    CLI 对话模式
python -m agent.main

#    CLI 单次模式
python -m agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"

# 5. 得到完整的 Markdown 日报
#    新闻摘要 + 储量数据 + 价格走势 + 风险提示 + 引用来源

# Docker
docker compose up --build
#    打开 http://localhost:8080
```
