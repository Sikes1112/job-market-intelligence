import { useState, type FormEvent, type MouseEvent, type ReactNode } from "react";

import type { FrontendAuthContextValue } from "./auth";
import { BetaFeedback } from "./BetaFeedback";
import {
  accountUrl,
  careerAgentUrl,
  careerIdentityUrl,
  currentOpportunityOperationsUrl,
  currentOpportunitiesUrl,
  decisionsUrl,
  exploreComparisonUrl,
  exploreUrl,
  institutionDashboardUrl,
  marketIntelligenceUrl,
  mySearchUrl,
  opportunityRoutesUrl,
  policyLandingUrl,
  profileUrl,
  recommendationsUrl,
  userIntelligenceDashboardUrl,
  type AppPage,
} from "./urlState";

export type ProductNavigationContext = {
  comparisonA: string;
  comparisonB: string;
};

type ProductShellProps = {
  accountNotice?: ReactNode;
  activePage: AppPage;
  auth: FrontendAuthContextValue;
  children: ReactNode;
  footer?: ReactNode;
  navigation: ProductNavigationContext;
  onNavigate: (url: string, options?: { replace?: boolean }) => void;
  onSearch: (query: string) => void | Promise<void>;
  routeLabel?: string;
  routePath: string;
  usesIndividualShell: boolean;
};

type Destination = {
  activePages: AppPage[];
  label: string;
  mobileLabel: string;
  url: (context: ProductNavigationContext) => string;
};

const FLAGSHIP_DESTINATIONS: Destination[] = [
  {
    activePages: ["explore", "region", "company"],
    label: "Explore",
    mobileLabel: "Explore",
    url: () => exploreUrl(),
  },
  {
    activePages: ["compare"],
    label: "Compare",
    mobileLabel: "Compare",
    url: ({ comparisonA, comparisonB }) => exploreComparisonUrl({
      selected: [comparisonA, comparisonB],
      view: "list",
    }),
  },
  {
    activePages: ["current-opportunities"],
    label: "Opportunities",
    mobileLabel: "Jobs",
    url: () => currentOpportunitiesUrl(),
  },
  {
    activePages: ["recommendations", "discovery"],
    label: "Recommendations",
    mobileLabel: "For you",
    url: () => recommendationsUrl(),
  },
  {
    activePages: ["decisions", "my-search"],
    label: "Decisions",
    mobileLabel: "Decide",
    url: () => decisionsUrl(),
  },
];

const WORKSPACE_LINKS = [
  { label: "Career Identity", url: careerIdentityUrl() },
  { label: "My Search", url: mySearchUrl() },
  { label: "Profile", url: profileUrl() },
  { label: "Account settings", url: accountUrl() },
];

const ADVANCED_LINKS = [
  { label: "Intelligence dashboard", url: userIntelligenceDashboardUrl() },
  { label: "Market intelligence", url: marketIntelligenceUrl() },
  { label: "Career agent", url: careerAgentUrl() },
  { label: "Opportunity routing", url: opportunityRoutesUrl() },
  { label: "Opportunity data health", url: currentOpportunityOperationsUrl() },
  { label: "Policy intelligence", url: policyLandingUrl() },
  { label: "Institution workspace", url: institutionDashboardUrl() },
];

function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button === 0 && !event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey;
}

function ProductLink({
  children,
  className,
  current,
  onNavigate,
  url,
}: {
  children: ReactNode;
  className?: string;
  current?: boolean;
  onNavigate: ProductShellProps["onNavigate"];
  url: string;
}) {
  return (
    <a
      aria-current={current ? "page" : undefined}
      className={className}
      href={url}
      onClick={(event) => {
        if (!isPlainLeftClick(event)) return;
        event.preventDefault();
        onNavigate(url);
      }}
    >
      {children}
    </a>
  );
}

