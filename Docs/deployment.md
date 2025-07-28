---
title: 部署配置指南
description: "生產環境部署配置和運維指南。"
inclusion: always
---

# CWatcher 部署配置指南

## 部署架構概覽

### 推薦架構
```
Internet
    │
    ▼
┌─────────────────┐
│   Load Balancer │  (Nginx/HAProxy)
│   (SSL 終止)    │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│   Reverse Proxy │  (Nginx)
│   (快取/壓縮)   │
└─────────────────┘
    │
    ├─────────────────┐
    ▼                 ▼
┌─────────────────┐ ┌─────────────────┐
│   Frontend      │ │   Backend API   │
│   (React SPA)   │ │   (FastAPI)     │
└─────────────────┘ └─────────────────┘
                        │
                        ▼
                    ┌─────────────────┐
                    │   MySQL 8.0     │
                    │   (主資料庫)    │
                    └─────────────────┘
                        │
                        ▼
                    ┌─────────────────┐
                    │   Redis         │
                    │   (快取/會話)   │
                    └─────────────────┘
```

## 系統需求

### 硬體需求

#### 最低配置
- **CPU**：2 核心
- **記憶體**：4GB RAM
- **存儲**：20GB SSD
- **網路**：100Mbps

#### 推薦配置
- **CPU**：4 核心
- **記憶體**：8GB RAM
- **存儲**：100GB SSD
- **網路**：1Gbps

#### 企業級配置
- **CPU**：8 核心
- **記憶體**：16GB RAM
- **存儲**：500GB SSD（RAID 1）
- **網路**：10Gbps

### 軟體需求
- **作業系統**：Ubuntu 20.04 LTS 或 CentOS 8
- **Docker**：20.10 或以上
- **Docker Compose**：2.0 或以上
- **Nginx**：1.18 或以上
- **MySQL**：8.0 或以上

## Docker 部署

### 1. 生產環境 Docker Compose

#### docker-compose.yml
```yaml
version: '3.8'

services:
  # 前端服務
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    container_name: cwatcher_frontend
    restart: unless-stopped
    environment:
      - NODE_ENV=production
    volumes:
      - frontend_static:/app/dist
    networks:
      - cwatcher_network

  # 後端 API 服務
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: cwatcher_backend
    restart: unless-stopped
    environment:
      - DATABASE_URL=mysql+pymysql://cabie:${MYSQL_PASSWORD}@mysql:3306/cwatcher
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - ENVIRONMENT=production
    depends_on:
      - mysql
      - redis
    volumes:
      - backend_logs:/app/logs
    networks:
      - cwatcher_network

  # MySQL 資料庫
  mysql:
    image: mysql:8.0
    container_name: cwatcher_mysql
    restart: unless-stopped
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=cwatcher
      - MYSQL_USER=cabie
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./database/init:/docker-entrypoint-initdb.d
      - ./database/config/my.cnf:/etc/mysql/conf.d/my.cnf
    ports:
      - "3306:3306"
    networks:
      - cwatcher_network
    command: --default-authentication-plugin=mysql_native_password

  # Redis 快取
  redis:
    image: redis:7-alpine
    container_name: cwatcher_redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf
    ports:
      - "6379:6379"
    networks:
      - cwatcher_network
    command: redis-server /usr/local/etc/redis/redis.conf

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: cwatcher_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - frontend_static:/var/www/html
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/sites-available:/etc/nginx/sites-available
      - ./ssl:/etc/nginx/ssl
      - nginx_logs:/var/log/nginx
    depends_on:
      - frontend
      - backend
    networks:
      - cwatcher_network

volumes:
  mysql_data:
  redis_data:
  frontend_static:
  backend_logs:
  nginx_logs:

networks:
  cwatcher_network:
    driver: bridge
```

#### .env 生產環境配置
```bash
# 資料庫密碼
MYSQL_ROOT_PASSWORD=secure_root_password_here
MYSQL_PASSWORD=Aa-12345

# 應用安全金鑰
SECRET_KEY=your-super-secret-key-here-must-be-32-chars-or-more
JWT_SECRET=your-jwt-secret-key-here

# 環境設定
ENVIRONMENT=production
DEBUG=false

# 外部服務
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# SSL 設定
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
```

### 2. Dockerfile 配置

#### Frontend Dockerfile.prod
```dockerfile
# 多階段建構
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# 生產階段
FROM nginx:alpine

# 複製建構檔案
COPY --from=builder /app/dist /var/www/html

# 複製 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 健康檢查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

EXPOSE 80
```

#### Backend Dockerfile.prod
```dockerfile
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴檔案
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY . .

# 建立非 root 用戶
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 啟動命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Nginx 配置

### nginx.conf
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日誌格式
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    # 基本設定
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;

    # Gzip 壓縮
    gzip on;
    gzip_vary on;
    gzip_min_length 10240;
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/x-javascript
        application/javascript
        application/xml+rss
        application/json;

    # 速率限制
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # 上游服務器
    upstream backend {
        server backend:8000;
        keepalive 32;
    }

    # 引入站點配置
    include /etc/nginx/sites-available/*.conf;
}
```

### sites-available/cwatcher.conf
```nginx
server {
    listen 80;
    server_name cwatcher.example.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name cwatcher.example.com;

    # SSL 配置
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # 安全標頭
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    # 前端靜態檔案
    location / {
        root /var/www/html;
        index index.html;
        try_files $uri $uri/ /index.html;

        # 快取設定
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # 速率限制
        limit_req zone=api burst=20 nodelay;
    }

    # WebSocket 代理
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # 登入端點特殊限制
    location /api/auth/login {
        proxy_pass http://backend;
        limit_req zone=login burst=5 nodelay;
    }

    # 健康檢查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

## 資料庫配置

### MySQL 配置 (my.cnf)
```ini
[mysqld]
# 基本設定
default-authentication-plugin=mysql_native_password
bind-address=0.0.0.0
port=3306

