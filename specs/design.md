# CWatcher 技術設計文件

## 1. 系統架構設計

### 1.1 微服務架構概覽

```mermaid
graph TB
    subgraph "客戶端層"
        WB[Web Browser<br/>React + TypeScript]
        MB[Mobile Browser<br/>響應式設計]
    end
    
    subgraph "網關層"
        LB[Load Balancer<br/>Nginx]
        SSL[SSL Termination<br/>Let's Encrypt]
    end
    
    subgraph "應用層"
        API[API Gateway<br/>FastAPI]
        WS[WebSocket Service<br/>Socket.IO]
        AUTH[Authentication Service<br/>JWT]
    end
    
    subgraph "業務邏輯層"
        SM[SSH Manager<br/>paramiko]
        MC[Metrics Collector<br/>定時任務]
        DP[Data Processor<br/>數據處理]
        NM[Notification Manager<br/>警報系統]
    end
    
    subgraph "數據層"
        DB[(MySQL 8.0<br/>主資料庫)]
        CACHE[(Redis<br/>快取層)]
        FS[File Storage<br/>SSH金鑰存儲]
    end
    
    subgraph "目標系統"
        LS1[Linux Server 1<br/>Ubuntu/CentOS]
        LS2[Linux Server 2<br/>Debian/SUSE]
        LSN[Linux Server N<br/>其他發行版]
    end
    
    WB --> LB
    MB --> LB
    LB --> SSL
    SSL --> API
    SSL --> WS
    
    API --> AUTH
    API --> SM
    API --> MC
    API --> DP
    API --> NM
    
    WS --> MC
    WS --> DP
    
    SM --> DB
    MC --> DB
    MC --> CACHE
    DP --> DB
    DP --> CACHE
    AUTH --> DB
    NM --> DB
    
    SM -.SSH.-> LS1
    SM -.SSH.-> LS2
    SM -.SSH.-> LSN
    
    MC -.數據收集.-> SM
    DP -.數據處理.-> MC
    NM -.監控告警.-> DP
```

### 1.2 組件間通訊設計

#### 1.2.1 內部服務通訊
- **API Gateway** ↔ **業務服務**：直接函數調用（同進程）
- **WebSocket Service** ↔ **數據處理**：事件發布/訂閱模式
- **定時任務** ↔ **數據收集**：APScheduler 排程

#### 1.2.2 外部通訊協議
```yaml
前端 ← → 後端:
  - HTTP/HTTPS: RESTful API 調用
  - WebSocket/WSS: 即時數據推送
  - Content-Type: application/json

後端 ← → 目標伺服器:
  - Protocol: SSH (Port 22)
  - Authentication: 密鑰對 / 帳密認證
  - Connection: 連接池管理（最大3個並發）

後端 ← → 資料庫:
  - Protocol: MySQL Protocol
  - Connection Pool: SQLAlchemy 連接池
  - Security: TLS 加密連接
```

### 1.3 資料流設計

```mermaid
sequenceDiagram
    participant F as Frontend
    participant A as API Gateway
    participant S as SSH Manager
    participant D as Data Processor
    participant W as WebSocket
    participant DB as MySQL
    participant LS as Linux Server
    
    Note over F,LS: 即時監控資料流程
    
    loop 每30秒
        S->>LS: SSH連接執行監控指令
        LS-->>S: 返回系統指標原始數據
        S->>D: 傳送原始數據進行處理
        D->>D: 數據標準化與驗證
        D->>DB: 儲存處理後的監控數據
        D->>W: 推送即時數據到WebSocket
        W-->>F: 廣播數據更新到前端
        F->>F: 更新圖表與指標卡片
    end
    
    Note over F,LS: API查詢歷史數據流程
    
    F->>A: 請求歷史數據(時間範圍)
    A->>DB: 查詢時序數據表
    DB-->>A: 返回聚合後的歷史數據
    A-->>F: JSON格式回應
    F->>F: 渲染歷史圖表
```

### 1.4 快取策略

#### 1.4.1 多層快取架構
```yaml
快取層級:
  L1 - 前端快取:
    - 類型: 瀏覽器記憶體 + LocalStorage
    - 數據: 最近30分鐘監控數據、使用者偏好設定
    - TTL: 5分鐘
    
  L2 - API快取:
    - 類型: Redis 記憶體快取
    - 數據: 系統資訊、聚合統計數據
    - TTL: 15分鐘
    
  L3 - 數據庫快取:
    - 類型: MySQL Query Cache + InnoDB Buffer Pool
    - 數據: 熱點查詢結果
    - 大小: 1GB Buffer Pool
```

#### 1.4.2 快取失效策略
- **主動失效**：數據更新時清除相關快取
- **被動失效**：TTL 到期自動清除
- **版本控制**：快取鍵包含版本號避免髒數據

## 2. 資料庫設計

### 2.1 實體關係圖（ERD）

```mermaid
erDiagram
    SERVERS {
        int id PK
        varchar name
        varchar ip_address
        int ssh_port
        varchar username
        text password_encrypted
        text private_key_encrypted
        enum status
        timestamp created_at
        timestamp updated_at
        timestamp last_seen
    }
    
    SYSTEM_METRICS {
        bigint id PK
        int server_id FK
        enum metric_type
        timestamp timestamp
        json value_json
        timestamp created_at
    }
    
    SYSTEM_INFO {
        int id PK
        int server_id FK
        varchar hostname
        varchar os_name
        varchar os_version
        varchar kernel_version
        varchar cpu_model
        int cpu_cores
        int cpu_threads
        decimal memory_total_gb
        timestamp updated_at
    }
    
    ALERT_RULES {
        int id PK
        int server_id FK
        enum metric_type
        varchar rule_name
        json condition_json
        boolean enabled
        timestamp created_at
        timestamp updated_at
    }
    
    ALERT_HISTORY {
        bigint id PK
        int server_id FK
        int rule_id FK
        enum alert_level
        varchar message
        timestamp triggered_at
        timestamp resolved_at
        enum status
    }
    
    USERS {
        int id PK
        varchar username
        varchar email
        varchar password_hash
        varchar role
        timestamp created_at
        timestamp last_login
        boolean active
    }
    
    USER_SESSIONS {
        int id PK
        int user_id FK
        varchar session_token
        timestamp expires_at
        varchar ip_address
        varchar user_agent
        timestamp created_at
    }
    
    SERVERS ||--o{ SYSTEM_METRICS : collects
    SERVERS ||--|| SYSTEM_INFO : has
    SERVERS ||--o{ ALERT_RULES : monitors
    SERVERS ||--o{ ALERT_HISTORY : triggers
    USERS ||--o{ USER_SESSIONS : creates
    ALERT_RULES ||--o{ ALERT_HISTORY : generates
```

### 2.2 資料表結構詳細設計

