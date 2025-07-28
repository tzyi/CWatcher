---
title: API 設計規範
description: "RESTful API 與 WebSocket 通訊協定設計規範。"
inclusion: always
---

# CWatcher API 設計規範

## API 概覽

CWatcher 提供 RESTful API 和 WebSocket 接口，用於管理伺服器監控和即時數據傳輸。

### 基礎資訊
- **Base URL**：`https://api.cwatcher.com/api/v1`
- **認證方式**：JWT Bearer Token
- **內容類型**：`application/json`
- **編碼格式**：UTF-8
- **API 版本**：v1

### 回應格式
```json
{
    "success": true,
    "data": {},
    "message": "操作成功",
    "timestamp": "2024-01-01T12:00:00.000Z",
    "request_id": "req_123456789"
}
```

### 錯誤格式
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "請求參數無效",
        "details": {
            "field": "ip_address",
            "reason": "IP 地址格式不正確"
        }
    },
    "timestamp": "2024-01-01T12:00:00.000Z",
    "request_id": "req_123456789"
}
```

## 認證 API

### 登入
```http
POST /auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "password123"
}
```

**回應**：
```json
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin"
        }
    }
}
```

### 刷新令牌
```http
POST /auth/refresh
Authorization: Bearer <access_token>
```

### 登出
```http
POST /auth/logout
Authorization: Bearer <access_token>
```

## 伺服器管理 API

### 獲取伺服器列表
```http
GET /servers
Authorization: Bearer <access_token>
```

**查詢參數**：
- `page`：頁碼（預設：1）
- `limit`：每頁數量（預設：20，最大：100）
- `status`：狀態篩選（online/offline/warning）
- `search`：搜尋關鍵字

**回應**：
```json
{
    "success": true,
    "data": {
        "servers": [
            {
                "id": 1,
                "name": "Web Server 01",
                "ip_address": "192.168.1.50",
                "ssh_port": 22,
                "username": "admin",
                "status": "online",
                "last_seen": "2024-01-01T12:00:00.000Z",
                "created_at": "2024-01-01T10:00:00.000Z",
                "updated_at": "2024-01-01T12:00:00.000Z"
            }
        ],
        "pagination": {
            "current_page": 1,
            "per_page": 20,
            "total": 50,
            "total_pages": 3
        }
    }
}
```

### 獲取單個伺服器
```http
GET /servers/{server_id}
Authorization: Bearer <access_token>
```

### 新增伺服器
```http
POST /servers
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "Database Server",
    "ip_address": "192.168.1.100",
    "ssh_port": 22,
    "username": "admin",
    "password": "server_password",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...",
    "description": "主資料庫伺服器"
}
```

**驗證規則**：
- `name`：必填，1-100 字元
- `ip_address`：必填，有效的 IPv4 或 IPv6 地址
- `ssh_port`：可選，1-65535 範圍內的整數
- `username`：必填，1-50 字元
- `password` 或 `private_key`：至少提供一個

### 更新伺服器
```http
PUT /servers/{server_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "Updated Server Name",
    "description": "更新後的描述"
}
```

### 刪除伺服器
```http
DELETE /servers/{server_id}
Authorization: Bearer <access_token>
```

### 測試伺服器連接
```http
POST /servers/{server_id}/test
Authorization: Bearer <access_token>
```

**回應**：
```json
{
    "success": true,
    "data": {
        "connection_status": "success",
        "response_time_ms": 150,
        "ssh_version": "OpenSSH_8.2",
        "tested_at": "2024-01-01T12:00:00.000Z"
    }
}
```

## 監控數據 API

### 獲取即時監控數據
```http
GET /servers/{server_id}/metrics/current
Authorization: Bearer <access_token>
```

**回應**：
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
                "processes": 156
            },
            "memory": {
                "total_gb": 8.0,
                "used_gb": 5.4,
                "free_gb": 1.4,
                "cached_gb": 1.2,
                "swap_total_gb": 2.0,
                "swap_used_gb": 0.1,
                "usage_percent": 67.5
            },
            "disk": {
                "filesystems": [
                    {
                        "device": "/dev/sda1",
                        "mountpoint": "/",
                        "total_gb": 500,
                        "used_gb": 380,
                        "free_gb": 120,
                        "usage_percent": 76,
                        "filesystem": "ext4"
                    }
                ],
                "io": {
                    "read_mb_s": 12.4,
                    "write_mb_s": 8.7,
                    "read_iops": 145,
                    "write_iops": 89
                }
            },
            "network": {
                "interfaces": [
                    {
                        "name": "eth0",
                        "download_mb_s": 2.4,
                        "upload_mb_s": 0.8,
                        "download_total_gb": 125.6,
                        "upload_total_gb": 45.2,
                        "status": "up"
                    }
                ],
                "total_download_mb_s": 2.4,
                "total_upload_mb_s": 0.8
            }
        }
    }
}
```

