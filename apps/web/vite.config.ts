import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/**
 * 后端地址。开发环境下前端统一请求同源 `/api/*`，由 Vite 代理转发到 FastAPI，
 * 这样浏览器侧不存在跨域问题，也无需在前端硬编码绝对地址。
 */
const apiTarget = process.env.POKEMON_LAB_API_TARGET ?? 'http://127.0.0.1:18000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '@data': path.resolve(import.meta.dirname, '../../data'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      // 图鉴立绘由后端静态托管（本地缓存，离线可用），开发态同样走同源代理。
      '/media': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: false,
    clearMocks: true,
    restoreMocks: true,
  },
})