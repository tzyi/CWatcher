#!/bin/bash

# CWatcher 部署腳本

set -e

ENVIRONMENT=${1:-production}

echo "🚀 開始部署 CWatcher 到 $ENVIRONMENT 環境..."

case $ENVIRONMENT in
  "development"|"dev")
    echo "📦 部署到開發環境..."
    docker-compose -f docker-compose.dev.yml down
    docker-compose -f docker-compose.dev.yml pull
    docker-compose -f docker-compose.dev.yml up -d
    ;;
  "production"|"prod")
    echo "📦 部署到生產環境..."
    docker-compose down
    docker-compose pull
    docker-compose up -d
    ;;
  *)
    echo "❌ 未知環境: $ENVIRONMENT"
    echo "使用方式: $0 [development|production]"
    exit 1
    ;;
esac

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 30

# 健康檢查
echo "🔍 執行健康檢查..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 後端服務健康"
else
    echo "❌ 後端服務異常"
    exit 1
fi

if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ 前端服務健康"
else
    echo "❌ 前端服務異常"
    exit 1
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "📋 服務狀態:"
docker-compose ps
echo ""