### 獲取歷史監控數據
```http
GET /servers/{server_id}/metrics/history
Authorization: Bearer <access_token>
```

**查詢參數**：
- `metric_type`：指標類型（cpu/memory/disk/network）
- `start_time`：開始時間（ISO 8601 格式）
- `end_time`：結束時間（ISO 8601 格式）
- `interval`：數據間隔（5m/15m/1h/6h/1d）
- `limit`：數據點數量限制（預設：100，最大：1000）

**回應**：
```json
{
    "success": true,
    "data": {
        "server_id": 1,
        "metric_type": "cpu",
        "interval": "5m",
        "data_points": [
            {
                "timestamp": "2024-01-01T12:00:00.000Z",
                "value": {
                    "usage_percent": 42.5,
                    "load_avg": [1.52, 1.24, 0.92]
                }
            },
            {
                "timestamp": "2024-01-01T12:05:00.000Z",
                "value": {
                    "usage_percent": 38.2,
                    "load_avg": [1.45, 1.28, 0.95]
                }
            }
        ],
        "summary": {
            "min": 25.1,
            "max": 78.3,
            "avg": 42.7,
            "count": 48
        }
    }
}
```

### 獲取系統資訊
```http
GET /servers/{server_id}/system-info
Authorization: Bearer <access_token>
```

**回應**：
```json
{
    "success": true,
    "data": {
        "server_id": 1,
        "hardware": {
            "hostname": "web-server-01",
            "cpu_model": "Intel Xeon E5-2680 v4",
            "cpu_cores": 4,
            "cpu_threads": 8,
            "memory_total_gb": 8.0,
            "memory_type": "DDR4"
        },
        "operating_system": {
            "name": "Ubuntu",
            "version": "22.04 LTS",
            "kernel_version": "5.15.0-58-generic",
            "architecture": "x86_64",
            "uptime_seconds": 3724800
        },
        "storage": [
            {
                "device": "/dev/sda",
                "type": "SSD",
                "size_gb": 500,
                "model": "Samsung 980 PRO"
            }
        ],
        "network_interfaces": [
            {
                "name": "eth0",
                "mac_address": "00:1b:21:3c:2d:e1",
                "ip_address": "192.168.1.50",
                "speed_mbps": 1000
            }
        ],
        "updated_at": "2024-01-01T12:00:00.000Z"
    }
}
```

### 獲取伺服器狀態
```http
GET /servers/{server_id}/status
Authorization: Bearer <access_token>
```

**回應**：
```json
{
    "success": true,
    "data": {
        "server_id": 1,
        "status": "online",
        "last_seen": "2024-01-01T12:00:00.000Z",
        "response_time_ms": 120,
        "connection_info": {
            "ssh_connected": true,
            "last_connection_attempt": "2024-01-01T12:00:00.000Z",
            "connection_errors": 0,
            "uptime_seconds": 3724800
        },
        "health_checks": {
            "cpu_warning": false,
            "memory_warning": false,
            "disk_warning": true,
            "network_warning": false
        }
    }
}
```

## 警報管理 API

### 獲取警報規則
```http
GET /servers/{server_id}/alerts
Authorization: Bearer <access_token>
```

### 新增警報規則
```http
POST /servers/{server_id}/alerts
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "CPU 使用率警報",
    "metric_type": "cpu",
    "condition": "greater_than",
    "threshold": 80,
    "duration_minutes": 5,
    "severity": "warning",
    "enabled": true,
    "notification_channels": ["email", "slack"]
}
```

### 獲取警報歷史
```http
GET /servers/{server_id}/alerts/history
Authorization: Bearer <access_token>
```

## WebSocket API

### 連接端點
```
wss://api.cwatcher.com/ws
```

### 認證
```javascript
// 連接時傳送認證令牌
const socket = new WebSocket('wss://api.cwatcher.com/ws?token=<access_token>');
```

### 訂閱伺服器數據
```javascript
// 訂閱特定伺服器的即時數據
socket.send(JSON.stringify({
    type: 'subscribe',
    data: {
        server_id: 1,
        metrics: ['cpu', 'memory', 'disk', 'network']
    }
}));
```

### 取消訂閱
```javascript
socket.send(JSON.stringify({
    type: 'unsubscribe',
    data: {
        server_id: 1
    }
}));
```

