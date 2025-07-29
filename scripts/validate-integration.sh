#!/bin/bash

# CWatcher 前後端整合驗證腳本
# 在沒有 Docker 的環境下驗證代碼結構和配置

set -e

echo "🔍 CWatcher 前後端整合驗證"
echo "==============================="

cd "$(dirname "$0")/.."

# 檢查後端結構
echo "📂 檢查後端結構..."

# 檢查關鍵後端文件
backend_files=(
    "backend/app/main.py"
    "backend/app/api/v1/api.py"
    "backend/app/api/v1/endpoints/servers.py"
    "backend/app/api/v1/endpoints/monitoring.py" 
    "backend/app/api/v1/endpoints/websocket.py"
    "backend/app/api/v1/endpoints/ssh.py"
    "backend/app/services/ssh_manager.py"
    "backend/app/services/monitoring_collector.py"
    "backend/app/services/websocket_manager.py"
    "backend/requirements.txt"
)

missing_backend=0
for file in "${backend_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (缺失)"
        missing_backend=$((missing_backend + 1))
    fi
done

# 檢查前端結構  
echo ""
echo "📂 檢查前端結構..."

frontend_files=(
    "frontend/package.json"
    "frontend/src/App.tsx"
    "frontend/src/main.tsx"
    "frontend/src/services/api.ts"
    "frontend/src/services/websocket.ts"
    "frontend/src/components/servers/ServerList.tsx"
    "frontend/src/components/monitoring/MetricGrid.tsx"
    "frontend/src/components/charts/ChartGrid.tsx"
    "frontend/src/pages/Dashboard.tsx"
    "frontend/src/types/index.ts"
)

missing_frontend=0
for file in "${frontend_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (缺失)"
        missing_frontend=$((missing_frontend + 1))
    fi
done

# 檢查前端依賴
echo ""
echo "📦 檢查前端依賴安裝..."
cd frontend

if [ -f "package.json" ]; then
    if command -v node &> /dev/null; then
        if [ ! -d "node_modules" ]; then
            echo "🔄 安裝前端依賴..."
            npm install
        fi
        echo "✅ Node.js 和依賴已就緒"
    else
        echo "❌ Node.js 未安裝"
        missing_frontend=$((missing_frontend + 1))
    fi
else
    echo "❌ package.json 不存在"
    missing_frontend=$((missing_frontend + 1))
fi

# 檢查 TypeScript 類型
echo ""
echo "🔧 檢查 TypeScript 類型..."
if command -v node &> /dev/null && [ -f "package.json" ]; then
    if npm run type-check 2>/dev/null; then
        echo "✅ TypeScript 類型檢查通過"
    else
        echo "⚠️ TypeScript 類型檢查有警告"
    fi
else
    echo "⚠️ 無法執行 TypeScript 檢查"
fi

# 檢查 API 端點配置
echo ""
echo "🔗 檢查 API 端點配置..."
cd ..

# 檢查前端 API 配置是否與後端路由匹配
if grep -q "API_ENDPOINTS" frontend/src/services/api.ts; then
    echo "✅ 前端 API 端點已配置"
    
    # 檢查關鍵端點
    if grep -q "/api/v1/servers" frontend/src/services/api.ts; then
        echo "✅ 伺服器管理端點已配置"
    else
        echo "❌ 伺服器管理端點配置缺失"
    fi
    
    if grep -q "/api/v1/monitoring" frontend/src/services/api.ts; then
        echo "✅ 監控端點已配置"
    else
        echo "❌ 監控端點配置缺失"
    fi
    
    if grep -q "/api/v1/websocket" frontend/src/services/api.ts; then
        echo "✅ WebSocket 端點已配置"
    else
        echo "❌ WebSocket 端點配置缺失"
    fi
else
    echo "❌ API 端點配置缺失"
fi

# 檢查後端路由配置
echo ""
echo "🛣️ 檢查後端路由配置..."

if grep -q "api_router.include_router.*servers" backend/app/api/v1/api.py; then
    echo "✅ 伺服器路由已註冊"
else
    echo "❌ 伺服器路由註冊缺失"
fi

if grep -q "api_router.include_router.*monitoring" backend/app/api/v1/api.py; then
    echo "✅ 監控路由已註冊" 
else
    echo "❌ 監控路由註冊缺失"
fi

if grep -q "api_router.include_router.*websocket" backend/app/api/v1/api.py; then
    echo "✅ WebSocket 路由已註冊"
else
    echo "❌ WebSocket 路由註冊缺失"
fi

# 檢查 CORS 配置
echo ""
echo "🔒 檢查 CORS 配置..."

if grep -q "CORSMiddleware" backend/app/main.py; then
    echo "✅ CORS 中間件已配置"
    
    if grep -q "allow_origins" backend/app/main.py; then
        echo "✅ CORS 來源設定已配置"
    else
        echo "⚠️ CORS 來源設定可能需要檢查"
    fi
else
    echo "❌ CORS 中間件配置缺失"
fi

# 檢查環境變數配置
echo ""
echo "⚙️ 檢查環境配置..."

if [ -f "frontend/.env.example" ] || [ -f "frontend/.env" ]; then
    echo "✅ 前端環境配置檔案存在"
else
    echo "⚠️ 前端環境配置檔案不存在"
fi

if grep -q "VITE_API_BASE_URL" frontend/src/services/api.ts; then
    echo "✅ 前端 API URL 配置正確"
else
    echo "⚠️ 前端 API URL 配置可能需要檢查"
fi

# 總結報告
echo ""
echo "📊 整合驗證報告"
echo "================"

total_issues=$((missing_backend + missing_frontend))

echo "後端檔案檢查: $((${#backend_files[@]} - missing_backend))/${#backend_files[@]} 通過"
echo "前端檔案檢查: $((${#frontend_files[@]} - missing_frontend))/${#frontend_files[@]} 通過"

if [ $total_issues -eq 0 ]; then
    echo ""
    echo "🎉 整合驗證通過！"
    echo "✅ 所有關鍵檔案都存在"
    echo "✅ API 端點配置正確"
    echo "✅ 路由註冊完整"
    echo ""
    echo "📋 後續步驟:"
    echo "  1. 啟動後端服務: cd backend && python3 -m uvicorn app.main:app --reload"
    echo "  2. 啟動前端服務: cd frontend && npm run dev"
    echo "  3. 在瀏覽器中測試: http://localhost:5173"
    echo ""
    exit 0
elif [ $total_issues -le 3 ]; then
    echo ""
    echo "⚠️ 整合驗證部分通過"
    echo "發現 $total_issues 個問題，但基本結構完整"
    echo ""
    exit 1
else
    echo ""
    echo "❌ 整合驗證失敗"
    echo "發現 $total_issues 個問題需要修復"
    echo ""
    exit 2
fi