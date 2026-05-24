// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { FrontendAuthProvider, useFrontendAuth } from "./auth";

function AuthProbe() {
  const auth = useFrontendAuth();
  return (
    <div>
      <span data-testid="configured">{String(auth.isConfigured)}</span>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="loading">{String(auth.isLoading)}</span>
    </div>
  );
}

describe("frontend Auth0 local configuration behavior", () => {
  test("missing Auth0 config leaves the app in signed-out local mode", () => {
    render(
      <FrontendAuthProvider>
        <AuthProbe />
      </FrontendAuthProvider>,
    );

    expect(screen.getByTestId("configured").textContent).toBe("false");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });
});
