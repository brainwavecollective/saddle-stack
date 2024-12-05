import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Load environment variables
const HOST = process.env.HOST || 'localhost';
const BACKEND_PORT = process.env.BACKEND_PORT || '9000';
const BACKEND_URL = process.env.BACKEND_URL || `http://${HOST}:${BACKEND_PORT}`;
const WS_URL = BACKEND_URL.replace(/^http/, 'ws');

export default defineConfig({
  plugins: [react()],
  root: 'app/static',
  base: '/',
  server: {
    host: true,
    port: 5173,
    proxy: {
		'/api': {
		  target: BACKEND_URL,
		  changeOrigin: true,
		  secure: false,
		  ws: true
		}
    }
  },
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      input: 'app/static/index.html',
      output: {
        entryFileNames: 'static/js/[name].[hash].js',
        chunkFileNames: 'static/js/[name].[hash].js',
        assetFileNames: ({name}) => {
          if (/\.(gif|jpe?g|png|svg)$/.test(name)) {
            return 'static/images/[name].[hash][ext]';
          }
          if (/\.(mp3|wav)$/.test(name)) {
            return 'static/audio/[name].[hash][ext]';
          }
          if (/\.(mp4|webm)$/.test(name)) {
            return 'static/video/[name].[hash][ext]';
          }
          return 'static/assets/[name].[hash][ext]';
        }
      }
    }
  }
});