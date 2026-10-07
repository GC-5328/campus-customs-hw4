import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// FastAPI backend (backend/main.py). Override with API_PORT=8001 npm run dev.
const apiTarget = `http://127.0.0.1:${process.env.API_PORT ?? '8000'}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    // Forward API and image requests to the backend.
    proxy: {
      '/api': apiTarget,
      '/media': apiTarget,
    },
  },
})
