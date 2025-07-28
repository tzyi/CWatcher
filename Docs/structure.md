---
title: 專案結構
description: "定義專案的檔案組織、命名規範與開發流程。"
inclusion: always
---

# CWatcher 專案結構設計

## 根目錄結構

```
CWatcher/
├── README.md                    # 專案說明文件
├── .gitignore                   # Git 忽略規則
├── .env.example                 # 環境變數範本
├── docker-compose.yml           # Docker 編排配置
├── docker-compose.dev.yml       # 開發環境 Docker 配置
├── Makefile                     # 建構和部署指令
├── CHANGELOG.md                 # 版本變更記錄
├── LICENSE                      # 授權條款
│
├── Docs/                        # 專案文件目錄
│   ├── product.md               # 產品願景文件
│   ├── tech.md                  # 技術架構文件
│   ├── structure.md             # 專案結構文件（本文件）
│   ├── api.md                   # API 文件
│   ├── deployment.md            # 部署指南
│   └── development.md           # 開發指南
│
├── backend/                     # 後端應用目錄
├── frontend/                    # 前端應用目錄
├── database/                    # 資料庫相關檔案
├── scripts/                     # 腳本和工具
├── tests/                       # 跨應用整合測試
├── deployment/                  # 部署相關檔案
└── docs-archive/                # 歷史文件歸檔
    ├── Docs-1/                  # 原始規劃文件
    ├── UI/                      # UI 原型檔案
    └── trash/                   # 廢棄檔案
```

## 後端目錄結構

```
backend/
├── app/                         # 應用主目錄
│   ├── __init__.py              # 應用初始化
│   ├── main.py                  # FastAPI 應用入口
│   ├── dependencies.py          # 全域依賴注入
│   │
│   ├── api/                     # API 路由模組
│   │   ├── __init__.py
│   │   ├── api_v1/              # API v1 版本
│   │   │   ├── __init__.py
│   │   │   ├── api.py           # 路由聚合
│   │   │   ├── endpoints/       # API 端點
│   │   │   │   ├── __init__.py
│   │   │   │   ├── servers.py   # 伺服器管理 API
│   │   │   │   ├── metrics.py   # 監控數據 API
│   │   │   │   ├── auth.py      # 認證 API
│   │   │   │   └── websocket.py # WebSocket 端點
│   │   │   └── deps.py          # API 依賴
│   │   └── middleware/          # 中介軟體
│   │       ├── __init__.py
│   │       ├── cors.py          # CORS 設定
│   │       ├── auth.py          # 認證中介軟體
│   │       └── error_handler.py # 錯誤處理
│   │
│   ├── core/                    # 核心配置模組
│   │   ├── __init__.py
│   │   ├── config.py            # 應用配置
│   │   ├── database.py          # 資料庫連接
│   │   ├── security.py          # 安全設定
│   │   ├── logging.py           # 日誌配置
│   │   └── events.py            # 生命周期事件
│   │
│   ├── db/                      # 資料庫相關
│   │   ├── __init__.py
│   │   ├── base.py              # 資料庫基類
│   │   ├── session.py           # 資料庫會話
│   │   └── migrations/          # Alembic 遷移檔案
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/        # 遷移版本檔案
│   │
│   ├── models/                  # 資料庫模型
│   │   ├── __init__.py
│   │   ├── base.py              # 基礎模型
│   │   ├── server.py            # 伺服器模型
│   │   ├── metrics.py           # 監控數據模型
│   │   ├── system_info.py       # 系統資訊模型
│   │   └── user.py              # 用戶模型
│   │
│   ├── schemas/                 # Pydantic 資料模型
│   │   ├── __init__.py
│   │   ├── server.py            # 伺服器 Schema
│   │   ├── metrics.py           # 監控數據 Schema
│   │   ├── system_info.py       # 系統資訊 Schema
│   │   ├── user.py              # 用戶 Schema
│   │   ├── auth.py              # 認證 Schema
│   │   └── responses.py         # 回應 Schema
│   │
│   ├── services/                # 業務邏輯服務
│   │   ├── __init__.py
│   │   ├── ssh_manager.py       # SSH 連接管理
│   │   ├── metrics_collector.py # 監控數據收集
│   │   ├── data_processor.py    # 數據處理服務
│   │   ├── websocket_manager.py # WebSocket 管理
│   │   ├── auth_service.py      # 認證服務
│   │   └── notification_service.py # 通知服務
│   │
│   ├── tasks/                   # 背景任務
│   │   ├── __init__.py
│   │   ├── scheduler.py         # 任務調度器
│   │   ├── monitoring_tasks.py  # 監控任務
│   │   ├── cleanup_tasks.py     # 清理任務
│   │   └── notification_tasks.py # 通知任務
│   │
│   └── utils/                   # 工具函數
│       ├── __init__.py
│       ├── ssh_utils.py         # SSH 工具
│       ├── encryption.py        # 加密工具
│       ├── formatters.py        # 格式化工具
│       ├── validators.py        # 驗證工具
│       └── constants.py         # 常數定義
│
├── tests/                       # 測試目錄
│   ├── __init__.py
│   ├── conftest.py              # pytest 配置
│   ├── unit/                    # 單元測試
│   │   ├── __init__.py
│   │   ├── test_ssh_manager.py
│   │   ├── test_metrics_collector.py
│   │   └── test_services/
│   ├── integration/             # 整合測試
│   │   ├── __init__.py
│   │   ├── test_api_endpoints.py
│   │   └── test_websocket.py
│   └── fixtures/                # 測試資料
│       ├── __init__.py
│       ├── servers.py
│       └── metrics.py
│
├── requirements/                # 依賴需求
│   ├── base.txt                 # 基礎依賴
│   ├── dev.txt                  # 開發依賴
│   ├── test.txt                 # 測試依賴
│   └── prod.txt                 # 生產依賴
│
├── alembic.ini                  # Alembic 配置
├── pyproject.toml               # 專案配置
├── requirements.txt             # 主要依賴檔案
├── Dockerfile                   # Docker 映像檔
├── Dockerfile.dev               # 開發環境 Docker
├── .env.example                 # 環境變數範本
└── .dockerignore               # Docker 忽略檔案
```

