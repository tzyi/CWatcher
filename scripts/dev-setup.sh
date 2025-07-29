#!/bin/bash

# CWatcher 開發環境設置腳本

set -e

echo "🚀 開始設置 CWatcher 開發環境..."

# 檢查 Docker 是否安裝
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安裝，請先安裝 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安裝，請先安裝 Docker Compose"
    exit 1
fi

# 建立必要目錄
echo "📁 建立必要目錄..."
mkdir -p backend/logs
mkdir -p frontend/dist

# 複製環境變數檔案
if [ ! -f backend/.env ]; then
    echo "📝 建立後端環境變數檔案..."
    cp backend/.env.example backend/.env
    echo "請編輯 backend/.env 檔案設定您的配置"
fi

# 啟動開發環境
echo "🐳 啟動開發環境 Docker 容器..."
docker-compose -f docker-compose.dev.yml up -d database redis pgadmin mailhog

# 等待資料庫啟動
echo "⏳ 等待資料庫啟動..."
sleep 10

# 檢查資料庫連接
echo "🔍 檢查資料庫連接..."
docker-compose -f docker-compose.dev.yml exec database psql -U cwatcher -d cwatcher_dev -c "SELECT 'Database connected successfully' as status;"

echo ""
echo "✅ 開發環境設置完成！"
echo ""
echo "📋 服務訪問資訊:"
echo "   - 資料庫: localhost:5433"
echo "   - Redis: localhost:6380"
echo "   - pgAdmin: http://localhost:5050 (admin@cwatcher.local / admin123)"
echo "   - Mailhog: http://localhost:8025"
echo ""
echo "🔧 下一步:"
echo "   1. 進入 backend 目錄並執行: python -m venv venv && source venv/bin/activate"
echo "   2. 安裝 Python 依賴: pip install -r requirements.txt"
echo "   3. 執行資料庫遷移: alembic upgrade head"
echo "   4. 啟動後端: python app/main.py"
echo "   5. 進入 frontend 目錄並執行: npm install && npm run dev"
echo ""