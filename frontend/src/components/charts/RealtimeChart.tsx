// 即時監控圖表元件

import React, { useEffect, useRef, useMemo } from 'react'
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
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { format } from 'date-fns'
import { cn } from '@/utils'
import type { SystemMetrics } from '@/types'
import type { MetricType } from './MetricChart'

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

interface RealtimeChartProps {
  type: MetricType
  data: SystemMetrics[]
  maxDataPoints?: number
  height?: number
  className?: string
}

// 即時圖表配置
const realtimeConfigs = {
  cpu: {
    title: 'CPU Usage (Real-time)',
    color: '#3b82f6',
    unit: '%',
    max: 100,
  },
  memory: {
    title: 'Memory Usage (Real-time)',
    color: '#8b5cf6', 
    unit: '%',
    max: 100,
  },
  disk: {
    title: 'Disk I/O (Real-time)',
    color: '#10b981',
    unit: 'MB/s',
    max: null,
  },
  network: {
    title: 'Network Traffic (Real-time)',
    color: '#0ea5e9',
    unit: 'MB/s',
    max: null,
  },
}

/**
 * 即時監控圖表元件
 * 專為即時數據更新優化的圖表元件
 */
const RealtimeChart: React.FC<RealtimeChartProps> = ({
  type,
  data,
  maxDataPoints = 60, // 預設顯示最近 60 個數據點 (30分鐘，30秒間隔)
  height = 200,
  className,
}) => {
  const chartRef = useRef<ChartJS<'line'>>(null)
  const config = realtimeConfigs[type]
  
  // 限制數據點數量，保持即時性能
  const limitedData = useMemo(() => {
    if (!data || data.length === 0) return []
    return data.slice(-maxDataPoints)
  }, [data, maxDataPoints])

  // 準備即時圖表數據
  const chartData: ChartData<'line'> = useMemo(() => {
    if (limitedData.length === 0) {
      return {
        labels: [],
        datasets: [],
      }
    }

    const labels = limitedData.map(item => format(new Date(item.timestamp), 'HH:mm:ss'))
    
    let datasets: any[] = []

    switch (type) {
      case 'cpu':
        datasets = [
          {
            label: 'CPU %',
            data: limitedData.map(item => item.cpu.usage),
            borderColor: config.color,
            backgroundColor: `${config.color}15`,
            tension: 0.3,
            fill: true,
            pointRadius: 1,
            pointHoverRadius: 3,
            borderWidth: 1.5,
          },
        ]
        break
        
      case 'memory':
        datasets = [
          {
            label: 'Memory %',
            data: limitedData.map(item => item.memory.usage),
            borderColor: config.color,
            backgroundColor: `${config.color}15`,
            tension: 0.3,
            fill: true,
            pointRadius: 1,
            pointHoverRadius: 3,
            borderWidth: 1.5,
          },
        ]
        break
        
      case 'disk':
        datasets = [
          {
            label: 'Read',
            data: limitedData.map(item => (item.disk.readPerSecond || 0) / (1024 ** 2)),
            borderColor: '#10b981',
            backgroundColor: '#10b98110',
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 2,
            borderWidth: 1.5,
          },
          {
            label: 'Write',
            data: limitedData.map(item => (item.disk.writePerSecond || 0) / (1024 ** 2)),
            borderColor: '#f59e0b',
            backgroundColor: '#f59e0b10',
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 2,
            borderWidth: 1.5,
          },
        ]
        break
        
      case 'network':
        datasets = [
          {
            label: 'Download',
            data: limitedData.map(item => (item.network.receivedPerSecond || 0) / (1024 ** 2)),
            borderColor: '#10b981',
            backgroundColor: '#10b98110',
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 2,
            borderWidth: 1.5,
          },
          {
            label: 'Upload',
            data: limitedData.map(item => (item.network.sentPerSecond || 0) / (1024 ** 2)),
            borderColor: '#3b82f6',
            backgroundColor: '#3b82f610',
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 2,
            borderWidth: 1.5,
          },
        ]
        break
    }

    return {
      labels,
      datasets,
    }
  }, [limitedData, type, config])

  // 即時圖表選項 - 優化效能
  const options: ChartOptions<'line'> = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'nearest',
      intersect: false,
    },
    plugins: {
      legend: {
        display: false, // 即時圖表不顯示圖例節省空間
      },
      tooltip: {
        enabled: false, // 即時圖表禁用提示框提升效能
      },
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: false,
        },
        ticks: {
          display: false, // 隱藏 x 軸標籤節省空間
        },
      },
      y: {
        display: true,
        title: {
          display: false,
        },
        min: 0,
        max: config.max || undefined,
        grid: {
          color: '#374151',
          drawBorder: false,
          lineWidth: 0.5,
        },
        ticks: {
          color: '#6b7280',
          font: {
            size: 10,
          },
          maxTicksLimit: 4,
          callback: (value) => `${value}${config.unit}`,
        },
      },
    },
    elements: {
      line: {
        borderWidth: 1.5,
      },
      point: {
        borderWidth: 0,
        hoverBorderWidth: 1,
      },
    },
    animation: {
      duration: 0, // 禁用動畫提升即時效能
    },
  }), [config])

  // 即時更新圖表
  useEffect(() => {
    if (chartRef.current && limitedData.length > 0) {
      chartRef.current.update('none') // 無動畫更新
    }
  }, [limitedData])

  return (
    <div
      className={cn(
        'bg-dark-surface/30 border border-dark-border/30 rounded-md p-3',
        'backdrop-blur-sm',
        className
      )}
    >
      {/* 簡化標題 */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-text-secondary">{config.title}</h4>
        <div className="flex items-center space-x-1">
          <div className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
          <span className="text-xs text-text-secondary">Live</span>
        </div>
      </div>

      {/* 即時圖表 */}
      <div className="relative" style={{ height: `${height}px` }}>
        {limitedData.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-xs text-text-secondary">Waiting for data...</div>
          </div>
        ) : (
          <Line ref={chartRef} data={chartData} options={options} />
        )}
      </div>
    </div>
  )
}

export default RealtimeChart