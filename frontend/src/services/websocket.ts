// CWatcher WebSocket 客戶端服務

import { io, Socket } from 'socket.io-client'
import type {
  SubscribeMessage,
  UnsubscribeMessage,
  MetricsUpdateMessage,
  ServerStatusMessage
} from '@/types'
import { getErrorMessage } from '@/utils'
import toast from 'react-hot-toast'

// ======================== WebSocket 配置 ========================

/** WebSocket 伺服器 URL */
const WEBSOCKET_URL = import.meta.env.VITE_WEBSOCKET_URL || 'http://localhost:8000'

/** 重連設定 */
const RECONNECT_CONFIG = {
  maxAttempts: 5,
  delay: 3000,
  backoffMultiplier: 1.5,
  maxDelay: 30000,
}

/** 心跳設定 */
const HEARTBEAT_CONFIG = {
  interval: 30000, // 30 秒
  timeout: 5000,   // 5 秒
}

// ======================== 事件類型定義 ========================

export interface WebSocketEventHandlers {
  onConnect: () => void
  onDisconnect: (reason: string) => void
  onReconnect: (attempt: number) => void
  onReconnectFailed: () => void
  onError: (error: Error) => void
  onMetricsUpdate: (data: MetricsUpdateMessage) => void
  onServerStatus: (data: ServerStatusMessage) => void
}

// ======================== WebSocket 管理器類別 ========================

export class WebSocketManager {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private heartbeatInterval: number | null = null
  private isReconnecting = false
  private subscriptions = new Set<string>()
  private eventHandlers: Partial<WebSocketEventHandlers> = {}

  constructor() {
    this.connect()
  }

  // ======================== 連接管理 ========================

  /**
   * 建立 WebSocket 連接
   */
  private connect(): void {
    try {
      console.log('[WebSocket] 正在連接到:', WEBSOCKET_URL)
      
      this.socket = io(WEBSOCKET_URL, {
        path: '/api/v1/websocket/ws/',
        transports: ['websocket'],
        timeout: 10000,
        reconnection: false, // 我們手動處理重連
      })

      this.setupEventListeners()
      this.startHeartbeat()
      
    } catch (error) {
      console.error('[WebSocket] 連接失敗:', error)
      this.handleError(new Error(getErrorMessage(error)))
    }
  }

  /**
   * 斷開 WebSocket 連接
   */
  public disconnect(): void {
    console.log('[WebSocket] 正在斷開連接')
    
    this.isReconnecting = false
    this.stopHeartbeat()
    
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
    
    this.subscriptions.clear()
    this.reconnectAttempts = 0
  }

  /**
   * 檢查連接狀態
   */
  public isConnected(): boolean {
    return this.socket?.connected ?? false
  }

  /**
   * 手動重連
   */
  public reconnect(): void {
    if (this.isReconnecting) return
    
    console.log('[WebSocket] 手動重連')
    this.disconnect()
    
    setTimeout(() => {
      this.connect()
    }, 1000)
  }

  // ======================== 事件處理 ========================

  /**
   * 設定事件監聽器
   */
  private setupEventListeners(): void {
    if (!this.socket) return

    // 連接成功
    this.socket.on('connect', () => {
      console.log('[WebSocket] 連接成功')
      this.reconnectAttempts = 0
      this.isReconnecting = false
      
      // 重新訂閱之前的伺服器
      this.resubscribeAll()
      
      this.eventHandlers.onConnect?.()
      toast.success('WebSocket 連接成功')
    })

    // 連接斷開
    this.socket.on('disconnect', (reason) => {
      console.log('[WebSocket] 連接斷開:', reason)
      this.stopHeartbeat()
      
      this.eventHandlers.onDisconnect?.(reason)
      
      // 如果不是手動斷開，嘗試重連
      if (reason !== 'io client disconnect' && !this.isReconnecting) {
        this.attemptReconnect()
      }
    })

    // 連接錯誤
    this.socket.on('connect_error', (error) => {
      console.error('[WebSocket] 連接錯誤:', error)
      this.handleError(error)
      
      if (!this.isReconnecting) {
        this.attemptReconnect()
      }
    })

    // 監控資料更新
    this.socket.on('metrics_update', (data: MetricsUpdateMessage) => {
      console.log('[WebSocket] 收到監控資料更新:', data.serverId)
      this.eventHandlers.onMetricsUpdate?.(data)
    })

    // 伺服器狀態更新
    this.socket.on('server_status', (data: ServerStatusMessage) => {
      console.log('[WebSocket] 收到伺服器狀態更新:', data.serverId, data.status)
      this.eventHandlers.onServerStatus?.(data)
    })

    // 錯誤訊息
    this.socket.on('error', (error) => {
      console.error('[WebSocket] 伺服器錯誤:', error)
      this.handleError(new Error(getErrorMessage(error)))
    })

    // Pong 回應 (心跳)
    this.socket.on('pong', () => {
      console.log('[WebSocket] 收到 pong 回應')
    })
  }

  /**
   * 註冊事件處理器
   */
  public on<K extends keyof WebSocketEventHandlers>(
    event: K,
    handler: WebSocketEventHandlers[K]
  ): void {
    this.eventHandlers[event] = handler
  }