## 前端目錄結構

```
frontend/
├── public/                      # 靜態檔案
│   ├── index.html               # HTML 模板
│   ├── favicon.ico              # 網站圖示
│   ├── manifest.json            # PWA 配置
│   └── robots.txt               # 搜尋引擎規則
│
├── src/                         # 原始碼目錄
│   ├── index.tsx                # 應用入口點
│   ├── App.tsx                  # 根組件
│   ├── index.css                # 全域樣式
│   │
│   ├── components/              # 共用組件
│   │   ├── common/              # 基礎組件
│   │   │   ├── Button/          # 按鈕組件
│   │   │   │   ├── index.tsx
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Button.module.css
│   │   │   │   └── Button.test.tsx
│   │   │   ├── Input/           # 輸入組件
│   │   │   ├── Modal/           # 彈窗組件
│   │   │   ├── Loading/         # 載入組件
│   │   │   └── ErrorBoundary/   # 錯誤邊界
│   │   │
│   │   ├── layout/              # 版面配置組件
│   │   │   ├── Header/          # 頁首組件
│   │   │   ├── Sidebar/         # 側邊欄組件
│   │   │   ├── Footer/          # 頁尾組件
│   │   │   └── MainLayout/      # 主版面組件
│   │   │
│   │   ├── charts/              # 圖表組件
│   │   │   ├── LineChart/       # 折線圖
│   │   │   ├── AreaChart/       # 面積圖
│   │   │   ├── CircularProgress/ # 圓形進度
│   │   │   ├── MetricChart/     # 指標圖表
│   │   │   └── ChartContainer/  # 圖表容器
│   │   │
│   │   ├── metrics/             # 監控指標組件
│   │   │   ├── MetricCard/      # 指標卡片
│   │   │   ├── CPUCard/         # CPU 指標
│   │   │   ├── MemoryCard/      # 記憶體指標
│   │   │   ├── DiskCard/        # 磁碟指標
│   │   │   └── NetworkCard/     # 網路指標
│   │   │
│   │   ├── server/              # 伺服器相關組件
│   │   │   ├── ServerList/      # 伺服器列表
│   │   │   ├── ServerCard/      # 伺服器卡片
│   │   │   ├── AddServerModal/  # 新增伺服器彈窗
│   │   │   ├── ServerStatus/    # 伺服器狀態
│   │   │   └── ServerSearch/    # 伺服器搜尋
│   │   │
│   │   └── ui/                  # UI 元件
│   │       ├── Card/            # 卡片組件
│   │       ├── Badge/           # 徽章組件
│   │       ├── Tooltip/         # 工具提示
│   │       └── Toast/           # 通知組件
│   │
│   ├── pages/                   # 頁面組件
│   │   ├── Dashboard/           # 儀表板頁面
│   │   │   ├── index.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── components/      # 頁面專用組件
│   │   │   └── hooks/           # 頁面專用 hooks
│   │   ├── ServerDetail/        # 伺服器詳情頁面
│   │   ├── Settings/            # 設定頁面
│   │   ├── Login/               # 登入頁面
│   │   └── NotFound/            # 404 頁面
│   │
│   ├── hooks/                   # 自定義 hooks
│   │   ├── useServers.ts        # 伺服器相關 hooks
│   │   ├── useMetrics.ts        # 監控數據 hooks
│   │   ├── useWebSocket.ts      # WebSocket hooks
│   │   ├── useApi.ts            # API hooks
│   │   └── useLocalStorage.ts   # 本地存儲 hooks
│   │
│   ├── services/                # API 服務
│   │   ├── api.ts               # API 客戶端基類
│   │   ├── serverService.ts     # 伺服器 API 服務
│   │   ├── metricsService.ts    # 監控數據 API 服務
│   │   ├── authService.ts       # 認證 API 服務
│   │   └── websocketService.ts  # WebSocket 服務
│   │
│   ├── stores/                  # 狀態管理
│   │   ├── index.ts             # 狀態管理聚合
│   │   ├── serverStore.ts       # 伺服器狀態
│   │   ├── metricsStore.ts      # 監控數據狀態
│   │   ├── authStore.ts         # 認證狀態
│   │   ├── uiStore.ts           # UI 狀態
│   │   └── websocketStore.ts    # WebSocket 狀態
│   │
│   ├── utils/                   # 工具函數
│   │   ├── formatters.ts        # 數據格式化
│   │   ├── constants.ts         # 常數定義
│   │   ├── helpers.ts           # 輔助函數
│   │   ├── validators.ts        # 驗證函數
│   │   ├── dateUtils.ts         # 日期工具
│   │   └── chartUtils.ts        # 圖表工具
│   │
│   ├── types/                   # TypeScript 類型定義
│   │   ├── index.ts             # 類型聚合
│   │   ├── api.ts               # API 類型
│   │   ├── server.ts            # 伺服器類型
│   │   ├── metrics.ts           # 監控數據類型
│   │   ├── auth.ts              # 認證類型
│   │   ├── chart.ts             # 圖表類型
│   │   └── common.ts            # 通用類型
│   │
│   ├── config/                  # 配置檔案
│   │   ├── api.ts               # API 配置
│   │   ├── theme.ts             # 主題配置
│   │   ├── chart.ts             # 圖表配置
│   │   └── constants.ts         # 應用常數
│   │
│   └── styles/                  # 樣式檔案
│       ├── globals.css          # 全域樣式
│       ├── variables.css        # CSS 變數
│       ├── components.css       # 組件樣式
│       └── utilities.css        # 工具類樣式
│
├── tests/                       # 測試目錄
│   ├── setup.ts                 # 測試設定
│   ├── __mocks__/               # mock 檔案
│   ├── unit/                    # 單元測試
│   │   ├── components/          # 組件測試
│   │   ├── hooks/               # hooks 測試
│   │   ├── services/            # 服務測試
│   │   └── utils/               # 工具函數測試
│   ├── integration/             # 整合測試
│   └── e2e/                     # 端到端測試
│
├── package.json                 # npm 配置
├── package-lock.json            # npm 鎖定檔案
├── tsconfig.json                # TypeScript 配置
├── tailwind.config.js           # Tailwind CSS 配置
├── vite.config.ts               # Vite 配置
├── .eslintrc.js                 # ESLint 配置
├── .prettierrc                  # Prettier 配置
├── jest.config.js               # Jest 測試配置
├── Dockerfile                   # Docker 映像檔
├── .env.example                 # 環境變數範本
└── .gitignore                   # Git 忽略檔案
```

