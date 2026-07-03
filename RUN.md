# RUN.md — 5 步跑起来

```bash
# 1. 克隆项目
git clone https://github.com/yijianfu/mining_daily_agent.git
cd mining_daily_agent

# 2. 配置 API Key (不配也能跑，内置了 mock 数据)
cp .env.example .env

# 3 & 4. 二选一
#    A) pip 安装
pip install -r servers/lme_price_mcp/requirements.txt
pip install -r servers/mining_news_mcp/requirements.txt
pip install -r servers/mineral_pdf_mcp/requirements.txt
pip install -r agent/requirements.txt
python -m agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"

#    B) Docker
docker compose up --build

# 5. 得到一份完整的 Markdown 日报
#    新闻摘要 + 储量数据 + 价格走势 + 风险提示 + 引用来源
```
