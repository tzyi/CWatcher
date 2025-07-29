// CWatcher 前端應用程式類型定義

// ======================== 基礎類型 ========================

/** API 回應基礎類型 */
export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  message?: string
  timestamp?: string
}

/** 分頁資料類型 */
export interface PaginationInfo {
  page: number
  pageSize: number
  total: number
  totalPages: number
}

/** 分頁回應類型 */
export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: PaginationInfo
}

// ======================== 伺服器相關類型 ========================

/** 伺服器連接狀態 */
export type ServerStatus = 'online' | 'offline' | 'warning' | 'unknown'

/** SSH 認證類型 */
export type AuthType = 'password' | 'key'

/** 伺服器基礎資訊 */
export interface Server {
  id: string
  name: string
  host: string
  port: number
  username: string
  authType: AuthType
  status: ServerStatus
  lastConnected?: string
  createdAt: string
  updatedAt: string
  description?: string
  tags?: string[]
}

/** 新增伺服器請求 */
export interface CreateServerRequest {
  name: string
  host: string
  port: number
  username: string
  authType: AuthType
  password?: string
  privateKey?: string
  description?: string
  tags?: string[]
}

/** 更新伺服器請求 */
export interface UpdateServerRequest extends Partial<CreateServerRequest> {
  id: string
}

// ======================== 系統監控類型 ========================

/** CPU 監控資料 */
export interface CpuMetrics {
  usage: number // 使用率百分比
  cores: number // 核心數
  frequency: number // 頻率 (MHz)
  loadAverage: [number, number, number] // 1分鐘, 5分鐘, 15分鐘負載
  processes: number // 進程數
  threads: number // 線程數
}

/** 記憶體監控資料 */
export interface MemoryMetrics {
  usage: number // 使用率百分比
  total: number // 總記憶體 (bytes)
  used: number // 已使用 (bytes)
  free: number // 空閒 (bytes)
  available: number // 可用 (bytes)
  cached: number // 快取 (bytes)
  buffers: number // 緩衝區 (bytes)
  swapTotal: number // Swap 總量 (bytes)
  swapUsed: number // Swap 使用量 (bytes)
  swapUsage: number // Swap 使用率百分比
}

/** 磁碟分割區資訊 */
export interface DiskPartition {
  device: string // 設備名稱
  mountpoint: string // 掛載點
  filesystem: string // 檔案系統類型
  total: number // 總空間 (bytes)
  used: number // 已使用 (bytes)
  free: number // 空閒空間 (bytes)
  usage: number // 使用率百分比
}

/** 磁碟監控資料 */
export interface DiskMetrics {
  usage: number // 整體使用率百分比
  total: number // 總空間 (bytes)
  used: number // 已使用 (bytes)
  free: number // 空閒空間 (bytes)
  partitions: DiskPartition[] // 分割區詳情
  readPerSecond?: number // 每秒讀取字節數
  writePerSecond?: number // 每秒寫入字節數
  ioStats?: {
    readBytes: number // 累計讀取字節數
    writeBytes: number // 累計寫入字節數
    readOps: number // 讀取操作數
    writeOps: number // 寫入操作數
  }
}

/** 網路介面資訊 */
export interface NetworkInterface {
  name: string // 介面名稱
  ipAddress?: string // IP 地址
  macAddress?: string // MAC 地址
  mtu: number // 最大傳輸單元
  speed?: number // 介面速度 (Mbps)
  bytesReceived: number // 接收字節數
  bytesSent: number // 發送字節數
  packetsReceived: number // 接收封包數
  packetsSent: number // 發送封包數
  errorsReceived: number // 接收錯誤數
  errorsSent: number // 發送錯誤數
  droppedReceived: number // 接收丟棄數
  droppedSent: number // 發送丟棄數
}

/** 網路監控資料 */
export interface NetworkMetrics {
  totalReceived: number // 總接收字節數
  totalSent: number // 總發送字節數
  receivedPerSecond: number // 每秒接收速度 (bytes/s)
  sentPerSecond: number // 每秒發送速度 (bytes/s)
  interfaces: NetworkInterface[] // 網路介面詳情
}

/** 綜合系統監控資料 */
export interface SystemMetrics {
  serverId: string
  timestamp: string
  cpu: CpuMetrics
  memory: MemoryMetrics
  disk: DiskMetrics
  network: NetworkMetrics
}

// ======================== 系統資訊類型 ========================

/** 硬體資訊 */
export interface HardwareInfo {
  cpu: {
    model: string
    cores: number
    threads: number
    frequency: number // MHz
    cache?: string
    architecture: string
  }
  memory: {
    total: number // bytes
    slots: number
    type?: string // DDR4, DDR5 等
  }
  disk: {
    devices: Array<{
      name: string
      size: number // bytes
      type: string // SSD, HDD
      model?: string
    }>
  }
  network: {
    interfaces: Array<{
      name: string
      type: string // ethernet, wifi
      speed?: number // Mbps
    }>
  }
}

/** 軟體資訊 */
export interface SoftwareInfo {
  os: {
    name: string
    version: string
    architecture: string
    kernel: string
    uptime: number // seconds
  }
  services: Array<{
    name: string
    status: 'running' | 'stopped' | 'failed'
    description?: string
  }>
  packages?: Array<{
    name: string
    version: string
    description?: string
  }>
}

