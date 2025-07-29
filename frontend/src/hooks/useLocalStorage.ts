// LocalStorage Hook

import { useState, useEffect } from 'react'
import { setLocalStorage, getLocalStorage } from '@/utils'

/**
 * LocalStorage Hook - 本地儲存狀態管理
 * @param key 儲存鍵名
 * @param initialValue 初始值
 * @returns [value, setValue] 狀態和設定函數
 */
export default function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  // 從 localStorage 讀取初始值
  const [storedValue, setStoredValue] = useState<T>(() => {
    return getLocalStorage(key, initialValue)
  })

  // 設定值到 state 和 localStorage
  const setValue = (value: T | ((prev: T) => T)) => {
    try {
      // 如果是函數，計算新值
      const valueToStore = value instanceof Function ? value(storedValue) : value
      
      // 更新 state
      setStoredValue(valueToStore)
      
      // 儲存到 localStorage
      setLocalStorage(key, valueToStore)
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error)
    }
  }

  // 監聽 localStorage 變化 (跨標籤頁同步)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          setStoredValue(JSON.parse(e.newValue))
        } catch {
          setStoredValue(e.newValue as unknown as T)
        }
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [key])

  return [storedValue, setValue]
}