// WebSocket Hook

import { useEffect, useCallback } from 'react'
import { useWebSocketStore, useMonitoringStore } from '@/stores'
import { getWebSocketManager } from '@/services/websocket'
import type { MetricsUpdateMessage, ServerStatusMessage } from '@/types'

/**
 * WebSocket 連接和事件處理 Hook
 */
export default function useWebSocket() {
  const {
    isConnected,
    setConnected,
    setReconnectAttempts,
    setError,
    addSubscription,
    removeSubscription,
  } = useWebSocketStore()
  
  const { updateMetrics } = useMonitoringStore()
  
  const wsManager = getWebSocketManager()

  // 設定 WebSocket 事件處理器
  useEffect(() => {
    // 連接成功
    const handleConnect = () => {
      setConnected(true)
      setError(null)
    }

    // 連接斷開
    const handleDisconnect = (reason: string) => {
      setConnected(false)
      setError(`連接斷開: ${reason}`)
    }

    // 重連嘗試
    const handleReconnect = (attempt: number) => {
      setReconnectAttempts(attempt)
    }

    // 重連失敗
    const handleReconnectFailed = () => {
      setError('重連失敗，請檢查網路連接')
    }

    // 錯誤處理
    const handleError = (error: Error) => {
      setError(error.message)
    }

    // 監控資料更新
    const handleMetricsUpdate = (data: MetricsUpdateMessage) => {
      updateMetrics(data.serverId, data.metrics)
    }

    // 伺服器狀態更新
    const handleServerStatus = (data: ServerStatusMessage) => {
      // TODO: 更新伺服器狀態
      console.log('伺服器狀態更新:', data)
    }

    // 註冊事件處理器
    wsManager.on('onConnect', handleConnect)
    wsManager.on('onDisconnect', handleDisconnect)
    wsManager.on('onReconnect', handleReconnect)
    wsManager.on('onReconnectFailed', handleReconnectFailed)
    wsManager.on('onError', handleError)
    wsManager.on('onMetricsUpdate', handleMetricsUpdate)
    wsManager.on('onServerStatus', handleServerStatus)

    // 清理事件處理器
    return () => {
      wsManager.off('onConnect')
      wsManager.off('onDisconnect')
      wsManager.off('onReconnect')
      wsManager.off('onReconnectFailed')
      wsManager.off('onError')
      wsManager.off('onMetricsUpdate')
      wsManager.off('onServerStatus')
    }
  }, [
    setConnected,
    setReconnectAttempts,
    setError,
    updateMetrics,
    wsManager
  ])

  // 訂閱伺服器
  const subscribe = useCallback((serverId: string) => {
    wsManager.subscribe(serverId)
    addSubscription(serverId)
  }, [wsManager, addSubscription])

  // 取消訂閱
  const unsubscribe = useCallback((serverId: string) => {
    wsManager.unsubscribe(serverId)
    removeSubscription(serverId)
  }, [wsManager, removeSubscription])

  // 手動重連
  const reconnect = useCallback(() => {
    wsManager.reconnect()
  }, [wsManager])

  // 取得連接狀態
  const getStatus = useCallback(() => {
    return wsManager.getStatus()
  }, [wsManager])

  return {
    isConnected,
    subscribe,
    unsubscribe,
    reconnect,
    getStatus,
  }
}