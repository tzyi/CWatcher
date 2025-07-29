// 監控指標卡片元件

import React from 'react'
import { Cpu, MemoryStick, HardDrive, Network, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '@/utils'
import type { SystemMetrics } from '@/types'
import CircularProgress from './CircularProgress'
import Loading from '@/components/common/Loading'

interface MetricCardProps {
  type: 'cpu' | 'memory' | 'disk' | 'network'
  metrics?: SystemMetrics
  loading?: boolean
  error?: string
  className?: string
}

/**
 * 監控指標卡片元件
 * 根據原型設計，顯示 CPU、記憶體、磁碟和網路的即時監控數據
 */
const MetricCard: React.FC<MetricCardProps> = ({
  type,
  metrics,
  loading = false,
  error,
  className,
}) => {
  // 卡片配置
  const cardConfig = {
    cpu: {
      title: 'CPU',
      icon: <Cpu className="h-5 w-5" />,
      color: '#3b82f6',
      unit: '%',
    },
    memory: {
      title: 'Memory',
      icon: <MemoryStick className="h-5 w-5" />,
      color: '#8b5cf6',
      unit: '%',
    },
    disk: {
      title: 'Disk',
      icon: <HardDrive className="h-5 w-5" />,
      color: '#10b981',
      unit: '%',
    },
    network: {
      title: 'Network',
      icon: <Network className="h-5 w-5" />,
      color: '#f59e0b',
      unit: 'MB/s',
    },
  }

  const config = cardConfig[type]

  // 計算數據
  const getMetricData = () => {
    if (!metrics) return null

    switch (type) {
      case 'cpu':
        return {
          percentage: metrics.cpu.usage,
          primary: `${Math.round(metrics.cpu.usage)}%`,
          secondary: `${metrics.cpu.cores} cores @ ${(metrics.cpu.frequency / 1000).toFixed(1)}GHz`,
        }
      case 'memory':
        return {
          percentage: metrics.memory.usage,
          primary: `${Math.round(metrics.memory.usage)}%`,
          secondary: `${(metrics.memory.used / (1024**3)).toFixed(1)} GB / ${(metrics.memory.total / (1024**3)).toFixed(1)} GB`,
        }
      case 'disk':
        return {
          percentage: metrics.disk.usage,
          primary: `${Math.round(metrics.disk.usage)}%`,
          secondary: `${(metrics.disk.used / (1024**3)).toFixed(0)} GB / ${(metrics.disk.total / (1024**3)).toFixed(0)} GB`,
        }
      case 'network':
        return {
          percentage: 0, // 網路不顯示百分比
          primary: null,
          secondary: null,
          download: (metrics.network.receivedPerSecond / (1024**2)).toFixed(1),
          upload: (metrics.network.sentPerSecond / (1024**2)).toFixed(1),
        }
      default:
        return null
    }
  }

  const data = getMetricData()

  return (
    <div
      className={cn(
        'bg-dark-card/70 border border-dark-border/50 rounded-lg p-4',
        'hover:transform hover:-translate-y-1 hover:shadow-card-hover',
        'transition-all duration-300 backdrop-blur-sm',
        className
      )}
    >
      {/* 卡片標題 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-medium text-text-primary">{config.title}</h3>
        <div 
          className="text-xl"
          style={{ color: config.color }}
        >
          {config.icon}
        </div>
      </div>

      {/* 載入狀態 */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loading size="md" />
        </div>
      )}

      {/* 錯誤狀態 */}
      {error && !loading && (
        <div className="py-8 text-center">
          <div className="text-red-400 text-sm mb-2">
            <i className="fas fa-exclamation-triangle mr-2" />
            Error
          </div>
          <div className="text-text-secondary text-xs">{error}</div>
        </div>
      )}

      {/* 正常數據顯示 */}
      {data && !loading && !error && (
        <div className="flex items-end justify-between">
          <div className="flex-1">
            {/* 網路卡片特殊佈局 */}
            {type === 'network' ? (
              <div className="space-y-2">
                <div className="flex items-center">
                  <TrendingDown className="h-4 w-4 text-green-500 mr-1" />
                  <span className="text-lg font-bold text-text-primary">
                    {data.download} MB/s
                  </span>
                </div>
                <div className="flex items-center">
                  <TrendingUp className="h-4 w-4 text-blue-500 mr-1" />
                  <span className="text-lg font-bold text-text-primary">
                    {data.upload} MB/s
                  </span>
                </div>
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold text-text-primary mb-1">
                  {data.primary}
                </div>
                <div className="text-sm text-text-secondary">
                  {data.secondary}
                </div>
              </>
            )}
          </div>

          {/* 右側圓形進度條或圖標 */}
          <div className="ml-4 flex-shrink-0">
            {type === 'network' ? (
              <div className="w-16 h-16 flex items-center justify-center">
                <Network 
                  className="h-8 w-8"
                  style={{ color: config.color }}
                />
              </div>
            ) : (
              <CircularProgress
                percentage={data.percentage}
                size={64}
                strokeWidth={3}
                color={config.color}
                className="drop-shadow-lg"
              />
            )}
          </div>
        </div>
      )}

      {/* 無數據狀態 */}
      {!data && !loading && !error && (
        <div className="py-8 text-center">
          <div className="text-text-secondary text-sm">
            <Minus className="h-4 w-4 mx-auto mb-2" />
            No data available
          </div>
        </div>
      )}
    </div>
  )
}

export default MetricCard