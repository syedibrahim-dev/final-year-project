// client/vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Vite automatically serves index.html for all unmatched routes in dev mode,
  // so React Router handles client-side navigation without any extra config.
});
