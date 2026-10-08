import { defineConfig, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

// SPA proxy option: allows browser page refresh / direct navigation to serve index.html (SPA)
// while proxying API fetch calls to the FastAPI backend.
const apiProxy: ProxyOptions = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  bypass: (req) => {
    const accept = (req.headers.accept || '') as string
    const secFetchDest = (req.headers['sec-fetch-dest'] || '') as string
    // If the browser is requesting an HTML document (page refresh or direct URL visit),
    // bypass proxy and return index.html for React Router to handle
    if (accept.includes('text/html') || secFetchDest === 'document') {
      return '/index.html'
    }
  },
}

const streamProxy: ProxyOptions = {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  secure: false,
  ws: false,
  timeout: 0,
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/auth': apiProxy,
      '/floors': apiProxy,
      '/tables': apiProxy,
      '/sessions': apiProxy,
      '/users': apiProxy,
      '/menu': apiProxy,
      '/reservations': apiProxy,
      '/orders': apiProxy,
      '/guest': apiProxy,
      '/billing': apiProxy,
      '/payments': apiProxy,
      '/cashier-shifts': apiProxy,
      '/refunds': apiProxy,
      '/revenue': apiProxy,
      '/settings': apiProxy,
      '/rbac': apiProxy,
      '/audit-logs': apiProxy,
      '/insights': apiProxy,
      '/vision': apiProxy,
      '/stream': streamProxy,
      '/health': apiProxy,
      '/ai': apiProxy,
      '/customer': apiProxy,
      '/ai-booking': apiProxy,
      '/ai-timeslot': apiProxy,
      '/ai-waitlist': apiProxy,
      '/voice': apiProxy,
    },
  },
})
