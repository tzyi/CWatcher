// CWatcher Zustand 狀態管理中心

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'
import type {
  Server,
  SystemMetrics,
  SystemInfo,
  TimeRange,
  LoadingState,
  ChartDataPoint,
  AppConfig,
} from '@/types'
import { api } from '@/services/api'
import { getWebSocketManager } from '@/services/websocket'
import { getErrorMessage } from '@/utils'
import toast from 'react-hot-toast'

// ======================== 應用程式狀態 ========================

export interface AppStore {
  // 基礎狀態
  isInitialized: boolean
  isLoading: boolean
  error: string | null
  
  // 配置
  config: AppConfig
  
  // 初始化和配置
  initialize: () => Promise<void>
  setConfig: (config: Partial<AppConfig>) => void
  clearError: () => void
}

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      immer((set, get) => ({
        // 初始狀態
        isInitialized: false,
        isLoading: false,
        error: null,
        
        // 預設配置
        config: {
          apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
          websocketUrl: import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000',
          defaultRefreshInterval: 30000,
          maxReconnectAttempts: 5,
          chartAnimations: true,
          theme: 'dark',
          language: 'zh-TW',
        },

        // 初始化應用程式
        initialize: async () => {
          if (get().isInitialized) return
          
          set((state) => {
            state.isLoading = true
            state.error = null
          })

          try {
            // 檢查 API 健康狀態
            await api.health.checkHealth()
            
            set((state) => {
              state.isInitialized = true
              state.isLoading = false
            })
            
            console.log('[App] 應用程式初始化完成')
          } catch (error) {
            const errorMessage = getErrorMessage(error)
            set((state) => {
              state.error = errorMessage
              state.isLoading = false
            })
            console.error('[App] 初始化失敗:', errorMessage)
          }
        },

        // 設定配置
        setConfig: (newConfig) => {
          set((state) => {
            Object.assign(state.config, newConfig)
          })
        },

        // 清除錯誤
        clearError: () => {
          set((state) => {
            state.error = null
          })
        },
      })),
      {
        name: 'cwatcher-app',
        partialize: (state) => ({ config: state.config }),
      }
    ),
    { name: 'AppStore' }
  )
)

// ======================== 伺服器狀態 ========================

export interface ServerStore {
  // 伺服器列表
  servers: Server[]
  selectedServer: Server | null
  
  // 載入狀態
  loading: LoadingState
  error: string | null
  
  // 操作方法
  fetchServers: () => Promise<void>
  selectServer: (server: Server | null) => void
  createServer: (serverData: Omit<Server, 'id' | 'createdAt' | 'updatedAt'>) => Promise<Server>
  updateServer: (id: string, serverData: Partial<Server>) => Promise<Server>
  deleteServer: (id: string) => Promise<void>
  testConnection: (id: string) => Promise<boolean>
  clearError: () => void
}

