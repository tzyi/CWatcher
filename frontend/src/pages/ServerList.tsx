// ServerList 伺服器列表頁面

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Server, Trash2, Edit, Eye, Play } from 'lucide-react'
import { Card, Button, Badge, Modal, Loading } from '@/components/common'
import { StatusBadge } from '@/components/common'
import { useServerStore } from '@/stores'
import { formatRelativeTime } from '@/utils'
import toast from 'react-hot-toast'

/**
 * 伺服器列表頁面
 */
const ServerList: React.FC = () => {
  const navigate = useNavigate()
  const { 
    servers, 
    loading, 
    error, 
    fetchServers, 
    deleteServer, 
    testConnection,
    clearError 
  } = useServerStore()
  
  const [deleteModal, setDeleteModal] = useState<{
    isOpen: boolean
    server: any
  }>({ isOpen: false, server: null })
  
  const [testingServers, setTestingServers] = useState<Set<string>>(new Set())

  // 載入伺服器列表
  useEffect(() => {
    fetchServers()
  }, [fetchServers])

  // 處理新增伺服器
  const handleAddServer = () => {
    navigate('/login')
  }

  // 處理查看伺服器
  const handleViewServer = (serverId: string) => {
    navigate(`/dashboard/${serverId}`)
  }

  // 處理編輯伺服器
  const handleEditServer = (serverId: string) => {
    navigate(`/servers/${serverId}/edit`)
  }

  // 處理刪除伺服器
  const handleDeleteServer = async () => {
    if (!deleteModal.server) return

    try {
      await deleteServer(deleteModal.server.id)
      setDeleteModal({ isOpen: false, server: null })
      toast.success('伺服器刪除成功')
    } catch (error) {
      // 錯誤處理已在 store 中完成
    }
  }

  // 處理測試連接
  const handleTestConnection = async (serverId: string) => {
    setTestingServers(prev => new Set(prev).add(serverId))
    
    try {
      const result = await testConnection(serverId)
      
      if (result) {
        toast.success('連接測試成功')
      }
    } catch (error) {
      // 錯誤處理已在 store 中完成
    } finally {
      setTestingServers(prev => {
        const newSet = new Set(prev)
        newSet.delete(serverId)
        return newSet
      })
    }
  }

  return (
    <div className="min-h-screen bg-dark-darker">
      {/* 頂部導航列 */}
      <header className="bg-dark-card border-b border-dark-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
                CWatcher
              </h1>
              <div className="h-6 w-px bg-dark-border" />
              <h2 className="text-lg font-semibold text-text-primary">
                伺服器管理
              </h2>
            </div>

            <Button
              onClick={handleAddServer}
              leftIcon={<Plus size={16} />}
            >
              新增伺服器
            </Button>
          </div>
        </div>
      </header>

      {/* 主要內容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 錯誤訊息 */}
        {error && (
          <div className="mb-6 p-4 bg-status-offline bg-opacity-20 border border-status-offline border-opacity-30 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-status-offline">{error}</p>
              <Button variant="ghost" size="sm" onClick={clearError}>
                關閉
              </Button>
            </div>
          </div>
        )}

        {/* 載入狀態 */}
        {loading === 'loading' && servers.length === 0 && (
          <div className="flex justify-center py-12">
            <Loading text="載入伺服器列表..." />
          </div>
        )}

        {/* 空狀態 */}
        {loading !== 'loading' && servers.length === 0 && (
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-dark-surface rounded-full mb-4">
              <Server className="w-8 h-8 text-text-secondary" />
            </div>
            <h3 className="text-lg font-semibold text-text-primary mb-2">
              尚未新增任何伺服器
            </h3>
            <p className="text-text-secondary mb-6">
              新增您的第一台 Linux 伺服器開始監控
            </p>
            <Button onClick={handleAddServer} leftIcon={<Plus size={16} />}>
              新增伺服器
            </Button>
          </div>
        )}

        {/* 伺服器列表 */}
        {servers.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {servers.map((server) => (
              <Card key={server.id} hover className="p-0">
                <div className="p-6">
                  {/* 伺服器基本資訊 */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-primary-500 bg-opacity-20 rounded-lg">
                        <Server className="w-5 h-5 text-primary-400" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-text-primary">
                          {server.name}
                        </h3>
                        <p className="text-sm text-text-secondary">
                          {server.host}:{server.port}
                        </p>
                      </div>
                    </div>
                    
                    <StatusBadge status={server.status} size="sm" />
                  </div>

                  {/* 伺服器詳情 */}
                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">使用者</span>
                      <span className="text-text-primary">{server.username}</span>
                    </div>
                    
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">認證類型</span>
                      <Badge variant="default" size="sm">
                        {server.authType === 'password' ? '密碼' : '金鑰'}
                      </Badge>
                    </div>
                    
                    {server.lastConnected && (
                      <div className="flex justify-between text-sm">
                        <span className="text-text-secondary">最後連接</span>
                        <span className="text-text-primary">
                          {formatRelativeTime(server.lastConnected)}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* 標籤 */}
                  {server.tags && server.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-4">
                      {server.tags.map((tag, index) => (
                        <Badge key={index} variant="info" size="sm">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* 描述 */}
                  {server.description && (
                    <p className="text-sm text-text-secondary mb-4 line-clamp-2">
                      {server.description}
                    </p>
                  )}
                </div>

                {/* 操作按鈕 */}
                <div className="px-6 py-4 bg-dark-surface bg-opacity-50 border-t border-dark-border">
                  <div className="flex items-center justify-between">
                    <div className="flex space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewServer(server.id)}
                        leftIcon={<Eye size={14} />}
                      >
                        查看
                      </Button>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditServer(server.id)}
                        leftIcon={<Edit size={14} />}
                      >
                        編輯
                      </Button>
                    </div>

                    <div className="flex space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        loading={testingServers.has(server.id)}
                        onClick={() => handleTestConnection(server.id)}
                        leftIcon={<Play size={14} />}
                      >
                        測試
                      </Button>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteModal({ isOpen: true, server })}
                        leftIcon={<Trash2 size={14} />}
                        className="text-status-offline hover:text-red-400"
                      >
                        刪除
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </main>

      {/* 刪除確認對話框 */}
      <Modal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, server: null })}
        title="確認刪除"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-text-secondary">
            確定要刪除伺服器 <span className="font-semibold text-text-primary">
              {deleteModal.server?.name}
            </span> 嗎？
          </p>
          
          <p className="text-sm text-status-warning">
            此操作將永久刪除伺服器資訊和所有相關的監控資料，無法復原。
          </p>

          <div className="flex space-x-3 pt-4">
            <Button
              variant="error"
              onClick={handleDeleteServer}
              loading={loading === 'loading'}
              fullWidth
            >
              確認刪除
            </Button>
            
            <Button
              variant="ghost"
              onClick={() => setDeleteModal({ isOpen: false, server: null })}
              disabled={loading === 'loading'}
              fullWidth
            >
              取消
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default ServerList