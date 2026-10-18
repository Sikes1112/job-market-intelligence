import type { MouseEvent } from "react";

import { PUBLIC_INFO_LINKS } from "./publicContent";
import { landingUrl, type PublicPage } from "./urlState";

export type PublicLinkClickHandler = (event: MouseEvent<HTMLAnchorElement>, url: string) => void;

export function PublicInfoLinks({
  activePage,
  onNavigate,
  variant,
  includeOverview = false,
}: {
  activePage: PublicPage | null;
  onNavigate: PublicLinkClickHandler;
  variant: "sidebar" | "footer" | "top";
  includeOverview?: boolean;
}) {
  const links = variant === "top"
    ? PUBLIC_INFO_LINKS.filter((item) => ["guides", "benchmarks", "reports", "methodology"].includes(item.page))
    : PUBLIC_INFO_LINKS;
  return (
    <nav className={`public-link-list public-link-list-${variant}`} aria-label="Public information">
      {includeOverview ? (
        <a
          className={activePage === "landing" ? "public-link-active" : ""}
          href={landingUrl()}
          onClick={(event) => onNavigate(event, landingUrl())}
        >
          Overview
        </a>
      ) : null}
      {links.map((item) => (
        <a
          className={activePage === item.page ? "public-link-active" : ""}
          href={item.href}
          key={item.page}
          onClick={(event) => onNavigate(event, item.href)}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

export function PublicFooter({
  activePage,
  onNavigate,
}: {
  activePage: PublicPage | null;
  onNavigate: PublicLinkClickHandler;
}) {
  return (
    <footer className="public-footer">
      <p>Public demo only. Verify important decisions independently.</p>
      <PublicInfoLinks activePage={activePage} includeOverview onNavigate={onNavigate} variant="footer" />
    </footer>
  );
}
