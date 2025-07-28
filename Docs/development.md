---
title: 開發環境設置指南
description: "詳細的開發環境配置和初始化步驟。"
inclusion: always
---

# CWatcher 開發環境設置指南

## 系統需求

### 硬體需求
- **CPU**：Intel i5 或 AMD Ryzen 5 以上
- **記憶體**：8GB RAM 以上（推薦 16GB）
- **存儲空間**：20GB 可用空間
- **網路**：穩定的網際網路連接

### 軟體需求
- **作業系統**：Windows 10+、macOS 10.15+、Ubuntu 18.04+
- **Node.js**：16.x 或 18.x LTS 版本
- **Python**：3.9 或 3.10 版本
- **MySQL**：8.0 或以上版本
- **Git**：2.30 或以上版本
- **Docker**：20.x 或以上（可選）

## 環境安裝步驟

### 1. 安裝基礎工具

#### Node.js 安裝
```bash
# 使用 nvm 安裝（推薦）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# 或直接下載安裝
# 訪問 https://nodejs.org/ 下載 LTS 版本
```

#### Python 安裝
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-dev

# macOS (使用 Homebrew)
brew install python@3.9

# Windows
# 訪問 https://python.org 下載安裝程式
```

#### MySQL 安裝
```bash
# Ubuntu/Debian
sudo apt install mysql-server mysql-client

# macOS
brew install mysql

# Windows
# 訪問 https://dev.mysql.com/downloads/mysql/ 下載安裝程式
```

### 2. 專案初始化

#### 克隆專案
```bash
git clone https://github.com/your-username/CWatcher.git
cd CWatcher
```

#### 建立專案結構
```bash
# 建立主要目錄
mkdir -p backend frontend database scripts deployment docs-archive

# 移動現有檔案到歸檔目錄
mv Docs-1 docs-archive/
mv UI docs-archive/
mv trash docs-archive/
```

### 3. 後端環境設置

#### 建立虛擬環境
```bash
cd backend

# 建立虛擬環境
python3.9 -m venv venv

# 啟動虛擬環境
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

#### 安裝依賴
```bash
# 建立 requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
alembic==1.12.1
pymysql==1.1.0
cryptography==41.0.7
paramiko==3.3.1
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
APScheduler==3.10.4
redis==5.0.1
python-dotenv==1.0.0
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
httpx==0.25.2
EOF

# 安裝依賴
pip install -r requirements.txt
```

#### 建立基礎專案結構
```bash
mkdir -p app/{api,core,db,models,schemas,services,tasks,utils}
mkdir -p app/api/{api_v1,middleware}
mkdir -p app/api/api_v1/endpoints
mkdir -p tests/{unit,integration,fixtures}

# 建立基礎檔案
touch app/__init__.py
touch app/main.py
touch app/api/__init__.py
touch app/core/__init__.py
```

#### 設置環境變數
```bash
cat > .env.example << EOF
# 資料庫配置
DATABASE_URL=mysql+pymysql://cabie:Aa-12345@localhost:3306/cwatcher
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=cwatcher
DATABASE_USER=cabie
DATABASE_PASSWORD=Aa-12345

# 應用配置
APP_NAME=CWatcher
APP_VERSION=1.0.0
DEBUG=true
SECRET_KEY=your-secret-key-here

# Redis 配置（可選）
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379

# SSH 配置
SSH_TIMEOUT=30
SSH_CONNECTION_POOL_SIZE=10

# WebSocket 配置
WS_HEARTBEAT_INTERVAL=30

# 日誌配置
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF

cp .env.example .env
```

### 4. 前端環境設置

#### 建立 React 專案
```bash
cd ../frontend

# 使用 Vite 建立 React + TypeScript 專案
npm create vite@latest . -- --template react-ts

# 或使用 Create React App
# npx create-react-app . --template typescript
```

