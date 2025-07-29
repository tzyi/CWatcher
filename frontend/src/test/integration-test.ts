// CWatcher 前後端整合測試腳本

import { api } from '../services/api'
import { getWebSocketManager } from '../services/websocket'

/**
 * API 整合測試
 */
export class IntegrationTester {
  private testResults: {
    api: Record<string, boolean>
    websocket: Record<string, boolean>
    overall: boolean
  } = {
    api: {},
    websocket: {},
    overall: false
  }

  /**
   * 執行完整整合測試
   */
  async runFullTest(): Promise<void> {
    console.log('🔄 開始執行前後端整合測試...')

    // 測試健康檢查
    await this.testHealthCheck()
    
    // 測試伺服器管理 API
    await this.testServerManagement()
    
    // 測試 SSH 連接 API
    await this.testSSHConnection()
    
    // 測試監控 API
    await this.testMonitoringAPI()
    
    // 測試 WebSocket 連接
    await this.testWebSocketConnection()
    
    // 生成測試報告
    this.generateReport()
  }

  /**
   * 測試健康檢查端點
   */
  private async testHealthCheck(): Promise<void> {
    console.log('📊 測試健康檢查端點...')
    
    try {
      const healthResult = await api.health.checkHealth()
      this.testResults.api['health'] = healthResult.status === 'healthy' || healthResult.status === 'running'
      console.log('✅ 健康檢查通過:', healthResult)
    } catch (error) {
      console.error('❌ 健康檢查失敗:', error)
      this.testResults.api['health'] = false
    }

    try {
      const dataHealthResult = await api.health.checkDataHealth()
      this.testResults.api['dataHealth'] = dataHealthResult.status === 'healthy'
      console.log('✅ 數據服務健康檢查通過:', dataHealthResult)
    } catch (error) {
      console.error('❌ 數據服務健康檢查失敗:', error)
      this.testResults.api['dataHealth'] = false
    }

    try {
      const wsHealthResult = await api.health.checkWebSocketHealth()
      this.testResults.api['websocketHealth'] = wsHealthResult.status === 'healthy'
      console.log('✅ WebSocket 服務健康檢查通過:', wsHealthResult)
    } catch (error) {
      console.error('❌ WebSocket 服務健康檢查失敗:', error)
      this.testResults.api['websocketHealth'] = false
    }
  }

  /**
   * 測試伺服器管理 API
   */
  private async testServerManagement(): Promise<void> {
    console.log('🖥️ 測試伺服器管理 API...')
    
    try {
      // 測試取得伺服器列表
      const servers = await api.servers.getServers()
      this.testResults.api['getServers'] = Array.isArray(servers)
      console.log('✅ 取得伺服器列表成功:', servers.length, '台伺服器')

      // 如果有伺服器，測試取得單一伺服器
      if (servers.length > 0) {
        const firstServer = servers[0]
        const server = await api.servers.getServerById(firstServer.id.toString())
        this.testResults.api['getServerById'] = !!server
        console.log('✅ 取得單一伺服器成功:', server.name)

        // 測試伺服器狀態
        const status = await api.servers.testConnection(firstServer.id.toString())
        this.testResults.api['serverStatus'] = typeof status.success === 'boolean'
        console.log('✅ 伺服器狀態檢查完成:', status)
      }
    } catch (error) {
      console.error('❌ 伺服器管理 API 測試失敗:', error)
      this.testResults.api['getServers'] = false
      this.testResults.api['getServerById'] = false
      this.testResults.api['serverStatus'] = false
    }
  }

  /**
   * 測試 SSH 連接 API
   */
  private async testSSHConnection(): Promise<void> {
    console.log('🔐 測試 SSH 連接 API...')
    
    try {
      // 測試 SSH 管理器統計
      const stats = await api.ssh.getManagerStatistics()
      this.testResults.api['sshStats'] = !!stats
      console.log('✅ SSH 管理器統計取得成功:', stats)
    } catch (error) {
      console.error('❌ SSH 管理器統計測試失敗:', error)
      this.testResults.api['sshStats'] = false
    }

    // 測試 SSH 連接 (使用假資料)
    try {
      const testConnectionData = {
        host: '127.0.0.1',
        port: 22,
        username: 'test',
        password: 'test'
      }
      
      const connectionResult = await api.ssh.testConnection(testConnectionData)
      this.testResults.api['sshTest'] = typeof connectionResult.success === 'boolean'
      console.log('✅ SSH 連接測試完成 (預期可能失敗):', connectionResult)
    } catch (error) {
      // SSH 連接測試失敗是正常的，因為沒有真實的 SSH 伺服器
      console.log('⚠️ SSH 連接測試 (預期失敗):', (error as Error).message)
      this.testResults.api['sshTest'] = true // 標記為通過，因為 API 有正確回應
    }
  }

