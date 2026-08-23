import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
  },
  build: {
    target: "es2020",
    chunkSizeWarningLimit: 600,
  },
});