export const useServerStore = create<ServerStore>()(
  devtools(
    immer((set, get) => ({
      // 初始狀態
      servers: [],
      selectedServer: null,
      loading: 'idle',
      error: null,

      // 取得伺服器列表
      fetchServers: async () => {
        set((state) => {
          state.loading = 'loading'
          state.error = null
        })

        try {
          const servers = await api.servers.getServers()
          
          set((state) => {
            state.servers = servers
            state.loading = 'success'
            
            // 如果目前選中的伺服器不在列表中，清除選擇
            if (state.selectedServer && 
                !servers.find((s: Server) => s.id === state.selectedServer!.id)) {
              state.selectedServer = null
            }
          })
        } catch (error) {
          const errorMessage = getErrorMessage(error)
          set((state) => {
            state.error = errorMessage
            state.loading = 'error'
          })
          toast.error(`載入伺服器列表失敗: ${errorMessage}`)
        }
      },

      // 選擇伺服器
      selectServer: (server) => {
        set((state) => {
          state.selectedServer = server
        })
        
        // 管理 WebSocket 訂閱
        const wsManager = getWebSocketManager()
        
        if (get().selectedServer) {
          wsManager.unsubscribe(get().selectedServer!.id)
        }
        
        if (server) {
          wsManager.subscribe(server.id)
        }
      },

      // 新增伺服器
      createServer: async (serverData) => {
        set((state) => {
          state.loading = 'loading'
          state.error = null
        })

        try {
          const newServer = await api.servers.createServer(serverData as any)
          
          set((state) => {
            state.servers.push(newServer)
            state.loading = 'success'
          })
          
          toast.success('伺服器新增成功')
          return newServer
        } catch (error) {
          const errorMessage = getErrorMessage(error)
          set((state) => {
            state.error = errorMessage
            state.loading = 'error'
          })
          toast.error(`新增伺服器失敗: ${errorMessage}`)
          throw error
        }
      },

      // 更新伺服器
      updateServer: async (id, serverData) => {
        set((state) => {
          state.loading = 'loading'
          state.error = null
        })

        try {
          const updatedServer = await api.servers.updateServer({ id, ...serverData } as any)
          
          set((state) => {
            const index = state.servers.findIndex((s: Server) => s.id === id)
            if (index !== -1) {
              state.servers[index] = updatedServer
            }
            
            if (state.selectedServer?.id === id) {
              state.selectedServer = updatedServer
            }
            
            state.loading = 'success'
          })
          
          toast.success('伺服器更新成功')
          return updatedServer
        } catch (error) {
          const errorMessage = getErrorMessage(error)
          set((state) => {
            state.error = errorMessage
            state.loading = 'error'
          })
          toast.error(`更新伺服器失敗: ${errorMessage}`)
          throw error
        }
      },

      // 刪除伺服器
      deleteServer: async (id) => {
        set((state) => {
          state.loading = 'loading'
          state.error = null
        })

        try {
          await api.servers.deleteServer(id)
          
          set((state) => {
            state.servers = state.servers.filter((s: Server) => s.id !== id)
            
            if (state.selectedServer?.id === id) {
              state.selectedServer = null
            }
            
            state.loading = 'success'
          })
          
          // 取消 WebSocket 訂閱
          const wsManager = getWebSocketManager()
          wsManager.unsubscribe(id)
          
          toast.success('伺服器刪除成功')
        } catch (error) {
          const errorMessage = getErrorMessage(error)
          set((state) => {
            state.error = errorMessage
            state.loading = 'error'
          })
          toast.error(`刪除伺服器失敗: ${errorMessage}`)
          throw error
        }
      },

      // 測試連接
      testConnection: async (id) => {
        try {
          const result = await api.servers.testConnection(id)
          
          if (result.success) {
            toast.success('連接測試成功')
            return true
          } else {
            toast.error(`連接測試失敗: ${result.message}`)
            return false
          }
        } catch (error) {
          const errorMessage = getErrorMessage(error)
          toast.error(`連接測試失敗: ${errorMessage}`)
          return false
        }
      },

      // 清除錯誤
      clearError: () => {
        set((state) => {
          state.error = null
        })
      },
    })),
    { name: 'ServerStore' }
  )
)

// ======================== 監控資料狀態 ========================

export interface MonitoringStore {
  // 監控資料
  currentMetrics: Record<string, SystemMetrics>
  historicalData: Record<string, ChartDataPoint[]>
  systemInfo: Record<string, SystemInfo>
  
  // 設定
  timeRange: TimeRange
  autoRefresh: boolean
  refreshInterval: number
  
  // 載入狀態
  loading: LoadingState
  error: string | null
  
  // 操作方法
  fetchCurrentMetrics: (serverId: string) => Promise<void>
  fetchHistoricalData: (serverId: string, timeRange?: TimeRange) => Promise<void>
  fetchSystemInfo: (serverId: string) => Promise<void>
  updateMetrics: (serverId: string, metrics: SystemMetrics) => void
  setTimeRange: (timeRange: TimeRange) => void
  setAutoRefresh: (enabled: boolean) => void
  setRefreshInterval: (interval: number) => void
  clearData: (serverId?: string) => void
  clearError: () => void
}