/** 系統詳細資訊 */
export interface SystemInfo {
  serverId: string
  hostname: string
  hardware: HardwareInfo
  software: SoftwareInfo
  lastUpdated: string
}

// ======================== 圖表相關類型 ========================

/** 時間範圍選項 */
export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d'

/** 圖表數據點 */
export interface ChartDataPoint {
  timestamp: string
  value: number
  label?: string
}

/** 圖表資料集 */
export interface ChartDataset {
  label: string
  data: ChartDataPoint[]
  color: string
  unit?: string
}

/** 圖表配置 */
export interface ChartConfig {
  type: 'line' | 'bar' | 'doughnut' | 'pie'
  title: string
  timeRange: TimeRange
  datasets: ChartDataset[]
  yAxisMax?: number
  showLegend?: boolean
  showGrid?: boolean
  animations?: boolean
}

// ======================== WebSocket 相關類型 ========================

/** WebSocket 訊息類型 */
export type WebSocketMessageType = 
  | 'subscribe'
  | 'unsubscribe' 
  | 'metrics_update'
  | 'server_status'
  | 'error'
  | 'ping'
  | 'pong'

/** WebSocket 基礎訊息 */
export interface WebSocketMessage<T = unknown> {
  type: WebSocketMessageType
  data: T
  timestamp: string
  serverId?: string
}

/** 訂閱請求 */
export interface SubscribeMessage {
  serverId: string
  metrics?: ('cpu' | 'memory' | 'disk' | 'network')[]
}

/** 取消訂閱請求 */
export interface UnsubscribeMessage {
  serverId: string
}

/** 指標更新訊息 */
export interface MetricsUpdateMessage {
  serverId: string
  metrics: SystemMetrics
}

/** 伺服器狀態訊息 */
export interface ServerStatusMessage {
  serverId: string
  status: ServerStatus
  message?: string
}

// ======================== 表單相關類型 ========================

/** 表單驗證錯誤 */
export interface FormError {
  field: string
  message: string
}

/** 載入狀態 */
export type LoadingState = 'idle' | 'loading' | 'success' | 'error'

/** 操作結果 */
export interface OperationResult<T = unknown> {
  success: boolean
  data?: T
  error?: string
  errors?: FormError[]
}

// ======================== UI 相關類型 ========================

/** 模態視窗 Props */
export interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  children: import('react').ReactNode
}

/** 按鈕變體 */
export type ButtonVariant = 
  | 'primary' 
  | 'secondary' 
  | 'success' 
  | 'warning' 
  | 'error' 
  | 'ghost'

/** 按鈕大小 */
export type ButtonSize = 'sm' | 'md' | 'lg'

/** 通知類型 */
export type NotificationType = 'success' | 'error' | 'warning' | 'info'

/** 通知選項 */
export interface NotificationOptions {
  duration?: number
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
  action?: {
    label: string
    onClick: () => void
  }
}

// ======================== 狀態管理相關類型 ========================

/** 應用程式狀態 */
export interface AppState {
  servers: Server[]
  currentServer: Server | null
  metrics: Record<string, SystemMetrics>
  systemInfo: Record<string, SystemInfo>
  isConnected: boolean
  lastUpdate: string | null
}

/** 伺服器狀態 */
export interface ServerState {
  servers: Server[]
  loading: LoadingState
  error: string | null
  selectedServer: Server | null
}

/** 監控狀態 */
export interface MonitoringState {
  metrics: Record<string, SystemMetrics>
  historicalData: Record<string, ChartDataPoint[]>
  timeRange: TimeRange
  autoRefresh: boolean
  refreshInterval: number
}

/** WebSocket 狀態 */
export interface WebSocketState {
  isConnected: boolean
  reconnectAttempts: number
  lastError: string | null
  subscriptions: Set<string>
}

// ======================== API 端點相關類型 ========================

/** API 端點 */
export interface ApiEndpoints {
  // 伺服器管理
  servers: string
  serverById: (id: string) => string
  testConnection: (id: string) => string
  
  // 監控資料
  metrics: (serverId: string) => string
  historicalMetrics: (serverId: string, timeRange: TimeRange) => string
  
  // 系統資訊
  systemInfo: (serverId: string) => string
  
  // WebSocket
  websocket: string
}

// ======================== 錯誤處理類型 ========================

/** 應用程式錯誤類型 */
export type AppErrorType = 
  | 'network'
  | 'authentication'
  | 'authorization'
  | 'validation'
  | 'server'
  | 'unknown'

/** 應用程式錯誤 */
export interface AppError {
  type: AppErrorType
  message: string
  code?: string | number
  details?: unknown
  timestamp: string
}

// ======================== 配置相關類型 ========================

/** 應用程式配置 */
export interface AppConfig {
  apiBaseUrl: string
  websocketUrl: string
  defaultRefreshInterval: number
  maxReconnectAttempts: number
  chartAnimations: boolean
  theme: 'dark' | 'light'
  language: 'zh-TW' | 'en'
}

// ======================== 匯出所有類型 ========================

// React 相關類型已通過 import React 自動可用