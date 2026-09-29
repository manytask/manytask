import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/static/dist/',
  plugins: [react()],
  build: {
    outDir: '../manytask/static/dist',
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {input: 'src/main.tsx'},
  },
});
