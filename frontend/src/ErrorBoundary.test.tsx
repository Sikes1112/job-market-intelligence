// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { AppErrorBoundary } from "./ErrorBoundary";
import { configureFrontendErrorReporter } from "./errorMonitoring";

function ThrowingView() {
  throw new Error("secret stack trace detail");
  return null;
}

describe("frontend error boundary", () => {
  afterEach(() => {
    cleanup();
    configureFrontendErrorReporter(null);
    vi.restoreAllMocks();
  });

  test("renders a safe fallback and reports a provider-neutral event", () => {
    const reporter = vi.fn();
    configureFrontendErrorReporter(reporter);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <AppErrorBoundary>
        <ThrowingView />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "Demo temporarily unavailable" })).toBeTruthy();
    expect(screen.queryByText(/secret stack trace detail/i)).toBeNull();
    expect(reporter).toHaveBeenCalledWith(expect.objectContaining({
      source: "error_boundary",
      name: "Error",
      message: "secret stack trace detail",
    }));
  });
});