#### 2.2.1 伺服器配置表（servers）
```sql
CREATE TABLE servers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL COMMENT '伺服器名稱',
    ip_address VARCHAR(45) NOT NULL COMMENT 'IP位址（支援IPv4/IPv6）',
    ssh_port INT DEFAULT 22 COMMENT 'SSH連接埠',
    username VARCHAR(50) NOT NULL COMMENT 'SSH登入用戶名',
    password_encrypted TEXT COMMENT 'AES-256-GCM加密密碼',
    private_key_encrypted TEXT COMMENT 'AES-256-GCM加密私鑰',
    status ENUM('online', 'offline', 'warning', 'unknown') DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen TIMESTAMP NULL COMMENT '最後連線時間',
    
    UNIQUE KEY uk_servers_ip_port (ip_address, ssh_port),
    INDEX idx_servers_status (status),
    INDEX idx_servers_last_seen (last_seen),
    INDEX idx_servers_created_at (created_at)
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### 2.2.2 監控數據表（system_metrics）
```sql
CREATE TABLE system_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    server_id INT NOT NULL,
    metric_type ENUM('cpu', 'memory', 'disk', 'network') NOT NULL,
    timestamp TIMESTAMP(3) NOT NULL COMMENT '數據收集時間（毫秒精度）',
    value_json JSON NOT NULL COMMENT 'JSON格式的指標數據',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY fk_metrics_server (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    INDEX idx_metrics_server_type_time (server_id, metric_type, timestamp),
    INDEX idx_metrics_timestamp (timestamp),
    INDEX idx_metrics_created_at (created_at)
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (UNIX_TIMESTAMP(timestamp)) (
    PARTITION p_202401 VALUES LESS THAN (UNIX_TIMESTAMP('2024-02-01')),
    PARTITION p_202402 VALUES LESS THAN (UNIX_TIMESTAMP('2024-03-01')),
    PARTITION p_202403 VALUES LESS THAN (UNIX_TIMESTAMP('2024-04-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

#### 2.2.3 系統資訊表（system_info）
```sql
CREATE TABLE system_info (
    id INT PRIMARY KEY AUTO_INCREMENT,
    server_id INT NOT NULL,
    hostname VARCHAR(255) COMMENT '主機名',
    os_name VARCHAR(100) COMMENT '作業系統名稱',
    os_version VARCHAR(100) COMMENT '作業系統版本',
    kernel_version VARCHAR(100) COMMENT '核心版本',
    cpu_model VARCHAR(255) COMMENT 'CPU型號',
    cpu_cores INT COMMENT 'CPU核心數',
    cpu_threads INT COMMENT 'CPU線程數',
    cpu_frequency_mhz INT COMMENT 'CPU頻率（MHz）',
    memory_total_gb DECIMAL(10,2) COMMENT '總記憶體（GB）',
    disk_total_gb DECIMAL(12,2) COMMENT '總磁碟空間（GB）',
    network_interfaces JSON COMMENT '網路介面資訊',
    uptime_seconds BIGINT COMMENT '系統執行時間（秒）',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY fk_sysinfo_server (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_sysinfo_server (server_id)
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### 2.2.4 警報規則表（alert_rules）
```sql
CREATE TABLE alert_rules (
    id INT PRIMARY KEY AUTO_INCREMENT,
    server_id INT NOT NULL,
    metric_type ENUM('cpu', 'memory', 'disk', 'network') NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    condition_json JSON NOT NULL COMMENT '警報條件配置',
    threshold_value DECIMAL(10,2) NOT NULL COMMENT '閾值',
    comparison_operator ENUM('>', '>=', '<', '<=', '=', '!=') NOT NULL,
    duration_minutes INT DEFAULT 3 COMMENT '持續時間（分鐘）',
    severity ENUM('info', 'warning', 'critical') DEFAULT 'warning',
    enabled BOOLEAN DEFAULT TRUE,
    notification_channels JSON COMMENT '通知管道配置',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY fk_alert_server (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    INDEX idx_alert_server_enabled (server_id, enabled),
    INDEX idx_alert_metric_type (metric_type)
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.3 索引策略

#### 2.3.1 查詢優化索引
```sql
-- 監控數據查詢優化（最重要）
ALTER TABLE system_metrics 
ADD INDEX idx_metrics_query_optimized (server_id, metric_type, timestamp DESC);

-- 時間範圍查詢優化
ALTER TABLE system_metrics 
ADD INDEX idx_metrics_time_range (timestamp, server_id);

-- 狀態查詢優化
ALTER TABLE servers 
ADD INDEX idx_servers_status_name (status, name);

-- 警報查詢優化
ALTER TABLE alert_history 
ADD INDEX idx_alert_recent (server_id, triggered_at DESC, status);
```

#### 2.3.2 複合索引設計原則
- **左前綴原則**：最常用的查詢欄位放在索引左側
- **選擇性原則**：選擇性高的欄位優先
- **排序優化**：包含 ORDER BY 欄位在索引中

### 2.4 分區策略

#### 2.4.1 時間分區（按月）
```sql
-- 動態新增月份分區的預儲程序
DELIMITER ;;
CREATE PROCEDURE AddMonthlyPartitions()
BEGIN
    DECLARE next_month_start DATE;
    DECLARE partition_name VARCHAR(20);
    
    SET next_month_start = DATE_ADD(LAST_DAY(CURDATE()), INTERVAL 1 DAY);
    SET partition_name = CONCAT('p_', DATE_FORMAT(next_month_start, '%Y%m'));
    
    SET @sql = CONCAT('ALTER TABLE system_metrics ADD PARTITION (PARTITION ', 
                     partition_name, ' VALUES LESS THAN (UNIX_TIMESTAMP(''', 
                     DATE_ADD(next_month_start, INTERVAL 1 MONTH), ''')))');
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
END;;
DELIMITER ;

-- 定期執行分區維護（通過事件調度器）
CREATE EVENT monthly_partition_maintenance
ON SCHEDULE EVERY 1 MONTH
STARTS '2024-01-01 02:00:00'
DO CALL AddMonthlyPartitions();
```

#### 2.4.2 分區管理策略
- **新增分區**：每月自動新增下個月的分區
- **刪除分區**：保留最近6個月數據，自動清理舊分區
- **分區查詢**：啟用分區裁剪優化查詢性能

### 2.5 備份與恢復策略

#### 2.5.1 備份頻率與保留
```yaml
備份類型:
  完整備份:
    頻率: 每週日晚上2點
    保留: 4週
    壓縮: gzip
    
  增量備份:
    頻率: 每日晚上1點
    保留: 7天
    類型: binlog增量
    
  時間點恢復:
    啟用: binlog
    保留: 7天
    格式: ROW
```

#### 2.5.2 備份腳本示例
```bash
#!/bin/bash
# 資料庫備份腳本

DB_NAME="cwatcher"
DB_USER="cabie"
DB_PASS="Aa-12345"
BACKUP_DIR="/var/backups/mysql"
DATE=$(date +%Y%m%d_%H%M%S)

# 完整備份
mysqldump --single-transaction --routines --triggers \
  -u${DB_USER} -p${DB_PASS} ${DB_NAME} | \
  gzip > ${BACKUP_DIR}/full_backup_${DATE}.sql.gz

# 清理舊備份（保留30天）
find ${BACKUP_DIR} -name "full_backup_*.sql.gz" -mtime +30 -delete
```

## 3. API 設計

### 3.1 RESTful API 規範

#### 3.1.1 API 版本控制
- **URL版本控制**：`/api/v1/`, `/api/v2/`
- **向後兼容**：維護至少2個主要版本
- **棄用政策**：提前6個月通知API棄用

#### 3.1.2 統一回應格式
```json
{
  "success": true,
  "data": {},
  "message": "操作成功",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "version": "v1.0.0",
  "errors": []
}
```

#### 3.1.3 錯誤處理規範
```json
{
  "success": false,
  "data": null,
  "message": "請求處理失敗",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "version": "v1.0.0",
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "field": "ip_address",
      "message": "IP位址格式不正確",
      "details": "期望IPv4或IPv6格式"
    }
  ]
}
```

### 3.2 伺服器管理 API

#### 3.2.1 端點定義
```yaml
POST /api/v1/servers:
  description: 新增伺服器配置
  request_body:
    name: string (required, 1-100字符)
    ip_address: string (required, IPv4/IPv6)
    ssh_port: integer (optional, 1-65535, default=22)
    username: string (required, 1-50字符)
    auth_type: enum (required, "password"|"key")
    password: string (conditional, auth_type=password)
    private_key: string (conditional, auth_type=key)
  responses:
    201: 創建成功
    400: 請求參數錯誤
    409: 伺服器已存在
    422: 連接測試失敗

GET /api/v1/servers:
  description: 獲取伺服器列表
  query_parameters:
    page: integer (optional, default=1)
    limit: integer (optional, 1-100, default=20)
    status: enum (optional, "online"|"offline"|"warning")
    search: string (optional, 搜尋名稱或IP)
  responses:
    200: 查詢成功
    400: 參數錯誤

GET /api/v1/servers/{id}:
  description: 獲取單個伺服器詳情
  path_parameters:
    id: integer (required, 伺服器ID)
  responses:
    200: 查詢成功
    404: 伺服器不存在

PUT /api/v1/servers/{id}:
  description: 更新伺服器配置
  path_parameters:
    id: integer (required, 伺服器ID)
  request_body: # 同POST，但所有欄位為optional
  responses:
    200: 更新成功
    400: 參數錯誤
    404: 伺服器不存在
    422: 連接測試失敗

DELETE /api/v1/servers/{id}:
  description: 刪除伺服器
  path_parameters:
    id: integer (required, 伺服器ID)
  responses:
    204: 刪除成功
    404: 伺服器不存在
    409: 伺服器正在監控中，無法刪除

POST /api/v1/servers/{id}/test:
  description: 測試伺服器連接
  path_parameters:
    id: integer (required, 伺服器ID)
  responses:
    200: 連接成功
    404: 伺服器不存在
    422: 連接失敗
```

#### 3.2.2 請求示例
```json
POST /api/v1/servers
{
  "name": "Web Server 01",
  "ip_address": "192.168.1.100",
  "ssh_port": 22,
  "username": "ubuntu",
  "auth_type": "key",
  "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
}
```

#### 3.2.3 回應示例
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Web Server 01",
    "ip_address": "192.168.1.100",
    "ssh_port": 22,
    "username": "ubuntu",
    "status": "online",
    "created_at": "2024-01-01T12:00:00.000Z",
    "updated_at": "2024-01-01T12:00:00.000Z",
    "last_seen": "2024-01-01T12:05:00.000Z"
  },
  "message": "伺服器新增成功",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "version": "v1.0.0"
}
```

### 3.3 監控數據 API

#### 3.3.1 即時數據端點
```yaml
GET /api/v1/servers/{id}/metrics/current:
  description: 獲取伺服器最新監控數據
  path_parameters:
    id: integer (required, 伺服器ID)
  query_parameters:
    metrics: array (optional, ["cpu","memory","disk","network"])
  responses:
    200: 查詢成功
    404: 伺服器不存在
    503: 伺服器離線
```

#### 3.3.2 歷史數據端點
```yaml
GET /api/v1/servers/{id}/metrics/history:
  description: 獲取歷史監控數據
  path_parameters:
    id: integer (required, 伺服器ID)
  query_parameters:
    metric_type: enum (required, "cpu"|"memory"|"disk"|"network")
    start_time: datetime (required, ISO8601格式)
    end_time: datetime (required, ISO8601格式)
    interval: enum (optional, "1m"|"5m"|"15m"|"1h"|"1d", default="5m")
    aggregation: enum (optional, "avg"|"max"|"min", default="avg")
  responses:
    200: 查詢成功
    400: 參數錯誤
    404: 伺服器不存在
```

#### 3.3.3 數據格式規範
```json
{
  "success": true,
  "data": {
    "server_id": 1,
    "timestamp": "2024-01-01T12:00:00.000Z",
    "metrics": {
      "cpu": {
        "usage_percent": 42.5,
        "cores": 4,
        "frequency_mhz": 2400,
        "load_avg": [1.52, 1.24, 0.92],
        "processes": 156,
        "context_switches": 12458
      },
      "memory": {
        "total_gb": 8.0,
        "used_gb": 5.4,
        "free_gb": 1.4,
        "cached_gb": 1.2,
        "buffers_gb": 0.3,
        "swap_total_gb": 2.0,
        "swap_used_gb": 0.1,
        "usage_percent": 67.5
      },
      "disk": {
        "filesystems": [
          {
            "mount": "/",
            "total_gb": 50,
            "used_gb": 38,
            "free_gb": 12,
            "usage_percent": 76
          }
        ],
        "io_stats": {
          "read_mb_s": 12.4,
          "write_mb_s": 8.7,
          "read_iops": 245,
          "write_iops": 167
        }
      },
      "network": {
        "interfaces": [
          {
            "name": "eth0",
            "rx_mb_s": 2.4,
            "tx_mb_s": 0.8,
            "rx_total_gb": 1.2,
            "tx_total_gb": 0.6,
            "status": "up"
          }
        ],
        "total_rx_mb_s": 2.4,
        "total_tx_mb_s": 0.8
      }
    }
  }
}
```

### 3.4 WebSocket 事件設計

#### 3.4.1 連接與認證
```javascript
// 客戶端連接
const socket = io('wss://api.example.com', {
  auth: {
    token: 'jwt_token_here'
  },
  transports: ['websocket']
});

// 伺服器端認證
socket.on('connect', async () => {
  const token = socket.handshake.auth.token;
  const user = await validateJWT(token);
  if (!user) {
    socket.disconnect();
    return;
  }
  socket.userId = user.id;
});
```

#### 3.4.2 訂閱管理
```javascript
// 訂閱特定伺服器
socket.emit('subscribe', {
  type: 'server_metrics',
  server_id: 1,
  metrics: ['cpu', 'memory'] // 可選，預設全部
});

// 取消訂閱
socket.emit('unsubscribe', {
  type: 'server_metrics',
  server_id: 1
});

// 訂閱所有伺服器狀態
socket.emit('subscribe', {
  type: 'server_status'
});
```

#### 3.4.3 事件定義
```yaml
metrics_update:
  description: 監控數據更新
  payload:
    server_id: integer
    timestamp: datetime
    metrics: object
  frequency: 每30秒

server_status_change:
  description: 伺服器狀態變化
  payload:
    server_id: integer
    old_status: enum
    new_status: enum
    timestamp: datetime
  frequency: 狀態變化時

alert_triggered:
  description: 警報觸發
  payload:
    alert_id: integer
    server_id: integer
    rule_name: string
    severity: enum
    message: string
    timestamp: datetime
  frequency: 警報觸發時

connection_error:
  description: 連接錯誤
  payload:
    server_id: integer
    error_type: string
    error_message: string
    timestamp: datetime
  frequency: 錯誤發生時
```

### 3.5 認證與授權機制

#### 3.5.1 JWT Token 設計
```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "user_id": 1,
    "username": "admin",
    "role": "administrator",
    "permissions": ["read", "write", "admin"],
    "iat": 1704067200,
    "exp": 1704153600,
    "iss": "cwatcher-api",
    "aud": "cwatcher-frontend"
  }
}
```

#### 3.5.2 權限控制矩陣
```yaml
角色權限:
  administrator:
    - 所有操作權限
    - 用戶管理
    - 系統設定
    
  operator:
    - 伺服器管理（增刪改查）
    - 監控數據查看
    - 警報設定
    
  viewer:
    - 監控數據查看（唯讀）
    - 報告匯出
    
  guest:
    - 有限的監控數據查看
    - 無操作權限
```

#### 3.5.3 API 安全措施
```yaml
安全防護:
  Rate Limiting:
    - 一般API: 100次/分鐘/IP
    - 登入API: 5次/分鐘/IP
    - WebSocket: 1000則訊息/分鐘/連接
    
  Input Validation:
    - 所有輸入參數驗證
    - SQL注入防護
    - XSS防護
    
  CORS設定:
    - 允許的來源域名
    - 預檢請求處理
    - 憑證包含設定
    
  HTTPS強制:
    - 所有API僅支援HTTPS
    - HSTS頭部設定
    - 安全Cookie設定
```

## 4. 前端架構設計

### 4.1 React 組件架構

#### 4.1.1 組件層次結構
```mermaid
graph TD
    App[App<br/>應用根組件]
    
    App --> Router[Router<br/>路由管理]
    App --> ErrorBoundary[ErrorBoundary<br/>錯誤邊界]
    App --> Toast[ToastProvider<br/>通知系統]
    
    Router --> Layout[MainLayout<br/>主版面]
    Layout --> Header[Header<br/>頁首導航]
    Layout --> Sidebar[Sidebar<br/>側邊選單]
    Layout --> Content[Content<br/>主內容區]
    
    Content --> Dashboard[Dashboard<br/>儀表板頁面]
    Content --> ServerDetail[ServerDetail<br/>伺服器詳情]
    Content --> Settings[Settings<br/>設定頁面]
    
    Dashboard --> ServerList[ServerList<br/>伺服器列表]
    Dashboard --> MetricsGrid[MetricsGrid<br/>指標網格]
    
    ServerList --> ServerCard[ServerCard<br/>伺服器卡片]
    MetricsGrid --> MetricCard[MetricCard<br/>指標卡片]
    MetricCard --> MetricChart[MetricChart<br/>指標圖表]
    
    ServerDetail --> SystemInfo[SystemInfo<br/>系統資訊]
    ServerDetail --> HistoryCharts[HistoryCharts<br/>歷史圖表]
    
    HistoryCharts --> LineChart[LineChart<br/>折線圖]
    HistoryCharts --> AreaChart[AreaChart<br/>面積圖]
```

#### 4.1.2 組件設計原則
```yaml
設計原則:
  Single Responsibility:
    - 每個組件職責單一
    - 易於測試和維護
    
  Composition over Inheritance:
    - 使用組合而非繼承
    - 高度可重用性
    
  Props Interface:
    - 明確的props類型定義
    - 預設值設定
    - 文件說明
    
  State Management:
    - 局部狀態使用useState
    - 全域狀態使用Zustand
    - 衍生狀態使用useMemo
```

#### 4.1.3 核心組件設計

##### MetricCard 組件
```typescript
interface MetricCardProps {
  title: string;
  value: number;
  unit: string;
  trend?: 'up' | 'down' | 'stable';
  threshold?: {
    warning: number;
    critical: number;
  };
  size?: 'small' | 'medium' | 'large';
  loading?: boolean;
  error?: string;
  onClick?: () => void;
  className?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  trend,
  threshold,
  size = 'medium',
  loading = false,
  error,
  onClick,
  className
}) => {
  const status = useMemo(() => {
    if (error) return 'error';
    if (loading) return 'loading';
    if (!threshold) return 'normal';
    
    if (value >= threshold.critical) return 'critical';
    if (value >= threshold.warning) return 'warning';
    return 'normal';
  }, [value, threshold, loading, error]);
  
  return (
    <Card 
      className={cn(
        'metric-card',
        `metric-card--${size}`,
        `metric-card--${status}`,
        className
      )}
      onClick={onClick}
    >
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {trend && <TrendIndicator trend={trend} />}
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-20" />
        ) : error ? (
          <ErrorMessage message={error} />
        ) : (
          <div className="metric-value">
            <span className="value">{formatNumber(value)}</span>
            <span className="unit">{unit}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
```

##### MetricChart 組件
```typescript
interface MetricChartProps {
  data: MetricDataPoint[];
  type: 'line' | 'area' | 'bar';
  timeRange: TimeRange;
  theme: 'light' | 'dark';
  height?: number;
  loading?: boolean;
  error?: string;
  onTimeRangeChange?: (range: TimeRange) => void;
}

const MetricChart: React.FC<MetricChartProps> = ({
  data,
  type,
  timeRange,
  theme,
  height = 300,
  loading,
  error,
  onTimeRangeChange
}) => {
  const chartData = useMemo(() => 
    processChartData(data, timeRange), 
    [data, timeRange]
  );
  
  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        type: 'time' as const,
        time: {
          displayFormats: getTimeDisplayFormats(timeRange)
        }
      },
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value: number) => formatYAxisValue(value)
        }
      }
    },
    plugins: {
      legend: {
        display: false
      },
      tooltip: {
        callbacks: {
          label: (context: any) => formatTooltipLabel(context)
        }
      }
    }
  }), [timeRange]);
  
  if (loading) {
    return <ChartSkeleton height={height} />;
  }
  
  if (error) {
    return <ChartError message={error} height={height} />;
  }
  
  return (
    <div className="metric-chart" style={{ height }}>
      <ChartHeader 
        timeRange={timeRange}
        onTimeRangeChange={onTimeRangeChange}
      />
      <Chart 
        type={type}
        data={chartData}
        options={chartOptions}
      />
    </div>
  );
};
```

### 4.2 狀態管理設計

#### 4.2.1 Zustand Store 架構
```typescript
// 伺服器狀態管理
interface ServerStore {
  // 狀態
  servers: Server[];
  selectedServerId: number | null;
  connectionStatus: Record<number, ConnectionStatus>;
  loading: boolean;
  error: string | null;
  
