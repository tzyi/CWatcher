// CWatcher API 客戶端服務

import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios'
import type {
  ApiResponse,
  Server,
  CreateServerRequest,
  UpdateServerRequest,
  SystemMetrics,
  SystemInfo,
  TimeRange,
  AppError
} from '@/types'
import { getErrorMessage } from '@/utils'
import toast from 'react-hot-toast'

// ======================== API 配置 ========================

/** API 基礎 URL */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** 請求超時時間 */
const REQUEST_TIMEOUT = 10000

/** API 端點配置 */
export const API_ENDPOINTS = {
  // 伺服器管理 - 基於後端 servers.py
  servers: '/api/v1/servers',
  serverById: (id: string) => `/api/v1/servers/${id}`,
  serverStatus: (id: string) => `/api/v1/servers/${id}/status`,
  serverMonitoring: (id: string) => `/api/v1/servers/${id}/monitoring`,
  pushServerData: (id: string) => `/api/v1/servers/${id}/push-now`,
  serversOverview: '/api/v1/servers/stats/overview',
  
  // 監控資料 - 基於後端 monitoring.py
  monitoringSummary: (serverId: string) => `/api/v1/servers/${serverId}/monitoring/summary`,
  monitoringMetrics: (serverId: string, metricType: string) => 
    `/api/v1/servers/${serverId}/monitoring/metrics/${metricType}`,
  monitoringTest: (serverId: string) => `/api/v1/servers/${serverId}/monitoring/test`,
  monitoringAlerts: (serverId: string) => `/api/v1/servers/${serverId}/monitoring/alerts`,
  monitoringThresholds: '/api/v1/monitoring/thresholds',
  monitoringBatch: '/api/v1/servers/monitoring/batch',
  
  // 數據管理 - 基於後端 data_management.py  
  chartTimeseries: '/api/v1/data/charts/timeseries',
  serverDashboard: (serverId: string) => `/api/v1/data/servers/${serverId}/dashboard`,
  chartsBatch: '/api/v1/data/charts/batch',
  dashboardBatch: '/api/v1/data/servers/dashboard/batch',
  historySummary: '/api/v1/data/history/summary',
  historyExport: '/api/v1/data/history/export',
  
  // SSH 管理 - 基於後端 ssh.py
  sshTest: '/api/v1/ssh/test-connection',
  sshExecute: (serverId: string) => `/api/v1/ssh/servers/${serverId}/execute`,
  sshStatus: (serverId: string) => `/api/v1/ssh/servers/${serverId}/status`,
  sshManagerStats: '/api/v1/ssh/manager/statistics',
  
  // 系統指令 - 基於後端 command.py
  commandExecute: '/api/v1/command/execute',
  commandPredefined: '/api/v1/command/predefined',
  systemInfo: '/api/v1/command/system-info',
  commandStats: '/api/v1/command/statistics',
  
  // WebSocket 管理
  websocketStats: '/api/v1/websocket/connections/stats',
  websocketConnections: '/api/v1/websocket/connections',
  websocketBroadcast: '/api/v1/websocket/broadcast',
  
  // 健康檢查
  health: '/api/v1/health',
  healthData: '/api/v1/data/health',
  healthWebsocket: '/api/v1/websocket/health',
} as const

// ======================== API 客戶端設定 ========================

/** 建立 Axios 實例 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: REQUEST_TIMEOUT,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // 請求攔截器
  client.interceptors.request.use(
    (config) => {
      // 可在此處添加認證 token
      // config.headers.Authorization = `Bearer ${getToken()}`
      
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
      return config
    },
    (error) => {
      console.error('[API] Request Error:', error)
      return Promise.reject(error)
    }
  )

  // 回應攔截器
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      console.log(`[API] ${response.status} ${response.config.url}`)
      return response
    },
    (error: AxiosError) => {
      console.error('[API] Response Error:', error)
      
      // 處理常見錯誤狀態
      if (error.response) {
        const { status, data } = error.response
        
        switch (status) {
          case 401:
            toast.error('認證失敗，請重新登入')
            // 可在此處處理登出邏輯
            break
          case 403:
            toast.error('權限不足')
            break
          case 404:
            toast.error('請求的資源不存在')
            break
          case 500:
            toast.error('伺服器內部錯誤')
            break
          default:
            toast.error(getErrorMessage(data) || '請求失敗')
        }
      } else if (error.request) {
        toast.error('網路連接錯誤，請檢查網路設定')
      } else {
        toast.error('請求設定錯誤')
      }
      
      return Promise.reject(error)
    }
  )

  return client
}

/** API 客戶端實例 */
export const apiClient = createApiClient()

