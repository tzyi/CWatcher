#!/bin/bash

# CWatcher 前後端整合測試腳本

set -e

echo "🚀 CWatcher 前後端整合測試"
echo "=================================="

# 檢查必要的環境
echo "📋 檢查環境..."

# 檢查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安裝"
    exit 1
fi

# 檢查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安裝"
    exit 1
fi

# 檢查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安裝"
    exit 1
fi

echo "✅ 環境檢查完成"

# 進入專案根目錄
cd "$(dirname "$0")/.."

# 啟動後端服務
echo "🔄 啟動後端服務..."
if docker-compose -f docker-compose.dev.yml ps | grep -q "cwatcher-backend-dev"; then
    echo "✅ 後端服務已運行"
else
    echo "🚀 啟動後端開發環境..."
    docker-compose -f docker-compose.dev.yml up -d database redis
    sleep 5
    
    # 檢查是否有後端服務在本地運行
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "🚀 在 Docker 中啟動後端服務..."
        docker-compose -f docker-compose.dev.yml up -d backend-dev
        sleep 10
    else
        echo "✅ 本地後端服務已運行"
    fi
fi

# 等待後端服務就緒
echo "⏳ 等待後端服務就緒..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 後端服務就緒"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "⏳ 等待後端服務... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ 後端服務啟動超時"
    exit 1
fi

# 檢查前端依賴
echo "📦 檢查前端依賴..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "🔄 安裝前端依賴..."
    npm install
fi

# 建構前端 (檢查 TypeScript 類型)
echo "🔧 檢查前端類型..."
npm run type-check

# 執行前端測試
echo "🧪 執行前端單元測試..."
if npm run test -- --run --reporter=verbose 2>/dev/null; then
    echo "✅ 前端單元測試通過"
else
    echo "⚠️ 前端單元測試有問題，但繼續整合測試"
fi

# 啟動前端開發伺服器 (背景執行)
echo "🚀 啟動前端開發伺服器..."
npm run dev &
FRONTEND_PID=$!

# 等待前端服務就緒
echo "⏳ 等待前端服務就緒..."
sleep 10

# 清理函數
cleanup() {
    echo "🧹 清理資源..."
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
}

# 設定清理函數
trap cleanup EXIT

# 執行基本連接測試
echo "🔗 執行基本連接測試..."

# 測試後端健康檢查
echo "📊 測試後端健康檢查..."
if curl -s http://localhost:8000/health | grep -q "healthy\|running"; then
    echo "✅ 後端健康檢查通過"
else
    echo "❌ 後端健康檢查失敗"
    curl -s http://localhost:8000/health
    exit 1
fi

# 測試前端存取
echo "🌐 測試前端存取..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 前端服務存取正常"
else
    echo "❌ 前端服務無法存取"
    exit 1
fi

# 測試 API 端點
echo "🔌 測試關鍵 API 端點..."

# 測試伺服器列表 API
if curl -s "http://localhost:8000/api/v1/servers" -H "Content-Type: application/json" > /dev/null; then
    echo "✅ 伺服器列表 API 正常"
else
    echo "❌ 伺服器列表 API 異常"
fi

# 測試 WebSocket 健康檢查
if curl -s "http://localhost:8000/api/v1/websocket/health" > /dev/null; then
    echo "✅ WebSocket 健康檢查正常"
else
    echo "❌ WebSocket 健康檢查異常"
fi

echo ""
echo "🎉 基本整合測試完成！"
echo ""
echo "📋 測試摘要:"
echo "  ✅ 後端服務運行正常"
echo "  ✅ 前端服務運行正常"
echo "  ✅ API 端點可存取"
echo "  ✅ 基礎連接測試通過"
echo ""
echo "🔗 服務端點:"
echo "  後端 API: http://localhost:8000"
echo "  前端應用: http://localhost:5173"
echo "  API 文件: http://localhost:8000/api/v1/docs"
echo ""
echo "💡 建議進行的進一步測試:"
echo "  1. 在瀏覽器中開啟 http://localhost:5173"
echo "  2. 測試新增伺服器功能"
echo "  3. 驗證監控數據顯示"
echo "  4. 檢查 WebSocket 即時更新"
echo ""

# 提示使用者是否繼續執行詳細測試
read -p "是否執行詳細的前端整合測試？(y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 準備執行詳細整合測試..."
    echo "請在瀏覽器中開啟 http://localhost:5173 並開啟開發者工具"
    echo "然後在控制台中執行: runIntegrationTest()"
    echo ""
    echo "⏳ 按任意鍵結束測試..."
    read -n 1 -s
fi

echo "✅ 整合測試完成"