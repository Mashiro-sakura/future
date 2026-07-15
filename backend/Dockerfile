FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码和静态文件
COPY app/ app/
COPY static/ static/
COPY Procfile .

# Zeabur 会通过 $PORT 指定端口
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
