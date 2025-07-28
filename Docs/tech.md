---
title: 技術架構
description: "定義專案的技術棧、架構設計與實現規範。"
inclusion: always
---

# CWatcher 技術架構設計

## 技術棧概覽

### 前端技術
- **框架**：React 18 + TypeScript
- **UI 框架**：Tailwind CSS 3.x
- **圖表庫**：Chart.js + react-chartjs-2
- **狀態管理**：Zustand / Redux Toolkit
- **HTTP 客戶端**：Axios
- **即時通訊**：Socket.io-client
- **表單管理**：React Hook Form
- **路由管理**：React Router v6
- **建構工具**：Vite / Create React App

### 後端技術
- **主框架**：Python 3.9+ + FastAPI
- **ASGI 伺服器**：Uvicorn
- **SSH 客戶端**：paramiko
- **資料庫 ORM**：SQLAlchemy 2.0
- **資料庫遷移**：Alembic
- **即時通訊**：WebSocket (FastAPI 內建)
- **任務調度**：APScheduler / Celery
- **快取**：Redis (可選)
- **數據驗證**：Pydantic v2

### 資料庫
- **主資料庫**：MySQL 8.0+
  - 帳號：cabie
  - 密碼：Aa-12345
- **資料庫設計**：
  - 伺服器配置表
  - 監控數據時序表
  - 用戶認證表
  - 系統設定表

### 系統監控
- **Linux 指令**：
  - CPU：`top`, `cat /proc/stat`, `cat /proc/cpuinfo`
  - 記憶體：`free`, `cat /proc/meminfo`
  - 磁碟：`df`, `iostat`, `cat /proc/diskstats`
  - 網路：`cat /proc/net/dev`, `ss`, `netstat`
- **系統檔案**：`/proc/*` 虛擬檔案系統
- **連接方式**：純 SSH 方式（無需安裝 agent）

## 系統架構設計

### 整體架構圖

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Nginx Proxy   │    │   Target Linux  │
│   (React App)   │    │   (SSL Term.)   │    │    Servers      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ HTTPS/WSS            │ HTTP/WS              │ SSH (22)
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   SSH Manager   │
│   (React +TS)   │◄──►│   (FastAPI)     │◄──►│   (paramiko)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │
                       ┌─────────────────┐
                       │   MySQL 8.0     │
                       │   Database      │
                       │   (cabie/Aa-)   │
                       └─────────────────┘
```

### 資料流架構

```
1. 資料收集：SSH → 系統指令 → 解析數據
2. 資料處理：標準化 → 驗證 → 計算衍生指標
3. 資料存儲：MySQL 時序表 → 索引優化
4. 即時推送：WebSocket → 前端即時更新
5. 歷史查詢：API 查詢 → 數據聚合 → 圖表展示
```

## 資料庫設計

### 核心資料表

#### servers 表（伺服器配置）
```sql
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
```

#### system_metrics 表（監控數據）
```sql
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
```

#### system_info 表（系統資訊）
```sql
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
```

### 資料庫優化策略

1. **索引優化**：
   - 按伺服器 ID + 時間範圍查詢優化
   - 支援分頁查詢的複合索引
   - 狀態查詢的單列索引

2. **分區策略**：
   - 按月分區 system_metrics 表
   - 自動清理超過 6 個月的歷史數據

3. **連接池配置**：
   - 最小連接：5
   - 最大連接：20
   - 連接超時：30秒

## API 設計規範

### RESTful API 設計

#### 伺服器管理 API
```
POST   /api/v1/servers           # 新增伺服器
GET    /api/v1/servers           # 獲取伺服器列表
GET    /api/v1/servers/{id}      # 獲取單個伺服器
PUT    /api/v1/servers/{id}      # 更新伺服器配置
DELETE /api/v1/servers/{id}      # 刪除伺服器
POST   /api/v1/servers/{id}/test # 測試連接
```

#### 監控數據 API
```
GET /api/v1/servers/{id}/metrics/current    # 即時數據
GET /api/v1/servers/{id}/metrics/history    # 歷史數據
GET /api/v1/servers/{id}/system-info        # 系統資訊
GET /api/v1/servers/{id}/status             # 連接狀態
```

### WebSocket API 設計

#### 連接與訂閱
```javascript
// 建立連接
const socket = io('wss://api.example.com');

// 訂閱伺服器數據
socket.emit('subscribe', { serverId: 1 });

// 接收即時數據
socket.on('metrics_update', (data) => {
    // 處理監控數據更新
});

// 接收狀態變化
socket.on('server_status_change', (data) => {
    // 處理伺服器狀態變化
});
```

### 數據格式規範

#### 監控數據格式
```json
{
    "timestamp": "2024-01-01T12:00:00.000Z",
    "server_id": 1,
    "metrics": {
        "cpu": {
            "usage_percent": 42.5,
            "cores": 4,
            "frequency_mhz": 2400,
            "load_avg": [1.52, 1.24, 0.92]
        },
        "memory": {
            "total_gb": 8.0,
            "used_gb": 5.4,
            "free_gb": 1.4,
            "cached_gb": 1.2,
            "usage_percent": 67.5
        },
        "disk": {
            "total_gb": 500,
            "used_gb": 380,
            "free_gb": 120,
            "usage_percent": 76,
            "io_read_mb_s": 12.4,
            "io_write_mb_s": 8.7
        },
        "network": {
            "download_mb_s": 2.4,
            "upload_mb_s": 0.8,
            "total_gb": 1.2,
            "interfaces": ["eth0", "lo"]
        }
    }
}
```

## 前端架構設計

### 目錄結構
```
src/
├── components/          # 共用組件
│   ├── common/         # 基礎組件
│   ├── charts/         # 圖表組件
│   ├── metrics/        # 指標組件
│   └── modals/         # 彈窗組件
├── pages/              # 頁面組件
│   ├── Dashboard/      # 儀表板
│   ├── ServerDetail/   # 伺服器詳情
│   └── Settings/       # 設定頁面
├── services/           # API 服務
│   ├── api.ts          # API 客戶端
│   ├── websocket.ts    # WebSocket 服務
│   └── auth.ts         # 認證服務
├── stores/             # 狀態管理
│   ├── serverStore.ts  # 伺服器狀態
│   ├── metricsStore.ts # 監控數據狀態
│   └── uiStore.ts      # UI 狀態
├── utils/              # 工具函數
│   ├── formatters.ts   # 數據格式化
│   ├── constants.ts    # 常數定義
│   └── helpers.ts      # 輔助函數
├── types/              # TypeScript 類型
│   ├── api.ts          # API 類型
│   ├── metrics.ts      # 監控數據類型
│   └── server.ts       # 伺服器類型
└── styles/             # 樣式文件
    ├── globals.css     # 全域樣式
    └── components.css  # 組件樣式
