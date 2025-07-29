#!/bin/bash

# CWatcher 安裝驗證腳本

set -e

echo "🔍 驗證 CWatcher 專案設置..."

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查函數
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1 不存在${NC}"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1 目錄不存在${NC}"
        return 1
    fi
}

echo ""
echo "📁 檢查專案目錄結構..."

# 後端結構檢查
echo "後端結構:"
check_dir "backend"
check_dir "backend/app"
check_dir "backend/tests"
check_file "backend/requirements.txt"
check_file "backend/Dockerfile"
check_file "backend/.env.example"

# 前端結構檢查
echo ""
echo "前端結構:"
check_dir "frontend"
check_dir "frontend/src"
check_file "frontend/package.json"
check_file "frontend/Dockerfile"
check_file "frontend/.env.example"

# Docker 配置檢查
echo ""
echo "Docker 配置:"
check_file "docker-compose.yml"
check_file "docker-compose.dev.yml"
check_dir "docker"
check_dir "scripts"

# Python 環境檢查
echo ""
echo "🐍 檢查 Python 環境..."
cd backend
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Python 虛擬環境存在${NC}"
    
    # 檢查是否能啟動虛擬環境
    if source venv/bin/activate 2>/dev/null; then
        echo -e "${GREEN}✅ 虛擬環境可以啟動${NC}"
        
        # 檢查主要套件
        if python -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null; then
            echo -e "${GREEN}✅ 主要 Python 套件已安裝${NC}"
        else
            echo -e "${YELLOW}⚠️  部分 Python 套件可能未安裝${NC}"
        fi
        
        deactivate 2>/dev/null || true
    else
        echo -e "${RED}❌ 無法啟動虛擬環境${NC}"
    fi
else
    echo -e "${RED}❌ Python 虛擬環境不存在${NC}"
fi
cd ..

# Node.js 環境檢查
echo ""
echo "📦 檢查 Node.js 環境..."
cd frontend
if [ -d "node_modules" ]; then
    echo -e "${GREEN}✅ Node.js 依賴已安裝${NC}"
    
    # 檢查 TypeScript 編譯
    if npm run type-check >/dev/null 2>&1; then
        echo -e "${GREEN}✅ TypeScript 編譯通過${NC}"
    else
        echo -e "${YELLOW}⚠️  TypeScript 編譯有警告或錯誤${NC}"
    fi
else
    echo -e "${RED}❌ Node.js 依賴未安裝${NC}"
fi
cd ..

# Docker 檢查
echo ""
echo "🐳 檢查 Docker 環境..."
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker 已安裝${NC}"
    
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✅ Docker Compose 已安裝${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker Compose 未安裝${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Docker 未安裝（可選）${NC}"
fi

echo ""
echo "📋 專案資訊:"
echo "   - 專案名稱: CWatcher"
echo "   - 版本: 0.1.0"
echo "   - 後端框架: FastAPI"
echo "   - 前端框架: React + TypeScript"
echo "   - 資料庫: PostgreSQL"
echo "   - 容器化: Docker & Docker Compose"

echo ""
echo "🎯 快速開始指令:"
echo "   後端開發: cd backend && source venv/bin/activate && python app/main.py"
echo "   前端開發: cd frontend && npm run dev"
echo "   Docker 開發: ./scripts/dev-setup.sh （需要 Docker）"

echo ""
echo "✅ 驗證完成！"