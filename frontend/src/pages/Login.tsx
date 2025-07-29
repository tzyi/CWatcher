// Login 登入頁面

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Server, Wifi, Eye, EyeOff } from 'lucide-react'
import { Button, Input, Card } from '@/components/common'
import { useServerStore } from '@/stores'
import { isValidHost, isValidPort } from '@/utils'
import toast from 'react-hot-toast'

interface LoginFormData {
  name: string
  host: string
  port: string // 改為字串以配合 input 元件
  username: string
  password: string
}

/**
 * SSH 連接登入頁面
 */
const Login: React.FC = () => {
  const navigate = useNavigate()
  const { createServer, loading } = useServerStore()
  
  const [formData, setFormData] = useState<LoginFormData>({
    name: '',
    host: '',
    port: '22',
    username: '',
    password: '',
  })
  
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Partial<LoginFormData>>({})

  // 表單驗證
  const validateForm = (): boolean => {
    const newErrors: Partial<LoginFormData> = {}

    if (!formData.name.trim()) {
      newErrors.name = '請輸入伺服器名稱'
    }

    if (!formData.host.trim()) {
      newErrors.host = '請輸入主機地址'
    } else if (!isValidHost(formData.host)) {
      newErrors.host = '請輸入有效的 IP 地址或主機名稱'
    }

    const portNumber = parseInt(formData.port)
    if (!formData.port || isNaN(portNumber) || !isValidPort(portNumber)) {
      newErrors.port = '請輸入有效的端口號 (1-65535)'
    }

    if (!formData.username.trim()) {
      newErrors.username = '請輸入使用者名稱'
    }

    if (!formData.password.trim()) {
      newErrors.password = '請輸入密碼'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // 處理表單輸入
  const handleInputChange = (field: keyof LoginFormData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = e.target.value
    
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }))

    // 清除對應的錯誤
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: undefined,
      }))
    }
  }

  // 處理登入提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    try {
      // 建立伺服器連接
      const server = await createServer({
        name: formData.name,
        host: formData.host,
        port: parseInt(formData.port),
        username: formData.username,
        authType: 'password',
        description: '',
        tags: [],
      } as any)

      toast.success('連接成功！')
      
      // 導航到儀表板
      navigate('/dashboard', { 
        state: { serverId: server.id }
      })
    } catch (error) {
      // 錯誤處理已在 store 中完成
      console.error('登入失敗:', error)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-darker px-4">
      <div className="w-full max-w-md">
        {/* 標題區域 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-500 bg-opacity-20 rounded-full mb-4">
            <Server className="w-8 h-8 text-primary-400" />
          </div>
          
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
            CWatcher
          </h1>
          
          <p className="text-text-secondary mt-2">
            連接到您的 Linux 伺服器
          </p>
        </div>

        {/* 登入表單 */}
        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 伺服器名稱 */}
            <Input
              label="伺服器名稱"
              type="text"
              placeholder="例：生產環境伺服器"
              value={formData.name}
              onChange={handleInputChange('name')}
              error={errors.name}
              leftIcon={<Server size={16} />}
              fullWidth
            />

            {/* 主機地址 */}
            <Input
              label="主機地址"
              type="text"
              placeholder="192.168.1.100 或 server.example.com"
              value={formData.host}
              onChange={handleInputChange('host')}
              error={errors.host}
              leftIcon={<Wifi size={16} />}
              fullWidth
            />

            {/* 端口號 */}
            <Input
              label="SSH 端口"
              type="number"
              placeholder="22"
              value={formData.port}
              onChange={handleInputChange('port')}
              error={errors.port}
              helperText="預設 SSH 端口為 22"
              fullWidth
            />

            {/* 使用者名稱 */}
            <Input
              label="使用者名稱"
              type="text"
              placeholder="root 或 ubuntu"
              value={formData.username}
              onChange={handleInputChange('username')}
              error={errors.username}
              fullWidth
            />

            {/* 密碼 */}
            <Input
              label="密碼"
              type={showPassword ? 'text' : 'password'}
              placeholder="請輸入 SSH 密碼"
              value={formData.password}
              onChange={handleInputChange('password')}
              error={errors.password}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-text-secondary hover:text-text-primary"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
              fullWidth
            />

            {/* 提交按鈕 */}
            <Button
              type="submit"
              loading={loading === 'loading'}
              fullWidth
              size="lg"
            >
              {loading === 'loading' ? '連接中...' : '連接伺服器'}
            </Button>
          </form>

          {/* 說明文字 */}
          <div className="mt-6 pt-6 border-t border-dark-border">
            <div className="text-sm text-text-secondary space-y-2">
              <p className="flex items-center">
                <span className="w-2 h-2 bg-status-online rounded-full mr-2" />
                支援 SSH 密碼認證
              </p>
              <p className="flex items-center">
                <span className="w-2 h-2 bg-primary-400 rounded-full mr-2" />
                所有連接資料採用 AES 加密儲存
              </p>
              <p className="flex items-center">
                <span className="w-2 h-2 bg-secondary-400 rounded-full mr-2" />
                即時監控 CPU、記憶體、磁碟、網路
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default Login