# 期现分析终端 —— Zeabur/Docker 部署
# 关键点：
# 1. TZ=Asia/Shanghai 必须设——_is_trading_time 的盘中判定、date.today()、scheduler
#    全依赖本地时间，容器默认 UTC 会导致盘中判定永久 False、日频数据错日
# 2. 首启从 /app/seed/future_analysis.db 拷贝净化种子库到持久卷
#    （1269 期货+3681 现货+140 波动率+123 持仓排名行；admin 凭据已清，
#    首启按 ADMIN_USERNAME/ADMIN_PASSWORD 环境变量重建）
# 3. Zeabur 控制台需挂持久卷到 /app/data，否则每次部署数据清零（7 月教训）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    DATABASE_URL=sqlite:////app/data/future_analysis.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /app/data && if [ ! -f /app/data/future_analysis.db ]; then echo '>>> 首次启动：从种子库初始化数据'; cp /app/seed/future_analysis.db /app/data/future_analysis.db; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