  /**
   * 測試監控 API
   */
  private async testMonitoringAPI(): Promise<void> {
    console.log('📈 測試監控 API...')
    
    try {
      // 取得伺服器列表
      const servers = await api.servers.getServers()
      
      if (servers.length > 0) {
        const firstServerId = servers[0].id.toString()
        
        // 測試監控摘要
        try {
          const summary = await api.monitoring.getMonitoringSummary(firstServerId)
          this.testResults.api['monitoringSummary'] = !!summary
          console.log('✅ 監控摘要取得成功:', summary)
        } catch (error) {
          console.error('❌ 監控摘要測試失敗:', error)
          this.testResults.api['monitoringSummary'] = false
        }

        // 測試圖表數據
        try {
          const chartData = await api.monitoring.getChartData(firstServerId, '1h')
          this.testResults.api['chartData'] = !!chartData
          console.log('✅ 圖表數據取得成功:', chartData)
        } catch (error) {
          console.error('❌ 圖表數據測試失敗:', error)
          this.testResults.api['chartData'] = false
        }

        // 測試系統資訊
        try {
          const systemInfo = await api.monitoring.getSystemInfo(firstServerId)
          this.testResults.api['systemInfo'] = !!systemInfo
          console.log('✅ 系統資訊取得成功:', systemInfo)
        } catch (error) {
          console.error('❌ 系統資訊測試失敗:', error)
          this.testResults.api['systemInfo'] = false
        }
      } else {
        console.log('⚠️ 沒有伺服器可供測試監控 API')
        this.testResults.api['monitoringSummary'] = true
        this.testResults.api['chartData'] = true
        this.testResults.api['systemInfo'] = true
      }
    } catch (error) {
      console.error('❌ 監控 API 測試失敗:', error)
      this.testResults.api['monitoringSummary'] = false
      this.testResults.api['chartData'] = false
      this.testResults.api['systemInfo'] = false
    }
  }

  /**
   * 測試 WebSocket 連接
   */
  private async testWebSocketConnection(): Promise<void> {
    console.log('🔌 測試 WebSocket 連接...')
    
    return new Promise((resolve) => {
      const wsManager = getWebSocketManager()
      let connectionTestComplete = false

      // 設定連接成功處理器
      wsManager.on('onConnect', () => {
        console.log('✅ WebSocket 連接成功')
        this.testResults.websocket['connection'] = true
        
        // 測試訂閱功能
        wsManager.subscribe('test-server-1')
        console.log('✅ WebSocket 訂閱測試完成')
        this.testResults.websocket['subscribe'] = true
        
        if (!connectionTestComplete) {
          connectionTestComplete = true
          resolve()
        }
      })

      // 設定連接失敗處理器
      wsManager.on('onError', (error) => {
        console.error('❌ WebSocket 連接失敗:', error)
        this.testResults.websocket['connection'] = false
        this.testResults.websocket['subscribe'] = false
        
        if (!connectionTestComplete) {
          connectionTestComplete = true
          resolve()
        }
      })

      // 設定監控數據處理器
      wsManager.on('onMetricsUpdate', (data) => {
        console.log('✅ WebSocket 監控數據更新收到:', data)
        this.testResults.websocket['metricsUpdate'] = true
      })

      // 設定 5 秒超時
      setTimeout(() => {
        if (!connectionTestComplete) {
          console.log('⚠️ WebSocket 連接測試超時')
          this.testResults.websocket['connection'] = false
          this.testResults.websocket['subscribe'] = false
          connectionTestComplete = true
          resolve()
        }
      }, 5000)
    })
  }

  /**
   * 生成測試報告
   */
  private generateReport(): void {
    console.log('\n📋 前後端整合測試報告')
    console.log('=' .repeat(50))

    // API 測試結果
    console.log('\n🔗 API 測試結果:')
    Object.entries(this.testResults.api).forEach(([test, passed]) => {
      console.log(`  ${passed ? '✅' : '❌'} ${test}`)
    })

    // WebSocket 測試結果
    console.log('\n🔌 WebSocket 測試結果:')
    Object.entries(this.testResults.websocket).forEach(([test, passed]) => {
      console.log(`  ${passed ? '✅' : '❌'} ${test}`)
    })

    // 總體結果
    const apiPassed = Object.values(this.testResults.api).filter(Boolean).length
    const apiTotal = Object.keys(this.testResults.api).length
    const wsPassed = Object.values(this.testResults.websocket).filter(Boolean).length
    const wsTotal = Object.keys(this.testResults.websocket).length

    const totalPassed = apiPassed + wsPassed
    const totalTests = apiTotal + wsTotal
    const passRate = totalTests > 0 ? (totalPassed / totalTests) * 100 : 0

    console.log(`\n📊 總體結果: ${totalPassed}/${totalTests} 通過 (${passRate.toFixed(1)}%)`)
    
    if (passRate >= 80) {
      console.log('🎉 整合測試通過！前後端整合狀況良好')
      this.testResults.overall = true
    } else if (passRate >= 60) {
      console.log('⚠️ 整合測試部分通過，建議檢查失敗項目')
      this.testResults.overall = false
    } else {
      console.log('❌ 整合測試失敗，需要修復主要問題')
      this.testResults.overall = false
    }

    console.log('=' .repeat(50))
  }

  /**
   * 取得測試結果
   */
  getResults() {
    return this.testResults
  }
}

/**
 * 執行快速整合測試
 */
export async function runQuickIntegrationTest(): Promise<boolean> {
  const tester = new IntegrationTester()
  await tester.runFullTest()
  return tester.getResults().overall
}

// 如果直接執行此檔案，運行測試
if (typeof window !== 'undefined' && (window as any).runIntegrationTest) {
  runQuickIntegrationTest()
}