  // 操作
  fetchServers: () => Promise<void>;
  addServer: (server: CreateServerRequest) => Promise<void>;
  updateServer: (id: number, server: UpdateServerRequest) => Promise<void>;
  removeServer: (id: number) => Promise<void>;
  selectServer: (id: number) => void;
  testConnection: (id: number) => Promise<boolean>;
  updateConnectionStatus: (id: number, status: ConnectionStatus) => void;
  
  // 清理
  clearError: () => void;
  reset: () => void;
}

const useServerStore = create<ServerStore>()((set, get) => ({
  // 初始狀態
  servers: [],
  selectedServerId: null,
  connectionStatus: {},
  loading: false,
  error: null,
  
  // 實現操作
  fetchServers: async () => {
    set({ loading: true, error: null });
    try {
      const servers = await serverService.getServers();
      set({ servers, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },
  
  addServer: async (serverData) => {
    set({ loading: true, error: null });
    try {
      const server = await serverService.createServer(serverData);
      set(state => ({
        servers: [...state.servers, server],
        loading: false
      }));
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },
  
  // ... 其他操作實現
}));
```

#### 4.2.2 監控數據狀態管理
```typescript
interface MetricsStore {
  // 即時數據
  currentMetrics: Record<number, ServerMetrics>;
  lastUpdated: Record<number, Date>;
  
  // 歷史數據
  historicalData: Record<string, HistoricalMetrics>;
  timeRange: TimeRange;
  
  // WebSocket連接
  connected: boolean;
  subscriptions: Set<number>;
  
  // 操作
  updateCurrentMetrics: (serverId: number, metrics: ServerMetrics) => void;
  setTimeRange: (range: TimeRange) => void;
  fetchHistoricalData: (serverId: number, metricType: MetricType, range: TimeRange) => Promise<void>;
  subscribe: (serverId: number) => void;
  unsubscribe: (serverId: number) => void;
  setConnectionStatus: (connected: boolean) => void;
}

const useMetricsStore = create<MetricsStore>()((set, get) => ({
  currentMetrics: {},
  lastUpdated: {},
  historicalData: {},
  timeRange: TimeRange.HOUR_1,
  connected: false,
  subscriptions: new Set(),
  
  updateCurrentMetrics: (serverId, metrics) => {
    set(state => ({
      currentMetrics: {
        ...state.currentMetrics,
        [serverId]: metrics
      },
      lastUpdated: {
        ...state.lastUpdated,
        [serverId]: new Date()
      }
    }));
  },
  
  fetchHistoricalData: async (serverId, metricType, range) => {
    const key = `${serverId}-${metricType}-${range}`;
    try {
      const data = await metricsService.getHistoricalData(serverId, metricType, range);
      set(state => ({
        historicalData: {
          ...state.historicalData,
          [key]: data
        }
      }));
    } catch (error) {
      console.error('Failed to fetch historical data:', error);
    }
  },
  
  // ... 其他操作
}));
```

### 4.3 路由設計

#### 4.3.1 路由結構
```typescript
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    errorElement: <ErrorPage />,
    children: [
      {
        index: true,
        element: <Dashboard />
      },
      {
        path: 'servers',
        children: [
          {
            index: true,
            element: <ServerList />
          },
          {
            path: ':id',
            element: <ServerDetail />,
            loader: serverDetailLoader
          },
          {
            path: 'add',
            element: <AddServer />
          }
        ]
      },
      {
        path: 'alerts',
        children: [
          {
            index: true,
            element: <AlertList />
          },
          {
            path: ':id',
            element: <AlertDetail />
          }
        ]
      },
      {
        path: 'settings',
        element: <Settings />,
        children: [
          {
            index: true,
            element: <GeneralSettings />
          },
          {
            path: 'users',
            element: <UserManagement />
          },
          {
            path: 'notifications',
            element: <NotificationSettings />
          }
        ]
      }
    ]
  },
  {
    path: '/login',
    element: <LoginPage />
  },
  {
    path: '/auth/callback',
    element: <AuthCallback />
  }
]);

// 資料載入器
async function serverDetailLoader({ params }: LoaderFunctionArgs) {
  const serverId = Number(params.id);
  const [server, systemInfo] = await Promise.all([
    serverService.getServer(serverId),
    serverService.getSystemInfo(serverId)
  ]);
  return { server, systemInfo };
}
```

#### 4.3.2 導航守衛
```typescript
// 認證守衛
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  
  if (loading) {
    return <LoadingSpinner />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  
  return <>{children}</>;
};

// 權限守衛
const RoleGuard: React.FC<{
  children: React.ReactNode;
  requiredRole: UserRole;
}> = ({ children, requiredRole }) => {
  const { user } = useAuth();
  
  if (!hasRequiredRole(user?.role, requiredRole)) {
    return <Forbidden />;
  }
  
  return <>{children}</>;
};
```

### 4.4 即時數據處理

#### 4.4.1 WebSocket Hook
```typescript
interface UseWebSocketOptions {
  url: string;
  token?: string;
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
}

const useWebSocket = (options: UseWebSocketOptions) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectAttemptsRef = useRef(0);
  
  const connect = useCallback(() => {
    if (socket?.connected) return;
    
    const newSocket = io(options.url, {
      auth: {
        token: options.token
      },
      transports: ['websocket']
    });
    
    newSocket.on('connect', () => {
      setConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0;
    });
    
    newSocket.on('disconnect', () => {
      setConnected(false);
    });
    
    newSocket.on('connect_error', (err) => {
      setError(err.message);
      setConnected(false);
      
      // 自動重連
      if (reconnectAttemptsRef.current < (options.reconnectAttempts ?? 5)) {
        setTimeout(() => {
          reconnectAttemptsRef.current++;
          connect();
        }, options.reconnectDelay ?? 3000);
      }
    });
    
    setSocket(newSocket);
  }, [options.url, options.token]);
  
  const disconnect = useCallback(() => {
    socket?.disconnect();
    setSocket(null);
    setConnected(false);
  }, [socket]);
  
  const emit = useCallback((event: string, data: any) => {
    if (socket?.connected) {
      socket.emit(event, data);
    }
  }, [socket]);
  
  const on = useCallback((event: string, handler: (...args: any[]) => void) => {
    socket?.on(event, handler);
    return () => socket?.off(event, handler);
  }, [socket]);
  
  useEffect(() => {
    if (options.autoConnect !== false) {
      connect();
    }
    
    return () => disconnect();
  }, [connect, disconnect, options.autoConnect]);
  
  return {
    socket,
    connected,
    error,
    connect,
    disconnect,
    emit,
    on
  };
};
```

#### 4.4.2 即時數據管理
```typescript
const useRealTimeMetrics = () => {
  const { updateCurrentMetrics, subscriptions } = useMetricsStore();
  const { emit, on, connected } = useWebSocket({
    url: process.env.REACT_APP_WS_URL!,
    token: useAuthStore.getState().token,
    autoConnect: true
  });
  
  // 處理監控數據更新
  useEffect(() => {
    return on('metrics_update', (data: MetricsUpdateEvent) => {
      updateCurrentMetrics(data.server_id, data.metrics);
    });
  }, [on, updateCurrentMetrics]);
  
  // 處理伺服器狀態變化
  useEffect(() => {
    return on('server_status_change', (data: StatusChangeEvent) => {
      useServerStore.getState().updateConnectionStatus(
        data.server_id, 
        data.new_status
      );
    });
  }, [on]);
  
  // 處理警報觸發
  useEffect(() => {
    return on('alert_triggered', (data: AlertTriggeredEvent) => {
      useAlertStore.getState().addAlert(data);
      // 顯示通知
      toast.warning(`${data.rule_name}: ${data.message}`);
    });
  }, [on]);
  
  // 訂閱管理
  const subscribe = useCallback((serverId: number) => {
    if (connected) {
      emit('subscribe', {
        type: 'server_metrics',
        server_id: serverId
      });
    }
  }, [emit, connected]);
  
  const unsubscribe = useCallback((serverId: number) => {
    if (connected) {
      emit('unsubscribe', {
        type: 'server_metrics',
        server_id: serverId
      });
    }
  }, [emit, connected]);
  
  // 重新訂閱所有已訂閱的伺服器
  useEffect(() => {
    if (connected && subscriptions.size > 0) {
      subscriptions.forEach(serverId => {
        subscribe(serverId);
      });
    }
  }, [connected, subscriptions, subscribe]);
  
  return {
    connected,
    subscribe,
    unsubscribe
  };
};
```

## 5. 安全設計

### 5.1 SSH 金鑰管理

#### 5.1.1 金鑰加密存儲
```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class SSHKeyManager:
    def __init__(self, master_key: str):
        self.master_key = master_key.encode()
        
    def _get_cipher(self, salt: bytes) -> Fernet:
        """生成加密器"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        return Fernet(key)
    
    def encrypt_private_key(self, private_key: str) -> dict:
        """加密私鑰"""
        salt = os.urandom(16)
        cipher = self._get_cipher(salt)
        encrypted_key = cipher.encrypt(private_key.encode())
        
        return {
            'encrypted_data': base64.b64encode(encrypted_key).decode(),
            'salt': base64.b64encode(salt).decode(),
            'algorithm': 'AES-256-GCM',
            'iterations': 100000
        }
    
    def decrypt_private_key(self, encrypted_data: dict) -> str:
        """解密私鑰"""
        salt = base64.b64decode(encrypted_data['salt'])
        encrypted_key = base64.b64decode(encrypted_data['encrypted_data'])
        
        cipher = self._get_cipher(salt)
        private_key = cipher.decrypt(encrypted_key)
        
        return private_key.decode()
    
    def encrypt_password(self, password: str) -> dict:
        """加密密碼（使用相同的方法）"""
        return self.encrypt_private_key(password)
    
    def decrypt_password(self, encrypted_data: dict) -> str:
        """解密密碼"""
        return self.decrypt_private_key(encrypted_data)
```

#### 5.1.2 SSH 連接安全配置
```python
import paramiko
from typing import Optional, Dict, Any
import socket
import threading
import time

class SecureSSHManager:
    def __init__(self, key_manager: SSHKeyManager):
        self.key_manager = key_manager
        self.connections: Dict[int, paramiko.SSHClient] = {}
        self.connection_locks: Dict[int, threading.Lock] = {}
        self.max_connections_per_server = 3
        self.connection_timeout = 30
        self.operation_timeout = 60
        
    def create_ssh_client(self) -> paramiko.SSHClient:
        """創建安全的SSH客戶端"""
        client = paramiko.SSHClient()
        
        # 安全配置
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        
        return client
        
    def connect_with_key(self, server_config: dict) -> paramiko.SSHClient:
        """使用私鑰連接"""
        client = self.create_ssh_client()
        
        # 解密私鑰
        encrypted_key = server_config['private_key_encrypted']
        private_key_str = self.key_manager.decrypt_private_key(encrypted_key)
        
        # 載入私鑰
        try:
            private_key = paramiko.RSAKey.from_private_key(
                io.StringIO(private_key_str)
            )
        except paramiko.PasswordRequiredException:
            raise ValueError("私鑰需要密碼，但未提供")
        except Exception as e:
            raise ValueError(f"無效的私鑰格式: {e}")
        
        # 建立連接
        client.connect(
            hostname=server_config['ip_address'],
            port=server_config['ssh_port'],
            username=server_config['username'],
            pkey=private_key,
            timeout=self.connection_timeout,
            auth_timeout=self.connection_timeout,
            look_for_keys=False,
            allow_agent=False
        )
        
        return client
    
    def connect_with_password(self, server_config: dict) -> paramiko.SSHClient:
        """使用密碼連接"""
        client = self.create_ssh_client()
        
        # 解密密碼
        encrypted_password = server_config['password_encrypted']
        password = self.key_manager.decrypt_password(encrypted_password)
        
        # 建立連接
        client.connect(
            hostname=server_config['ip_address'],
            port=server_config['ssh_port'],
            username=server_config['username'],
            password=password,
            timeout=self.connection_timeout,
            auth_timeout=self.connection_timeout,
            look_for_keys=False,
            allow_agent=False
        )
        
        return client
    
    def get_connection(self, server_id: int, server_config: dict) -> paramiko.SSHClient:
        """獲取安全的SSH連接"""
        # 檢查並發連接限制
        if server_id not in self.connection_locks:
            self.connection_locks[server_id] = threading.Lock()
            
        with self.connection_locks[server_id]:
            # 檢查現有連接
            if server_id in self.connections:
                client = self.connections[server_id]
                if client.get_transport() and client.get_transport().is_active():
                    return client
                else:
                    # 清理失效連接
                    self.connections.pop(server_id, None)
            
            # 建立新連接
            try:
                if server_config.get('private_key_encrypted'):
                    client = self.connect_with_key(server_config)
                elif server_config.get('password_encrypted'):
                    client = self.connect_with_password(server_config)
                else:
                    raise ValueError("缺少認證憑證")
                
                self.connections[server_id] = client
                return client
                
            except Exception as e:
                raise ConnectionError(f"SSH連接失敗: {e}")
    
    def execute_command(self, server_id: int, server_config: dict, command: str) -> tuple:
        """安全執行命令"""
        client = self.get_connection(server_id, server_config)
        
        try:
            stdin, stdout, stderr = client.exec_command(
                command,
                timeout=self.operation_timeout
            )
            
            # 讀取輸出
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            return stdout_data, stderr_data, exit_code
            
        except socket.timeout:
            raise TimeoutError(f"命令執行超時: {command}")
        except Exception as e:
            raise RuntimeError(f"命令執行失敗: {e}")
    
    def close_connection(self, server_id: int):
        """關閉SSH連接"""
        if server_id in self.connections:
            try:
                self.connections[server_id].close()
            except:
                pass
            finally:
                self.connections.pop(server_id, None)
    
    def close_all_connections(self):
        """關閉所有SSH連接"""
        for server_id in list(self.connections.keys()):
            self.close_connection(server_id)
```

### 5.2 資料加密策略

#### 5.2.1 資料庫加密配置
```yaml
# MySQL 加密配置
[mysqld]
# 啟用資料加密
innodb_encrypt_tables = ON
innodb_encrypt_log = ON
innodb_encrypt_temp_tables = ON

# SSL/TLS 配置
ssl-ca = /etc/mysql/ssl/ca-cert.pem
ssl-cert = /etc/mysql/ssl/server-cert.pem
ssl-key = /etc/mysql/ssl/server-key.pem
require_secure_transport = ON

# 密碼驗證
validate_password.policy = STRONG
validate_password.length = 12
validate_password.mixed_case_count = 2
validate_password.number_count = 2
validate_password.special_char_count = 2
```

#### 5.2.2 API 資料加密
```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import os
import base64

class DataEncryption:
    def __init__(self, encryption_key: bytes):
        self.key = encryption_key
        
    def encrypt_sensitive_data(self, data: str) -> dict:
        """加密敏感數據"""
        # 生成隨機IV
        iv = os.urandom(16)
        
        # 建立加密器
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        
        # 填充數據
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode()) + padder.finalize()
        
        # 加密
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        return {
            'data': base64.b64encode(encrypted_data).decode(),
            'iv': base64.b64encode(iv).decode(),
            'algorithm': 'AES-256-CBC'
        }
    
    def decrypt_sensitive_data(self, encrypted_data: dict) -> str:
        """解密敏感數據"""
        data = base64.b64decode(encrypted_data['data'])
        iv = base64.b64decode(encrypted_data['iv'])
        
        # 建立解密器
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        
        # 解密
        padded_data = decryptor.update(data) + decryptor.finalize()
        
        # 移除填充
        unpadder = padding.PKCS7(128).unpadder()
        original_data = unpadder.update(padded_data) + unpadder.finalize()
        
        return original_data.decode()
```

### 5.3 存取控制設計

#### 5.3.1 RBAC 權限模型
```python
from enum import Enum
from typing import List, Set
from dataclasses import dataclass

class Permission(Enum):
    # 伺服器管理
    SERVER_READ = "server:read"
    SERVER_WRITE = "server:write"
    SERVER_DELETE = "server:delete"
    
    # 監控數據
    METRICS_READ = "metrics:read"
    METRICS_EXPORT = "metrics:export"
    
    # 警報管理
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_DELETE = "alert:delete"
    
    # 用戶管理
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # 系統管理
    SYSTEM_CONFIG = "system:config"
    SYSTEM_BACKUP = "system:backup"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]
    description: str

# 預定義角色
ROLES = {
    "administrator": Role(
        name="administrator",
        permissions=set(Permission),  # 所有權限
        description="系統管理員"
    ),
    "operator": Role(
        name="operator",
        permissions={
            Permission.SERVER_READ,
            Permission.SERVER_WRITE,
            Permission.METRICS_READ,
            Permission.METRICS_EXPORT,
            Permission.ALERT_READ,
            Permission.ALERT_WRITE
        },
        description="運維人員"
    ),
    "viewer": Role(
        name="viewer",
        permissions={
            Permission.SERVER_READ,
            Permission.METRICS_READ,
            Permission.METRICS_EXPORT,
            Permission.ALERT_READ
        },
        description="只讀用戶"
    ),
    "guest": Role(
        name="guest",
        permissions={
            Permission.SERVER_READ,
            Permission.METRICS_READ
        },
        description="訪客用戶"
    )
}

class PermissionChecker:
    def __init__(self, user_role: str):
        self.role = ROLES.get(user_role)
        if not self.role:
            raise ValueError(f"未知角色: {user_role}")
    
    def has_permission(self, permission: Permission) -> bool:
        """檢查是否有特定權限"""
        return permission in self.role.permissions
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """檢查是否有任意一個權限"""
        return any(p in self.role.permissions for p in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """檢查是否有所有權限"""
        return all(p in self.role.permissions for p in permissions)
    
    def require_permission(self, permission: Permission):
        """權限檢查裝飾器"""
        if not self.has_permission(permission):
            raise PermissionError(f"缺少權限: {permission.value}")
```

#### 5.3.2 API 權限中介軟體
```python
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def require_permission(permission: Permission):
    """權限檢查裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 從請求中獲取用戶資訊
            current_user = get_current_user()
            
            # 檢查權限
            checker = PermissionChecker(current_user.role)
            if not checker.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少權限: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """獲取當前用戶"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑證"
            )
        
        # 從資料庫獲取用戶資訊
        user = await get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶不存在"
            )
        
        return user
        
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑證"
        )

# 使用示例
@app.post("/api/v1/servers")
@require_permission(Permission.SERVER_WRITE)
async def create_server(server_data: CreateServerRequest):
    # 創建伺服器的邏輯
    pass

@app.delete("/api/v1/servers/{server_id}")
@require_permission(Permission.SERVER_DELETE)
async def delete_server(server_id: int):
    # 刪除伺服器的邏輯
    pass
```

### 5.4 安全稽核

#### 5.4.1 操作日誌記錄
```python
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    request_data = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    session_id = Column(String(255), nullable=True)

class SecurityAuditor:
    def __init__(self, db_session):
        self.db = db_session
        self.logger = logging.getLogger("security.audit")
        
    def log_action(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: str = "",
        user_agent: Optional[str] = None,
        request_data: Optional[Dict[Any, Any]] = None,
        response_status: Optional[int] = None,
        session_id: Optional[str] = None
    ):
        """記錄安全相關操作"""
        
        # 過濾敏感數據
        filtered_data = self._filter_sensitive_data(request_data) if request_data else None
        
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_data=filtered_data,
            response_status=response_status,
            session_id=session_id
        )
        
        try:
            self.db.add(audit_log)
            self.db.commit()
            
            # 同時記錄到日誌檔案
            self.logger.info(
                f"AUDIT: {action} on {resource_type}:{resource_id} "
                f"by {username}({user_id}) from {ip_address}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to log audit entry: {e}")
            self.db.rollback()
    
    def _filter_sensitive_data(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """過濾敏感數據"""
        sensitive_fields = {
            'password', 'private_key', 'secret', 'token', 
            'api_key', 'credential', 'auth'
        }
        
        filtered = {}
        for key, value in data.items():
            if any(field in str(key).lower() for field in sensitive_fields):
                filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value
                
        return filtered
    
    def log_login_attempt(self, username: str, ip_address: str, success: bool, user_agent: str = ""):
        """記錄登入嘗試"""
        action = "LOGIN_SUCCESS" if success else "LOGIN_FAILED"
        self.log_action(
            action=action,
            resource_type="authentication",
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            response_status=200 if success else 401
        )
    
    def log_permission_denied(self, user_id: int, username: str, action: str, resource: str, ip_address: str):
        """記錄權限拒絕"""
        self.log_action(
            action="PERMISSION_DENIED",
            resource_type=resource,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            request_data={"attempted_action": action},
            response_status=403
        )
    
    def log_data_access(self, user_id: int, username: str, resource_type: str, resource_id: str, ip_address: str):
        """記錄數據訪問"""
        self.log_action(
            action="DATA_ACCESS",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            response_status=200
        )
```

#### 5.4.2 安全監控與告警
```python
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

class SecurityMonitor:
    def __init__(self, db_session, alert_service):
        self.db = db_session
        self.alert_service = alert_service
        self.failed_login_threshold = 5  # 5次失敗登入
        self.time_window = timedelta(minutes=15)  # 15分鐘時間窗口
        
    async def monitor_failed_logins(self):
        """監控失敗登入嘗試"""
        cutoff_time = datetime.utcnow() - self.time_window
        
        # 查詢最近失敗的登入
        failed_logins = self.db.query(AuditLog).filter(
            AuditLog.action == "LOGIN_FAILED",
            AuditLog.timestamp >= cutoff_time
        ).all()
        
        # 按IP地址分組統計
        ip_counts = defaultdict(list)
        for login in failed_logins:
            ip_counts[login.ip_address].append(login)
        
        # 檢查是否超過閾值
        for ip_address, attempts in ip_counts.items():
            if len(attempts) >= self.failed_login_threshold:
                await self._trigger_security_alert(
                    "BRUTE_FORCE_ATTACK",
                    f"IP {ip_address} 在 {self.time_window.total_seconds()/60} 分鐘內嘗試登入失敗 {len(attempts)} 次",
                    {
                        "ip_address": ip_address,
                        "attempt_count": len(attempts),
                        "usernames": list(set(a.username for a in attempts))
                    }
                )
    
    async def monitor_permission_violations(self):
        """監控權限違規"""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        violations = self.db.query(AuditLog).filter(
            AuditLog.action == "PERMISSION_DENIED",
            AuditLog.timestamp >= cutoff_time
        ).all()
        
        # 按用戶分組
        user_violations = defaultdict(list)
        for violation in violations:
            user_violations[violation.user_id].append(violation)
        
        # 檢查異常權限嘗試
        for user_id, attempts in user_violations.items():
            if len(attempts) >= 3:  # 1小時內3次權限拒絕
                await self._trigger_security_alert(
                    "PERMISSION_VIOLATION",
                    f"用戶 {attempts[0].username} 在1小時內被拒絕權限 {len(attempts)} 次",
                    {
                        "user_id": user_id,
                        "username": attempts[0].username,
                        "violation_count": len(attempts),
                        "attempted_actions": [a.request_data.get("attempted_action") for a in attempts]
                    }
                )
    
    async def monitor_data_access_patterns(self):
        """監控異常數據訪問模式"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # 查詢大量數據訪問
        data_access = self.db.query(AuditLog).filter(
            AuditLog.action == "DATA_ACCESS",
            AuditLog.timestamp >= cutoff_time
        ).all()
        
        # 分析訪問模式
        user_access = defaultdict(list)
        for access in data_access:
            user_access[access.user_id].append(access)
        
        for user_id, accesses in user_access.items():
            # 檢查是否有異常大量訪問
            if len(accesses) > 1000:  # 24小時內超過1000次訪問
                await self._trigger_security_alert(
                    "EXCESSIVE_DATA_ACCESS",
                    f"用戶 {accesses[0].username} 在24小時內訪問數據 {len(accesses)} 次",
                    {
                        "user_id": user_id,
                        "username": accesses[0].username,
                        "access_count": len(accesses),
                        "resource_types": list(set(a.resource_type for a in accesses))
                    }
                )
    
    async def _trigger_security_alert(self, alert_type: str, message: str, details: dict):
        """觸發安全告警"""
        await self.alert_service.send_security_alert({
            "type": alert_type,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "high"
        })
        
        # 記錄安全事件
        self.db.add(AuditLog(
            action="SECURITY_ALERT",
            resource_type="security",
            username="system",
            request_data={
                "alert_type": alert_type,
                "message": message,
                "details": details
            }
        ))
        self.db.commit()
