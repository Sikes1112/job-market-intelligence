export type FrontendErrorSource = "api_request" | "error_boundary";

export type FrontendErrorEvent = {
  source: FrontendErrorSource;
  name: string;
  message: string;
  route?: string;
  path?: string;
  statusCode?: number;
  requestId?: string;
};

export type FrontendErrorReporter = (event: FrontendErrorEvent) => void;

let configuredReporter: FrontendErrorReporter | null = null;

export function configureFrontendErrorReporter(reporter: FrontendErrorReporter | null): void {
  configuredReporter = reporter;
}

export function reportFrontendError(
  error: unknown,
  context: Omit<FrontendErrorEvent, "name" | "message">,
): void {
  if (!configuredReporter) return;

  const event: FrontendErrorEvent = {
    ...context,
    name: error instanceof Error ? error.name : "Error",
    message: error instanceof Error ? error.message : "Unknown frontend error",
  };

  try {
    configuredReporter(event);
  } catch {
    // Monitoring adapters must not break the public demo experience.
  }
}
