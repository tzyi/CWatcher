// Modal 基礎元件

import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '@/utils'
import type { ModalProps } from '@/types'

/**
 * 模態視窗元件
 */
const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  size = 'md',
  children,
}) => {
  // 尺寸樣式
  const sizeStyles = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  // 處理 ESC 鍵關閉
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      // 防止背景滾動
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  // 處理背景點擊
  const handleBackdropClick = (event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  if (!isOpen) return null

  const modalContent = (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* 背景遮罩 */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity duration-300"
        onClick={handleBackdropClick}
      />

      {/* 模態視窗容器 */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <div
          className={cn(
            'relative w-full bg-dark-card rounded-lg shadow-card border border-dark-border transform transition-all duration-300',
            sizeStyles[size]
          )}
        >
          {/* 標題列 */}
          {title && (
            <div className="flex items-center justify-between p-6 border-b border-dark-border">
              <h3 className="text-lg font-semibold text-text-primary">
                {title}
              </h3>
              
              <button
                onClick={onClose}
                className="p-1 rounded-lg hover:bg-dark-surface text-text-secondary hover:text-text-primary transition-colors"
                aria-label="關閉"
              >
                <X size={20} />
              </button>
            </div>
          )}

          {/* 沒有標題時的關閉按鈕 */}
          {!title && (
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1 rounded-lg hover:bg-dark-surface text-text-secondary hover:text-text-primary transition-colors z-10"
              aria-label="關閉"
            >
              <X size={20} />
            </button>
          )}

          {/* 內容區域 */}
          <div className={cn('p-6', !title && 'pt-12')}>
            {children}
          </div>
        </div>
      </div>
    </div>
  )

  // 使用 Portal 渲染到 body
  return createPortal(modalContent, document.body)
}

export default Modal