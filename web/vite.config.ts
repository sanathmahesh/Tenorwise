/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // No env vars are exposed to the bundle: Vite only exposes VITE_-prefixed
  // variables, and this project defines none. Secrets stay server-side.
  server: {
    // Local development: forward /api to the FastAPI app (uvicorn on :8000).
    proxy: { '/api': 'http://127.0.0.1:8000' },
    // The About page imports docs/strategy/, LIMITATIONS.md and MODEL_CARD.md as raw text; allow only those outside web/.
    fs: {
      allow: [
        searchForWorkspaceRoot(process.cwd()),
        fileURLToPath(new URL('../docs/strategy', import.meta.url)),
        fileURLToPath(new URL('../LIMITATIONS.md', import.meta.url)),
        fileURLToPath(new URL('../MODEL_CARD.md', import.meta.url)),
      ],
    },
  },
  // Component and unit tests only; the browser smoke tests in e2e/ run under Playwright.
  test: { include: ['src/**/*.test.{ts,tsx}'] },
})
