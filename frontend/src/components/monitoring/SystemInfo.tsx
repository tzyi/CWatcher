// 系統資訊面板元件

import React from 'react'
import { Expand } from 'lucide-react'
import { cn } from '@/utils'
import type { SystemInfo as SystemInfoType, SystemMetrics } from '@/types'
import Button from '@/components/common/Button'
import Loading from '@/components/common/Loading'

interface SystemInfoProps {
  systemInfo?: SystemInfoType
  metrics?: SystemMetrics
  loading?: boolean
  error?: string
  onViewDetails?: () => void
  className?: string
}

/**
 * 系統資訊面板元件
 * 根據原型設計，展示硬體、作業系統和儲存資訊
 */
const SystemInfo: React.FC<SystemInfoProps> = ({
  systemInfo,
  metrics,
  loading = false,
  error,
  onViewDetails,
  className,
}) => {
  // 格式化數值
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return `${days} days, ${hours} hours`
  }

  if (loading) {
    return (
      <div className={cn('bg-dark-card border border-dark-border rounded-lg p-6', className)}>
        <div className="flex items-center justify-center py-8">
          <Loading size="md" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('bg-dark-card border border-dark-border rounded-lg p-6', className)}>
        <div className="text-center py-8">
          <div className="text-red-400 text-sm mb-2">
            Error loading system information
          </div>
          <div className="text-text-secondary text-xs">{error}</div>
        </div>
      </div>
    )
  }

  if (!systemInfo) {
    return (
      <div className={cn('bg-dark-card border border-dark-border rounded-lg p-6', className)}>
        <div className="text-center py-8">
          <div className="text-text-secondary text-sm">
            No system information available
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('bg-dark-card border border-dark-border rounded-lg p-6', className)}>
      {/* 標題和操作 */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-medium text-text-primary">System Information</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={onViewDetails}
          leftIcon={<Expand className="h-4 w-4" />}
          className="text-text-secondary hover:text-text-primary"
        >
          Details
        </Button>
      </div>

      {/* 系統資訊網格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* 硬體資訊 */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 uppercase tracking-wider">
            Hardware
          </h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Hostname:</span>
              <span className="text-text-primary text-sm font-medium">
                {systemInfo.hostname}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">CPU:</span>
              <span className="text-text-primary text-sm font-medium truncate ml-2">
                {systemInfo.hardware.cpu.model.length > 20 
                  ? `${systemInfo.hardware.cpu.model.slice(0, 20)}...`
                  : systemInfo.hardware.cpu.model
                }
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Cores:</span>
              <span className="text-text-primary text-sm font-medium">
                {systemInfo.hardware.cpu.cores} ({systemInfo.hardware.cpu.threads} threads)
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Memory:</span>
              <span className="text-text-primary text-sm font-medium">
                {formatBytes(systemInfo.hardware.memory.total)} {systemInfo.hardware.memory.type || 'DDR4'}
              </span>
            </div>
          </div>
        </div>

        {/* 作業系統資訊 */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 uppercase tracking-wider">
            Operating System
          </h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">OS:</span>
              <span className="text-text-primary text-sm font-medium">
                {systemInfo.software.os.name} {systemInfo.software.os.version}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Kernel:</span>
              <span className="text-text-primary text-sm font-medium">
                {systemInfo.software.os.kernel}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Uptime:</span>
              <span className="text-text-primary text-sm font-medium">
                {formatUptime(systemInfo.software.os.uptime)}
              </span>
            </div>
            {metrics && (
              <div className="flex justify-between items-center">
                <span className="text-text-secondary text-sm">Load Avg:</span>
                <span className="text-text-primary text-sm font-medium">
                  {metrics.cpu.loadAverage.map(avg => avg.toFixed(2)).join(', ')}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* 儲存資訊 */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 uppercase tracking-wider">
            Storage
          </h4>
          <div className="space-y-3">
            {systemInfo.hardware.disk.devices.length > 0 && (
              <>
                <div className="flex justify-between items-center">
                  <span className="text-text-secondary text-sm">Disk:</span>
                  <span className="text-text-primary text-sm font-medium">
                    {formatBytes(systemInfo.hardware.disk.devices[0].size)} {systemInfo.hardware.disk.devices[0].type}
                  </span>
                </div>
                {metrics && (
                  <>
                    <div className="flex justify-between items-center">
                      <span className="text-text-secondary text-sm">Used:</span>
                      <span className="text-text-primary text-sm font-medium">
                        {formatBytes(metrics.disk.used)} ({Math.round(metrics.disk.usage)}%)
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-text-secondary text-sm">Free:</span>
                      <span className="text-text-primary text-sm font-medium">
                        {formatBytes(metrics.disk.free)} ({Math.round(100 - metrics.disk.usage)}%)
                      </span>
                    </div>
                  </>
                )}
                {metrics && metrics.disk.partitions.length > 0 && (
                  <div className="flex justify-between items-center">
                    <span className="text-text-secondary text-sm">File System:</span>
                    <span className="text-text-primary text-sm font-medium">
                      {metrics.disk.partitions[0].filesystem}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* 服務狀態 (如果有資料) */}
      {systemInfo.software.services && systemInfo.software.services.length > 0 && (
        <div className="mt-6 pt-6 border-t border-dark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-text-secondary uppercase tracking-wider">
              Services
            </h4>
            <span className="text-xs text-text-secondary">
              {systemInfo.software.services.filter(s => s.status === 'running').length} running
            </span>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {systemInfo.software.services.slice(0, 8).map((service, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-dark-surface/50 rounded text-xs">
                <span className="text-text-primary truncate mr-2">{service.name}</span>
                <span className={cn(
                  'px-2 py-0.5 rounded-full text-xs',
                  service.status === 'running' ? 'bg-green-900/30 text-green-300' :
                  service.status === 'stopped' ? 'bg-gray-900/30 text-gray-300' :
                  'bg-red-900/30 text-red-300'
                )}>
                  {service.status}
                </span>
              </div>
            ))}
          </div>
          
          {systemInfo.software.services.length > 8 && (
            <div className="text-center mt-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={onViewDetails}
                className="text-text-secondary hover:text-text-primary"
              >
                View all {systemInfo.software.services.length} services
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default SystemInfo