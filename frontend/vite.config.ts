import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/regions": "http://127.0.0.1:8000",
      "/companies": "http://127.0.0.1:8000",
      "/compare": "http://127.0.0.1:8000",
      "/discover": "http://127.0.0.1:8000",
      "/recommendations": "http://127.0.0.1:8000",
      "/me": "http://127.0.0.1:8000",
    },
  },
});
