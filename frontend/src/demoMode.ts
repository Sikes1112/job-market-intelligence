import type { ProductPage } from "./urlState";

const PUBLIC_DEMO_BLOCKED_PRODUCTS = new Set<ProductPage>([
  "opportunity-routes",
  "policy",
]);

export function isPublicDemoMode(): boolean {
  return import.meta.env.VITE_PUBLIC_DEMO === "true";
}

export function isPublicDemoBlockedProduct(page: ProductPage): boolean {
  return isPublicDemoMode() && PUBLIC_DEMO_BLOCKED_PRODUCTS.has(page);
}

