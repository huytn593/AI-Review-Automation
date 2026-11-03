import { defineConfig } from 'vite'
export default defineConfig({
  server: {host:"127.0.0.1",proxy: Object.fromEntries(['/jobs','/health'].map(path => [path, {target:'http://127.0.0.1:8001',changeOrigin:false}]))},
})
