import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_ALLOWED_HOSTS: comma-separated extra hostnames allowed to reach the dev server
// (e.g. an ngrok tunnel for testing on a phone). Leave unset for localhost only.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || '')
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean)

  return {
    plugins: [react()],
    server: {
      host: true,
      allowedHosts,
    },
  }
})
