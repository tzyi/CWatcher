// Input 基礎元件

import React from 'react'
import { cn } from '@/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  fullWidth?: boolean
}

/**
 * 基礎輸入框元件
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      className,
      id,
      ...props
    },
    ref
  ) => {
    // 生成 ID
    const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`

    // 基礎樣式
    const baseStyles = 'block px-3 py-2 text-text-primary bg-dark-card border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50 disabled:cursor-not-allowed'

    // 錯誤狀態樣式
    const errorStyles = error
      ? 'border-status-offline focus:ring-red-500 focus:border-red-500'
      : 'border-dark-border hover:border-dark-surface'

    // 圖示樣式調整
    const leftPadding = leftIcon ? 'pl-10' : ''
    const rightPadding = rightIcon ? 'pr-10' : ''

    // 寬度樣式
    const widthStyles = fullWidth ? 'w-full' : ''

    return (
      <div className={cn('relative', fullWidth ? 'w-full' : '')}>
        {/* 標籤 */}
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-text-primary mb-2"
          >
            {label}
          </label>
        )}

        {/* 輸入框容器 */}
        <div className="relative">
          {/* 左側圖示 */}
          {leftIcon && (
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <span className="text-text-secondary">
                {leftIcon}
              </span>
            </div>
          )}

          {/* 輸入框 */}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              baseStyles,
              errorStyles,
              leftPadding,
              rightPadding,
              widthStyles,
              className
            )}
            disabled={disabled}
            {...props}
          />

          {/* 右側圖示 */}
          {rightIcon && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <span className="text-text-secondary">
                {rightIcon}
              </span>
            </div>
          )}
        </div>

        {/* 錯誤訊息 */}
        {error && (
          <p className="mt-1 text-sm text-status-offline">
            {error}
          </p>
        )}

        {/* 輔助文字 */}
        {helperText && !error && (
          <p className="mt-1 text-sm text-text-secondary">
            {helperText}
          </p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

export default Input