// Loading 載入元件

import React from 'react'
import { cn } from '@/utils'

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg'
  text?: string
  fullScreen?: boolean
  className?: string
}

/**
 * 載入指示器元件
 */
const Loading: React.FC<LoadingProps> = ({
  size = 'md',
  text,
  fullScreen = false,
  className,
}) => {
  // 尺寸樣式
  const sizeStyles = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  }

  // 文字尺寸
  const textSizeStyles = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  }

  // 載入動畫
  const spinner = (
    <svg
      className={cn('animate-spin text-primary-500', sizeStyles[size])}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-dark-darker bg-opacity-75 flex items-center justify-center z-50">
        <div className="flex flex-col items-center space-y-4">
          {spinner}
          {text && (
            <p className={cn('text-text-primary', textSizeStyles[size])}>
              {text}
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('flex items-center justify-center', className)}>
      <div className="flex flex-col items-center space-y-2">
        {spinner}
        {text && (
          <p className={cn('text-text-secondary', textSizeStyles[size])}>
            {text}
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * 載入條元件
 */
export const LoadingBar: React.FC<{
  className?: string
}> = ({ className }) => {
  return (
    <div className={cn('loading-bar', className)} />
  )
}

/**
 * 骨架載入元件
 */
export const Skeleton: React.FC<{
  className?: string
  lines?: number
}> = ({ className, lines = 1 }) => {
  const skeletonLines = Array.from({ length: lines }, (_, index) => (
    <div
      key={index}
      className={cn(
        'h-4 bg-dark-surface rounded animate-pulse',
        index > 0 && 'mt-2',
        index === lines - 1 && lines > 1 && 'w-3/4' // 最後一行較短
      )}
    />
  ))

  return (
    <div className={cn('space-y-2', className)}>
      {skeletonLines}
    </div>
  )
}

/**
 * 卡片骨架載入元件
 */
export const SkeletonCard: React.FC<{
  className?: string
}> = ({ className }) => {
  return (
    <div className={cn('bg-dark-card p-6 rounded-lg border border-dark-border', className)}>
      <div className="animate-pulse">
        {/* 標題 */}
        <div className="h-6 bg-dark-surface rounded w-1/3 mb-4" />
        
        {/* 內容行 */}
        <div className="space-y-3">
          <div className="h-4 bg-dark-surface rounded" />
          <div className="h-4 bg-dark-surface rounded w-5/6" />
          <div className="h-4 bg-dark-surface rounded w-4/6" />
        </div>
        
        {/* 底部 */}
        <div className="mt-6 flex space-x-4">
          <div className="h-8 bg-dark-surface rounded w-20" />
          <div className="h-8 bg-dark-surface rounded w-16" />
        </div>
      </div>
    </div>
  )
}

export default Loading