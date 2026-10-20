// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import type { FrontendAuthContextValue } from "./auth";
import { ProductShell } from "./ProductShell";

const auth = {
  error: null,
  getAccessTokenSilently: vi.fn(),
  isAuthenticated: true,
  isConfigured: true,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
  user: { name: "Local Reviewer", sub: "local|explorer" },
} as unknown as FrontendAuthContextValue;

afterEach(cleanup);

describe("ProductShell", () => {
  test("exposes every flagship destination in desktop and mobile navigation", () => {
    render(
      <ProductShell
        activePage="current-opportunities"
        auth={auth}
        navigation={{ comparisonA: "greater_boston", comparisonB: "washington_dc" }}
        onNavigate={vi.fn()}
        onSearch={vi.fn()}
        routePath="/markets/current-opportunities"
        usesIndividualShell
      >
        <p>Page content</p>
      </ProductShell>,
    );

    for (const label of ["Explore", "Compare", "Opportunities", "Recommendations", "Decisions", "Jobs", "For you", "Decide"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByRole("link", { current: "page" }).map((link) => link.textContent)).toEqual(expect.arrayContaining(["Opportunities", "Jobs"]));
  });

  test("routes searches and keeps advanced tools available", () => {
    const onSearch = vi.fn();
    render(
      <ProductShell
        activePage="explore"
        auth={auth}
        navigation={{ comparisonA: "greater_boston", comparisonB: "sf_bay_area" }}
        onNavigate={vi.fn()}
        onSearch={onSearch}
        routePath="/markets"
        usesIndividualShell
      >
        <p>Page content</p>
      </ProductShell>,
    );
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Boston" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(onSearch).toHaveBeenCalledWith("Boston");
    expect(screen.getByText("Market intelligence")).toBeInTheDocument();
    expect(screen.getByText("Opportunity data health")).toBeInTheDocument();
  });

  test("closes the account popover after internal navigation", () => {
    const onNavigate = vi.fn();
    const { container } = render(
      <ProductShell
        activePage="explore"
        auth={auth}
        navigation={{ comparisonA: "greater_boston", comparisonB: "sf_bay_area" }}
        onNavigate={onNavigate}
        onSearch={vi.fn()}
        routePath="/markets"
        usesIndividualShell
      >
        <p>Page content</p>
      </ProductShell>,
    );
    const menu = container.querySelector<HTMLDetailsElement>("details.account-menu");
    expect(menu).not.toBeNull();
    menu!.open = true;

    const profileLink = menu!.querySelector<HTMLAnchorElement>('a[href="/markets/profile"]');
    expect(profileLink).not.toBeNull();
    fireEvent.click(profileLink!);

    expect(menu).not.toHaveAttribute("open");
    expect(onNavigate).toHaveBeenCalledWith("/markets/profile", undefined);
  });
});
