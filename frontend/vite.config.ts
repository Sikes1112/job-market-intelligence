import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, ".", "");
  const deploymentMode = env.VITE_DEPLOYMENT_MODE?.trim();
  const deployedBuild = command === "build"
    && (env.VERCEL === "1" || ["beta", "production"].includes(deploymentMode));
  if (deployedBuild) {
    const required = [
      "VITE_DEPLOYMENT_MODE",
      "VITE_API_BASE_URL",
      "VITE_AUTH0_DOMAIN",
      "VITE_AUTH0_CLIENT_ID",
      "VITE_AUTH0_AUDIENCE",
      "VITE_RELEASE_ID",
    ];
    const missing = required.filter((name) => !env[name]?.trim());
    if (missing.length) {
      throw new Error(`Missing deployed frontend configuration: ${missing.join(", ")}`);
    }
    if (!["beta", "production"].includes(deploymentMode)) {
      throw new Error("VITE_DEPLOYMENT_MODE must be beta or production for a deployed build");
    }
    if (!env.VITE_API_BASE_URL.startsWith("https://")) {
      throw new Error("VITE_API_BASE_URL must use HTTPS for a deployed build");
    }
    if (env.VITE_LOCAL_AUTH === "true") {
      throw new Error("VITE_LOCAL_AUTH is forbidden in deployed builds");
    }
  }

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/health": "http://127.0.0.1:8000",
        "/regions": "http://127.0.0.1:8000",
        "/companies": "http://127.0.0.1:8000",
        "/compare": "http://127.0.0.1:8000",
        "/discover": "http://127.0.0.1:8000",
        "/recommendations": "http://127.0.0.1:8000",
        "/current-opportunities": "http://127.0.0.1:8000",
        "/user-intelligence": "http://127.0.0.1:8000",
        "/monetization": "http://127.0.0.1:8000",
        "/me": "http://127.0.0.1:8000",
      },
    },
  };
});
