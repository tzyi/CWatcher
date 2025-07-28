# CWatcher 專案文件架構

## 文件概覽

本目錄包含 CWatcher Linux 系統監控平台的完整技術文件，提供開發團隊所需的所有指導資訊。

## 文件結構

### 核心指導文件

1. **[product.md](./product.md)** - 產品願景與功能定義
   - 核心目標與價值主張
   - 目標用戶群體分析
   - 功能優先級規劃
   - 商業價值與成功指標

2. **[tech.md](./tech.md)** - 技術架構設計
   - 完整技術棧定義
   - 系統架構與數據流設計
   - 資料庫結構與 API 規範
   - 前後端架構詳細說明

3. **[structure.md](./structure.md)** - 專案結構與規範
   - 完整目錄結構規劃
   - 檔案命名與組織規範
   - Git 工作流程與代碼審查
   - 開發最佳實踐

### 實作指導文件

4. **[development.md](./development.md)** - 開發環境設置指南
   - 詳細的環境安裝步驟
   - 專案初始化與配置
   - 開發工具設定
   - 常見問題解決方案

5. **[api.md](./api.md)** - API 設計規範
   - RESTful API 完整定義
   - WebSocket 即時通訊協定
   - 認證與授權機制
   - 錯誤處理與狀態碼

6. **[deployment.md](./deployment.md)** - 部署配置指南
   - Docker 容器化部署
   - 生產環境配置
   - 安全性與性能調優
   - 監控與維護指南

## 專案現狀

### 已完成
- ✅ 完整的 PRD 需求分析（位於 `../docs-archive/Docs-1/prd.md`）
- ✅ 詳細的開發計劃（位於 `../docs-archive/Docs-1/TODO.md`）
- ✅ 功能完整的 UI 原型（位於 `../docs-archive/UI/`）
- ✅ 核心架構文件（本目錄所有文件）

### 開發中
- ⏳ 後端 FastAPI 應用程式
- ⏳ 前端 React + TypeScript 應用
- ⏳ MySQL 資料庫實作
- ⏳ Docker 容器化部署

### 規劃中
- 📋 自動化測試套件
- 📋 CI/CD 流水線
- 📋 監控與警報系統
- 📋 用戶文件與幫助系統

## 技術棧總覽

### 前端技術
- **框架**: React 18 + TypeScript
- **UI**: Tailwind CSS + 自定義暗色主題
- **圖表**: Chart.js + react-chartjs-2
- **狀態管理**: Zustand 或 Redux Toolkit
- **建構**: Vite 或 Create React App

### 後端技術
- **框架**: Python 3.9+ + FastAPI
- **資料庫**: MySQL 8.0 (帳號: cabie, 密碼: Aa-12345)
- **ORM**: SQLAlchemy 2.0
- **即時通訊**: WebSocket
- **任務調度**: APScheduler
- **快取**: Redis (可選)

### 基礎架構
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx
- **SSL**: Let's Encrypt 或自簽證書
- **監控**: SSH 連接到目標 Linux 伺服器

## 開始開發

### 1. 環境準備
```bash
# 閱讀開發環境設置指南
cat development.md

# 安裝必要工具
# - Node.js 18+ 
# - Python 3.9+
# - MySQL 8.0+
# - Docker 20.10+
```

### 2. 專案初始化
```bash
# 克隆專案
git clone <repository-url>
cd CWatcher

# 參考 structure.md 建立目錄結構
mkdir -p backend frontend database deployment

# 參考 development.md 配置開發環境
```

### 3. 開發流程
```bash
# 1. 閱讀相關文件
# 2. 建立功能分支
# 3. TDD 開發（先寫測試）
# 4. 實作功能
# 5. 代碼審查
# 6. 合併主分支
```

## UI 設計參考

專案已有完整的 UI 原型設計，位於 `../docs-archive/UI/prototype-1/`：

### 設計特色
- **暗色主題**: 適合長時間監控使用
- **現代化設計**: 使用 Tailwind CSS 和玻璃態效果
- **響應式佈局**: 支援桌面、平板、手機
- **視覺化圖表**: Chart.js 即時監控圖表
- **直觀操作**: 清晰的狀態指示和互動回饋

