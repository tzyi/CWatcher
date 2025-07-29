import { useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { Login, Dashboard, ServerList } from '@/pages'
import { useAppStore } from '@/stores'
import { Loading } from '@/components/common'

function App() {
  const { isInitialized, isLoading, error, initialize } = useAppStore()

  // 初始化應用程式
  useEffect(() => {
    initialize()
  }, [initialize])

  // 載入狀態
  if (isLoading || !isInitialized) {
    return (
      <div className="min-h-screen bg-dark-darker">
        <Loading 
          fullScreen 
          text="正在初始化 CWatcher..." 
          size="lg"
        />
      </div>
    )
  }

  // 初始化錯誤
  if (error) {
    return (
      <div className="min-h-screen bg-dark-darker flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <div className="mb-6">
            <div className="w-16 h-16 bg-status-offline bg-opacity-20 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">⚠️</span>
            </div>
            <h1 className="text-2xl font-bold text-text-primary mb-2">
              初始化失敗
            </h1>
            <p className="text-text-secondary">
              無法連接到 CWatcher 後端服務
            </p>
          </div>
          
          <div className="bg-dark-card p-4 rounded-lg border border-status-offline border-opacity-30 mb-6">
            <p className="text-sm text-status-offline">
              {error}
            </p>
          </div>
          
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors"
          >
            重新載入
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-dark-darker text-text-primary">
      <Router>
        <Routes>
          {/* 根路徑重導向到伺服器列表 */}
          <Route path="/" element={<Navigate to="/servers" replace />} />
          
          {/* 登入頁面 */}
          <Route path="/login" element={<Login />} />
          
          {/* 伺服器管理 */}
          <Route path="/servers" element={<ServerList />} />
          
          {/* 儀表板 */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/dashboard/:serverId" element={<Dashboard />} />
          
          {/* 404 頁面 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Router>
      
      {/* 全域通知 */}
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#1e293b',
            color: '#f1f5f9',
            border: '1px solid #334155',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#f1f5f9',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#f1f5f9',
            },
          },
          loading: {
            iconTheme: {
              primary: '#0ea5e9',
              secondary: '#f1f5f9',
            },
          },
        }}
      />
    </div>
  )
}

// 404 頁面
function NotFoundPage() {
  return (
    <div className="min-h-screen bg-dark-darker flex items-center justify-center">
      <div className="text-center">
        <div className="mb-8">
          <h1 className="text-6xl font-bold text-text-primary mb-4">404</h1>
          <h2 className="text-2xl font-semibold text-text-primary mb-4">
            頁面不存在
          </h2>
          <p className="text-text-secondary">
            您訪問的頁面不存在或已被移動
          </p>
        </div>
        
        <div className="space-x-4">
          <button
            onClick={() => window.history.back()}
            className="px-4 py-2 bg-dark-card hover:bg-dark-surface text-text-primary border border-dark-border rounded-lg transition-colors"
          >
            返回上頁
          </button>
          
          <button
            onClick={() => window.location.href = '/'}
            className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors"
          >
            回到首頁
          </button>
        </div>
      </div>
    </div>
  )
}

export default App