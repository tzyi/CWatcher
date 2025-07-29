// CWatcher 前端工具函數

import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, isValid } from 'date-fns'
import { zhTW } from 'date-fns/locale'

// ======================== 樣式工具 ========================

/**
 * 組合 CSS 類別名稱，支援條件式類別和 Tailwind 合併
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ======================== 格式化工具 ========================

/**
 * 格式化位元組大小為人類可讀格式
 * @param bytes 位元組數
 * @param decimals 小數位數 (預設 2)
 * @param binary 是否使用 1024 進制 (預設 false，使用 1000 進制)
 */
export function formatBytes(bytes: number, decimals = 2, binary = false): string {
  if (bytes === 0) return '0 B'
  
  const k = binary ? 1024 : 1000
  const dm = decimals < 0 ? 0 : decimals
  const sizes = binary 
    ? ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    : ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

/**
 * 格式化百分比
 * @param value 數值 (0-100)
 * @param decimals 小數位數 (預設 1)
 */
export function formatPercentage(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

/**
 * 格式化數字，添加千分位分隔符
 */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-TW').format(value)
}

/**
 * 格式化網路速度
 * @param bytesPerSecond 每秒位元組數
 */
export function formatNetworkSpeed(bytesPerSecond: number): string {
  const bitsPerSecond = bytesPerSecond * 8
  
  if (bitsPerSecond < 1000) {
    return `${bitsPerSecond.toFixed(0)} bps`
  } else if (bitsPerSecond < 1000000) {
    return `${(bitsPerSecond / 1000).toFixed(1)} Kbps`
  } else if (bitsPerSecond < 1000000000) {
    return `${(bitsPerSecond / 1000000).toFixed(1)} Mbps`
  } else {
    return `${(bitsPerSecond / 1000000000).toFixed(1)} Gbps`
  }
}

// ======================== 時間工具 ========================

/**
 * 格式化時間戳為本地時間
 * @param timestamp 時間戳字串或 Date 物件
 * @param formatStr 格式字串 (預設 'yyyy-MM-dd HH:mm:ss')
 */
export function formatTimestamp(
  timestamp: string | Date, 
  formatStr = 'yyyy-MM-dd HH:mm:ss'
): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  
  if (!isValid(date)) {
    return '無效時間'
  }
  
  return format(date, formatStr, { locale: zhTW })
}

/**
 * 格式化相對時間 (例: "3 分鐘前")
 * @param timestamp 時間戳字串或 Date 物件
 */
export function formatRelativeTime(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  
  if (!isValid(date)) {
    return '無效時間'
  }
  
  return formatDistanceToNow(date, { 
    addSuffix: true, 
    locale: zhTW 
  })
}

/**
 * 格式化運行時間 (秒數轉換為可讀格式)
 * @param seconds 秒數
 */
export function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  const parts: string[] = []
  
  if (days > 0) parts.push(`${days} 天`)
  if (hours > 0) parts.push(`${hours} 小時`)
  if (minutes > 0) parts.push(`${minutes} 分鐘`)
  if (secs > 0 || parts.length === 0) parts.push(`${secs} 秒`)
  
  return parts.join(' ')
}

// ======================== 驗證工具 ========================

/**
 * 驗證 IP 地址格式
 */
export function isValidIP(ip: string): boolean {
  const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
  const ipv6Regex = /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/
  
  return ipv4Regex.test(ip) || ipv6Regex.test(ip)
}

/**
 * 驗證主機名稱格式
 */
export function isValidHostname(hostname: string): boolean {
  const hostnameRegex = /^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$/
  return hostnameRegex.test(hostname)
}

/**
 * 驗證端口號
 */
export function isValidPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535
}

/**
 * 驗證伺服器地址 (IP 或主機名稱)
 */
export function isValidHost(host: string): boolean {
  return isValidIP(host) || isValidHostname(host)
}

// ======================== 狀態工具 ========================

/**
 * 根據 CPU 使用率取得狀態
 */
export function getCpuStatus(usage: number): 'normal' | 'warning' | 'critical' {
  if (usage < 70) return 'normal'
  if (usage < 90) return 'warning'
  return 'critical'
}

/**
 * 根據記憶體使用率取得狀態
 */
export function getMemoryStatus(usage: number): 'normal' | 'warning' | 'critical' {
  if (usage < 80) return 'normal'
  if (usage < 95) return 'warning'
  return 'critical'
}

/**
 * 根據磁碟使用率取得狀態
 */
export function getDiskStatus(usage: number): 'normal' | 'warning' | 'critical' {
  if (usage < 85) return 'normal'
  if (usage < 95) return 'warning'
  return 'critical'
}

/**
 * 取得狀態對應的顏色類別
 */