### 核心組件
- 伺服器列表側邊欄
- 監控指標卡片（CPU/記憶體/磁碟/網路）
- 即時圖表展示
- 系統資訊面板
- 新增伺服器彈窗

## 資料庫設計

### 核心資料表
- **servers**: 伺服器配置資訊
- **system_metrics**: 監控數據時序表
- **system_info**: 系統硬體資訊
- **users**: 用戶認證（未來擴展）

### 資料庫配置
- **主機**: localhost:3306
- **資料庫**: cwatcher
- **用戶**: cabie
- **密碼**: Aa-12345

## API 設計

### RESTful API
- `/api/v1/servers` - 伺服器管理
- `/api/v1/servers/{id}/metrics` - 監控數據
- `/api/v1/servers/{id}/system-info` - 系統資訊
- `/api/v1/auth` - 認證授權

### WebSocket
- `/ws` - 即時數據推送
- 訂閱/取消訂閱機制
- 心跳檢測與自動重連

## 安全考量

### 資料傳輸
- HTTPS/WSS 加密傳輸
- JWT Token 認證
- CORS 跨域限制

### SSH 連接
- 支援密碼和金鑰認證
- AES 加密存儲憑證
- 連接超時和重試機制

### 系統安全
- SQL 注入防護
- XSS 攻擊防護
- 速率限制
- 輸入驗證

## 性能目標

### 系統性能
- 頁面載入時間 < 3 秒
- 數據更新延遲 < 5 秒
- 支援 100+ 並發用戶
- 監控 50+ 伺服器

### 可用性
- 99.5% 系統可用性
- 自動故障恢復
- 資料完整性保證
- 水平擴展支援

## 測試策略

### 測試類型
- **單元測試**: ≥80% 覆蓋率
- **整合測試**: ≥70% 覆蓋率
- **端到端測試**: 關鍵用戶流程
- **性能測試**: 負載和壓力測試

### 測試工具
- **後端**: pytest, pytest-asyncio
- **前端**: Jest, React Testing Library
- **E2E**: Playwright 或 Cypress
- **API**: HTTPx, Mock Service Worker

## 部署策略

### 環境區分
- **開發環境**: 本地 Docker Compose
- **測試環境**: 雲端容器部署
- **生產環境**: 負載均衡 + 高可用

### 部署流程
- Docker 容器化
- Nginx 反向代理
- SSL 證書配置
- 監控和日誌收集

## 維護與監控

### 系統監控
- 應用性能監控 (APM)
- 資料庫性能監控
- 伺服器資源監控
- 使用者行為分析

### 日誌管理
- 結構化日誌格式
- 集中化日誌收集
- 錯誤追蹤和警報
- 日誌輪替和清理

## 文件維護

### 更新原則
- 程式碼變更時同步更新文件
- 定期檢閱文件正確性
- 版本控制和變更追蹤
- 團隊協作和知識分享

### 貢獻指南
- 遵循現有文件格式
- 使用清晰的中文表達
- 提供實際範例和代碼
- 保持文件結構一致性

---

## 快速導航

| 想要了解... | 請查看... |
|------------|-----------|
| 專案目標和功能 | [product.md](./product.md) |
| 技術架構和設計 | [tech.md](./tech.md) |
| 專案結構和規範 | [structure.md](./structure.md) |
| 開發環境設置 | [development.md](./development.md) |
| API 接口定義 | [api.md](./api.md) |
| 部署和運維 | [deployment.md](./deployment.md) |
| 原始需求文件 | [../docs-archive/Docs-1/prd.md](../docs-archive/Docs-1/prd.md) |
| 開發計劃 | [../docs-archive/Docs-1/TODO.md](../docs-archive/Docs-1/TODO.md) |
| UI 原型 | [../docs-archive/UI/prototype-1/](../docs-archive/UI/prototype-1/) |

這套文件架構為 CWatcher 專案提供了完整的技術指導，從產品願景到具體實作，從開發環境到生產部署，確保開發團隊能夠高效、一致地進行專案開發。