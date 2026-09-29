import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    setupFiles: ['src/test/setup.ts'],
    server: {deps: {inline: ['@gravity-ui/uikit', '@gravity-ui/table', '@gravity-ui/icons']}},
  },
});
