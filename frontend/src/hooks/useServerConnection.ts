// ServerConnection Hook - 暫時預留

import { useState } from 'react'

/**
 * 伺服器連接管理 Hook (預留)
 */
export default function useServerConnection() {
  const [isConnected, setIsConnected] = useState(false)

  return {
    isConnected,
    connect: () => setIsConnected(true),
    disconnect: () => setIsConnected(false),
  }
}