## 資料庫目錄結構

```
database/
├── migrations/                  # 資料庫遷移檔案
│   ├── 001_initial_schema.sql   # 初始資料庫結構
│   ├── 002_add_indexes.sql      # 新增索引
│   └── 003_add_partitions.sql   # 新增分區
│
├── seeds/                       # 種子資料
│   ├── development/             # 開發環境資料
│   │   ├── servers.sql          # 測試伺服器資料
│   │   └── users.sql            # 測試用戶資料
│   ├── staging/                 # 測試環境資料
│   └── production/              # 生產環境資料
│
├── schema/                      # 資料庫結構檔案
│   ├── tables/                  # 資料表定義
│   │   ├── servers.sql          # 伺服器表
│   │   ├── system_metrics.sql   # 監控數據表
│   │   ├── system_info.sql      # 系統資訊表
│   │   └── users.sql            # 用戶表
│   ├── indexes/                 # 索引定義
│   ├── triggers/                # 觸發器定義
│   └── procedures/              # 存儲過程定義
│
├── backup/                      # 資料庫備份
│   ├── daily/                   # 每日備份
│   ├── weekly/                  # 每週備份
│   └── monthly/                 # 每月備份
│
├── scripts/                     # 資料庫腳本
│   ├── setup.sql                # 初始化腳本
│   ├── cleanup.sql              # 清理腳本
│   ├── optimization.sql         # 優化腳本
│   └── monitoring.sql           # 監控腳本
│
└── docker/                      # Docker 相關
    ├── mysql.cnf                # MySQL 配置
    ├── init.sql                 # 初始化 SQL
    └── Dockerfile               # 資料庫 Docker 映像
```

