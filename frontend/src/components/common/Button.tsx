// Button 基礎元件

import React from 'react'
import { cn } from '@/utils'
import type { ButtonVariant, ButtonSize } from '@/types'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  fullWidth?: boolean
  children: React.ReactNode
}

/**
 * 基礎按鈕元件
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      className,
      children,
      ...props
    },
    ref
  ) => {
    // 變體樣式
    const variantStyles = {
      primary: 'bg-primary-500 hover:bg-primary-600 text-white border-primary-500 hover:border-primary-600 shadow-glow hover:shadow-glow-lg',
      secondary: 'bg-secondary-500 hover:bg-secondary-600 text-white border-secondary-500 hover:border-secondary-600',
      success: 'bg-status-online hover:bg-green-600 text-white border-status-online hover:border-green-600',
      warning: 'bg-status-warning hover:bg-yellow-600 text-white border-status-warning hover:border-yellow-600',
      error: 'bg-status-offline hover:bg-red-600 text-white border-status-offline hover:border-red-600',
      ghost: 'bg-transparent hover:bg-dark-surface text-text-primary border-dark-border hover:border-primary-500',
    }

    // 尺寸樣式
    const sizeStyles = {
      sm: 'px-3 py-1.5 text-sm',
      md: 'px-4 py-2 text-base',
      lg: 'px-6 py-3 text-lg',
    }

    // 基礎樣式
    const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-dark-darker disabled:opacity-50 disabled:cursor-not-allowed'

    // 載入動畫樣式
    const loadingStyles = loading ? 'cursor-wait' : ''

    // 寬度樣式
    const widthStyles = fullWidth ? 'w-full' : ''

    return (
      <button
        ref={ref}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          loadingStyles,
          widthStyles,
          className
        )}
        disabled={disabled || loading}
        {...props}
      >
        {/* 左側圖示 */}
        {leftIcon && !loading && (
          <span className="mr-2 flex-shrink-0">
            {leftIcon}
          </span>
        )}

        {/* 載入指示器 */}
        {loading && (
          <span className="mr-2 flex-shrink-0">
            <svg
              className="animate-spin h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </span>
        )}

        {/* 按鈕文字 */}
        <span>{children}</span>

        {/* 右側圖示 */}
        {rightIcon && !loading && (
          <span className="ml-2 flex-shrink-0">
            {rightIcon}
          </span>
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'

export default Button