  /**
   * 移除事件處理器
   */
  public off<K extends keyof WebSocketEventHandlers>(event: K): void {
    delete this.eventHandlers[event]
  }

  // ======================== 重連機制 ========================

  /**
   * 嘗試重連
   */
  private attemptReconnect(): void {
    if (this.isReconnecting) return
    
    this.isReconnecting = true
    this.reconnectAttempts++
    
    if (this.reconnectAttempts > RECONNECT_CONFIG.maxAttempts) {
      console.error('[WebSocket] 重連次數超過限制')
      this.isReconnecting = false
      this.eventHandlers.onReconnectFailed?.()
      toast.error('WebSocket 重連失敗，請檢查網路連接')
      return
    }
    
    const delay = Math.min(
      RECONNECT_CONFIG.delay * Math.pow(RECONNECT_CONFIG.backoffMultiplier, this.reconnectAttempts - 1),
      RECONNECT_CONFIG.maxDelay
    )
    
    console.log(`[WebSocket] 第 ${this.reconnectAttempts} 次重連嘗試，${delay}ms 後重試`)
    
    setTimeout(() => {
      if (this.isReconnecting) {
        this.disconnect()
        this.connect()
        this.eventHandlers.onReconnect?.(this.reconnectAttempts)
      }
    }, delay)
  }

  // ======================== 心跳機制 ========================

  /**
   * 啟動心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat()
    
    this.heartbeatInterval = window.setInterval(() => {
      if (this.isConnected()) {
        console.log('[WebSocket] 發送 ping')
        this.socket?.emit('ping')
      }
    }, HEARTBEAT_CONFIG.interval)
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      window.clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  // ======================== 訂閱管理 ========================

  /**
   * 訂閱伺服器監控資料
   */
  public subscribe(serverId: string, metrics?: ('cpu' | 'memory' | 'disk' | 'network')[]): void {
    if (!this.isConnected()) {
      console.warn('[WebSocket] 連接未建立，無法訂閱')
      return
    }

    const message: SubscribeMessage = {
      serverId,
      metrics,
    }

    console.log('[WebSocket] 訂閱伺服器:', serverId)
    this.socket?.emit('subscribe', message)
    this.subscriptions.add(serverId)
  }

  /**
   * 取消訂閱伺服器監控資料
   */
  public unsubscribe(serverId: string): void {
    if (!this.isConnected()) {
      console.warn('[WebSocket] 連接未建立，無法取消訂閱')
      return
    }

    const message: UnsubscribeMessage = {
      serverId,
    }

    console.log('[WebSocket] 取消訂閱伺服器:', serverId)
    this.socket?.emit('unsubscribe', message)
    this.subscriptions.delete(serverId)
  }

  /**
   * 重新訂閱所有伺服器
   */
  private resubscribeAll(): void {
    console.log('[WebSocket] 重新訂閱所有伺服器')
    const subscriptions = Array.from(this.subscriptions)
    this.subscriptions.clear()
    
    subscriptions.forEach(serverId => {
      this.subscribe(serverId)
    })
  }

  /**
   * 取得當前訂閱列表
   */
  public getSubscriptions(): string[] {
    return Array.from(this.subscriptions)
  }

  // ======================== 錯誤處理 ========================

  /**
   * 處理錯誤
   */
  private handleError(error: Error): void {
    console.error('[WebSocket] 錯誤:', error)
    this.eventHandlers.onError?.(error)
  }

  // ======================== 狀態資訊 ========================

  /**
   * 取得連接狀態資訊
   */
  public getStatus() {
    return {
      connected: this.isConnected(),
      reconnectAttempts: this.reconnectAttempts,
      isReconnecting: this.isReconnecting,
      subscriptions: this.getSubscriptions(),
    }
  }
}

// ======================== 單例 WebSocket 管理器 ========================

let websocketManager: WebSocketManager | null = null

/**
 * 取得 WebSocket 管理器實例
 */
export function getWebSocketManager(): WebSocketManager {
  if (!websocketManager) {
    websocketManager = new WebSocketManager()
  }
  return websocketManager
}

/**
 * 銷毀 WebSocket 管理器實例
 */
export function destroyWebSocketManager(): void {
  if (websocketManager) {
    websocketManager.disconnect()
    websocketManager = null
  }
}

// ======================== React Hook 友好的 API ========================

export interface UseWebSocketReturn {
  isConnected: boolean
  reconnectAttempts: number
  subscribe: (serverId: string) => void
  unsubscribe: (serverId: string) => void
  subscriptions: string[]
}

/**
 * WebSocket Hook 介面 (將在 hooks 中實現)
 */
export function createWebSocketHook() {
  const manager = getWebSocketManager()
  
  return {
    manager,
    on: manager.on.bind(manager),
    off: manager.off.bind(manager),
    subscribe: manager.subscribe.bind(manager),
    unsubscribe: manager.unsubscribe.bind(manager),
    isConnected: manager.isConnected.bind(manager),
    getStatus: manager.getStatus.bind(manager),
    reconnect: manager.reconnect.bind(manager),
  }
}

// ======================== 預設匯出 ========================

export default {
  getManager: getWebSocketManager,
  destroy: destroyWebSocketManager,
  create: createWebSocketHook,
}