## 部署目錄結構

```
deployment/
├── docker/                      # Docker 部署
│   ├── docker-compose.yml       # 生產環境編排
│   ├── docker-compose.dev.yml   # 開發環境編排
│   ├── docker-compose.staging.yml # 測試環境編排
│   └── env/                     # 環境變數檔案
│       ├── .env.production
│       ├── .env.staging
│       └── .env.development
│
├── kubernetes/                  # Kubernetes 部署
│   ├── namespace.yaml           # 命名空間
│   ├── configmap.yaml           # 配置映射
│   ├── secret.yaml              # 機密資料
│   ├── deployment.yaml          # 部署配置
│   ├── service.yaml             # 服務配置
│   ├── ingress.yaml             # 入口配置
│   └── persistentvolume.yaml    # 持久卷
│
├── nginx/                       # Nginx 配置
│   ├── nginx.conf               # 主配置檔案
│   ├── sites-available/         # 可用站點
│   ├── ssl/                     # SSL 證書
│   └── logs/                    # 日誌檔案
│
├── scripts/                     # 部署腳本
│   ├── deploy.sh                # 部署腳本
│   ├── rollback.sh              # 回滾腳本
│   ├── backup.sh                # 備份腳本
│   ├── health-check.sh          # 健康檢查
│   └── update.sh                # 更新腳本
│
└── monitoring/                  # 監控配置
    ├── prometheus/              # Prometheus 配置
    ├── grafana/                 # Grafana 配置
    └── alerts/                  # 告警配置
```

## 檔案命名規範

