import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './index.css'
import { AppProviders } from './app/providers'
import { AppRouter } from './app/router'

const container = document.getElementById('root')

if (!container) {
  throw new Error('未找到 #root 挂载点，请检查 index.html。')
}

createRoot(container).render(
  <StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </StrictMode>,
)