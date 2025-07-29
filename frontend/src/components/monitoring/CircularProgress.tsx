// 圓形進度條元件

import React from 'react'
import { cn } from '@/utils'

interface CircularProgressProps {
  percentage: number
  size?: number
  strokeWidth?: number
  color?: string
  backgroundColor?: string
  showText?: boolean
  className?: string
}

/**
 * 圓形進度條元件
 * 根據原型設計，提供 CPU、記憶體和磁碟使用率的圓形視覺化
 */
const CircularProgress: React.FC<CircularProgressProps> = ({
  percentage,
  size = 64,
  strokeWidth = 3,
  color = '#3b82f6',
  backgroundColor = '#2d3748',
  showText = false,
  className,
}) => {
  // 計算 SVG 參數
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (percentage / 100) * circumference

  // 確保百分比在有效範圍內
  const clampedPercentage = Math.max(0, Math.min(100, percentage))

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
        viewBox={`0 0 ${size} ${size}`}
      >
        {/* 背景圓圈 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={backgroundColor}
          strokeWidth={strokeWidth}
          fill="none"
          className="opacity-30"
        />
        
        {/* 進度圓圈 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
          style={{
            filter: `drop-shadow(0 0 4px ${color}40)`,
          }}
        />
      </svg>
      
      {/* 中央文字 */}
      {showText && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-semibold text-text-primary">
            {Math.round(clampedPercentage)}%
          </span>
        </div>
      )}
    </div>
  )
}

export default CircularProgress