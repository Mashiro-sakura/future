#!/bin/bash
# ============================================
# 一键部署脚本 - 期现分析推送系统
# 在服务器上运行：bash deploy.sh
# ============================================
set -e

echo ">>> 1. 安装依赖..."
sudo apt update -qq
sudo apt install -y -qq python3 python3-pip python3-venv git

echo ">>> 2. 克隆项目..."
cd /opt
sudo rm -rf future 2>/dev/null || true
sudo git clone https://github.com/Mashiro-sakura/future.git
sudo chown -R ubuntu:ubuntu future
cd future/backend

echo ">>> 3. 创建虚拟环境并安装 Python 包..."
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -r requirements.txt
pip install --quiet akshare 2>/dev/null || true

echo ">>> 4. 创建 systemd 服务..."
sudo tee /etc/systemd/system/future-api.service > /dev/null <<'SVC'
[Unit]
Description=期现分析 API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/future/backend
ExecStart=/opt/future/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVC

echo ">>> 5. 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable future-api
sudo systemctl restart future-api

echo ">>> 6. 配置防火墙..."
sudo ufw allow 8000/tcp 2>/dev/null || true

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "后端 API: http://43.153.205.118:8000"
echo "前端页面: http://43.153.205.118:8000"
echo "健康检查: http://43.153.205.118:8000/health"
echo ""
echo "查看日志: sudo journalctl -u future-api -f"
echo "重启服务: sudo systemctl restart future-api"
echo "=========================================="
