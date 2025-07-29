// Dashboard 儀表板頁面 - 完整實現原型設計

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart3, Plus, Settings, LogOut, RefreshCw } from 'lucide-react'
import { Button } from '@/components/common'
import { MetricCard, SystemInfo } from '@/components/monitoring'
import { ServerList, AddServerModal } from '@/components/servers'
import { ChartGrid } from '@/components/charts'
import type { TimeRange } from '@/components/charts/TimeRangeSelector'
import type { CreateServerRequest } from '@/types'
import { useServerStore } from '@/stores'
import { useMonitoring, useWebSocket } from '@/hooks'
import { cn } from '@/utils'
import toast from 'react-hot-toast'

/**
 * 主儀表板頁面 - 根據原型設計實現完整功能
 * 包含：左側伺服器列表、監控指標卡片、圖表系統、系統資訊面板
 */
const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  
  // 狀態管理
  const { 
    servers, 
    selectedServer, 
    selectServer, 
    createServer,
    loading: serverLoading,
    error: serverError 
  } = useServerStore()
  
  const { 
    metrics, 
    systemInfo, 
    loading: monitoringLoading, 
    error: monitoringError, 
    refreshMetrics,
    clearError 
  } = useMonitoring(selectedServer?.id)
  
  useWebSocket() // WebSocket 連接
  
  // 本地狀態
  const [showAddServerModal, setShowAddServerModal] = useState(false)
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>('1h')
  const [refreshing, setRefreshing] = useState(false)

  // 初始化選擇第一台伺服器（如果沒有選中的話）
  useEffect(() => {
    if (!selectedServer && servers.length > 0) {
      selectServer(servers[0])
    }
  }, [selectedServer, servers, selectServer])

  // 處理新增伺服器
  const handleAddServer = async (serverData: CreateServerRequest) => {
    try {
      const serverWithStatus = {
        ...serverData,
        status: 'unknown' as const,
        lastConnected: undefined,
      }
      await createServer(serverWithStatus)
      setShowAddServerModal(false)
      toast.success('Server added successfully!')
    } catch (error) {
      console.error('Failed to add server:', error)
      toast.error('Failed to add server')
    }
  }

  // 處理連接測試
  const handleTestConnection = async (_serverData: CreateServerRequest): Promise<boolean> => {
    try {
      // TODO: 實現連接測試 API 調用
      await new Promise(resolve => setTimeout(resolve, 2000)) // 模擬測試
      return true
    } catch (error) {
      toast.error('Connection test failed')
      return false
    }
  }

  // 處理刷新
  const handleRefresh = async () => {
    if (!selectedServer) return
    
    setRefreshing(true)
    try {
      await refreshMetrics()
      toast.success('Data refreshed')
    } catch (error) {
      toast.error('Failed to refresh data')
    } finally {
      setRefreshing(false)
    }
  }

  // 處理登出
  const handleLogout = () => {
    selectServer(null)
    navigate('/login')
  }

  return (
    <div className="h-screen flex flex-col bg-dark-darker">
      {/* 頂部導航列 - 根據原型設計 */}
      <header className="bg-dark-lighter border-b border-dark-border py-3 px-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          {/* 左側 - Logo 和標題 */}
          <div className="flex items-center space-x-3">
            <BarChart3 className="h-6 w-6 text-primary-500" />
            <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
              CWatcher
            </h1>
          </div>
          
          {/* 右側 - 當前伺服器和操作 */}
          <div className="flex items-center space-x-4">
            {selectedServer && (
              <div className="flex items-center space-x-2">
                <div className={cn(
                  'h-2 w-2 rounded-full',
                  selectedServer.status === 'online' ? 'bg-status-online shadow-online' :
                  selectedServer.status === 'warning' ? 'bg-status-warning shadow-warning' :
                  selectedServer.status === 'offline' ? 'bg-status-offline shadow-offline' :
                  'bg-status-unknown shadow-gray'
                )} />
                <span className="text-sm font-medium text-text-primary">
                  {selectedServer.host}
                </span>
              </div>
            )}
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAddServerModal(true)}
              className="text-text-secondary hover:text-text-primary"
            >
              <Plus className="h-4 w-4" />
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="text-text-secondary hover:text-text-primary"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* 主要內容區域 - 完全按原型佈局 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左側伺服器列表 */}
        <ServerList
          servers={servers}
          selectedServer={selectedServer}
          loading={serverLoading === 'loading'}
          onSelectServer={selectServer}
          onAddServer={() => setShowAddServerModal(true)}
        />
        
        {/* 主要內容區 */}
        <main className="flex-1 overflow-y-auto bg-dark-bg p-6">
          {/* 伺服器資訊標題區 */}
          {selectedServer && (
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-text-primary">
                  {selectedServer.name || selectedServer.host}
                </h2>
                <div className="flex items-center mt-1 space-x-3">
                  <span className="text-sm text-text-secondary">
                    {selectedServer.host}:{selectedServer.port}
                  </span>
                  <span className={cn(
                    'px-2 py-0.5 text-xs rounded-full',
                    selectedServer.status === 'online' ? 'bg-green-900/30 text-green-300' :
                    selectedServer.status === 'warning' ? 'bg-yellow-900/30 text-yellow-300' :
                    selectedServer.status === 'offline' ? 'bg-red-900/30 text-red-300' :
                    'bg-gray-900/30 text-gray-300'
                  )}>
                    {selectedServer.status === 'online' ? 'Online' :
                     selectedServer.status === 'warning' ? 'Warning' :
                     selectedServer.status === 'offline' ? 'Offline' : 'Unknown'}
                  </span>
                </div>
              </div>
              
              <div className="flex space-x-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRefresh}
                  loading={refreshing}
                  leftIcon={<RefreshCw className="h-4 w-4" />}
                  className="bg-dark-surface hover:bg-dark-border"
                >
                  Refresh
                </Button>
                
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Settings className="h-4 w-4" />}
                  className="bg-dark-surface hover:bg-dark-border"
                >
                  Settings
                </Button>
              </div>
            </div>
          )}

          {/* 錯誤訊息 */}
          {(serverError || monitoringError) && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <div className="flex items-center justify-between">
                <p className="text-red-400">{serverError || monitoringError}</p>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={clearError}
                  className="text-red-400 hover:text-red-300"
                >
                  ×
                </Button>
              </div>
            </div>
          )}

          {/* 無伺服器狀態 */}
          {servers.length === 0 && !serverLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <BarChart3 className="h-16 w-16 text-text-secondary mx-auto mb-4" />
                <h3 className="text-lg font-medium text-text-primary mb-2">
                  No Servers Added
                </h3>
                <p className="text-text-secondary mb-4">
                  Add your first server to start monitoring.
                </p>
                <Button
                  variant="primary"
                  onClick={() => setShowAddServerModal(true)}
                  leftIcon={<Plus className="h-4 w-4" />}
                  className="shadow-glow hover:shadow-glow-lg"
                >
                  Add Server
                </Button>
              </div>
            </div>
          ) : selectedServer && (
            <>
              {/* 系統概覽卡片 - 四大指標 */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                <MetricCard
                  type="cpu"
                  metrics={metrics || undefined}
                  loading={monitoringLoading === 'loading'}
                  error={monitoringError || undefined}
                />
                <MetricCard
                  type="memory"
                  metrics={metrics || undefined}
                  loading={monitoringLoading === 'loading'}
                  error={monitoringError || undefined}
                />
                <MetricCard
                  type="disk"
                  metrics={metrics || undefined}
                  loading={monitoringLoading === 'loading'}
                  error={monitoringError || undefined}
                />
                <MetricCard
                  type="network"
                  metrics={metrics || undefined}
                  loading={monitoringLoading === 'loading'}
                  error={monitoringError || undefined}
                />
              </div>

              {/* 圖表區域 */}
              <div className="mb-8">
                <ChartGrid
                  data={[]}
                  selectedRange={selectedTimeRange}
                  onRangeChange={setSelectedTimeRange}
                  loading={monitoringLoading === 'loading'}
                  error={monitoringError || undefined}
                />
              </div>

              {/* 系統資訊面板 */}
              <SystemInfo
                systemInfo={systemInfo || undefined}
                metrics={metrics || undefined}
                loading={monitoringLoading === 'loading'}
                error={monitoringError || undefined}
                className="mb-6"
              />
            </>
          )}
        </main>
      </div>

      {/* 新增伺服器模態視窗 */}
      <AddServerModal
        isOpen={showAddServerModal}
        onClose={() => setShowAddServerModal(false)}
        onSubmit={handleAddServer}
        onTestConnection={handleTestConnection}
      />
    </div>
  )
}

export default Dashboard