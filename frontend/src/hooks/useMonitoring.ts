// 監控資料 Hook

import { useEffect, useCallback } from 'react'
import { useMonitoringStore, useServerStore } from '@/stores'
import { useWebSocket } from '@/hooks'
import type { TimeRange } from '@/types'

/**
 * 監控資料管理 Hook
 */
export default function useMonitoring(serverId?: string) {
  const {
    currentMetrics,
    historicalData,
    systemInfo,
    timeRange,
    autoRefresh,
    refreshInterval,
    loading,
    error,
    fetchCurrentMetrics,
    fetchHistoricalData,
    fetchSystemInfo,
    setTimeRange,
    setAutoRefresh,
    clearError,
  } = useMonitoringStore()

  const { selectedServer } = useServerStore()
  const { isConnected, subscribe, unsubscribe } = useWebSocket()

  // 使用傳入的 serverId 或當前選中的伺服器
  const targetServerId = serverId || selectedServer?.id

  // 取得當前伺服器的監控資料
  const serverMetrics = targetServerId ? currentMetrics[targetServerId] : null
  const serverSystemInfo = targetServerId ? systemInfo[targetServerId] : null
  
  // 取得歷史資料
  const getHistoricalData = useCallback((range?: TimeRange) => {
    const targetRange = range || timeRange
    return targetServerId ? historicalData[`${targetServerId}-${targetRange}`] : null
  }, [targetServerId, timeRange, historicalData])

  // 初始化監控資料
  const initializeMonitoring = useCallback(async (serverId: string) => {
    try {
      // 並行取得當前監控資料和系統資訊
      await Promise.all([
        fetchCurrentMetrics(serverId),
        fetchSystemInfo(serverId),
        fetchHistoricalData(serverId, timeRange),
      ])
    } catch (error) {
      console.error('初始化監控資料失敗:', error)
    }
  }, [fetchCurrentMetrics, fetchSystemInfo, fetchHistoricalData, timeRange])

  // 刷新監控資料
  const refreshMetrics = useCallback(async () => {
    if (!targetServerId) return

    try {
      await fetchCurrentMetrics(targetServerId)
    } catch (error) {
      console.error('刷新監控資料失敗:', error)
    }
  }, [targetServerId, fetchCurrentMetrics])

  // 載入歷史資料
  const loadHistoricalData = useCallback(async (range: TimeRange) => {
    if (!targetServerId) return

    try {
      await fetchHistoricalData(targetServerId, range)
    } catch (error) {
      console.error('載入歷史資料失敗:', error)
    }
  }, [targetServerId, fetchHistoricalData])

  // 切換時間範圍
  const changeTimeRange = useCallback((range: TimeRange) => {
    setTimeRange(range)
    if (targetServerId) {
      loadHistoricalData(range)
    }
  }, [setTimeRange, targetServerId, loadHistoricalData])

  // 當選中伺服器變更時
  useEffect(() => {
    if (targetServerId) {
      // 訂閱 WebSocket 更新
      if (isConnected) {
        subscribe(targetServerId)
      }
      
      // 初始化監控資料
      initializeMonitoring(targetServerId)
    }

    return () => {
      if (targetServerId && isConnected) {
        unsubscribe(targetServerId)
      }
    }
  }, [targetServerId, isConnected, subscribe, unsubscribe, initializeMonitoring])

  // 自動刷新機制
  useEffect(() => {
    if (!autoRefresh || !targetServerId || isConnected) return

    const interval = setInterval(() => {
      refreshMetrics()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, targetServerId, isConnected, refreshInterval, refreshMetrics])

  // WebSocket 連接狀態變化處理
  useEffect(() => {
    if (isConnected && targetServerId) {
      subscribe(targetServerId)
    }
  }, [isConnected, targetServerId, subscribe])

  return {
    // 資料
    metrics: serverMetrics,
    systemInfo: serverSystemInfo,
    historicalData: getHistoricalData(),
    
    // 設定
    timeRange,
    autoRefresh,
    refreshInterval,
    
    // 狀態
    loading,
    error,
    isConnected,
    
    // 操作方法
    refreshMetrics,
    loadHistoricalData,
    changeTimeRange,
    setAutoRefresh,
    clearError,
    
    // 工具方法
    getHistoricalData,
  }
}