# 字元集
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci

# InnoDB 設定
innodb_buffer_pool_size=1G
innodb_log_file_size=256M
innodb_flush_log_at_trx_commit=1
innodb_file_per_table=1

# 連接設定
max_connections=200
max_user_connections=180
wait_timeout=600
interactive_timeout=600

# 查詢快取
query_cache_type=1
query_cache_size=64M

# 日誌設定
slow_query_log=1
slow_query_log_file=/var/log/mysql/slow.log
long_query_time=2

# 二進制日誌（用於備份）
log-bin=mysql-bin
binlog_format=row
expire_logs_days=7

[mysql]
default-character-set=utf8mb4

[client]
default-character-set=utf8mb4
```

### Redis 配置 (redis.conf)
```
# 網路設定
bind 0.0.0.0
port 6379
protected-mode yes

# 記憶體設定
maxmemory 512mb
maxmemory-policy allkeys-lru

# 持久化設定
save 900 1
save 300 10
save 60 10000

# 安全設定
requirepass your_redis_password_here

# 日誌設定
loglevel notice
logfile /var/log/redis/redis.log

# 客戶端設定
timeout 300
tcp-keepalive 300
```

## SSL/TLS 配置

### 使用 Let's Encrypt
```bash
# 安裝 Certbot
sudo apt install certbot python3-certbot-nginx

# 獲取證書
sudo certbot --nginx -d cwatcher.example.com

# 自動續期
sudo crontab -e
# 添加以下行
0 12 * * * /usr/bin/certbot renew --quiet
```

### 自簽證書（開發用）
```bash
# 建立 SSL 目錄
mkdir -p ssl

# 生成私鑰
openssl genrsa -out ssl/key.pem 2048

# 生成證書請求
openssl req -new -key ssl/key.pem -out ssl/cert.csr

# 生成自簽證書
openssl x509 -req -days 365 -in ssl/cert.csr -signkey ssl/key.pem -out ssl/cert.pem
```

## 部署腳本

### deploy.sh
```bash
#!/bin/bash

set -e

echo "開始部署 CWatcher..."

# 檢查 Docker
if ! command -v docker &> /dev/null; then
    echo "錯誤：未安裝 Docker"
    exit 1
fi

# 檢查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "錯誤：未安裝 Docker Compose"
    exit 1
fi

# 停止現有服務
echo "停止現有服務..."
docker-compose down

# 清理舊映像
echo "清理舊映像..."
docker system prune -f

# 拉取最新代碼
echo "拉取最新代碼..."
git pull origin main

# 建構映像
echo "建構映像..."
docker-compose build --no-cache

# 啟動服務
echo "啟動服務..."
docker-compose up -d

# 等待服務啟動
echo "等待服務啟動..."
sleep 30

# 健康檢查
echo "執行健康檢查..."
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ 部署成功！"
else
    echo "❌ 部署失敗，請檢查日誌"
    docker-compose logs
    exit 1
fi

echo "部署完成！"
```

### backup.sh
```bash
#!/bin/bash

BACKUP_DIR="/backup/cwatcher"
DATE=$(date +%Y%m%d_%H%M%S)

# 建立備份目錄
mkdir -p $BACKUP_DIR

# 備份資料庫
echo "備份資料庫..."
docker exec cwatcher_mysql mysqldump -u cabie -pAa-12345 cwatcher > $BACKUP_DIR/database_$DATE.sql

# 備份 Redis
echo "備份 Redis..."
docker exec cwatcher_redis redis-cli --rdb $BACKUP_DIR/redis_$DATE.rdb

# 壓縮備份
echo "壓縮備份檔案..."
tar -czf $BACKUP_DIR/cwatcher_backup_$DATE.tar.gz -C $BACKUP_DIR database_$DATE.sql redis_$DATE.rdb

# 清理臨時檔案
rm $BACKUP_DIR/database_$DATE.sql $BACKUP_DIR/redis_$DATE.rdb

# 保留最近 7 天的備份
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "備份完成：$BACKUP_DIR/cwatcher_backup_$DATE.tar.gz"
```

## 監控和日誌

### 日誌收集
```yaml
# 在 docker-compose.yml 中添加
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "3"
```

### Prometheus 監控
```yaml
# 添加到 docker-compose.yml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3001:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin123
  volumes:
    - grafana_data:/var/lib/grafana
```

### 健康檢查端點
```python
# 在 FastAPI 中添加
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }
```

## 安全配置

### 防火牆設定
```bash
# Ubuntu UFW
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 定期安全更新
```bash
# 建立自動更新腳本
cat > /etc/cron.weekly/security-updates << 'EOF'
#!/bin/bash
apt update && apt upgrade -y
docker system prune -f
EOF

chmod +x /etc/cron.weekly/security-updates
```

## 性能調優

### 系統級調優
```bash
# 增加檔案描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 調整網路參數
echo "net.core.somaxconn = 65536" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65536" >> /etc/sysctl.conf
sysctl -p
```

### 應用級調優
- **資料庫連接池**：設定適當的連接池大小
- **快取策略**：使用 Redis 快取頻繁查詢的數據
- **異步處理**：使用後台任務處理耗時操作
- **負載均衡**：多實例部署時配置負載均衡

這個部署指南提供了完整的生產環境部署配置，包括容器化部署、安全配置、監控和維護等各個方面，確保系統能夠穩定、安全地運行。