```

## 6. 效能設計

### 6.1 負載平衡策略

#### 6.1.1 Nginx 負載平衡配置
```nginx
# /etc/nginx/nginx.conf

upstream backend_api {
    # 負載平衡算法：least_conn 最少連接數
    least_conn;
    
    # 後端服務器配置
    server 127.0.0.1:8001 weight=3 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 weight=3 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8003 weight=2 max_fails=3 fail_timeout=30s backup;
    
    # 健康檢查
    keepalive 32;
    keepalive_requests 1000;
    keepalive_timeout 60s;
}

upstream websocket_servers {
    # WebSocket 負載平衡（IP Hash 保持會話親和性）
    ip_hash;
    
    server 127.0.0.1:9001 weight=1;
    server 127.0.0.1:9002 weight=1;
    server 127.0.0.1:9003 weight=1;
}

server {
    listen 443 ssl http2;
    server_name cwatcher.example.com;
    
    # SSL 配置
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    
    # 安全頭部
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # 壓縮配置
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # 靜態檔案快取
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }
    
    # API 請求代理
    location /api/ {
        proxy_pass http://backend_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # 超時設定
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 緩衝設定
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # 限流
        limit_req zone=api burst=20 nodelay;
    }
    
    # WebSocket 代理
    location /socket.io/ {
        proxy_pass http://websocket_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 特殊設定
        proxy_redirect off;
        proxy_buffering off;
        proxy_cache off;
        
        # 長連接支持
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
    
    # 前端應用
    location / {
        try_files $uri $uri/ /index.html;
        
        # 安全設定
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
}

# 限流配置
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    
    # 限制同時連接數
    limit_conn_zone $binary_remote_addr zone=addr:10m;
    limit_conn addr 10;
}
```

#### 6.1.2 應用層負載分散
```python
# 後端服務負載分散配置
import asyncio
import aioredis
from typing import List, Dict, Optional
import hashlib
import time