export function getStatusColor(status: 'normal' | 'warning' | 'critical'): string {
  switch (status) {
    case 'normal':
      return 'text-status-online'
    case 'warning':
      return 'text-status-warning'
    case 'critical':
      return 'text-status-offline'
    default:
      return 'text-text-secondary'
  }
}

/**
 * 取得狀態對應的背景顏色類別
 */
export function getStatusBgColor(status: 'normal' | 'warning' | 'critical'): string {
  switch (status) {
    case 'normal':
      return 'bg-status-online'
    case 'warning':
      return 'bg-status-warning'
    case 'critical':
      return 'bg-status-offline'
    default:
      return 'bg-status-unknown'
  }
}

// ======================== 陣列工具 ========================

/**
 * 根據屬性對陣列進行排序
 */
export function sortBy<T>(array: T[], key: keyof T, direction: 'asc' | 'desc' = 'asc'): T[] {
  return [...array].sort((a, b) => {
    const aVal = a[key]
    const bVal = b[key]
    
    if (aVal < bVal) return direction === 'asc' ? -1 : 1
    if (aVal > bVal) return direction === 'asc' ? 1 : -1
    return 0
  })
}

/**
 * 根據多個條件對陣列進行篩選
 */
export function filterBy<T>(
  array: T[], 
  filters: Partial<Record<keyof T, unknown>>
): T[] {
  return array.filter(item => {
    return Object.entries(filters).every(([key, value]) => {
      if (value === undefined || value === '') return true
      return item[key as keyof T] === value
    })
  })
}

/**
 * 深度克隆物件
 */
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') return obj
  if (obj instanceof Date) return new Date(obj.getTime()) as unknown as T
  if (obj instanceof Array) return obj.map(item => deepClone(item)) as unknown as T
  if (typeof obj === 'object') {
    const clonedObj = {} as T
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        clonedObj[key] = deepClone(obj[key])
      }
    }
    return clonedObj
  }
  return obj
}

// ======================== 錯誤處理工具 ========================

/**
 * 安全的 JSON 解析
 */
export function safeParseJSON<T>(jsonString: string, defaultValue: T): T {
  try {
    return JSON.parse(jsonString)
  } catch {
    return defaultValue
  }
}

/**
 * 處理 API 錯誤訊息
 */
export function getErrorMessage(error: unknown): string {
  if (typeof error === 'string') {
    return error
  }
  
  if (error instanceof Error) {
    return error.message
  }
  
  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message)
  }
  
  return '發生未知錯誤'
}

// ======================== 本地儲存工具 ========================

/**
 * 安全的本地儲存設定
 */
export function setLocalStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.warn('Failed to set localStorage:', error)
  }
}

/**
 * 安全的本地儲存讀取
 */
export function getLocalStorage<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : defaultValue
  } catch (error) {
    console.warn('Failed to get localStorage:', error)
    return defaultValue
  }
}

/**
 * 移除本地儲存項目
 */
export function removeLocalStorage(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch (error) {
    console.warn('Failed to remove localStorage:', error)
  }
}

// ======================== URL 工具 ========================

/**
 * 建構 URL 參數
 */
export function buildUrlParams(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams()
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value))
    }
  })
  
  const result = searchParams.toString()
  return result ? `?${result}` : ''
}

// ======================== 防抖與節流 ========================

/**
 * 防抖函數
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: number
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeout)
    timeout = window.setTimeout(() => func(...args), wait)
  }
}

/**
 * 節流函數
 */
export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      window.setTimeout(() => inThrottle = false, limit)
    }
  }
}

// ======================== 隨機工具 ========================

/**
 * 產生隨機 ID
 */
export function generateId(length = 8): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

/**
 * 產生隨機顏色 (十六進制)
 */
export function generateRandomColor(): string {
  return `#${Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0')}`
}

// ======================== 常數定義 ========================

/** 預設配置 */
export const DEFAULT_CONFIG = {
  REFRESH_INTERVAL: 30000, // 30 秒
  CHART_ANIMATION_DURATION: 300,
  MAX_CHART_POINTS: 50,
  WEBSOCKET_RECONNECT_DELAY: 3000,
  MAX_RECONNECT_ATTEMPTS: 5,
  REQUEST_TIMEOUT: 10000, // 10 秒
} as const

/** 伺服器狀態顏色映射 */
export const SERVER_STATUS_COLORS = {
  online: '#10b981',   // 綠色
  offline: '#ef4444',  // 紅色
  warning: '#f59e0b',  // 橙色
  unknown: '#6b7280',  // 灰色
} as const

/** 時間範圍標籤 */
export const TIME_RANGE_LABELS = {
  '1h': '1 小時',
  '6h': '6 小時',
  '24h': '24 小時',
  '7d': '7 天',
  '30d': '30 天',
} as const