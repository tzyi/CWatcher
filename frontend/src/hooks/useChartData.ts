// ChartData Hook - 暫時預留

import { useState } from 'react'
import type { ChartDataPoint } from '@/types'

/**
 * 圖表資料管理 Hook (預留)
 */
export default function useChartData() {
  const [data, setData] = useState<ChartDataPoint[]>([])

  return {
    data,
    setData,
    addDataPoint: (point: ChartDataPoint) => {
      setData(prev => [...prev, point])
    },
    clearData: () => setData([]),
  }
}