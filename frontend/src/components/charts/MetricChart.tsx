// 監控指標圖表元件 - Chart.js 整合

import React, { useMemo, useEffect, useRef } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  ChartData,
  TooltipItem,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { format } from 'date-fns'
import { cn } from '@/utils'
import type { SystemMetrics } from '@/types'
import Loading from '@/components/common/Loading'

// 註冊 Chart.js 元件
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

export type MetricType = 'cpu' | 'memory' | 'disk' | 'network'

interface MetricChartProps {
  type: MetricType
  data: SystemMetrics[]
  loading?: boolean
  error?: string
  height?: number
  className?: string
}

// 圖表配置
const chartConfigs = {
  cpu: {
    title: 'CPU Usage',
    color: '#3b82f6',
    unit: '%',
    max: 100,
  },
  memory: {
    title: 'Memory Usage', 
    color: '#8b5cf6',
    unit: '%',
    max: 100,
  },
  disk: {
    title: 'Disk I/O',
    color: '#10b981',
    unit: 'MB/s',
    max: null,
  },
  network: {
    title: 'Network Traffic',
    color: '#0ea5e9',
    unit: 'MB/s', 
    max: null,
  },
}

/**
 * 監控指標圖表元件
 * 使用 Chart.js 實現深色主題的時序圖表
 */
const MetricChart: React.FC<MetricChartProps> = ({
  type,
  data,
  loading = false,
  error,
  height = 240,
  className,
}) => {
  const chartRef = useRef<ChartJS<'line'>>(null)
  const config = chartConfigs[type]

  // 準備圖表數據
  const chartData: ChartData<'line'> = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        labels: [],
        datasets: [],
      }
    }

    const labels = data.map(item => format(new Date(item.timestamp), 'HH:mm'))
    
    let datasets: any[] = []

    switch (type) {
      case 'cpu':
        datasets = [
          {
            label: 'CPU Usage',
            data: data.map(item => item.cpu.usage),
            borderColor: config.color,
            backgroundColor: `${config.color}20`,
            tension: 0.4,
            fill: true,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ]
        break
        
      case 'memory':
        datasets = [
          {
            label: 'Memory Usage',
            data: data.map(item => item.memory.usage),
            borderColor: config.color,
            backgroundColor: `${config.color}20`,
            tension: 0.4,
            fill: true,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ]
        break
        
      case 'disk':
        datasets = [
          {
            label: 'Read',
            data: data.map(item => (item.disk.readPerSecond || 0) / (1024 ** 2)),
            borderColor: '#10b981',
            backgroundColor: '#10b98120',
            tension: 0.4,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: 'Write',
            data: data.map(item => (item.disk.writePerSecond || 0) / (1024 ** 2)),
            borderColor: '#f59e0b',
            backgroundColor: '#f59e0b20',
            tension: 0.4,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ]
        break
        
      case 'network':
        datasets = [
          {
            label: 'Download',
            data: data.map(item => (item.network.receivedPerSecond || 0) / (1024 ** 2)),
            borderColor: '#10b981',
            backgroundColor: '#10b98120',
            tension: 0.4,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: 'Upload',
            data: data.map(item => (item.network.sentPerSecond || 0) / (1024 ** 2)),
            borderColor: '#3b82f6',
            backgroundColor: '#3b82f620',
            tension: 0.4,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ]
        break
    }

    return {
      labels,
      datasets,
    }
  }, [data, type, config])

  // 圖表選項配置 - 深色主題
  const options: ChartOptions<'line'> = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        display: type === 'disk' || type === 'network',
        position: 'top',
        labels: {
          color: '#94a3b8',
          font: {
            size: 12,
          },
          usePointStyle: true,
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f1f5f9',
        bodyColor: '#cbd5e1',
        borderColor: '#475569',
        borderWidth: 1,
        cornerRadius: 8,
        displayColors: true,
        callbacks: {
          title: (context) => {
            const label = context[0]?.label
            if (!label) return ''
            return `Time: ${label}`
          },
          label: (context: TooltipItem<'line'>) => {
            const value = context.parsed.y
            return `${context.dataset.label}: ${value.toFixed(1)}${config.unit}`
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
        title: {
          display: false,
        },
        grid: {
          color: '#374151',
          drawBorder: false,
        },
        ticks: {
          color: '#9ca3af',
          maxTicksLimit: 8,
          font: {
            size: 11,
          },
        },
      },
      y: {
        display: true,
        title: {
          display: true,
          text: config.unit,
          color: '#9ca3af',
          font: {
            size: 11,
          },
        },
        min: 0,
        max: config.max || undefined,
        grid: {
          color: '#374151',
          drawBorder: false,
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 11,
          },
          callback: (value) => {
            return `${value}${config.unit}`
          },
        },
      },
    },
    elements: {
      line: {
        borderWidth: 2,
      },
      point: {
        borderWidth: 0,
        hoverBorderWidth: 2,
      },
    },
    animation: {
      duration: 300,
    },
  }), [type, config])

  // 更新圖表動畫
  useEffect(() => {
    if (chartRef.current && data.length > 0) {
      chartRef.current.update('none')
    }
  }, [data])

  return (
    <div
      className={cn(
        'bg-dark-card/70 border border-dark-border/50 rounded-lg p-4',
        'hover:transform hover:-translate-y-1 hover:shadow-card-hover',
        'transition-all duration-300 backdrop-blur-sm',
        className
      )}
    >
      {/* 圖表標題 */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-text-primary">{config.title}</h3>
        <div className="flex items-center space-x-2">
          {loading && (
            <div className="w-4 h-4">
              <Loading size="sm" />
            </div>
          )}
        </div>
      </div>

      {/* 圖表容器 */}
      <div className="relative" style={{ height: `${height}px` }}>
        {loading && data.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loading size="md" />
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="text-red-400 text-sm mb-2">
                <i className="fas fa-exclamation-triangle mr-2" />
                Chart Error
              </div>
              <div className="text-text-secondary text-xs">{error}</div>
            </div>
          </div>
        ) : data.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="text-text-secondary text-sm">
                <i className="fas fa-chart-line mr-2" />
                No data available
              </div>
            </div>
          </div>
        ) : (
          <Line ref={chartRef} data={chartData} options={options} />
        )}
      </div>
    </div>
  )
}

export default MetricChart