// ======================== API 錯誤處理 ========================

/**
 * 轉換 API 錯誤為應用程式錯誤
 */
function transformApiError(error: unknown): AppError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError
    
    return {
      type: axiosError.response?.status === 401 ? 'authentication' :
            axiosError.response?.status === 403 ? 'authorization' :
            axiosError.response?.status === 422 ? 'validation' :
            axiosError.code === 'NETWORK_ERROR' ? 'network' : 'server',
      message: getErrorMessage(axiosError.response?.data) || axiosError.message,
      code: axiosError.response?.status || axiosError.code,
      details: axiosError.response?.data,
      timestamp: new Date().toISOString(),
    }
  }
  
  return {
    type: 'unknown',
    message: getErrorMessage(error),
    timestamp: new Date().toISOString(),
  }
}

/**
 * 安全的 API 請求包裝器
 */
async function safeApiCall<T>(
  apiCall: () => Promise<AxiosResponse<ApiResponse<T>>>
): Promise<T> {
  try {
    const response = await apiCall()
    
    if (!response.data.success) {
      throw new Error(response.data.message || 'API 請求失敗')
    }
    
    return response.data.data
  } catch (error) {
    const appError = transformApiError(error)
    throw appError
  }
}

// ======================== 伺服器管理 API ========================

export const serverApi = {
  /**
   * 取得所有伺服器列表
   */
  async getServers(): Promise<Server[]> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<Server[]>>(API_ENDPOINTS.servers)
    )
  },

  /**
   * 根據 ID 取得伺服器詳情
   */
  async getServerById(id: string): Promise<Server> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<Server>>(API_ENDPOINTS.serverById(id))
    )
  },

  /**
   * 新增伺服器
   */
  async createServer(serverData: CreateServerRequest): Promise<Server> {
    return safeApiCall(() => 
      apiClient.post<ApiResponse<Server>>(API_ENDPOINTS.servers, serverData)
    )
  },

  /**
   * 更新伺服器
   */
  async updateServer(serverData: UpdateServerRequest): Promise<Server> {
    return safeApiCall(() => 
      apiClient.put<ApiResponse<Server>>(
        API_ENDPOINTS.serverById(serverData.id), 
        serverData
      )
    )
  },

  /**
   * 刪除伺服器
   */
  async deleteServer(id: string): Promise<void> {
    return safeApiCall(() => 
      apiClient.delete<ApiResponse<void>>(API_ENDPOINTS.serverById(id))
    )
  },

  /**
   * 測試伺服器連接
   */
  async testConnection(id: string): Promise<{ success: boolean; message: string }> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<{ success: boolean; message: string }>>(
        API_ENDPOINTS.serverStatus(id)
      )
    )
  },
}

// ======================== 監控資料 API ========================

