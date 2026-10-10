const deploymentMode = import.meta.env.VITE_DEPLOYMENT_MODE?.trim() || "local";
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, "") || "";
const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN?.trim() || "";
const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID?.trim() || "";
const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim() || "";
const releaseId = import.meta.env.VITE_RELEASE_ID?.trim() || "unknown";

if (import.meta.env.PROD && ["beta", "production"].includes(deploymentMode)) {
  const missing = [
    ["VITE_API_BASE_URL", apiBaseUrl],
    ["VITE_AUTH0_DOMAIN", auth0Domain],
    ["VITE_AUTH0_CLIENT_ID", auth0ClientId],
    ["VITE_AUTH0_AUDIENCE", auth0Audience],
    ["VITE_RELEASE_ID", releaseId === "unknown" ? "" : releaseId],
  ].filter(([, value]) => !value).map(([name]) => name);
  if (missing.length) throw new Error(`Missing deployed frontend configuration: ${missing.join(", ")}`);
  if (!apiBaseUrl.startsWith("https://")) throw new Error("VITE_API_BASE_URL must use HTTPS");
  if (import.meta.env.VITE_LOCAL_AUTH === "true") throw new Error("VITE_LOCAL_AUTH is forbidden in deployed builds");
}

export const runtimeConfig = {
  deploymentMode,
  apiBaseUrl,
  auth0Domain,
  auth0ClientId,
  auth0Audience,
  releaseId,
} as const;
