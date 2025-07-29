# CWatcher Backend

CWatcher Linux 系統監控平台的後端 API 服務。

## 目錄結構

```
backend/
├── app/                    # 主要應用程式目錄
│   ├── __init__.py
│   ├── main.py            # FastAPI 應用程式入口
│   ├── api/               # API 路由
│   │   ├── __init__.py
│   │   └── v1/            # API v1 版本
│   │       ├── __init__.py
│   │       ├── api.py     # 路由匯總
│   │       └── endpoints/ # 具體端點
│   ├── core/              # 核心配置
│   │   ├── __init__.py
│   │   └── config.py      # 應用程式配置
│   ├── db/                # 資料庫相關
│   ├── models/            # SQLAlchemy 模型
│   ├── schemas/           # Pydantic 模型
│   ├── services/          # 業務邏輯服務
│   └── utils/             # 工具函數
├── tests/                 # 測試目錄
│   ├── unit/              # 單元測試
│   ├── integration/       # 整合測試
│   └── e2e/              # 端到端測試
├── docs/                  # 文件
├── scripts/              # 腳本工具
├── requirements.txt      # Python 依賴
├── .env.example         # 環境變數範例
└── README.md            # 本文件
```

## 快速開始

### 1. 安裝依賴

```bash
cd backend
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 檔案設定您的配置
```

### 3. 啟動開發伺服器

```bash
python app/main.py
```

或使用 uvicorn：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 訪問 API 文件

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 開發指南

### 程式碼風格

使用以下工具維護程式碼品質：

```bash
# 格式化程式碼
black app/ tests/

# 檢查程式碼風格
flake8 app/ tests/

# 類型檢查
mypy app/

# 安全性檢查
bandit -r app/
```

### 測試

```bash
# 執行所有測試
pytest

# 執行測試並生成覆蓋率報告
pytest --cov=app tests/

# 執行特定測試類型
pytest tests/unit/      # 單元測試
pytest tests/integration/  # 整合測試
pytest tests/e2e/       # 端到端測試
```

## 主要功能

- ✅ FastAPI 框架設定
- ⏳ SSH 連接管理
- ⏳ 系統監控數據收集
- ⏳ WebSocket 即時通訊
- ⏳ 資料庫操作
- ⏳ 認證與授權
- ⏳ API 文件自動生成

## 技術棧

- **框架**: FastAPI 0.104.1
- **資料庫**: PostgreSQL + SQLAlchemy
- **認證**: JWT
- **WebSocket**: 原生 WebSocket 支援
- **SSH**: Paramiko
- **任務排程**: APScheduler
- **測試**: Pytest