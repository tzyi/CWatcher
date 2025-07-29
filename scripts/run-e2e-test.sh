#!/bin/bash

# CWatcher 端到端整合測試腳本
# 完整測試前後端整合功能

set -e

echo "🎯 CWatcher 端到端整合測試"
echo "================================"

# 進入專案根目錄
cd "$(dirname "$0")/.."

# 檢查 Python 環境
echo "🐍 檢查 Python 環境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安裝"
    exit 1
fi

# 檢查 Node.js 環境
echo "📦 檢查 Node.js 環境..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安裝"
    exit 1
fi

# 設定後端環境
echo "🔧 設定後端環境..."
cd backend

if [ ! -d "venv" ]; then
    echo "🔄 建立 Python 虛擬環境..."
    python3 -m venv venv
fi

echo "🔄 啟動 Python 虛擬環境..."
source venv/bin/activate

if [ ! -f "venv/.deps_installed" ]; then
    echo "📦 安裝後端依賴..."
    pip install -r requirements.txt
    touch venv/.deps_installed
fi

# 啟動後端服務 (背景執行)
echo "🚀 啟動後端服務..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 等待後端服務啟動
echo "⏳ 等待後端服務啟動..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 後端服務已啟動"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "⏳ 等待後端服務... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ 後端服務啟動超時"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 清理函數
cleanup() {
    echo "🧹 清理資源..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
}

# 設定清理函數
trap cleanup EXIT

# 執行後端測試
echo "🔄 執行後端整合測試..."
if python3 test_backend_integration.py; then
    echo "✅ 後端整合測試通過"
    BACKEND_TEST_PASSED=true
else
    echo "❌ 後端整合測試失敗"
    BACKEND_TEST_PASSED=false
fi

# 設定前端環境
echo "🎨 設定前端環境..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "📦 安裝前端依賴..."
    npm install
fi

# 建構前端 (檢查是否有錯誤)
echo "🔧 檢查前端建構..."
if npm run type-check; then
    echo "✅ 前端 TypeScript 檢查通過"
    FRONTEND_TYPECHECK_PASSED=true
else
    echo "❌ 前端 TypeScript 檢查失敗"
    FRONTEND_TYPECHECK_PASSED=false
fi

# 啟動前端開發伺服器 (背景執行)
echo "🚀 啟動前端服務..."
npm run dev &
FRONTEND_PID=$!

# 等待前端服務啟動
echo "⏳ 等待前端服務啟動..."
sleep 10

# 檢查前端服務是否可以存取
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 前端服務已啟動"
    FRONTEND_STARTED=true
else
    echo "❌ 前端服務啟動失敗"
    FRONTEND_STARTED=false
fi

# 執行基本連接測試
echo "🔗 執行前後端連接測試..."

# 測試 CORS 設定
echo "🔒 測試 CORS 設定..."
CORS_TEST=$(curl -s -H "Origin: http://localhost:5173" \
                -H "Access-Control-Request-Method: GET" \
                -H "Access-Control-Request-Headers: Content-Type" \
                -X OPTIONS \
                -w "%{http_code}" \
                http://localhost:8000/api/v1/servers)

if [ "$CORS_TEST" = "200" ]; then
    echo "✅ CORS 設定正確"
    CORS_PASSED=true
else
    echo "❌ CORS 設定有問題: HTTP $CORS_TEST"
    CORS_PASSED=false
fi

# 測試前端到後端的 API 調用
echo "📡 測試前端到後端 API 調用..."
API_TEST=$(curl -s -H "Origin: http://localhost:5173" \
               -H "Content-Type: application/json" \
               -w "%{http_code}" \
               http://localhost:8000/api/v1/servers)

if [ "$API_TEST" = "200" ]; then
    echo "✅ API 調用正常"
    API_CALL_PASSED=true
else
    echo "❌ API 調用失敗: HTTP $API_TEST"
    API_CALL_PASSED=false
fi

# 測試 WebSocket 連接可用性
echo "🔌 測試 WebSocket 可用性..."
WS_HEALTH=$(curl -s -w "%{http_code}" http://localhost:8000/api/v1/websocket/health)

if [ "$WS_HEALTH" = "200" ]; then
    echo "✅ WebSocket 服務可用"
    WS_PASSED=true
else
    echo "❌ WebSocket 服務不可用: HTTP $WS_HEALTH"
    WS_PASSED=false
fi

# 生成最終報告
echo ""
echo "🎯 端到端測試報告"
echo "=================="

echo ""
echo "🔧 服務啟動狀態："
echo "  後端服務: $([ "$BACKEND_TEST_PASSED" = "true" ] && echo "✅ 正常" || echo "❌ 異常")"
echo "  前端服務: $([ "$FRONTEND_STARTED" = "true" ] && echo "✅ 正常" || echo "❌ 異常")"

echo ""
echo "🔍 代碼品質檢查："
echo "  後端整合測試: $([ "$BACKEND_TEST_PASSED" = "true" ] && echo "✅ 通過" || echo "❌ 失敗")"
echo "  前端類型檢查: $([ "$FRONTEND_TYPECHECK_PASSED" = "true" ] && echo "✅ 通過" || echo "❌ 失敗")"

echo ""
echo "🔗 連接測試："
echo "  CORS 設定: $([ "$CORS_PASSED" = "true" ] && echo "✅ 正確" || echo "❌ 錯誤")"
echo "  API 調用: $([ "$API_CALL_PASSED" = "true" ] && echo "✅ 正常" || echo "❌ 異常")"
echo "  WebSocket: $([ "$WS_PASSED" = "true" ] && echo "✅ 可用" || echo "❌ 不可用")"

# 計算總體分數
TOTAL_TESTS=6
PASSED_TESTS=0

[ "$BACKEND_TEST_PASSED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ "$FRONTEND_STARTED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ "$FRONTEND_TYPECHECK_PASSED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ "$CORS_PASSED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ "$API_CALL_PASSED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ "$WS_PASSED" = "true" ] && PASSED_TESTS=$((PASSED_TESTS + 1))

PASS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))

echo ""
echo "📊 總體結果: $PASSED_TESTS/$TOTAL_TESTS 通過 ($PASS_RATE%)"

if [ $PASS_RATE -ge 80 ]; then
    echo "🎉 端到端測試通過！CWatcher 前後端整合成功"
    echo ""
    echo "🔗 服務端點："
    echo "  前端應用: http://localhost:5173"
    echo "  後端 API: http://localhost:8000"
    echo "  API 文件: http://localhost:8000/api/v1/docs"
    echo ""
    echo "💡 建議手動測試："
    echo "  1. 開啟瀏覽器到 http://localhost:5173"
    echo "  2. 測試新增伺服器功能"
    echo "  3. 驗證監控數據顯示"
    echo "  4. 檢查 WebSocket 即時更新"
    
    # 詢問是否保持服務運行
    echo ""
    read -p "是否保持服務運行以供手動測試？(y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "⏳ 服務保持運行中..."
        echo "按 Ctrl+C 結束測試"
        
        # 等待使用者中斷
        while true; do
            sleep 1
        done
    fi
    
    exit 0
elif [ $PASS_RATE -ge 60 ]; then
    echo "⚠️ 端到端測試部分通過，請檢查失敗項目"
    exit 1
else
    echo "❌ 端到端測試失敗，需要修復主要問題"
    exit 2
fi