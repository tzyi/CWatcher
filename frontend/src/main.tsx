import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './styles/index.css'

// 移除載入畫面
const loadingScreen = document.getElementById('loading-screen')
if (loadingScreen) {
  loadingScreen.style.display = 'none'
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)