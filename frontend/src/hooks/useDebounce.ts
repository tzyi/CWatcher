// Debounce Hook

import { useState, useEffect } from 'react'

/**
 * Debounce Hook - 防抖處理
 * @param value 要防抖的值
 * @param delay 延遲時間 (毫秒)
 * @returns 防抖後的值
 */
export default function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}