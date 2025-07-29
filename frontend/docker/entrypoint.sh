#!/bin/sh

# CWatcher Frontend 啟動腳本

set -e

echo "🚀 啟動 CWatcher Frontend..."

# 建立健康檢查檔案
echo "healthy" > /usr/share/nginx/html/health

# 替換環境變數（如果需要）
if [ -n "$API_BASE_URL" ]; then
    echo "📝 設定 API Base URL: $API_BASE_URL"
    # 這裡可以替換 JS 檔案中的 API URL
fi

echo "✅ CWatcher Frontend 準備就緒"

# 執行傳入的命令
exec "$@"