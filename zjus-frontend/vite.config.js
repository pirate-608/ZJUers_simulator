import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000, // 前端开发服务器跑在 3000 端口
    proxy: {
      // 将 /api 开头的请求代理到后端的 8000 端口
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 将 /ws 开头的 WebSocket 请求也代理过去
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
      // (可选) 如果前端需要拉取 /world 下的数据，也代理过去
      '/world': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})