// AsyncEffect Hook

import React, { useEffect, useRef } from 'react'

/**
 * AsyncEffect Hook - 支援 async/await 的 useEffect
 * @param asyncFunction 異步函數
 * @param deps 依賴陣列
 */
export default function useAsyncEffect(
  asyncFunction: () => Promise<void | (() => void)>,
  deps?: React.DependencyList
) {
  const isMountedRef = useRef(true)

  useEffect(() => {
    let cleanup: (() => void) | void

    const runAsync = async () => {
      try {
        cleanup = await asyncFunction()
      } catch (error) {
        if (isMountedRef.current) {
          console.error('AsyncEffect error:', error)
        }
      }
    }

    runAsync()

    return () => {
      isMountedRef.current = false
      if (typeof cleanup === 'function') {
        cleanup()
      }
    }
  }, deps)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])
}