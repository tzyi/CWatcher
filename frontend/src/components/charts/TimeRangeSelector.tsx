// 時間範圍選擇器元件

import React from 'react'
import { cn } from '@/utils'

export type TimeRange = '1h' | '6h' | '24h' | '7d'

interface TimeRangeOption {
  value: TimeRange
  label: string
  description: string
}

interface TimeRangeSelectorProps {
  selectedRange: TimeRange
  onRangeChange: (range: TimeRange) => void
  loading?: boolean
  className?: string
}

const timeRangeOptions: TimeRangeOption[] = [
  { value: '1h', label: '1H', description: 'Last hour' },
  { value: '6h', label: '6H', description: 'Last 6 hours' },
  { value: '24h', label: '24H', description: 'Last 24 hours' },
  { value: '7d', label: '7D', description: 'Last 7 days' },
]

/**
 * 時間範圍選擇器元件
 * 根據原型設計，提供 1h/6h/24h/7d 四個時間範圍選項
 */
const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({
  selectedRange,
  onRangeChange,
  loading = false,
  className,
}) => {
  return (
    <div className={cn('flex space-x-1', className)}>
      {timeRangeOptions.map((option) => {
        const isSelected = selectedRange === option.value
        
        return (
          <button
            key={option.value}
            onClick={() => onRangeChange(option.value)}
            disabled={loading}
            title={option.description}
            className={cn(
              'px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200',
              'border border-transparent',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              isSelected
                ? 'bg-primary-500 text-white border-primary-500 shadow-glow'
                : 'bg-dark-surface text-text-secondary hover:bg-dark-border hover:text-text-primary',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-dark-bg'
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export default TimeRangeSelector