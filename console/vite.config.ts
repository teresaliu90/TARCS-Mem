import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  base: "/console/",
  plugins: [react()],
  build: {
    outDir: resolve(import.meta.dirname, "../src/tarcsmem/console_dist"),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    proxy: {
      "/v1": "http://127.0.0.1:8000",
      "/metrics": "http://127.0.0.1:8000",
    },
  },
});
