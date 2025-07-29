// 伺服器狀態指示器元件

import React from 'react'
import { cn } from '@/utils'
import type { ServerStatus } from '@/types'

interface ServerStatusBadgeProps {
  status: ServerStatus
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}

/**
 * 伺服器狀態指示器元件
 * 根據原型設計，提供點狀指示器和文字標籤
 */
const ServerStatusBadge: React.FC<ServerStatusBadgeProps> = ({
  status,
  size = 'md',
  showText = false,
  className,
}) => {
  // 狀態配置
  const statusConfig = {
    online: {
      dotClass: 'bg-status-online shadow-online',
      textClass: 'bg-green-900/20 text-green-300 border-green-500/30',
      text: 'Online',
    },
    warning: {
      dotClass: 'bg-status-warning shadow-warning',
      textClass: 'bg-yellow-900/20 text-yellow-300 border-yellow-500/30',
      text: 'Warning',
    },
    offline: {
      dotClass: 'bg-status-offline shadow-offline',
      textClass: 'bg-red-900/20 text-red-300 border-red-500/30',
      text: 'Offline',
    },
    unknown: {
      dotClass: 'bg-gray-500 shadow-gray',
      textClass: 'bg-gray-900/20 text-gray-300 border-gray-500/30',
      text: 'Unknown',
    },
  }

  // 尺寸配置
  const sizeConfig = {
    sm: {
      dotSize: 'h-2 w-2',
      textSize: 'text-xs px-2 py-0.5',
    },
    md: {
      dotSize: 'h-2.5 w-2.5',
      textSize: 'text-sm px-2 py-1',
    },
    lg: {
      dotSize: 'h-3 w-3',
      textSize: 'text-sm px-3 py-1',
    },
  }

  const config = statusConfig[status]
  const sizes = sizeConfig[size]

  if (showText) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-full border font-medium',
          sizes.textSize,
          config.textClass,
          className
        )}
      >
        <span
          className={cn(
            'rounded-full mr-1.5',
            sizes.dotSize,
            config.dotClass
          )}
        />
        {config.text}
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-block rounded-full',
        sizes.dotSize,
        config.dotClass,
        className
      )}
    />
  )
}

export default ServerStatusBadge