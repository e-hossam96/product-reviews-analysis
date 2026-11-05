import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In development the browser talks to Vite, which forwards /api to the backend.
    // In Docker, nginx does the same job.
    proxy: { '/api': 'http://127.0.0.1:11696' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // let theme.test.ts read the real stylesheet (CSS imports are empty in tests otherwise)
    css: { include: /index\.css/ },
  },
})
