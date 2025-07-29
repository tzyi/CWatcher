// 圖表網格佈局元件

import React from 'react'
import { cn } from '@/utils'
import type { SystemMetrics } from '@/types'
import type { TimeRange } from './TimeRangeSelector'
import MetricChart from './MetricChart'
import TimeRangeSelector from './TimeRangeSelector'

interface ChartGridProps {
  data: SystemMetrics[]
  selectedRange: TimeRange
  onRangeChange: (range: TimeRange) => void
  loading?: boolean
  error?: string
  className?: string
}

/**
 * 圖表網格佈局元件
 * 根據原型設計，展示四個監控指標的時序圖表
 */
const ChartGrid: React.FC<ChartGridProps> = ({
  data,
  selectedRange,
  onRangeChange,
  loading = false,
  error,
  className,
}) => {
  return (
    <div className={cn('space-y-6', className)}>
      {/* 時間範圍選擇器 */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-text-primary">
          Performance Charts
        </h2>
        <TimeRangeSelector
          selectedRange={selectedRange}
          onRangeChange={onRangeChange}
          loading={loading}
        />
      </div>

      {/* 圖表網格 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU 使用率圖表 */}
        <MetricChart
          type="cpu"
          data={data}
          loading={loading}
          error={error}
          height={240}
        />

        {/* 記憶體使用率圖表 */}
        <MetricChart
          type="memory"
          data={data}
          loading={loading}
          error={error}
          height={240}
        />

        {/* 磁碟 I/O 圖表 */}
        <MetricChart
          type="disk"
          data={data}
          loading={loading}
          error={error}
          height={240}
        />

        {/* 網路流量圖表 */}
        <MetricChart
          type="network"
          data={data}
          loading={loading}
          error={error}
          height={240}
        />
      </div>

      {/* 全域錯誤狀態 */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <div className="flex items-center">
            <i className="fas fa-exclamation-triangle text-red-400 mr-3" />
            <div>
              <div className="text-red-400 font-medium">Chart Data Error</div>
              <div className="text-red-300 text-sm mt-1">{error}</div>
            </div>
          </div>
        </div>
      )}

      {/* 無資料狀態 */}
      {!loading && !error && data.length === 0 && (
        <div className="bg-dark-surface/50 border border-dark-border rounded-lg p-8">
          <div className="text-center">
            <i className="fas fa-chart-line text-4xl text-text-secondary mb-4" />
            <div className="text-text-primary text-lg font-medium mb-2">
              No Performance Data
            </div>
            <div className="text-text-secondary text-sm">
              Charts will appear here once monitoring data is available for the selected server.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChartGrid