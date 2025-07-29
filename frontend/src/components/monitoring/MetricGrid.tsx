// 指標網格佈局元件

import React from 'react'
import { cn } from '@/utils'
import type { SystemMetrics } from '@/types'
import MetricCard from './MetricCard'

interface MetricGridProps {
  metrics?: SystemMetrics
  loading?: boolean
  error?: string
  className?: string
}

/**
 * 指標網格佈局元件
 * 根據原型設計，以 2x2 網格展示 CPU、記憶體、磁碟和網路監控卡片
 */
const MetricGrid: React.FC<MetricGridProps> = ({
  metrics,
  loading = false,
  error,
  className,
}) => {
  return (
    <div 
      className={cn(
        'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
        className
      )}
    >
      <MetricCard
        type="cpu"
        metrics={metrics}
        loading={loading}
        error={error}
      />
      
      <MetricCard
        type="memory"
        metrics={metrics}
        loading={loading}
        error={error}
      />
      
      <MetricCard
        type="disk"
        metrics={metrics}
        loading={loading}
        error={error}
      />
      
      <MetricCard
        type="network"
        metrics={metrics}
        loading={loading}
        error={error}
      />
    </div>
  )
}

export default MetricGrid