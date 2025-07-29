# CWatcher Frontend Dockerfile
# 多階段建構，優化映像大小

# 第一階段：建構階段
FROM node:18-alpine as builder

# 設定工作目錄
WORKDIR /app

# 複製 package 檔案
COPY package*.json ./

# 安裝依賴
RUN npm ci --only=production && npm cache clean --force

# 複製原始碼
COPY . .

# 建構應用程式
RUN npm run build

# 第二階段：Nginx 服務階段
FROM nginx:alpine

# 安裝 curl 用於健康檢查
RUN apk add --no-cache curl

# 複製自訂 Nginx 配置
COPY docker/nginx.conf /etc/nginx/nginx.conf

# 複製建構產物到 Nginx 目錄
COPY --from=builder /app/dist /usr/share/nginx/html

# 複製啟動腳本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露埠
EXPOSE 80

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# 啟動 Nginx
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]