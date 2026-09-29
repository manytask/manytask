import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// Vite 8 forwards polling through its legacy `chokidar` option. Native
// filesystem events can stall on mounted workspaces; polling also works in Docker.
const watchOptions = {buildDelay: 100, chokidar: {usePolling: true, interval: 500}};

export default defineConfig({
  base: '/static/dist/',
  plugins: [react()],
  build: {
    outDir: '../manytask/static/dist',
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {input: 'src/main.tsx', watch: watchOptions},
  },
});
