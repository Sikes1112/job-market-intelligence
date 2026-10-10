// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { BetaFeedback } from "./BetaFeedback";
import type { FrontendAuthContextValue } from "./auth";

const mocks = vi.hoisted(() => ({ createSupportCase: vi.fn() }));

vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  createSupportCase: mocks.createSupportCase,
}));

const auth: FrontendAuthContextValue = {
  isConfigured: true,
  isAuthenticated: true,
  isLoading: false,
  error: null,
  user: { sub: "auth0|beta-feedback" },
  login: vi.fn(),
  logout: vi.fn(),
  getAccessTokenSilently: vi.fn(async () => "token"),
};

describe("beta feedback", () => {
  beforeEach(() => {
    mocks.createSupportCase.mockResolvedValue({ status: "success", data: {} });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("submits user text with route and release but no Profile payload", async () => {
    render(<BetaFeedback auth={auth} route="/explore?focus=boston" />);
    fireEvent.click(screen.getByRole("button", { name: "Beta feedback" }));
    fireEvent.change(screen.getByLabelText("What felt confusing or unhelpful?"), {
      target: { value: "The confidence label was unclear." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));

    await waitFor(() => expect(mocks.createSupportCase).toHaveBeenCalledTimes(1));
    const request = mocks.createSupportCase.mock.calls[0][0];
    expect(request.description).toContain("The confidence label was unclear.");
    expect(request.description).toContain("Route: /explore?focus=boston");
    expect(request.description).toContain("Release:");
    expect(JSON.stringify(request)).not.toMatch(/career_identity|resume|profile_text/i);
    expect(await screen.findByRole("status")).toHaveTextContent("feedback sent");
  });

  test("preserves the draft when submission fails", async () => {
    mocks.createSupportCase.mockRejectedValueOnce(new Error("network unavailable"));
    render(<BetaFeedback auth={auth} route="/my-search" />);
    fireEvent.click(screen.getByRole("button", { name: "Beta feedback" }));
    const field = screen.getByLabelText("What felt confusing or unhelpful?");
    fireEvent.change(field, { target: { value: "Keep this draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("text is still here");
    expect(field).toHaveValue("Keep this draft");
  });
});
