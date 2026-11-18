import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  // amazon-cognito-identity-js espera `global` (Node) en el navegador
  define: { global: 'globalThis' },
  test: { environment: 'node' },
})
