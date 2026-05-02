import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const proxyTarget = process.env.VITE_API_BASE || "http://localhost:8000";

// Every API surface the frontend hits in dev MUST be listed here. Missing a
// path means the request falls through to the Vite dev server (returns the
// SPA HTML), which surfaces in the UI as confusing JSON parse errors or
// "Failed to fetch". Keep this list aligned with packages/api/app/main.py.
const proxyPaths = [
  "/api",
  "/scan",
  "/lead", // singular — /lead/{id}/...
  "/leads", // plural — list endpoint
  "/voice",
  "/admin",
  "/financial",
  "/inbound",
  "/swarm",
  "/static", // generated decks, flux PNGs, swarm artifacts
  "/health",
];

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
