import { runtimeConfig } from "./runtimeConfig";

export type FrontendErrorSource = "api_request" | "error_boundary";

export type FrontendErrorEvent = {
  source: FrontendErrorSource;
  name: string;
  message: string;
  route?: string;
  path?: string;
  statusCode?: number;
  requestId?: string;
  releaseId: string;
};

export type FrontendErrorReporter = (event: FrontendErrorEvent) => void;

type PublicClientError = Error & { requestId?: unknown; statusCode?: unknown };

let configuredReporter: FrontendErrorReporter | null = null;

export function configureFrontendErrorReporter(reporter: FrontendErrorReporter | null): void {
  configuredReporter = reporter;
}

export function reportFrontendError(
  error: unknown,
  context: Omit<FrontendErrorEvent, "name" | "message" | "releaseId">,
): void {
  if (!configuredReporter) return;

  const event: FrontendErrorEvent = {
    ...context,
    name: error instanceof Error ? error.name : "Error",
    message: safeErrorMessage(error),
    releaseId: runtimeConfig.releaseId,
  };

  try {
    configuredReporter(event);
  } catch {
    // Monitoring adapters must not break the public demo experience.
  }
}

function safeErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) return "Unknown frontend error";
  const publicError = error as PublicClientError;
  if (typeof publicError.statusCode === "number" || typeof publicError.requestId === "string") {
    return error.message.slice(0, 512);
  }
  return "Frontend runtime error";
}
