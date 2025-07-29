// 新增伺服器模態視窗元件

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Server, User, Lock, Network, Tag, TestTube, Plus } from 'lucide-react'
import { cn } from '@/utils'
import type { CreateServerRequest } from '@/types'
import Modal from '@/components/common/Modal'
import Button from '@/components/common/Button'
import Input from '@/components/common/Input'
import toast from 'react-hot-toast'

interface AddServerModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: CreateServerRequest) => Promise<void>
  onTestConnection?: (data: CreateServerRequest) => Promise<boolean>
}

// 表單驗證 Schema
const serverSchema = z.object({
  name: z.string().min(1, '伺服器名稱為必填'),
  host: z.string()
    .min(1, 'IP 地址為必填')
    .regex(
      /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$|^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
      '請輸入有效的 IP 地址或域名'
    ),
  port: z.number().min(1).max(65535, '端口範圍為 1-65535'),
  username: z.string().min(1, '用戶名為必填'),
  authType: z.enum(['password', 'key'] as const),
  password: z.string().optional(),
  privateKey: z.string().optional(),
  description: z.string().optional(),
  tags: z.string().optional(),
}).refine((data) => {
  if (data.authType === 'password') {
    return data.password && data.password.length > 0
  }
  if (data.authType === 'key') {
    return data.privateKey && data.privateKey.length > 0
  }
  return true
}, {
  message: '請提供相應的認證資訊',
  path: ['password'],
})

type FormData = z.infer<typeof serverSchema>

/**
 * 新增伺服器模態視窗元件
 * 根據原型設計，提供完整的伺服器配置表單
 */