class LoadBalancer:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url)
        self.servers: List[Dict] = []
        self.health_check_interval = 30  # 30秒健康檢查
        
    async def register_server(self, server_id: str, host: str, port: int, weight: int = 1):
        """註冊服務器實例"""
        server_info = {
            'id': server_id,
            'host': host,
            'port': port,
            'weight': weight,
            'healthy': True,
            'last_check': time.time(),
            'connections': 0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0
        }
        
        await self.redis.hset(
            f"server:{server_id}",
            mapping=server_info
        )
        
        # 設置過期時間（避免殭屍服務器）
        await self.redis.expire(f"server:{server_id}", 120)
        
    async def get_available_servers(self) -> List[Dict]:
        """獲取可用服務器列表"""
        server_keys = await self.redis.keys("server:*")
        servers = []
        
        for key in server_keys:
            server_data = await self.redis.hgetall(key)
            if server_data and server_data.get('healthy') == 'True':
                servers.append({
                    'id': server_data['id'],
                    'host': server_data['host'],
                    'port': int(server_data['port']),
                    'weight': int(server_data['weight']),
                    'connections': int(server_data['connections']),
                    'cpu_usage': float(server_data['cpu_usage']),
                    'memory_usage': float(server_data['memory_usage'])
                })
        
        return servers
    
    async def select_server(self, client_id: Optional[str] = None) -> Optional[Dict]:
        """選擇最佳服務器"""
        servers = await self.get_available_servers()
        if not servers:
            return None
        
        # 如果有客戶端ID，使用一致性哈希保持會話親和性
        if client_id:
            return self._consistent_hash_select(servers, client_id)
        
        # 否則使用加權最少連接算法
        return self._weighted_least_connections_select(servers)
    
    def _consistent_hash_select(self, servers: List[Dict], client_id: str) -> Dict:
        """一致性哈希選擇"""
        hash_value = int(hashlib.md5(client_id.encode()).hexdigest(), 16)
        selected_index = hash_value % len(servers)
        return servers[selected_index]
    
    def _weighted_least_connections_select(self, servers: List[Dict]) -> Dict:
        """加權最少連接選擇"""
        best_score = float('inf')
        best_server = None
        
        for server in servers:
            # 計算負載分數（考慮連接數、CPU、記憶體）
            connection_score = server['connections'] / server['weight']
            cpu_score = server['cpu_usage'] * 0.3
            memory_score = server['memory_usage'] * 0.2
            
            total_score = connection_score + cpu_score + memory_score
            
            if total_score < best_score:
                best_score = total_score
                best_server = server
        
        return best_server
    
    async def update_server_metrics(self, server_id: str, metrics: Dict):
        """更新服務器指標"""
        await self.redis.hset(
            f"server:{server_id}",
            mapping={
                'cpu_usage': metrics['cpu_usage'],
                'memory_usage': metrics['memory_usage'],
                'connections': metrics['connections'],
                'last_check': time.time()
            }
        )
    
    async def health_check_loop(self):
        """健康檢查循環"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                print(f"Health check error: {e}")
                await asyncio.sleep(5)
    
    async def _perform_health_checks(self):
        """執行健康檢查"""
        server_keys = await self.redis.keys("server:*")
        
        for key in server_keys:
            server_data = await self.redis.hgetall(key)
            if not server_data:
                continue
            
            server_id = server_data['id']
            host = server_data['host']
            port = int(server_data['port'])
            
            # 檢查服務器健康狀態
            is_healthy = await self._check_server_health(host, port)
            
            await self.redis.hset(
                key,
                mapping={
                    'healthy': str(is_healthy),
                    'last_check': time.time()
                }
            )
    
    async def _check_server_health(self, host: str, port: int) -> bool:
        """檢查單個服務器健康狀態"""
        try:
            # 簡單的TCP連接檢查
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
```

### 6.2 快取分層設計

#### 6.2.1 Redis 快取配置
```yaml
# redis.conf 優化配置

# 記憶體設定
maxmemory 2gb
maxmemory-policy allkeys-lru

# 持久化設定（監控數據可以接受一定程度的數據丟失）
save 900 1
save 300 10
save 60 10000

# AOF持久化（可選）
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes

# 網路設定
tcp-keepalive 300
timeout 300

# 效能調優
lazy-free-lazy-eviction yes
lazy-free-lazy-expire yes
lazy-free-lazy-server-del yes

# 客戶端連接
maxclients 10000
```

#### 6.2.2 多層快取實現
```python
import asyncio
import aioredis
import json
import time
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CacheConfig:
    ttl: int  # 過期時間（秒）
    max_size: int  # 最大條目數
    compression: bool = False  # 是否壓縮

class MultiLevelCache:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url)
        self.local_cache: Dict[str, Dict] = {}
        self.cache_configs = {
            'metrics_current': CacheConfig(ttl=30, max_size=1000),
            'metrics_history': CacheConfig(ttl=300, max_size=500),
            'server_info': CacheConfig(ttl=900, max_size=200),
            'system_stats': CacheConfig(ttl=60, max_size=100)
        }
    
    async def get(self, key: str, cache_type: str = 'default') -> Optional[Any]:
        """多層快取獲取"""
        # L1: 本地記憶體快取
        local_data = self._get_from_local(key, cache_type)
        if local_data is not None:
            return local_data
        
        # L2: Redis 快取
        redis_data = await self._get_from_redis(key)
        if redis_data is not None:
            # 回寫到本地快取
            self._set_to_local(key, redis_data, cache_type)
            return redis_data
        
        return None
    
    async def set(self, key: str, value: Any, cache_type: str = 'default'):
        """多層快取設置"""
        # 設置到本地快取
        self._set_to_local(key, value, cache_type)
        
        # 設置到Redis
        await self._set_to_redis(key, value, cache_type)
    
    async def delete(self, key: str):
        """刪除快取項目"""
        # 從本地快取刪除
        if key in self.local_cache:
            del self.local_cache[key]
        
        # 從Redis刪除
        await self.redis.delete(key)
    
    async def clear_pattern(self, pattern: str):
        """清除符合模式的快取"""
        # 清除Redis中的匹配項
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
        
        # 清除本地快取中的匹配項
        to_delete = [k for k in self.local_cache.keys() if self._match_pattern(k, pattern)]
        for key in to_delete:
            del self.local_cache[key]
    
    def _get_from_local(self, key: str, cache_type: str) -> Optional[Any]:
        """從本地快取獲取"""
        if key not in self.local_cache:
            return None
        
        item = self.local_cache[key]
        config = self.cache_configs.get(cache_type, self.cache_configs['metrics_current'])
        
        # 檢查過期時間
        if time.time() - item['timestamp'] > config.ttl:
            del self.local_cache[key]
            return None
        
        return item['data']
    
    def _set_to_local(self, key: str, value: Any, cache_type: str):
        """設置到本地快取"""
        config = self.cache_configs.get(cache_type, self.cache_configs['metrics_current'])
        
        # 檢查快取大小限制
        if len(self.local_cache) >= config.max_size:
            self._evict_local_cache(cache_type)
        
        self.local_cache[key] = {
            'data': value,
            'timestamp': time.time(),
            'cache_type': cache_type
        }
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """從Redis獲取"""
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Redis get error: {e}")
        return None
    
    async def _set_to_redis(self, key: str, value: Any, cache_type: str):
        """設置到Redis"""
        try:
            config = self.cache_configs.get(cache_type, self.cache_configs['metrics_current'])
            serialized_data = json.dumps(value, default=str)
            await self.redis.setex(key, config.ttl, serialized_data)
        except Exception as e:
            print(f"Redis set error: {e}")
    
    def _evict_local_cache(self, cache_type: str):
        """LRU 驅逐本地快取"""
        # 找到相同類型的最舊項目
        same_type_items = [
            (k, v) for k, v in self.local_cache.items() 
            if v.get('cache_type') == cache_type
        ]
        
        if same_type_items:
            # 按時間戳排序，刪除最舊的
            oldest_key = min(same_type_items, key=lambda x: x[1]['timestamp'])[0]
            del self.local_cache[oldest_key]
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """簡單的模式匹配"""
        if '*' in pattern:
            prefix = pattern.split('*')[0]
            return key.startswith(prefix)
        return key == pattern

# 快取服務封裝
class CacheService:
    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
    
    async def get_current_metrics(self, server_id: int) -> Optional[Dict]:
        """獲取當前監控數據"""
        key = f"metrics:current:{server_id}"
        return await self.cache.get(key, 'metrics_current')
    
    async def set_current_metrics(self, server_id: int, metrics: Dict):
        """設置當前監控數據"""
        key = f"metrics:current:{server_id}"
        await self.cache.set(key, metrics, 'metrics_current')
    
    async def get_historical_metrics(self, server_id: int, metric_type: str, timerange: str) -> Optional[List]:
        """獲取歷史監控數據"""
        key = f"metrics:history:{server_id}:{metric_type}:{timerange}"
        return await self.cache.get(key, 'metrics_history')
    
    async def set_historical_metrics(self, server_id: int, metric_type: str, timerange: str, data: List):
        """設置歷史監控數據"""
        key = f"metrics:history:{server_id}:{metric_type}:{timerange}"
        await self.cache.set(key, data, 'metrics_history')
    
    async def get_server_info(self, server_id: int) -> Optional[Dict]:
        """獲取伺服器資訊"""
        key = f"server:info:{server_id}"
        return await self.cache.get(key, 'server_info')
    
    async def set_server_info(self, server_id: int, info: Dict):
        """設置伺服器資訊"""
        key = f"server:info:{server_id}"
        await self.cache.set(key, info, 'server_info')
    
    async def invalidate_server_cache(self, server_id: int):
        """使伺服器相關快取失效"""
        patterns = [
            f"metrics:current:{server_id}",
            f"metrics:history:{server_id}:*",
            f"server:info:{server_id}"
        ]
        
        for pattern in patterns:
            await self.cache.clear_pattern(pattern)
```

### 6.3 資料庫優化

#### 6.3.1 MySQL 性能調優
```sql
-- MySQL 性能優化配置

-- InnoDB 設定
SET GLOBAL innodb_buffer_pool_size = 2147483648;  -- 2GB
SET GLOBAL innodb_log_file_size = 268435456;      -- 256MB
SET GLOBAL innodb_log_buffer_size = 16777216;     -- 16MB
SET GLOBAL innodb_flush_log_at_trx_commit = 2;    -- 性能優化
SET GLOBAL innodb_io_capacity = 2000;             -- SSD優化

-- 查詢快取
SET GLOBAL query_cache_size = 134217728;          -- 128MB
SET GLOBAL query_cache_type = ON;

-- 連接設定
SET GLOBAL max_connections = 500;
SET GLOBAL thread_cache_size = 50;
SET GLOBAL table_open_cache = 4000;

-- 臨時表設定
SET GLOBAL tmp_table_size = 67108864;             -- 64MB
SET GLOBAL max_heap_table_size = 67108864;        -- 64MB

-- 排序和分組優化
SET GLOBAL sort_buffer_size = 2097152;            -- 2MB
SET GLOBAL read_buffer_size = 131072;             -- 128KB
SET GLOBAL read_rnd_buffer_size = 262144;         -- 256KB
```

#### 6.3.2 查詢優化策略
```sql
-- 監控數據查詢優化

-- 1. 創建覆蓋索引（包含所有查詢欄位）
CREATE INDEX idx_metrics_coverage ON system_metrics 
(server_id, metric_type, timestamp, value_json(100));

-- 2. 分區裁剪優化
EXPLAIN PARTITIONS 
SELECT * FROM system_metrics 
WHERE server_id = 1 
  AND metric_type = 'cpu' 
  AND timestamp >= '2024-01-01 00:00:00'
  AND timestamp < '2024-01-02 00:00:00';

-- 3. 聚合查詢優化
SELECT 
    server_id,
    metric_type,
    DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour_bucket,
    AVG(JSON_EXTRACT(value_json, '$.usage_percent')) as avg_usage,
    MAX(JSON_EXTRACT(value_json, '$.usage_percent')) as max_usage,
    MIN(JSON_EXTRACT(value_json, '$.usage_percent')) as min_usage,
    COUNT(*) as sample_count
FROM system_metrics
WHERE server_id = 1 
  AND metric_type = 'cpu'
  AND timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY server_id, metric_type, hour_bucket
ORDER BY hour_bucket;

-- 4. 創建物化視圖（每小時聚合）
CREATE TABLE metrics_hourly_summary AS
SELECT 
    server_id,
    metric_type,
    DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour_timestamp,
    AVG(JSON_EXTRACT(value_json, '$.usage_percent')) as avg_value,
    MAX(JSON_EXTRACT(value_json, '$.usage_percent')) as max_value,
    MIN(JSON_EXTRACT(value_json, '$.usage_percent')) as min_value,
    COUNT(*) as sample_count,
    STD(JSON_EXTRACT(value_json, '$.usage_percent')) as std_value
FROM system_metrics
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY server_id, metric_type, hour_timestamp;

-- 為物化視圖創建索引
CREATE INDEX idx_hourly_summary ON metrics_hourly_summary 
(server_id, metric_type, hour_timestamp);

-- 5. 定期更新物化視圖的存儲過程
DELIMITER ;;
CREATE PROCEDURE UpdateHourlySummary()
BEGIN
    DECLARE last_update DATETIME;
    
    -- 獲取最後更新時間
    SELECT MAX(hour_timestamp) INTO last_update 
    FROM metrics_hourly_summary;
    
    -- 如果沒有數據，設置為24小時前
    IF last_update IS NULL THEN
        SET last_update = DATE_SUB(NOW(), INTERVAL 24 HOUR);
    END IF;
    
    -- 插入新的小時聚合數據
    INSERT INTO metrics_hourly_summary
    SELECT 
        server_id,
        metric_type,
        DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour_timestamp,
        AVG(JSON_EXTRACT(value_json, '$.usage_percent')) as avg_value,
        MAX(JSON_EXTRACT(value_json, '$.usage_percent')) as max_value,
        MIN(JSON_EXTRACT(value_json, '$.usage_percent')) as min_value,
        COUNT(*) as sample_count,
        STD(JSON_EXTRACT(value_json, '$.usage_percent')) as std_value
    FROM system_metrics
    WHERE timestamp > last_update
      AND timestamp <= DATE_FORMAT(NOW(), '%Y-%m-%d %H:00:00')
    GROUP BY server_id, metric_type, hour_timestamp
    ON DUPLICATE KEY UPDATE
        avg_value = VALUES(avg_value),
        max_value = VALUES(max_value),
        min_value = VALUES(min_value),
        sample_count = VALUES(sample_count),
        std_value = VALUES(std_value);
        
END;;
DELIMITER ;

-- 創建事件調度器定期執行
CREATE EVENT hourly_summary_update
ON SCHEDULE EVERY 1 HOUR
STARTS NOW()
DO CALL UpdateHourlySummary();
```

#### 6.3.3 連接池優化
```python
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import asyncio

class OptimizedDatabaseManager:
    def __init__(self, database_url: str):
        # 連接池配置
        self.engine = create_engine(
            database_url,
            # 連接池設定
            poolclass=QueuePool,
            pool_size=20,              # 連接池大小
            max_overflow=30,           # 最大溢出連接
            pool_timeout=30,           # 獲取連接超時
            pool_recycle=3600,         # 連接回收時間（1小時）
            pool_pre_ping=True,        # 連接預檢查
            
            # MySQL 特定優化
            connect_args={
                "charset": "utf8mb4",
                "autocommit": False,
                "connect_timeout": 10,
                "read_timeout": 30,
                "write_timeout": 30,
                
                # MySQL 連接優化
                "sql_mode": "STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO",
                "isolation_level": "READ_COMMITTED",
                
                # 批量插入優化
                "bulk_insert_buffer_size": "16M",
                "max_allowed_packet": "64M"
            },
            
            # 引擎選項
            echo=False,                # 生產環境關閉SQL日誌
            echo_pool=False,
            future=True
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def get_session(self):
        """獲取資料庫會話"""
        session = self.SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    async def batch_insert_metrics(self, metrics_data: List[Dict]):
        """批量插入監控數據"""
        if not metrics_data:
            return
        
        session = self.SessionLocal()
        try:
            # 使用 bulk_insert_mappings 進行批量插入
            session.bulk_insert_mappings(SystemMetrics, metrics_data)
            session.commit()
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    async def execute_batch_update(self, updates: List[Dict]):
        """批量更新操作"""
        if not updates:
            return
            
        session = self.SessionLocal()
        try:
            # 使用 bulk_update_mappings 進行批量更新
            session.bulk_update_mappings(SystemMetrics, updates)
            session.commit()
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_connection_pool_status(self) -> Dict:
        """獲取連接池狀態"""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    
    async def optimize_tables(self):
        """定期優化表"""
        session = self.SessionLocal()
        try:
            # 分析表統計信息
            session.execute("ANALYZE TABLE system_metrics")
            session.execute("ANALYZE TABLE servers")
            session.execute("ANALYZE TABLE alert_rules")
            
            # 優化表（僅在低峰期執行）
            session.execute("OPTIMIZE TABLE metrics_hourly_summary")
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
```

### 6.4 前端效能優化

#### 6.4.1 代碼分割與懶載入
```typescript
// 路由層級的代碼分割
import { lazy, Suspense } from 'react';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';

// 懶載入頁面組件
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const ServerDetail = lazy(() => import('@/pages/ServerDetail'));
const Settings = lazy(() => import('@/pages/Settings'));

// 組件層級的懶載入
const MetricChart = lazy(() => import('@/components/charts/MetricChart'));
const AlertModal = lazy(() => import('@/components/modals/AlertModal'));

// 路由配置
export const routes = [
  {
    path: '/',
    element: (
      <Suspense fallback={<LoadingSpinner />}>
        <Dashboard />
      </Suspense>
    )
  },
  {
    path: '/servers/:id',
    element: (
      <Suspense fallback={<LoadingSpinner />}>
        <ServerDetail />
      </Suspense>
    )
  }
];

// 動態導入組件Hook
const useLazyComponent = <T extends React.ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>
) => {
  const [Component, setComponent] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const loadComponent = useCallback(async () => {
    if (Component) return Component;
    
    setLoading(true);
    setError(null);
    
    try {
      const module = await importFunc();
      setComponent(() => module.default);
      return module.default;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load component');
      return null;
    } finally {
      setLoading(false);
    }
  }, [importFunc, Component]);
  
  return { Component, loading, error, loadComponent };
};
```

#### 6.4.2 虛擬滾動優化
```typescript
import { FixedSizeList as List } from 'react-window';
import { memo, useMemo } from 'react';

interface VirtualServerListProps {
  servers: Server[];
  height: number;
  onServerSelect: (server: Server) => void;
}

// 服務器項目組件（記憶化）
const ServerItem = memo<{
  index: number;
  style: React.CSSProperties;
  data: {
    servers: Server[];
    onSelect: (server: Server) => void;
  };
}>(({ index, style, data }) => {
  const server = data.servers[index];
  
  return (
    <div style={style} className="server-item">
      <ServerCard 
        server={server}
        onClick={() => data.onSelect(server)}
      />
    </div>
  );
});

// 虛擬滾動服務器列表
const VirtualServerList: React.FC<VirtualServerListProps> = ({
  servers,
  height,
  onServerSelect
}) => {
  const itemData = useMemo(() => ({
    servers,
    onSelect: onServerSelect
  }), [servers, onServerSelect]);
  
  return (
    <List
      height={height}
      itemCount={servers.length}
      itemSize={120} // 每個項目高度
      itemData={itemData}
      overscanCount={5} // 預渲染項目數
    >
      {ServerItem}
    </List>
  );
};

// 大數據量圖表優化
const OptimizedChart: React.FC<{
  data: MetricDataPoint[];
  maxDataPoints?: number;
}> = ({ data, maxDataPoints = 1000 }) => {
  // 數據採樣優化
  const sampledData = useMemo(() => {
    if (data.length <= maxDataPoints) return data;
    
    const step = Math.ceil(data.length / maxDataPoints);
    return data.filter((_, index) => index % step === 0);
  }, [data, maxDataPoints]);
  
  // 使用 Web Worker 進行數據處理
  const processedData = useMemo(() => {
    return sampledData.map(point => ({
      ...point,
      formattedValue: formatValue(point.value),
      timestamp: new Date(point.timestamp)
    }));
  }, [sampledData]);
  
  return (
    <Chart 
      data={processedData}
      options={{
        animation: {
          duration: data.length > 100 ? 0 : 300 // 大數據時禁用動畫
        },
        plugins: {
          decimation: {
            enabled: true,
            algorithm: 'lttb', // Largest-Triangle-Three-Buckets
            samples: maxDataPoints
          }
        }
      }}
    />
  );
};
```

#### 6.4.3 記憶體管理與清理
```typescript
// 記憶體泄漏防護Hook
const useMemoryCleanup = () => {
  const timeoutsRef = useRef<Set<NodeJS.Timeout>>(new Set());
  const intervalsRef = useRef<Set<NodeJS.Timeout>>(new Set());
  const listenersRef = useRef<Map<string, () => void>>(new Map());
  
  const setTimeout = useCallback((callback: () => void, delay: number) => {
    const id = globalThis.setTimeout(callback, delay);
    timeoutsRef.current.add(id);
    return id;
  }, []);
  
  const setInterval = useCallback((callback: () => void, delay: number) => {
    const id = globalThis.setInterval(callback, delay);
    intervalsRef.current.add(id);
    return id;
  }, []);
  
  const addEventListener = useCallback((
    element: EventTarget,
    event: string,
    handler: () => void
  ) => {
    element.addEventListener(event, handler);
    const key = `${element.constructor.name}_${event}`;
    listenersRef.current.set(key, () => {
      element.removeEventListener(event, handler);
    });
  }, []);
  
  useEffect(() => {
    return () => {
      // 清理計時器
      timeoutsRef.current.forEach(clearTimeout);
      intervalsRef.current.forEach(clearInterval);
      
      // 清理事件監聽器
      listenersRef.current.forEach(cleanup => cleanup());
      
      // 清空引用
      timeoutsRef.current.clear();
      intervalsRef.current.clear();
      listenersRef.current.clear();
    };
  }, []);
  
  return {
    setTimeout,
    setInterval,
    addEventListener
  };
};

// 大型對象的記憶體優化
const useMemoryEfficientStore = <T>() => {
  const [data, setData] = useState<Map<string, T>>(new Map());
  const maxSize = 1000; // 最大緩存項目數
  
  const set = useCallback((key: string, value: T) => {
    setData(prev => {
      const newMap = new Map(prev);
      
      // LRU 策略：如果超過最大大小，刪除最舊的項目
      if (newMap.size >= maxSize && !newMap.has(key)) {
        const firstKey = newMap.keys().next().value;
        newMap.delete(firstKey);
      }
      
      newMap.set(key, value);
      return newMap;
    });
  }, [maxSize]);
  
  const get = useCallback((key: string): T | undefined => {
    return data.get(key);
  }, [data]);
  
  const clear = useCallback(() => {
    setData(new Map());
  }, []);
  
  const size = data.size;
  
  return { set, get, clear, size };
};

// WebSocket 連接清理
const useWebSocketCleanup = (url: string) => {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }
    
    const socket = new WebSocket(url);
    socketRef.current = socket;
    
    socket.onclose = () => {
      // 清理並重連
      socketRef.current = null;
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    };
    
    return socket;
  }, [url]);
  
  useEffect(() => {
    return () => {
      // 清理 WebSocket 連接
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      
      // 清理重連計時器
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, []);
  
  return connect;
};
```

#### 6.4.4 Bundle 優化配置
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: 'dist/stats.html',
      open: true
    })
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // 第三方庫分離
          vendor: ['react', 'react-dom'],
          charts: ['chart.js', 'react-chartjs-2'],
          ui: ['@headlessui/react', '@heroicons/react'],
          utils: ['date-fns', 'lodash-es'],
          
          // 按功能分離
          dashboard: ['./src/pages/Dashboard'],
          serverDetail: ['./src/pages/ServerDetail'],
          settings: ['./src/pages/Settings']
        },
        // 文件名哈希化
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.');
          const extType = info[info.length - 1];
          if (/\.(png|jpe?g|gif|svg)$/.test(assetInfo.name)) {
            return `images/[name]-[hash].${extType}`;
          }
          if (/\.(css)$/.test(assetInfo.name)) {
            return `css/[name]-[hash].${extType}`;
          }
          return `assets/[name]-[hash].${extType}`;
        }
      }
    },
    // 壓縮配置
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,  // 移除 console.log
        drop_debugger: true, // 移除 debugger
        pure_funcs: ['console.log', 'console.info'] // 移除指定函數
      }
    },
    // 警告閾值
    chunkSizeWarningLimit: 1000
  },
  // 開發服務器優化
  server: {
    hmr: {
      overlay: false
    }
  },
  // 優化依賴
  optimizeDeps: {
    include: ['chart.js', 'date-fns']
  }
});
```

---

**設計總結：**

本技術設計文件涵蓋了 CWatcher 系統的完整技術架構，包括：

1. **系統架構**：微服務架構、組件通訊、資料流設計和快取策略
2. **資料庫設計**：完整的 ERD、資料表結構、索引策略和分區管理
3. **API 設計**：RESTful API 規範、WebSocket 事件系統和安全認證
4. **前端架構**：React 組件設計、狀態管理、路由配置和即時數據處理
5. **安全設計**：SSH 金鑰管理、資料加密、存取控制和安全稽核
6. **效能設計**：負載平衡、多層快取、資料庫優化和前端效能優化

所有設計遵循需求規格中的 EARS 格式驗收標準，確保系統能夠滿足功能性和非功能性需求。技術架構具備高可用性、可擴展性和安全性，為後續的開發實作提供了完整的技術指導。