#### 安裝額外依賴
```bash
# 安裝 UI 和工具庫
npm install @tailwindcss/forms @tailwindcss/typography
npm install chart.js react-chartjs-2
npm install axios socket.io-client
npm install react-router-dom react-hook-form
npm install zustand # 或 @reduxjs/toolkit react-redux

# 安裝開發依賴
npm install -D @types/node
npm install -D eslint-config-prettier prettier
npm install -D @testing-library/react @testing-library/jest-dom
npm install -D @testing-library/user-event
npm install -D msw # Mock Service Worker
```

#### 設置 Tailwind CSS
```bash
# 安裝 Tailwind CSS
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# 配置 tailwind.config.js
cat > tailwind.config.js << EOF
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#0ea5e9',
          dark: '#0284c7',
        },
        secondary: '#10b981',
        accent: '#8b5cf6',
        dark: {
          bg: '#0f172a',
          card: '#1e293b',
          darker: '#020617',
        }
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
EOF
```

#### 設置環境變數
```bash
cat > .env.example << EOF
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_NAME=CWatcher
VITE_APP_VERSION=1.0.0
EOF

cp .env.example .env.local
```

### 5. 資料庫設置

#### MySQL 配置
```bash
# 啟動 MySQL 服務
sudo systemctl start mysql  # Linux
brew services start mysql   # macOS

# 連接到 MySQL
mysql -u root -p

# 建立資料庫和用戶
CREATE DATABASE cwatcher CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cabie'@'localhost' IDENTIFIED BY 'Aa-12345';
GRANT ALL PRIVILEGES ON cwatcher.* TO 'cabie'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### 資料庫初始化
```bash
cd ../database

# 建立資料庫腳本目錄
mkdir -p {migrations,seeds,schema,backup,scripts}

# 建立初始化腳本
cat > scripts/init.sql << EOF
-- 建立伺服器表
CREATE TABLE servers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    ssh_port INT DEFAULT 22,
    username VARCHAR(50) NOT NULL,
    password_encrypted TEXT,
    private_key_encrypted TEXT,
    status ENUM('online', 'offline', 'warning') DEFAULT 'offline',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen TIMESTAMP NULL,
    INDEX idx_ip_address (ip_address),
    INDEX idx_status (status)
);

-- 建立監控數據表
CREATE TABLE system_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    server_id INT NOT NULL,
    metric_type ENUM('cpu', 'memory', 'disk', 'network') NOT NULL,
    timestamp TIMESTAMP(3) NOT NULL,
    value_json JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    INDEX idx_server_metric_time (server_id, metric_type, timestamp),
    INDEX idx_timestamp (timestamp)
);

