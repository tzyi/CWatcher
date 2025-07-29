// 伺服器列表元件

import React, { useState, useMemo } from 'react'
import { Search, Plus } from 'lucide-react'
import { cn } from '@/utils'
import { useDebounce } from '@/hooks'
import type { Server } from '@/types'
import Button from '@/components/common/Button'
import Input from '@/components/common/Input'
import Loading from '@/components/common/Loading'
import ServerItem from './ServerItem'

interface ServerListProps {
  servers: Server[]
  selectedServer?: Server | null
  loading?: boolean
  onSelectServer?: (server: Server) => void
  onAddServer?: () => void
  className?: string
}

/**
 * 伺服器列表元件
 * 根據原型設計，提供搜尋、列表展示和新增功能
 */
const ServerList: React.FC<ServerListProps> = ({
  servers,
  selectedServer,
  loading = false,
  onSelectServer,
  onAddServer,
  className,
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedQuery = useDebounce(searchQuery, 300)

  // 過濾伺服器列表
  const filteredServers = useMemo(() => {
    if (!debouncedQuery.trim()) return servers

    const query = debouncedQuery.toLowerCase()
    return servers.filter(server => 
      server.host.toLowerCase().includes(query) ||
      server.name?.toLowerCase().includes(query) ||
      server.tags?.some(tag => tag.toLowerCase().includes(query))
    )
  }, [servers, debouncedQuery])

  // 按狀態分組排序
  const sortedServers = useMemo(() => {
    return [...filteredServers].sort((a, b) => {
      // 狀態優先級：online > warning > offline > unknown
      const statusOrder = { online: 0, warning: 1, offline: 2, unknown: 3 }
      const statusDiff = statusOrder[a.status] - statusOrder[b.status]
      
      if (statusDiff !== 0) return statusDiff
      
      // 相同狀態按名稱或主機排序
      const nameA = a.name || a.host
      const nameB = b.name || b.host
      return nameA.localeCompare(nameB)
    })
  }, [filteredServers])

  return (
    <aside 
      className={cn(
        'w-64 bg-dark-lighter border-r border-dark-border flex flex-col',
        className
      )}
    >
      {/* 搜尋框 */}
      <div className="p-4 border-b border-dark-border">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
          <Input
            type="text"
            placeholder="Search servers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-dark-surface border-dark-border focus:border-primary-500"
          />
        </div>
      </div>

      {/* 標題和統計 */}
      <div className="px-4 py-3 border-b border-dark-border">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
            Servers
          </h3>
          <span className="text-xs text-text-secondary bg-dark-surface px-2 py-1 rounded-full">
            {filteredServers.length}
          </span>
        </div>
      </div>

      {/* 伺服器列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loading size="md" />
          </div>
        ) : sortedServers.length === 0 ? (
          <div className="py-8 px-4 text-center">
            <div className="text-text-secondary text-sm">
              {searchQuery ? 'No servers found' : 'No servers added yet'}
            </div>
            {!searchQuery && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onAddServer}
                className="mt-2"
                leftIcon={<Plus className="h-4 w-4" />}
              >
                Add Server
              </Button>
            )}
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sortedServers.map((server) => (
              <ServerItem
                key={server.id}
                server={server}
                isSelected={selectedServer?.id === server.id}
                onClick={onSelectServer}
              />
            ))}
          </div>
        )}
      </div>

      {/* 新增伺服器按鈕 */}
      <div className="p-4 border-t border-dark-border">
        <Button
          variant="primary"
          size="md"
          fullWidth
          onClick={onAddServer}
          leftIcon={<Plus className="h-4 w-4" />}
          className="shadow-glow hover:shadow-glow-lg"
        >
          Add Server
        </Button>
      </div>

      {/* 狀態統計 */}
      {servers.length > 0 && (
        <div className="px-4 py-2 border-t border-dark-border bg-dark-surface/50">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-3">
              <div className="flex items-center">
                <div className="h-2 w-2 rounded-full bg-status-online mr-1" />
                <span className="text-text-secondary">
                  {servers.filter(s => s.status === 'online').length}
                </span>
              </div>
              <div className="flex items-center">
                <div className="h-2 w-2 rounded-full bg-status-warning mr-1" />
                <span className="text-text-secondary">
                  {servers.filter(s => s.status === 'warning').length}
                </span>
              </div>
              <div className="flex items-center">
                <div className="h-2 w-2 rounded-full bg-status-offline mr-1" />
                <span className="text-text-secondary">
                  {servers.filter(s => s.status === 'offline').length}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}

export default ServerList