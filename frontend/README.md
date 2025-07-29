# CWatcher Frontend

CWatcher Linux 系統監控平台的前端應用程式。

## 技術棧

- **框架**: React 18 + TypeScript
- **建構工具**: Vite
- **樣式**: Tailwind CSS
- **狀態管理**: Zustand
- **路由**: React Router v6
- **圖表**: Chart.js + react-chartjs-2
- **HTTP 客戶端**: Axios
- **WebSocket**: Socket.io Client
- **表單**: React Hook Form + Zod
- **測試**: Vitest + Testing Library + Playwright

## 目錄結構

```
frontend/
├── src/
│   ├── components/        # React 元件
│   │   ├── common/        # 通用元件
│   │   ├── charts/        # 圖表元件
│   │   ├── servers/       # 伺服器相關元件
│   │   └── monitoring/    # 監控相關元件
│   ├── pages/            # 頁面元件
│   ├── hooks/            # 自訂 Hooks
│   ├── services/         # API 服務
│   ├── types/            # TypeScript 型別定義
│   ├── utils/            # 工具函數
│   └── styles/           # 樣式檔案
├── public/               # 靜態資源
├── tests/                # 測試檔案
│   ├── unit/             # 單元測試
│   ├── integration/      # 整合測試
│   └── e2e/             # 端到端測試
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

## 快速開始

### 1. 安裝依賴

```bash
cd frontend
npm install
```

### 2. 啟動開發伺服器

```bash
npm run dev
```

應用程式將在 http://localhost:3000 啟動

### 3. 建構生產版本

```bash
npm run build
```

### 4. 預覽生產版本

```bash
npm run preview
```

## 開發指南

### 程式碼風格

```bash
# 檢查程式碼風格
npm run lint

# 自動修復程式碼風格
npm run lint:fix

# 類型檢查
npm run type-check
```

### 測試

```bash
# 執行單元測試
npm run test

# 執行測試並顯示 UI
npm run test:ui

# 執行測試覆蓋率
npm run test:coverage

# 執行 E2E 測試
npm run e2e

# 執行 E2E 測試並顯示 UI
npm run e2e:ui
```

## 設計系統

### 顏色主題

- **主色**: `primary-500` (#0ea5e9) - 霓虹藍
- **次要色**: `secondary-500` (#10b981) - 翠綠色
- **強調色**: `accent-500` (#8b5cf6) - 紫色
- **背景**: `dark-darker` (#020617) - 深色背景
- **卡片**: `dark-card` (#1e293b) - 卡片背景

### 狀態顏色

- **在線**: `status-online` (#10b981)
- **警告**: `status-warning` (#f59e0b)
- **離線**: `status-offline` (#ef4444)
- **未知**: `status-unknown` (#6b7280)

### 元件類別

- `.tech-button` - 技術風格按鈕
- `.tech-card` - 技術風格卡片
- `.metric-card` - 指標卡片
- `.server-item` - 伺服器列表項目
- `.status-dot` - 狀態指示點

## 功能特色

- ✅ 現代化 React 18 架構
- ✅ TypeScript 類型安全
- ✅ Tailwind CSS 樣式系統
- ✅ 響應式設計
- ✅ 深色主題
- ⏳ 即時數據更新
- ⏳ 互動式圖表
- ⏳ WebSocket 連接
- ⏳ 伺服器管理
- ⏳ 系統監控

## API 整合

前端通過 Vite 代理與後端 API 通訊：

- REST API: `http://localhost:8000/api/v1`
- WebSocket: `ws://localhost:8000/ws`

## 瀏覽器支援

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+