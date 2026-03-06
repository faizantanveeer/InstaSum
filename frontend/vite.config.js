import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = 'http://127.0.0.1:5000'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/static/dist/' : '/',
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': proxyTarget,
      '/auth': proxyTarget,
      '/dashboard': proxyTarget,
      '/export': proxyTarget,
      '/thumbnails': proxyTarget,
      '/audio': proxyTarget,
      '/proxy-image': proxyTarget,
    },
  },
}))