### 接收即時數據
```javascript
socket.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'metrics_update':
            // 處理監控數據更新
            console.log('收到監控數據:', message.data);
            break;
            
        case 'server_status_change':
            // 處理伺服器狀態變化
            console.log('伺服器狀態變化:', message.data);
            break;
            
        case 'alert_triggered':
            // 處理警報觸發
            console.log('警報觸發:', message.data);
            break;
    }
};
```

### 心跳檢測
```javascript
// 客戶端發送心跳
setInterval(() => {
    socket.send(JSON.stringify({
        type: 'ping'
    }));
}, 30000);

// 接收心跳回應
socket.onmessage = function(event) {
    const message = JSON.parse(event.data);
    if (message.type === 'pong') {
        console.log('心跳正常');
    }
};
```

### 消息格式

#### 監控數據更新
```json
{
    "type": "metrics_update",
    "data": {
        "server_id": 1,
        "timestamp": "2024-01-01T12:00:00.000Z",
        "metrics": {
            "cpu": {
                "usage_percent": 42.5
            }
        }
    }
}
```

#### 伺服器狀態變化
```json
{
    "type": "server_status_change",
    "data": {
        "server_id": 1,
        "old_status": "online",
        "new_status": "warning",
        "timestamp": "2024-01-01T12:00:00.000Z",
        "reason": "High CPU usage detected"
    }
}
```

#### 警報觸發
```json
{
    "type": "alert_triggered",
    "data": {
        "alert_id": 123,
        "server_id": 1,
        "rule_name": "CPU 使用率警報",
        "severity": "warning",
        "message": "CPU 使用率超過 80%",
        "current_value": 85.2,
        "threshold": 80,
        "timestamp": "2024-01-01T12:00:00.000Z"
    }
}
```

## 狀態碼

### HTTP 狀態碼
- `200 OK`：請求成功
- `201 Created`：資源創建成功
- `204 No Content`：請求成功，無返回內容
- `400 Bad Request`：請求參數錯誤
- `401 Unauthorized`：未授權
- `403 Forbidden`：權限不足
- `404 Not Found`：資源不存在
- `409 Conflict`：資源衝突
- `422 Unprocessable Entity`：資料驗證失敗
- `429 Too Many Requests`：請求頻率限制
- `500 Internal Server Error`：伺服器內部錯誤

### 自定義錯誤碼
```json
{
    "VALIDATION_ERROR": "資料驗證失敗",
    "SERVER_NOT_FOUND": "伺服器不存在",
    "CONNECTION_FAILED": "伺服器連接失敗",
    "SSH_AUTH_FAILED": "SSH 認證失敗",
    "PERMISSION_DENIED": "權限不足",
    "RESOURCE_CONFLICT": "資源衝突",
    "RATE_LIMIT_EXCEEDED": "請求頻率超限",
    "SERVER_UNAVAILABLE": "服務不可用"
}
```

## 速率限制

### 全域限制
- **一般用戶**：每分鐘 100 請求
- **進階用戶**：每分鐘 500 請求
- **企業用戶**：每分鐘 1000 請求

### 特定端點限制
- **認證端點**：每分鐘 20 請求
- **測試連接**：每分鐘 10 請求
- **監控數據**：每分鐘 200 請求

### 回應標頭
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 60
```

## API 版本控制

### URL 版本控制
- `v1`：當前穩定版本
- `v2`：下一個主要版本（開發中）

### 向後相容性
- 新增欄位不會破壞相容性
- 現有欄位不會被移除
- 重大變更會發布新的主要版本

### 棄用政策
- 提前 6 個月通知棄用
- 維護向後相容性 12 個月
- 在回應標頭中標記棄用狀態

```http
Deprecation: true
Sunset: Sat, 01 Jan 2025 00:00:00 GMT
Link: </api/v2/servers>; rel="successor-version"
```

## SDK 和客戶端庫

### JavaScript/TypeScript
```bash
npm install @cwatcher/api-client
```

```javascript
import { CWatcherClient } from '@cwatcher/api-client';

const client = new CWatcherClient({
    baseURL: 'https://api.cwatcher.com',
    apiKey: 'your-api-key'
});

// 獲取伺服器列表
const servers = await client.servers.list();

// 訂閱即時數據
client.websocket.subscribe('metrics', (data) => {
    console.log('收到監控數據:', data);
});
```

### Python
```bash
pip install cwatcher-client
```

```python
from cwatcher import CWatcherClient

client = CWatcherClient(
    base_url='https://api.cwatcher.com',
    api_key='your-api-key'
)

# 獲取伺服器列表
servers = client.servers.list()

# 獲取即時數據
metrics = client.servers.get_current_metrics(server_id=1)
```

這個 API 設計規範提供了完整的接口定義，包括認證、資源管理、即時通訊等所有必要的功能，為前端開發和第三方整合提供了清晰的指導。