export const useMonitoringStore = create<MonitoringStore>()(
  devtools(
    persist(
      immer((set, get) => ({
        // 初始狀態
        currentMetrics: {},
        historicalData: {},
        systemInfo: {},
        timeRange: '1h',
        autoRefresh: true,
        refreshInterval: 30000,
        loading: 'idle',
        error: null,

        // 取得當前監控資料
        fetchCurrentMetrics: async (serverId) => {
          set((state) => {
            state.loading = 'loading'
            state.error = null
          })

          try {
            const metrics = await api.monitoring.getMonitoringSummary(serverId)
            
            set((state) => {
              state.currentMetrics[serverId] = metrics
              state.loading = 'success'
            })
          } catch (error) {
            const errorMessage = getErrorMessage(error)
            set((state) => {
              state.error = errorMessage
              state.loading = 'error'
            })
          }
        },

        // 取得歷史資料
        fetchHistoricalData: async (serverId, timeRange) => {
          const targetTimeRange = timeRange || get().timeRange
          
          try {
            const data = await api.monitoring.getChartData(serverId, targetTimeRange)
            
            // 轉換為圖表資料格式
            const chartData: ChartDataPoint[] = data.map((metrics: any) => ({
              timestamp: metrics.timestamp,
              value: metrics.cpu?.usage || 0, // 預設顯示 CPU 使用率
            }))
            
            set((state) => {
              state.historicalData[`${serverId}-${targetTimeRange}`] = chartData
            })
          } catch (error) {
            const errorMessage = getErrorMessage(error)
            set((state) => {
              state.error = errorMessage
            })
          }
        },

        // 取得系統資訊
        fetchSystemInfo: async (serverId) => {
          try {
            const systemInfo = await api.monitoring.getSystemInfo(serverId)
            
            set((state) => {
              state.systemInfo[serverId] = systemInfo
            })
          } catch (error) {
            const errorMessage = getErrorMessage(error)
            set((state) => {
              state.error = errorMessage
            })
          }
        },

        // 更新監控資料 (WebSocket)
        updateMetrics: (serverId, metrics) => {
          set((state) => {
            state.currentMetrics[serverId] = metrics
          })
        },

        // 設定時間範圍
        setTimeRange: (timeRange) => {
          set((state) => {
            state.timeRange = timeRange
          })
        },

        // 設定自動刷新
        setAutoRefresh: (enabled) => {
          set((state) => {
            state.autoRefresh = enabled
          })
        },

        // 設定刷新間隔
        setRefreshInterval: (interval) => {
          set((state) => {
            state.refreshInterval = interval
          })
        },

        // 清除資料
        clearData: (serverId) => {
          set((state) => {
            if (serverId) {
              delete state.currentMetrics[serverId]
              delete state.systemInfo[serverId]
              
              // 清除相關的歷史資料
              Object.keys(state.historicalData).forEach(key => {
                if (key.startsWith(`${serverId}-`)) {
                  delete state.historicalData[key]
                }
              })
            } else {
              state.currentMetrics = {}
              state.historicalData = {}
              state.systemInfo = {}
            }
          })
        },

        // 清除錯誤
        clearError: () => {
          set((state) => {
            state.error = null
          })
        },
      })),
      {
        name: 'cwatcher-monitoring',
        partialize: (state) => ({
          timeRange: state.timeRange,
          autoRefresh: state.autoRefresh,
          refreshInterval: state.refreshInterval,
        }),
      }
    ),
    { name: 'MonitoringStore' }
  )
)

// ======================== WebSocket 狀態 ========================

export interface WebSocketStore {
  isConnected: boolean
  reconnectAttempts: number
  lastError: string | null
  subscriptions: Set<string>
  
  setConnected: (connected: boolean) => void
  setReconnectAttempts: (attempts: number) => void
  setError: (error: string | null) => void
  addSubscription: (serverId: string) => void
  removeSubscription: (serverId: string) => void
  clearSubscriptions: () => void
}

export const useWebSocketStore = create<WebSocketStore>()(
  devtools(
    immer((set) => ({
      isConnected: false,
      reconnectAttempts: 0,
      lastError: null,
      subscriptions: new Set(),

      setConnected: (connected) => {
        set((state) => {
          state.isConnected = connected
          if (connected) {
            state.lastError = null
            state.reconnectAttempts = 0
          }
        })
      },

      setReconnectAttempts: (attempts) => {
        set((state) => {
          state.reconnectAttempts = attempts
        })
      },

      setError: (error) => {
        set((state) => {
          state.lastError = error
        })
      },

      addSubscription: (serverId) => {
        set((state) => {
          state.subscriptions.add(serverId)
        })
      },

      removeSubscription: (serverId) => {
        set((state) => {
          state.subscriptions.delete(serverId)
        })
      },

      clearSubscriptions: () => {
        set((state) => {
          state.subscriptions.clear()
        })
      },
    })),
    { name: 'WebSocketStore' }
  )
)

// ======================== 組合 Store Hook ========================

/**
 * 組合所有 Store 的 Hook
 */
export function useStores() {
  const app = useAppStore()
  const servers = useServerStore()
  const monitoring = useMonitoringStore()
  const websocket = useWebSocketStore()

  return {
    app,
    servers,
    monitoring,
    websocket,
  }
}

// ======================== 匯出所有 Store ========================

export {
  useAppStore as useApp,
  useServerStore as useServers,
  useMonitoringStore as useMonitoring,
  useWebSocketStore as useWebSocket,
}