### 通用命名規則
- **目錄名稱**：使用小寫字母和連字號（kebab-case）
- **檔案名稱**：使用駝峰命名法（camelCase）或帕斯卡命名法（PascalCase）
- **常數**：使用大寫字母和底線（UPPER_SNAKE_CASE）
- **變數和函數**：使用駝峰命名法（camelCase）

### 前端檔案命名
```
✅ 正確範例：
- components/MetricCard/MetricCard.tsx
- hooks/useServerMetrics.ts
- services/apiClient.ts
- types/ServerTypes.ts

❌ 錯誤範例：
- components/metric-card/metric-card.tsx
- hooks/use_server_metrics.ts
- services/API_Client.ts
- types/server_types.ts
```

### 後端檔案命名
```
✅ 正確範例：
- models/server.py
- schemas/server_schema.py
- services/ssh_manager.py
- utils/encryption_utils.py

❌ 錯誤範例：
- models/Server.py
- schemas/ServerSchema.py
- services/SSHManager.py
- utils/EncryptionUtils.py
```

### 資料庫命名
```
✅ 正確範例：
- 表名：servers, system_metrics, user_sessions
- 欄位名：created_at, updated_at, server_id
- 索引名：idx_servers_ip_address, idx_metrics_timestamp

❌ 錯誤範例：
- 表名：Servers, SystemMetrics, UserSessions
- 欄位名：CreatedAt, UpdatedAt, ServerId
- 索引名：ServersIpAddressIndex, MetricsTimestampIndex
```

## Git 分支策略

### 分支命名規範
```
main                    # 主分支（生產環境）
develop                 # 開發分支
feature/user-auth       # 功能分支
hotfix/fix-memory-leak  # 熱修復分支
release/v1.0.0          # 發布分支
```

### 提交訊息規範
```
格式：<type>(<scope>): <description>

類型：
- feat: 新功能
- fix: 修復問題
- docs: 文件變更
- style: 代碼格式變更
- refactor: 重構
- test: 測試相關
- chore: 建構過程或輔助工具變更

範例：
feat(auth): add JWT authentication
fix(metrics): resolve memory leak in data collection
docs(api): update API documentation
```

## 開發工作流程

### 1. 專案初始化
```bash
# 1. 克隆專案
git clone <repository-url>
cd CWatcher

# 2. 設置後端環境
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 3. 設置前端環境
cd ../frontend
npm install

# 4. 設置資料庫
cd ../database
# 執行資料庫初始化腳本
```

### 2. 功能開發流程
```bash
# 1. 創建功能分支
git checkout -b feature/new-feature

# 2. 開發功能（TDD 方式）
# - 先寫測試
# - 再實現功能
# - 重構優化

# 3. 運行測試
cd backend && python -m pytest
cd frontend && npm test

# 4. 提交變更
git add .
git commit -m "feat(scope): description"

# 5. 推送並創建 PR
git push origin feature/new-feature
```

### 3. 測試策略
- **單元測試**：每個函數/組件都要有對應測試
- **整合測試**：API 端點和資料庫互動測試
- **端到端測試**：關鍵用戶流程測試
- **測試覆蓋率**：目標 80% 以上

### 4. 代碼審查檢查點
- [ ] 代碼符合專案規範
- [ ] 測試覆蓋率達標
- [ ] 無明顯性能問題
- [ ] 安全性考量完整
- [ ] 文件更新完整
- [ ] 符合無障礙設計原則

## 環境配置

### 開發環境要求
- **Node.js**：16.x 或以上
- **Python**：3.9 或以上
- **MySQL**：8.0 或以上
- **Docker**：20.x 或以上（可選）
- **Git**：2.x 或以上

### IDE 推薦設定
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./backend/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "editor.formatOnSave": true,
    "typescript.preferences.importModuleSpecifier": "relative"
}
```

這個專案結構設計考慮了：
- **可維護性**：清晰的模組分離和職責劃分
- **可擴展性**：易於新增功能和模組
- **一致性**：統一的命名規範和組織方式
- **測試友好**：完整的測試目錄結構
- **部署便利**：完整的部署配置和腳本