```

### 狀態管理設計
```typescript
// 使用 Zustand 的狀態管理示例
interface ServerStore {
    servers: Server[];
    selectedServer: Server | null;
    connectionStatus: Record<number, ConnectionStatus>;
    addServer: (server: CreateServerRequest) => Promise<void>;
    removeServer: (id: number) => Promise<void>;
    selectServer: (id: number) => void;
    updateConnectionStatus: (id: number, status: ConnectionStatus) => void;
}
```

## 後端架構設計

### 目錄結構
```
app/
├── api/                # API 路由
│   ├── v1/             # API v1 版本
│   │   ├── servers.py  # 伺服器管理
│   │   ├── metrics.py  # 監控數據
│   │   └── websocket.py # WebSocket 端點
│   └── dependencies.py # 依賴注入
├── core/               # 核心配置
│   ├── config.py       # 應用配置
│   ├── database.py     # 資料庫連接
│   └── security.py     # 安全配置
├── models/             # 資料庫模型
│   ├── server.py       # 伺服器模型
│   ├── metrics.py      # 監控數據模型
│   └── system_info.py  # 系統資訊模型
├── schemas/            # Pydantic 模型
│   ├── server.py       # 伺服器 schema
│   ├── metrics.py      # 監控數據 schema
│   └── responses.py    # 回應 schema
├── services/           # 業務邏輯
│   ├── ssh_manager.py  # SSH 連接管理
│   ├── metrics_collector.py # 數據收集
│   ├── data_processor.py # 數據處理
│   └── websocket_manager.py # WebSocket 管理
├── tasks/              # 背景任務
│   ├── monitoring.py   # 監控任務
│   └── cleanup.py      # 清理任務
└── utils/              # 工具函數
    ├── ssh_utils.py    # SSH 工具
    ├── encryption.py   # 加密工具
    └── formatters.py   # 格式化工具
```

### 監控任務設計
```python
# 使用 APScheduler 的定時任務
@scheduler.scheduled_job('interval', seconds=30)
async def collect_metrics():
    """每 30 秒收集一次監控數據"""
    active_servers = await get_active_servers()
    
    for server in active_servers:
        try:
            metrics = await collect_server_metrics(server)
            await save_metrics(server.id, metrics)
            await broadcast_metrics(server.id, metrics)
        except Exception as e:
            logger.error(f"Failed to collect metrics for {server.ip}: {e}")
            await update_server_status(server.id, 'offline')
```

## 安全性設計

### 資料傳輸安全
- **HTTPS/WSS**：所有通訊使用 TLS 1.3 加密
- **API 認證**：JWT Token 或 API Key 認證
- **CORS 設定**：限制允許的來源域名

### 憑證存儲安全
- **加密演算法**：AES-256-GCM
- **金鑰管理**：環境變數或密鑰管理服務
- **敏感數據**：資料庫加密存儲

### SSH 連接安全
- **金鑰認證**：優先使用 SSH 金鑰對認證
- **連接限制**：每台伺服器最多 3 個並發連接
- **超時設定**：連接超時 30 秒，操作超時 60 秒

## 性能優化策略

### 前端優化
- **代碼分割**：按路由和功能模組分割
- **快取策略**：API 回應快取、圖表數據快取
- **虛擬滾動**：大量伺服器列表使用虛擬滾動
- **圖表優化**：數據採樣、懶載入

### 後端優化
- **資料庫優化**：索引優化、查詢優化、連接池
- **快取層**：Redis 快取熱點數據
- **並發處理**：異步處理、協程優化
- **資源限制**：CPU 和記憶體使用監控

### 網路優化
- **資料壓縮**：啟用 gzip/brotli 壓縮
- **HTTP/2**：使用 HTTP/2 協定
- **CDN**：靜態資源 CDN 加速
- **WebSocket 優化**：消息批處理、心跳檢測

## 部署架構

### 容器化部署
```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://backend:8000

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql://cabie:Aa-12345@mysql:3306/cwatcher
    depends_on:
      - mysql

  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=rootpassword
      - MYSQL_DATABASE=cwatcher
      - MYSQL_USER=cabie
      - MYSQL_PASSWORD=Aa-12345
    volumes:
      - mysql_data:/var/lib/mysql

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - frontend
      - backend
```

### 系統需求
- **最低需求**：2 CPU 核心，4GB RAM，20GB 存儲
- **推薦配置**：4 CPU 核心，8GB RAM，100GB SSD
- **網路需求**：千兆網路，穩定的網際網路連接
- **作業系統**：Ubuntu 20.04+、CentOS 8+、Docker 支援環境