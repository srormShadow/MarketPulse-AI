import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/shopify': 'http://localhost:8000',
      '/upload_csv': 'http://localhost:8000',
      '/seed_demo': 'http://localhost:8000',
      '/forecast': 'http://localhost:8000',
      '/retrain': 'http://localhost:8000',
      '/recommendations': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/simulate': 'http://localhost:8000',
      '/diagnostics': 'http://localhost:8000',
      '/festivals': 'http://localhost:8000',
      '/insights': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
    },
  },
})
