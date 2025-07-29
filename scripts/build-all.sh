#!/bin/bash

# CWatcher 完整建構腳本

set -e

echo "🏗️  開始建構 CWatcher 專案..."

# 檢查 Docker 是否安裝
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安裝，請先安裝 Docker"
    exit 1
fi

# 建構後端映像
echo "🐍 建構後端映像..."
cd backend
docker build -t cwatcher-backend:latest .
cd ..

# 建構前端映像
echo "⚛️  建構前端映像..."
cd frontend
docker build -t cwatcher-frontend:latest .
cd ..

# 建構完整系統
echo "🐳 建構完整系統映像..."
docker-compose build

echo ""
echo "✅ 建構完成！"
echo ""
echo "🚀 啟動命令:"
echo "   開發環境: docker-compose -f docker-compose.dev.yml up -d"
echo "   生產環境: docker-compose up -d"
echo ""