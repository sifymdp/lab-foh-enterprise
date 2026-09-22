import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/floors': 'http://127.0.0.1:8000',
      '/tables': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
      '/users': 'http://127.0.0.1:8000',
      '/menu': 'http://127.0.0.1:8000',
      '/reservations': 'http://127.0.0.1:8000',
      '/orders': 'http://127.0.0.1:8000',
      '/guest': 'http://127.0.0.1:8000',
      '/billing': 'http://127.0.0.1:8000',
      '/payments': 'http://127.0.0.1:8000',
      '/cashier-shifts': 'http://127.0.0.1:8000',
      '/refunds': 'http://127.0.0.1:8000',
      '/revenue': 'http://127.0.0.1:8000',
      '/settings': 'http://127.0.0.1:8000',
      '/rbac': 'http://127.0.0.1:8000',
      '/audit-logs': 'http://127.0.0.1:8000',
      '/insights': 'http://127.0.0.1:8000',
      '/vision': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
