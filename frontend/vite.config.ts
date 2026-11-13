import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend (uv run routeevo serve) listens on :8000; in production it also serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
