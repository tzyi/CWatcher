// Badge 基礎元件

import React from 'react'
import { cn } from '@/utils'
import type { ServerStatus } from '@/types'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  status?: ServerStatus
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
  children: React.ReactNode
}

/**
 * 徽章元件
 */
const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  status,
  size = 'md',
  dot = false,
  className,
  children,
  ...props
}) => {
  // 根據 status 自動設定 variant
  const finalVariant = status
    ? status === 'online'
      ? 'success'
      : status === 'warning'
      ? 'warning'
      : status === 'offline'
      ? 'error'
      : 'default'
    : variant

  // 變體樣式
  const variantStyles = {
    default: 'bg-dark-surface text-text-secondary border-dark-border',
    success: 'bg-status-online bg-opacity-20 text-status-online border-status-online border-opacity-30',
    warning: 'bg-status-warning bg-opacity-20 text-status-warning border-status-warning border-opacity-30',
    error: 'bg-status-offline bg-opacity-20 text-status-offline border-status-offline border-opacity-30',
    info: 'bg-primary-500 bg-opacity-20 text-primary-400 border-primary-500 border-opacity-30',
  }

  // 尺寸樣式
  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  }

  // 基礎樣式
  const baseStyles = 'inline-flex items-center rounded-full border font-medium'

  // 狀態點樣式
  const dotColor = {
    default: 'bg-text-secondary',
    success: 'bg-status-online',
    warning: 'bg-status-warning',
    error: 'bg-status-offline',
    info: 'bg-primary-400',
  }

  return (
    <span
      className={cn(
        baseStyles,
        variantStyles[finalVariant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {/* 狀態點 */}
      {dot && (
        <span
          className={cn(
            'w-2 h-2 rounded-full mr-2 flex-shrink-0',
            dotColor[finalVariant],
            finalVariant === 'success' && 'shadow-[0_0_4px_rgba(16,185,129,0.5)]',
            finalVariant === 'warning' && 'shadow-[0_0_4px_rgba(245,158,11,0.5)]',
            finalVariant === 'error' && 'shadow-[0_0_4px_rgba(239,68,68,0.5)]'
          )}
        />
      )}
      
      {children}
    </span>
  )
}

/**
 * 狀態徽章元件 (專門用於顯示伺服器狀態)
 */
export const StatusBadge: React.FC<{
  status: ServerStatus
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}> = ({ status, size = 'md', showText = true, className }) => {
  const statusText = {
    online: '在線',
    offline: '離線',
    warning: '警告',
    unknown: '未知',
  }

  return (
    <Badge
      status={status}
      size={size}
      dot={true}
      className={className}
    >
      {showText && statusText[status]}
    </Badge>
  )
}

export default Badge