const AddServerModal: React.FC<AddServerModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  onTestConnection,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [saveCredentials, setSaveCredentials] = useState(true)

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    reset,
    getValues,
  } = useForm<FormData>({
    resolver: zodResolver(serverSchema),
    defaultValues: {
      name: '',
      host: '',
      port: 22,
      username: '',
      authType: 'password',
      password: '',
      privateKey: '',
      description: '',
      tags: '',
    },
  })

  const authType = watch('authType')

  // 處理表單提交
  const handleFormSubmit = async (data: FormData) => {
    setIsSubmitting(true)
    
    try {
      const serverData: CreateServerRequest = {
        name: data.name,
        host: data.host,
        port: data.port,
        username: data.username,
        authType: data.authType,
        password: data.authType === 'password' ? data.password : undefined,
        privateKey: data.authType === 'key' ? data.privateKey : undefined,
        description: data.description || undefined,
        tags: data.tags ? data.tags.split(',').map(tag => tag.trim()).filter(Boolean) : undefined,
      }

      await onSubmit(serverData)
      handleClose()
    } catch (error) {
      console.error('Failed to add server:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  // 測試連接
  const handleTestConnection = async () => {
    if (!onTestConnection) return

    const data = getValues()
    const validationResult = serverSchema.safeParse(data)
    
    if (!validationResult.success) {
      toast.error('請先填寫完整的伺服器資訊')
      return
    }

    setIsTesting(true)
    
    try {
      const serverData: CreateServerRequest = {
        name: data.name,
        host: data.host,
        port: data.port,
        username: data.username,
        authType: data.authType,
        password: data.authType === 'password' ? data.password : undefined,
        privateKey: data.authType === 'key' ? data.privateKey : undefined,
        description: data.description || undefined,
        tags: data.tags ? data.tags.split(',').map(tag => tag.trim()).filter(Boolean) : undefined,
      }

      const result = await onTestConnection(serverData)
      if (result) {
        toast.success('連接測試成功！')
      }
    } catch (error) {
      console.error('Connection test failed:', error)
    } finally {
      setIsTesting(false)
    }
  }

  // 關閉模態視窗
  const handleClose = () => {
    reset()
    setSaveCredentials(true)
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Add New Server"
      size="lg"
    >
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
        {/* 基本資訊 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-text-primary border-b border-dark-border pb-2">
            Basic Information
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 伺服器名稱 */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Server Name
              </label>
              <div className="relative">
                <Server className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
                <Input
                  {...register('name')}
                  placeholder="Web Server"
                  className={cn(
                    'pl-10',
                    errors.name && 'border-red-500 focus:border-red-500'
                  )}
                />
              </div>
              {errors.name && (
                <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>
              )}
            </div>

            {/* IP 地址 */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                IP Address *
              </label>
              <div className="relative">
                <Network className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
                <Input
                  {...register('host')}
                  placeholder="192.168.1.100"
                  className={cn(
                    'pl-10',
                    errors.host && 'border-red-500 focus:border-red-500'
                  )}
                />
              </div>
              {errors.host && (
                <p className="mt-1 text-xs text-red-500">{errors.host.message}</p>
              )}
            </div>

            {/* SSH 端口 */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                SSH Port
              </label>
              <Input
                {...register('port', { valueAsNumber: true })}
                type="number"
                placeholder="22"
                min="1"
                max="65535"
                className={errors.port ? 'border-red-500 focus:border-red-500' : ''}
              />
              {errors.port && (
                <p className="mt-1 text-xs text-red-500">{errors.port.message}</p>
              )}
            </div>

            {/* 用戶名 */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Username *
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
                <Input
                  {...register('username')}
                  placeholder="admin"
                  className={cn(
                    'pl-10',
                    errors.username && 'border-red-500 focus:border-red-500'
                  )}
                />
              </div>
              {errors.username && (
                <p className="mt-1 text-xs text-red-500">{errors.username.message}</p>
              )}
            </div>
          </div>
        </div>

        {/* 認證設定 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-text-primary border-b border-dark-border pb-2">
            Authentication
          </h3>

          {/* 認證類型 */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Authentication Type
            </label>
            <div className="flex space-x-4">
              <label className="flex items-center">
                <input
                  {...register('authType')}
                  type="radio"
                  value="password"
                  className="mr-2 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-text-primary">Password</span>
              </label>
              <label className="flex items-center">
                <input
                  {...register('authType')}
                  type="radio"
                  value="key"
                  className="mr-2 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-text-primary">SSH Key</span>
              </label>
            </div>
          </div>

          {/* 密碼認證 */}
          {authType === 'password' && (
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Password *
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
                <Input
                  {...register('password')}
                  type="password"
                  placeholder="••••••••"
                  className={cn(
                    'pl-10',
                    errors.password && 'border-red-500 focus:border-red-500'
                  )}
                />
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>
              )}
            </div>
          )}

          {/* SSH 金鑰認證 */}
          {authType === 'key' && (
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Private Key *
              </label>
              <textarea
                {...register('privateKey')}
                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                rows={6}
                className={cn(
                  'w-full px-3 py-2 bg-dark-surface border border-dark-border rounded-lg',
                  'text-text-primary placeholder-text-secondary',
                  'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                  'transition-colors duration-200 resize-vertical',
                  errors.privateKey && 'border-red-500 focus:border-red-500'
                )}
              />
              {errors.privateKey && (
                <p className="mt-1 text-xs text-red-500">{errors.privateKey.message}</p>
              )}
            </div>
          )}
        </div>

        {/* 可選設定 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-text-primary border-b border-dark-border pb-2">
            Optional Settings
          </h3>

          {/* 描述 */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Description
            </label>
            <Input
              {...register('description')}
              placeholder="Production web server"
            />
          </div>

          {/* 標籤 */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Tags (comma separated)
            </label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-secondary" />
              <Input
                {...register('tags')}
                placeholder="web, production, ubuntu"
                className="pl-10"
              />
            </div>
          </div>

          {/* 保存憑證選項 */}
          <div className="flex items-center">
            <input
              id="save-credentials"
              type="checkbox"
              checked={saveCredentials}
              onChange={(e) => setSaveCredentials(e.target.checked)}
              className="rounded bg-dark-surface border-dark-border text-primary-500 focus:ring-primary-500"
            />
            <label htmlFor="save-credentials" className="ml-2 text-sm text-text-secondary">
              Save credentials securely
            </label>
          </div>
        </div>

        {/* 操作按鈕 */}
        <div className="flex justify-between pt-6 border-t border-dark-border">
          <div>
            {onTestConnection && (
              <Button
                type="button"
                variant="ghost"
                onClick={handleTestConnection}
                loading={isTesting}
                leftIcon={<TestTube className="h-4 w-4" />}
              >
                Test Connection
              </Button>
            )}
          </div>

          <div className="flex space-x-3">
            <Button
              type="button"
              variant="ghost"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isSubmitting}
              leftIcon={<Plus className="h-4 w-4" />}
              className="shadow-glow hover:shadow-glow-lg"
            >
              Add Server
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}

export default AddServerModal