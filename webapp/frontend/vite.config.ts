import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI server (webapp/server.py) owns the API on :8317. In dev, Vite
// proxies /api and /health to it so the frontend can use relative URLs in both
// dev and production builds.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: "http://127.0.0.1:8317", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8317", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    emptyOutDir: true,
    sourcemap: false,
  },
});
