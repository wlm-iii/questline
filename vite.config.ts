import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
<<<<<<< Updated upstream
  plugins: [react()],
=======
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 5175, strictPort: true },
>>>>>>> Stashed changes
})
