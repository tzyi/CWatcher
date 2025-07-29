// 伺服器項目元件

import React from 'react'
import { cn } from '@/utils'
import type { Server } from '@/types'
import ServerStatusBadge from './ServerStatusBadge'

interface ServerItemProps {
  server: Server
  isSelected?: boolean
  onClick?: (server: Server) => void
}

/**
 * 伺服器項目元件
 * 根據原型設計，展示伺服器的基本資訊和狀態
 */
const ServerItem: React.FC<ServerItemProps> = ({
  server,
  isSelected = false,
  onClick,
}) => {
  const handleClick = () => {
    onClick?.(server)
  }

  return (
    <div
      className={cn(
        'group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200',
        'border-l-3 border-transparent hover:border-l-primary-500',
        'hover:bg-primary-500/10 hover:backdrop-blur-sm',
        {
          'border-l-primary-500 bg-primary-500/15 shadow-glow': isSelected,
        }
      )}
      onClick={handleClick}
    >
      <div className="flex items-center min-w-0 flex-1">
        {/* 狀態指示器 */}
        <ServerStatusBadge 
          status={server.status} 
          size="md" 
          className="mr-3 flex-shrink-0" 
        />
        
        {/* 伺服器資訊 */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center">
            <span 
              className={cn(
                'font-medium truncate transition-colors duration-200',
                isSelected ? 'text-primary-300' : 'text-text-primary',
                'group-hover:text-primary-300'
              )}
            >
              {server.host}
            </span>
            {server.port !== 22 && (
              <span className="ml-1 text-text-secondary text-sm">
                :{server.port}
              </span>
            )}
          </div>
          
          {server.name && (
            <div className="text-text-secondary text-sm truncate mt-0.5">
              {server.name}
            </div>
          )}
        </div>
      </div>

      {/* 右側資訊 */}
      <div className="flex items-center space-x-2 ml-2 flex-shrink-0">
        {/* 標籤 */}
        {server.tags && server.tags.length > 0 && (
          <div className="hidden sm:flex space-x-1">
            {server.tags.slice(0, 2).map((tag, index) => (
              <span
                key={index}
                className="inline-block px-2 py-0.5 text-xs rounded-full bg-dark-surface text-text-secondary border border-dark-border"
              >
                {tag}
              </span>
            ))}
            {server.tags.length > 2 && (
              <span className="text-xs text-text-secondary">
                +{server.tags.length - 2}
              </span>
            )}
          </div>
        )}

        {/* 連接時間 */}
        {server.lastConnected && (
          <div className="text-xs text-text-secondary hidden md:block">
            {new Date(server.lastConnected).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  )
}

export default ServerItem