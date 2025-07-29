// Interval Hook

import { useEffect, useRef } from 'react'

/**
 * Interval Hook - 安全的定時器處理
 * @param callback 回調函數
 * @param delay 間隔時間 (毫秒)，null 表示停止
 */
export default function useInterval(callback: () => void, delay: number | null) {
  const savedCallback = useRef<() => void>()

  // 儲存最新的 callback
  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  // 設定定時器
  useEffect(() => {
    function tick() {
      savedCallback.current?.()
    }

    if (delay !== null) {
      const id = setInterval(tick, delay)
      return () => clearInterval(id)
    }
  }, [delay])
}