export function ProductShell({
  accountNotice,
  activePage,
  auth,
  children,
  footer,
  navigation,
  onNavigate,
  onSearch,
  routeLabel,
  routePath,
  usesIndividualShell,
}: ProductShellProps) {
  const [search, setSearch] = useState("");

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSearch(search);
  }

  if (!usesIndividualShell) {
    return (
      <div className="app-shell secondary-context-shell">
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <header className="secondary-context-header">
          <ProductLink className="product-brand" onNavigate={onNavigate} url="/">
            <span className="brand-mark">JM</span>
            <strong>Job Market Intelligence</strong>
          </ProductLink>
          <strong>{routeLabel}</strong>
        </header>
        <main className="content-shell" id="main-content" tabIndex={-1}>
          {accountNotice}
          {children}
          {footer}
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell redesigned-app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="product-header">
        <ProductLink className="product-brand" onNavigate={onNavigate} url={exploreUrl()}>
          <span className="brand-mark">JM</span>
          <span className="brand-copy">
            <strong>Job Market Intelligence</strong>
            <small>Explore evidence. Make a move.</small>
          </span>
        </ProductLink>

        <form className="global-search" onSubmit={submitSearch} role="search">
          <label className="sr-only" htmlFor="global-search-input">Search markets or roles</label>
          <input
            id="global-search-input"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search markets or supported roles…"
            type="search"
            value={search}
          />
        </form>

        <nav className="primary-product-nav" aria-label="Main navigation">
          {FLAGSHIP_DESTINATIONS.map((item) => {
            const url = item.url(navigation);
            const active = item.activePages.includes(activePage);
            return (
              <ProductLink
                className={active ? "primary-nav-item primary-nav-item-active" : "primary-nav-item"}
                current={active}
                key={item.label}
                onNavigate={onNavigate}
                url={url}
              >
                {item.label}
              </ProductLink>
            );
          })}
        </nav>

        <details className="tools-menu shell-popover">
          <summary>Tools</summary>
          <div>
            <p>Workspace</p>
            {WORKSPACE_LINKS.slice(0, 3).map((item) => (
              <ProductLink key={item.url} onNavigate={onNavigate} url={item.url}>{item.label}</ProductLink>
            ))}
            <p>Advanced</p>
            {ADVANCED_LINKS.map((item) => (
              <ProductLink key={item.url} onNavigate={onNavigate} url={item.url}>{item.label}</ProductLink>
            ))}
          </div>
        </details>

        <details className="account-menu shell-popover">
          <summary aria-label="Account and workspace menu">
            {auth.user?.picture
              ? <img alt="" src={auth.user.picture} />
              : (auth.user?.name ?? auth.user?.email ?? "Account").slice(0, 2).toUpperCase()}
          </summary>
          <div>
            <strong>{auth.user?.name ?? auth.user?.email ?? (auth.isAuthenticated ? "Account" : "Signed out")}</strong>
            {auth.isAuthenticated ? (
              <>
                {WORKSPACE_LINKS.map((item) => (
                  <ProductLink key={item.url} onNavigate={onNavigate} url={item.url}>{item.label}</ProductLink>
                ))}
                <button onClick={auth.logout} type="button">Sign out</button>
              </>
            ) : <button onClick={() => void auth.login()} type="button">Sign in</button>}
          </div>
        </details>
      </header>

      <main className="content-shell redesigned-content-shell" id="main-content" tabIndex={-1}>
        {accountNotice}
        {children}
        {footer}
      </main>

      {auth.isAuthenticated ? <BetaFeedback auth={auth} route={routePath} /> : null}

      <nav className="mobile-product-nav" aria-label="Primary mobile navigation">
        {FLAGSHIP_DESTINATIONS.map((item) => {
          const url = item.url(navigation);
          const active = item.activePages.includes(activePage);
          return (
            <ProductLink current={active} key={item.label} onNavigate={onNavigate} url={url}>
              <span aria-hidden="true" className={`mobile-nav-icon mobile-nav-icon-${item.mobileLabel.toLowerCase().replace(" ", "-")}`} />
              <span>{item.mobileLabel}</span>
            </ProductLink>
          );
        })}
      </nav>
    </div>
  );
}