-- 建立系統資訊表
CREATE TABLE system_info (
    id INT PRIMARY KEY AUTO_INCREMENT,
    server_id INT NOT NULL,
    hostname VARCHAR(255),
    os_name VARCHAR(100),
    os_version VARCHAR(100),
    kernel_version VARCHAR(100),
    cpu_model VARCHAR(255),
    cpu_cores INT,
    cpu_threads INT,
    memory_total_gb DECIMAL(8,2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_server (server_id)
);
EOF

# 執行初始化
mysql -u cabie -p cwatcher < scripts/init.sql
```

### 6. Docker 環境設置（可選）

#### 建立 Docker Compose 配置
```bash
cd ..

cat > docker-compose.dev.yml << EOF
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: cwatcher_mysql_dev
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: cwatcher
      MYSQL_USER: cabie
      MYSQL_PASSWORD: Aa-12345
    ports:
      - "3306:3306"
    volumes:
      - mysql_dev_data:/var/lib/mysql
      - ./database/scripts:/docker-entrypoint-initdb.d
    command: --default-authentication-plugin=mysql_native_password

  redis:
    image: redis:7-alpine
    container_name: cwatcher_redis_dev
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data

volumes:
  mysql_dev_data:
  redis_dev_data:
EOF
```

#### 啟動開發服務
```bash
# 啟動資料庫服務
docker-compose -f docker-compose.dev.yml up -d mysql redis

# 檢查服務狀態
docker-compose -f docker-compose.dev.yml ps
```

### 7. 開發工具配置

#### VS Code 設置
```bash
mkdir .vscode

cat > .vscode/settings.json << EOF
{
    "python.defaultInterpreterPath": "./backend/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "typescript.preferences.importModuleSpecifier": "relative",
    "eslint.workingDirectories": ["frontend"],
    "prettier.configPath": "./frontend/.prettierrc"
}
EOF

cat > .vscode/extensions.json << EOF
{
    "recommendations": [
        "ms-python.python",
        "ms-python.black-formatter",
        "ms-vscode.vscode-typescript-next",
        "bradlc.vscode-tailwindcss",
        "esbenp.prettier-vscode",
        "ms-vscode.vscode-eslint"
    ]
}
EOF
```

#### 設置 pre-commit hooks
```bash
# 安裝 pre-commit
pip install pre-commit

cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        files: ^backend/

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        files: ^backend/

  - repo: local
    hooks:
      - id: frontend-lint
        name: Frontend ESLint
        entry: bash -c 'cd frontend && npm run lint'
        language: system
        files: ^frontend/.*\.(ts|tsx|js|jsx)$
EOF

# 安裝 hooks
pre-commit install
```

## 開發流程

### 1. 啟動開發環境

#### 後端開發伺服器
```bash
cd backend
source venv/bin/activate

# 啟動 FastAPI 開發伺服器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端開發伺服器
```bash
cd frontend

# 啟動 Vite 開發伺服器
npm run dev
```

### 2. 執行測試

#### 後端測試
```bash
cd backend

# 執行所有測試
python -m pytest

# 執行特定測試檔案
python -m pytest tests/unit/test_ssh_manager.py

# 測試覆蓋率報告
python -m pytest --cov=app --cov-report=html
```

#### 前端測試
```bash
cd frontend

# 執行單元測試
npm test

# 執行測試覆蓋率
npm run test:coverage

# 執行 E2E 測試
npm run test:e2e
```

### 3. 代碼格式化

#### 後端代碼格式化
```bash
cd backend

# 使用 Black 格式化
black app/ tests/

# 使用 isort 排序 imports
isort app/ tests/

# 使用 flake8 檢查代碼風格
flake8 app/ tests/
```

#### 前端代碼格式化
```bash
cd frontend

# 使用 Prettier 格式化
npm run format

# 使用 ESLint 檢查
npm run lint

# 自動修復 ESLint 問題
npm run lint:fix
```

## 常見問題解決

### 1. MySQL 連接問題
```bash
# 檢查 MySQL 服務狀態
sudo systemctl status mysql

# 重啟 MySQL 服務
sudo systemctl restart mysql

# 檢查連接配置
mysql -u cabie -p -e "SELECT 1"
```

### 2. Node.js 版本問題
```bash
# 檢查當前版本
node --version
npm --version

# 使用 nvm 切換版本
nvm use 18
nvm alias default 18
```

### 3. Python 虛擬環境問題
```bash
# 重建虛擬環境
rm -rf venv
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. 端口衝突問題
```bash
# 檢查端口占用
lsof -i :8000  # 檢查後端端口
lsof -i :3000  # 檢查前端端口

# 終止占用進程
kill -9 <PID>
```

## 開發最佳實踐

### 1. Git 工作流程
- 從 `develop` 分支建立功能分支
- 使用有意義的分支名稱：`feature/user-authentication`
- 提交前執行測試和代碼檢查
- 使用清晰的提交訊息

### 2. 測試驅動開發
- 先寫測試，後寫實現
- 保持高測試覆蓋率（>80%）
- 定期執行完整測試套件

### 3. 代碼審查
- 所有變更都需要 Code Review
- 檢查代碼風格和最佳實踐
- 確保測試覆蓋率達標

### 4. 性能監控
- 定期監控應用性能
- 優化資料庫查詢
- 監控記憶體使用情況

這個開發環境設置指南提供了完整的環境配置步驟，確保開發團隊能夠快速啟動並保持一致的開發環境。