export const monitoringApi = {
  /**
   * 取得伺服器監控摘要
   */
  async getMonitoringSummary(serverId: string): Promise<SystemMetrics> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<SystemMetrics>>(
        API_ENDPOINTS.monitoringSummary(serverId)
      )
    )
  },

  /**
   * 取得特定指標數據
   */
  async getMetricsByType(
    serverId: string, 
    metricType: 'cpu' | 'memory' | 'disk' | 'network'
  ): Promise<any> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<any>>(
        API_ENDPOINTS.monitoringMetrics(serverId, metricType)
      )
    )
  },

  /**
   * 取得歷史監控資料 (圖表數據)
   */
  async getChartData(
    serverId: string, 
    timeRange: TimeRange = '1h'
  ): Promise<any> {
    return safeApiCall(() => 
      apiClient.post<ApiResponse<any>>(
        API_ENDPOINTS.chartTimeseries,
        { serverId, timeRange }
      )
    )
  },

  /**
   * 取得伺服器儀表板數據
   */
  async getDashboardData(serverId: string): Promise<any> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<any>>(
        API_ENDPOINTS.serverDashboard(serverId)
      )
    )
  },

  /**
   * 取得系統詳細資訊
   */
  async getSystemInfo(serverId: string): Promise<SystemInfo> {
    return safeApiCall(() => 
      apiClient.post<ApiResponse<SystemInfo>>(
        API_ENDPOINTS.systemInfo,
        { serverId }
      )
    )
  },

  /**
   * 測試監控連接
   */
  async testMonitoring(serverId: string): Promise<{ success: boolean; message: string }> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<{ success: boolean; message: string }>>(
        API_ENDPOINTS.monitoringTest(serverId)
      )
    )
  },

  /**
   * 取得監控警告
   */
  async getAlerts(serverId: string): Promise<any[]> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<any[]>>(
        API_ENDPOINTS.monitoringAlerts(serverId)
      )
    )
  },
}

// ======================== SSH 管理 API ========================

export const sshApi = {
  /**
   * 測試 SSH 連接
   */
  async testConnection(connectionData: {
    host: string
    port: number
    username: string
    password?: string
    privateKey?: string
  }): Promise<{ success: boolean; message: string }> {
    return safeApiCall(() => 
      apiClient.post<ApiResponse<{ success: boolean; message: string }>>(
        API_ENDPOINTS.sshTest,
        connectionData
      )
    )
  },

  /**
   * 執行 SSH 命令
   */
  async executeCommand(
    serverId: string,
    command: string
  ): Promise<{ output: string; exitCode: number }> {
    return safeApiCall(() => 
      apiClient.post<ApiResponse<{ output: string; exitCode: number }>>(
        API_ENDPOINTS.sshExecute(serverId),
        { command }
      )
    )
  },

  /**
   * 取得 SSH 連接狀態
   */
  async getConnectionStatus(serverId: string): Promise<any> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<any>>(
        API_ENDPOINTS.sshStatus(serverId)
      )
    )
  },

  /**
   * 取得 SSH 管理器統計
   */
  async getManagerStatistics(): Promise<any> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<any>>(
        API_ENDPOINTS.sshManagerStats
      )
    )
  },
}

// ======================== 健康檢查 API ========================

export const healthApi = {
  /**
   * 檢查 API 服務狀態
   */
  async checkHealth(): Promise<{ status: string; timestamp: string }> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<{ status: string; timestamp: string }>>(
        API_ENDPOINTS.health
      )
    )
  },

  /**
   * 檢查數據服務狀態
   */
  async checkDataHealth(): Promise<{ status: string; message: string }> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<{ status: string; message: string }>>(
        API_ENDPOINTS.healthData
      )
    )
  },

  /**
   * 檢查 WebSocket 服務狀態
   */
  async checkWebSocketHealth(): Promise<{ status: string; message: string }> {
    return safeApiCall(() => 
      apiClient.get<ApiResponse<{ status: string; message: string }>>(
        API_ENDPOINTS.healthWebsocket
      )
    )
  },
}

// ======================== 匯出 API 客戶端 ========================

/**
 * 統一的 API 客戶端
 */
export const api = {
  servers: serverApi,
  monitoring: monitoringApi,
  ssh: sshApi,
  health: healthApi,
}

/**
 * 重新設定 API 基礎 URL (用於開發環境切換)
 */
export function setApiBaseUrl(baseUrl: string): void {
  apiClient.defaults.baseURL = baseUrl
}

/**
 * 設定認證 token
 */
export function setAuthToken(token: string): void {
  apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

/**
 * 清除認證 token
 */
export function clearAuthToken(): void {
  delete apiClient.defaults.headers.common['Authorization']
}

export default api