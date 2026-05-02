import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const proxyTarget = process.env.VITE_API_BASE || "http://localhost:8000";

const proxyPaths = ["/api", "/scan", "/lead", "/voice", "/admin", "/financial", "/health"];

export default defineConfig({
  // Load .env / .env.local from project root (monorepo) so VITE_* vars
  // populated in the root file are picked up here.
  envDir: path.resolve(__dirname, "../.."),
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      proxyPaths.map((p) => [
        p,
        {
          target: proxyTarget,
          changeOrigin: true,
          ws: true,
          // SSE: don't buffer
          configure: (proxy) => {
            proxy.on("proxyRes", (proxyRes) => {
              proxyRes.headers["x-accel-buffering"] = "no";
            });
          },
        },
      ])
    ),
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
});
