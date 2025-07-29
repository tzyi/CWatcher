/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // CWatcher 主色調 - 基於原型設計
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#0ea5e9', // 主色
          600: '#0284c7', // 深色主色
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        secondary: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981', // 次要色
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
        },
        accent: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#8b5cf6', // 強調色
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
        },
        // 深色主題背景
        dark: {
          bg: '#0f172a',       // 主背景
          darker: '#020617',   // 更深背景
          lighter: '#1e293b',  // 較亮背景 (sidebar)
          card: '#1e293b',     // 卡片背景
          surface: '#334155',  // 表面色
          border: '#475569',   // 邊框色
        },
        // 文字顏色
        text: {
          primary: '#f1f5f9',   // 主要文字
          secondary: '#94a3b8', // 次要文字
          accent: '#cbd5e1',    // 強調文字
        },
        // 狀態顏色
        status: {
          online: '#10b981',    // 在線
          warning: '#f59e0b',   // 警告
          offline: '#ef4444',   // 離線
          unknown: '#6b7280',   // 未知
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow': '0 0 15px rgba(14, 165, 233, 0.5)',
        'glow-lg': '0 0 25px rgba(14, 165, 233, 0.6)',
        'card': '0 4px 20px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 8px 16px rgba(0, 0, 0, 0.2)',
        'online': '0 0 5px #10b981',
        'warning': '0 0 5px #f59e0b',
        'offline': '0 0 5px #ef4444',
        'gray': '0 0 5px #6b7280',
      },
      backgroundImage: {
        'tech-gradient': 'linear-gradient(135deg, #0284c7, #0ea5e9)',
        'loading-gradient': 'linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'loading': 'loading 2s infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      borderWidth: {
        '3': '3px',
      },
      keyframes: {
        loading: {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}