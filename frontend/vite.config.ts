import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The landing is built into the Flask app's static dir so it ships with the
// same server. base '/landing/' makes every asset URL resolve under that path.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/landing/',
  build: {
    outDir: '../static/landing',
    emptyOutDir: true,
  },
})
