// Card 基礎元件

import React from 'react'
import { cn } from '@/utils'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  padding?: boolean
  hover?: boolean
  border?: boolean
}

/**
 * 基礎卡片元件類型
 */
interface CardComponent extends React.FC<CardProps> {
  Header: React.FC<{ children: React.ReactNode; className?: string }>
  Title: React.FC<{ children: React.ReactNode; className?: string }>
  Description: React.FC<{ children: React.ReactNode; className?: string }>
  Content: React.FC<{ children: React.ReactNode; className?: string }>
  Footer: React.FC<{ children: React.ReactNode; className?: string }>
}

/**
 * 基礎卡片元件
 */
const Card: CardComponent = ({
  children,
  padding = true,
  hover = false,
  border = true,
  className,
  ...props
}) => {
  const baseStyles = 'bg-dark-card rounded-lg shadow-card'
  const paddingStyles = padding ? 'p-6' : ''
  const hoverStyles = hover ? 'hover:shadow-card-hover transition-shadow duration-200' : ''
  const borderStyles = border ? 'border border-dark-border' : ''

  return (
    <div
      className={cn(
        baseStyles,
        paddingStyles,
        hoverStyles,
        borderStyles,
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * 卡片標題元件
 */
const CardHeader: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className }) => {
  return (
    <div className={cn('mb-4', className)}>
      {children}
    </div>
  )
}

/**
 * 卡片標題文字元件
 */
const CardTitle: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className }) => {
  return (
    <h3 className={cn('text-lg font-semibold text-text-primary', className)}>
      {children}
    </h3>
  )
}

/**
 * 卡片描述元件
 */
const CardDescription: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className }) => {
  return (
    <p className={cn('text-text-secondary mt-1', className)}>
      {children}
    </p>
  )
}

/**
 * 卡片內容元件
 */
const CardContent: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className }) => {
  return (
    <div className={cn(className)}>
      {children}
    </div>
  )
}

/**
 * 卡片底部元件
 */
const CardFooter: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className }) => {
  return (
    <div className={cn('mt-4 pt-4 border-t border-dark-border', className)}>
      {children}
    </div>
  )
}

// 組合匯出
Card.Header = CardHeader
Card.Title = CardTitle
Card.Description = CardDescription
Card.Content = CardContent
Card.Footer = CardFooter

export default Card