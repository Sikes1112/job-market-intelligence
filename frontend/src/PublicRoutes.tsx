import { Suspense, lazy, useEffect, useState, type ReactNode } from "react";

import { ApiError, getPlatformEmbed } from "./api";
import { PublicFooter, PublicInfoLinks, type PublicLinkClickHandler } from "./PublicNavigation";
import type {
  ApiEnvelope,
  FreshnessStatus,
  PlatformEmbedPayload,
  PredictiveReportForecast,
  PredictiveReportPayload,
  PredictiveReportSection,
  PublicBenchmark,
  PublicBenchmarkListPayload,
  PublicBenchmarkMarketResult,
  PublicCitation,
  PublicInstitutionalCta,
  PublicReport,
  PublicReportListPayload,
  PublicReportMarketResult,
  PublicShareSummary,
  PublicSourceAuthority,
} from "./types";
import {
  exploreUrl,
  landingUrl,
  publicBenchmarkUrl,
  publicPageUrl,
  publicReportUrl,
  type PublicPage,
  type RouteState,
} from "./urlState";
import {
  DATA_LICENSING_COPY,
  DEVELOPER_DOCS_COPY,
  DEVELOPER_DOCS_NAV,
  DEMO_DISCLOSURE_COPY,
  LANDING_COPY,
  LEGAL_PAGE_COPY,
  type DeveloperDocPageKey,
  type LegalPublicPage,
} from "./publicContent";
import {
  PUBLIC_SEO_PAGES,
  getPublicSeoPageBySlug,
  publicSeoPageUrl,
  relatedSeoPages,
  type PublicSeoConfidence,
  type PublicSeoLink,
  type PublicSeoPage,
} from "./publicSeoContent";

const DataStandardsPage = lazy(() => import("./DataStandardsPage"));

type LoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};

function segmentLabel(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state">
      <strong>Request failed</strong>
      <p>{message}</p>
    </div>
  );
}

function LoadingBlock({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="loading-block">
      <span />
      {label}
    </div>
  );
}

type LinkClickHandler = PublicLinkClickHandler;

function DemoDisclosure({ compact = false }: { compact?: boolean }) {
  return (
    <aside className={compact ? "demo-disclosure demo-disclosure-compact" : "demo-disclosure"}>
      <div>
        <strong>{DEMO_DISCLOSURE_COPY.title}</strong>
        <p>{DEMO_DISCLOSURE_COPY.summary}</p>
      </div>
      {!compact ? (
        <details>
          <summary>Data notes</summary>
          <ul>
            {DEMO_DISCLOSURE_COPY.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </aside>
  );
}

function PublicShell({
  activePage,
  children,
  onNavigate,
}: {
  activePage: PublicPage;
  children: ReactNode;
  onNavigate: LinkClickHandler;
}) {
  return (
    <main className="public-shell">
      <header className="public-header">
        <a className="public-brand" href={landingUrl()} onClick={(event) => onNavigate(event, landingUrl())}>
          <span className="brand-mark">JM</span>
          <span>
            <strong>Job Market Intelligence</strong>
            <small>Career market intelligence</small>
          </span>
        </a>
        <div className="public-header-actions">
          <PublicInfoLinks activePage={activePage} onNavigate={onNavigate} variant="top" />
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            Explore markets
          </a>
        </div>
      </header>
      <section className="public-content">
        {children}
      </section>
      <PublicFooter activePage={activePage} onNavigate={onNavigate} />
    </main>
  );
}

function LandingPage({
  onNavigate,
  unknownPath,
}: {
  onNavigate: LinkClickHandler;
  unknownPath?: string;
}) {
  return (
    <div className="public-page">
      <section className="public-intro">
        <p className="eyebrow">{LANDING_COPY.eyebrow}</p>
        <h1>{LANDING_COPY.title}</h1>
        <p className="public-lead">{LANDING_COPY.intro}</p>
        {unknownPath ? (
          <p className="meta-copy">Unknown public path opened the overview: {unknownPath}</p>
        ) : null}
        <div className="hero-actions">
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            {LANDING_COPY.ctaLabel}
          </a>
          <a
            className="secondary-button"
            href={publicPageUrl("methodology")}
            onClick={(event) => onNavigate(event, publicPageUrl("methodology"))}
          >
            {LANDING_COPY.secondaryCtaLabel}
          </a>
        </div>
      </section>

      <DemoDisclosure />

      <section className="public-section-grid" aria-label="Demo overview">
        {LANDING_COPY.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

function LegalPage({ page }: { page: LegalPublicPage }) {
  const copy = LEGAL_PAGE_COPY[page];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">{copy.eyebrow}</p>
        <h1>{copy.title}</h1>
        <p className="public-lead">{copy.intro}</p>
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={copy.title}>
        {copy.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}

function DevelopersPage({ onNavigate }: { onNavigate: LinkClickHandler }) {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Developer portal</p>
        <h1>Platform API developer portal</h1>
        <p className="public-lead">
          Build against secured, versioned, public-safe market intelligence endpoints with documented authentication,
          response metadata, limits, and product contracts.
        </p>
        <div className="hero-actions">
          <a
            className="primary-button"
            href={publicPageUrl("developer-docs")}
            onClick={(event) => onNavigate(event, publicPageUrl("developer-docs"))}
          >
            Read docs
          </a>
          <a
            className="secondary-button"
            href="/api/v1/platform/docs/openapi.json"
          >
            OpenAPI JSON
          </a>
          <a
            className="secondary-button"
            href="/api/v1/platform/docs/postman.json"
          >
            Postman JSON
          </a>
        </div>
      </section>
      <section className="public-section-grid" aria-label="Developer documentation areas">
        {DEVELOPER_DOCS_NAV.slice(0, 5).map((item) => (
          <article className="public-section" key={item.page}>
            <h2>{item.label}</h2>
            <p>{DEVELOPER_DOCS_COPY[item.page].summary}</p>
            <a href={item.href} onClick={(event) => onNavigate(event, item.href)}>
              Open {item.label.toLowerCase()}
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function DeveloperDocsPage({
  page,
  onNavigate,
}: {
  page: DeveloperDocPageKey;
  onNavigate: LinkClickHandler;
}) {
  const copy = DEVELOPER_DOCS_COPY[page];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Platform API docs</p>
        <h1>{copy.title}</h1>
        <p className="public-lead">{copy.summary}</p>
      </section>
      <nav className="developer-doc-nav" aria-label="Developer docs">
        {DEVELOPER_DOCS_NAV.map((item) => (
          <a
            className={item.page === page ? "public-link-active" : ""}
            href={item.href}
            key={item.page}
            onClick={(event) => onNavigate(event, item.href)}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <section className="public-document-list" aria-label={copy.title}>
        {copy.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}

function DataLicensingPage() {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">{DATA_LICENSING_COPY.eyebrow}</p>
        <h1>{DATA_LICENSING_COPY.title}</h1>
        <p className="public-lead">{DATA_LICENSING_COPY.intro}</p>
        <div className="hero-actions">
          <a className="primary-button" href="mailto:sales@example.com">
            {DATA_LICENSING_COPY.cta}
          </a>
        </div>
      </section>
      <section className="public-section-grid" aria-label="Licensed datasets">
        {DATA_LICENSING_COPY.datasets.map((dataset) => (
          <article className="public-section" key={dataset.datasetId}>
            <p className="eyebrow">{dataset.datasetId}</p>
            <h2>{dataset.title}</h2>
            <p>{dataset.description}</p>
            <dl className="authority-detail-list">
              <div>
                <dt>Sample fields</dt>
                <dd>{dataset.sampleFields.join(", ")}</dd>
              </div>
              <div>
                <dt>Source safety</dt>
                <dd>{dataset.sourceSafety}</dd>
              </div>
            </dl>
            <ul>
              {dataset.restrictions.map((restriction) => (
                <li key={restriction}>{restriction}</li>
              ))}
            </ul>
          </article>
        ))}
      </section>
    </div>
  );
}

type PlatformEmbedPage = "embed-region-comparison" | "embed-market-score-card";
type PlatformEmbedViewState = {
  loading: boolean;
  payload: PlatformEmbedPayload | null;
  denialCode: string | null;
};
type LocationWithAncestorOrigins = Location & {
  ancestorOrigins?: {
    length: number;
    [index: number]: string | undefined;
    item?: (index: number) => string | null;
  };
};

const PLATFORM_EMBED_SLUG_BY_PAGE: Record<PlatformEmbedPage, string> = {
  "embed-region-comparison": "region-comparison",
  "embed-market-score-card": "market-score-card",
};

function PlatformEmbedView({ page }: { page: PlatformEmbedPage }) {
  const productSlug = PLATFORM_EMBED_SLUG_BY_PAGE[page];
  const [state, setState] = useState<PlatformEmbedViewState>({
    loading: true,
    payload: null,
    denialCode: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, payload: null, denialCode: null });
    getPlatformEmbed(productSlug, readPlatformEmbedOrigin())
      .then((envelope) => {
        if (cancelled) return;
        const payload = envelope.data?.payload ?? null;
        setState({
          loading: false,
          payload,
          denialCode: payload ? null : "EMBED_POLICY_DENIED",
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const denialCode = error instanceof ApiError
          ? error.envelope?.error?.code ?? "EMBED_POLICY_DENIED"
          : "EMBED_POLICY_DENIED";
        setState({ loading: false, payload: null, denialCode });
      });
    return () => {
      cancelled = true;
    };
  }, [productSlug]);

  if (state.loading) {
    return (
      <main className="embed-shell">
        <section className="embed-card" aria-label="Embed loading">
          <p className="eyebrow">Partner embed</p>
          <h1>Checking embed access</h1>
        </section>
      </main>
    );
  }

  if (!state.payload) {
    return (
      <main className="embed-shell">
        <section className="embed-card embed-denial" aria-label="Embed denied">
          <p className="eyebrow">Partner embed</p>
          <h1>Embed unavailable</h1>
          <p className="meta-copy">{state.denialCode ?? "EMBED_POLICY_DENIED"}</p>
          <p>This embed is not approved for the requesting domain.</p>
        </section>
      </main>
    );
  }

  const payload = state.payload;
  return (
    <main className="embed-shell">
      <section className="embed-card" aria-label={`${payload.title} embed`}>
        <div>
          <p className="eyebrow">Partner embed</p>
          <h1>{payload.title}</h1>
          <p className="meta-copy">{payload.attribution}</p>
        </div>
        <div className="embed-metric-grid">
          {payload.metrics.map((metric, index) => (
            <article className="public-section" key={`${payload.embed_product_id}-${index}`}>
              <h2>{String(metric.label ?? "Metric")}</h2>
              {Object.entries(metric)
                .filter(([key]) => key !== "label")
                .map(([key, value]) => (
                  <p key={key}>
                    <strong>{formatEmbedMetricKey(key)}:</strong>{" "}
                    {formatEmbedMetricValue(value)}
                  </p>
                ))}
            </article>
          ))}
        </div>
        <dl className="authority-detail-list">
          <div>
            <dt>Freshness</dt>
            <dd>{formatEmbedFreshness(payload.freshness.status)}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{payload.confidence.label}</dd>
          </div>
          <div>
            <dt>Source summary</dt>
            <dd>
              {payload.source_summary.source_categories.join(", ")}
              {payload.source_summary.notes.length
                ? `; ${payload.source_summary.notes.join(" ")}`
                : ""}
            </dd>
          </div>
        </dl>
        <div className="warning-list" aria-label="Embed warnings">
          {payload.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Embed warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function readPlatformEmbedOrigin(): string | null {
  const locationWithAncestors = window.location as LocationWithAncestorOrigins;
  const ancestorOrigin = locationWithAncestors.ancestorOrigins?.[0]
    ?? locationWithAncestors.ancestorOrigins?.item?.(0)
    ?? null;
  if (ancestorOrigin) return ancestorOrigin;
  if (document.referrer) return document.referrer;
  return null;
}

function formatEmbedMetricKey(value: string): string {
  return value.replace(/_/g, " ");
}

function formatEmbedMetricValue(value: string | number | boolean | null): string {
  if (typeof value === "number") return value.toFixed(2);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return value ?? "Unknown";
}

function formatEmbedFreshness(status: string): string {
  if (status === "partial") return "Partial freshness metadata available";
  if (status === "fresh") return "Fresh metadata available";
  if (status === "stale") return "Freshness metadata is stale";
  return "Freshness metadata unavailable";
}

function publicConfidenceClass(
  confidence: PublicReport["confidence"] | PublicBenchmark["confidence"] | PublicSeoConfidence,
): string {
  if (confidence === "high") return "badge badge-success";
  if (confidence === "medium") return "badge badge-real";
  if (confidence === "low") return "badge badge-warning";
  return "badge badge-unknown";
}

function PublicReportBadgeRow({
  confidence,
  freshnessDate,
  freshnessStatus,
  warningCount,
}: {
  confidence: PublicReport["confidence"];
  freshnessDate: string;
  freshnessStatus?: FreshnessStatus;
  warningCount: number;
}) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(confidence)}>
        Confidence: {segmentLabel(confidence)}
      </span>
      <span className="badge badge-unknown">
        Freshness: {freshnessStatus ? segmentLabel(freshnessStatus) : "Unknown"}
      </span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(freshnessDate)}</span>
      {warningCount ? <span className="badge badge-warning">{warningCount} warning(s)</span> : null}
    </div>
  );
}

function PublicBenchmarkBadgeRow({
  confidence,
  freshnessDate,
  freshnessStatus,
  warningCount,
}: {
  confidence: PublicBenchmark["confidence"];
  freshnessDate: string;
  freshnessStatus?: FreshnessStatus;
  warningCount: number;
}) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(confidence)}>
        Confidence: {segmentLabel(confidence)}
      </span>
      <span className="badge badge-unknown">
        Freshness: {freshnessStatus ? segmentLabel(freshnessStatus) : "Unknown"}
      </span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(freshnessDate)}</span>
      {warningCount ? <span className="badge badge-warning">{warningCount} warning(s)</span> : null}
    </div>
  );
}

type CitationView = {
  sourceName: string;
  title: string;
  period: string;
  productAttribution: string;
  publicPath: string;
  accessedOrFreshnessDate: string;
};

type ShareSummaryView = {
  title: string;
  categoryClaim: string;
  confidenceLabel: string;
  freshnessLabel: string;
  takeaway: string;
  publicPath: string;
  warning: string;
};

type SourceAuthorityView = {
  labels: string[];
  summary: string;
};

type InstitutionalCtaView = {
  label: string;
  body: string;
  href: string;
};

function publicCitationView(citation: PublicCitation): CitationView {
  return {
    sourceName: citation.source_name,
    title: citation.title,
    period: citation.period,
    productAttribution: citation.product_attribution,
    publicPath: citation.public_path,
    accessedOrFreshnessDate: citation.accessed_or_freshness_date,
  };
}

function publicShareSummaryView(summary: PublicShareSummary): ShareSummaryView {
  return {
    title: summary.title,
    categoryClaim: summary.category_claim,
    confidenceLabel: summary.confidence_label,
    freshnessLabel: summary.freshness_label,
    takeaway: summary.takeaway,
    publicPath: summary.public_path,
    warning: summary.warning,
  };
}

function publicAuthorityView(authority: PublicSourceAuthority): SourceAuthorityView {
  return {
    labels: authority.labels,
    summary: authority.summary,
  };
}

function publicInstitutionalCtaView(cta: PublicInstitutionalCta): InstitutionalCtaView {
  return {
    label: cta.label,
    body: cta.body,
    href: cta.href,
  };
}

function CitationBlock({ citation }: { citation: CitationView }) {
  return (
    <article className="public-section authority-section">
      <h2>Suggested citation</h2>
      <p className="citation-copy">
        {citation.sourceName}. {citation.title}. {citation.period}.{" "}
        {citation.productAttribution}. {citation.publicPath}. Freshness date{" "}
        {formatDateOnly(citation.accessedOrFreshnessDate)}.
      </p>
      <dl className="authority-detail-list">
        <div>
          <dt>Source</dt>
          <dd>{citation.sourceName}</dd>
        </div>
        <div>
          <dt>Public path</dt>
          <dd>{citation.publicPath}</dd>
        </div>
        <div>
          <dt>Period</dt>
          <dd>{citation.period}</dd>
        </div>
      </dl>
    </article>
  );
}

function ShareSummaryCard({ summary }: { summary: ShareSummaryView }) {
  return (
    <article className="public-section share-summary-card">
      <h2>Share summary</h2>
      <p className="eyebrow">{publicNarrative(summary.categoryClaim)}</p>
      <strong className="share-summary-title">{publicNarrative(summary.title)}</strong>
      <div className="metadata-row">
        <span className="badge badge-warning">{summary.confidenceLabel}</span>
        <span className="badge badge-unknown">{summary.freshnessLabel}</span>
      </div>
      <p>{publicNarrative(summary.takeaway)}</p>
      <small>{summary.publicPath}</small>
      <div className="warning-list" aria-label="Share summary warning">
        <div className="warning-item">
          <div className="warning-header">
            <span className="warning-code">Share warning</span>
          </div>
          <p>{publicNarrative(summary.warning)}</p>
        </div>
      </div>
    </article>
  );
}

function SourceAuthorityLabel({ authority }: { authority: SourceAuthorityView }) {
  return (
    <article className="public-section authority-section">
      <h2>Source authority</h2>
      <div className="metadata-row">
        {authority.labels.map((label) => (
          <span className="badge badge-unknown" key={label}>{publicNarrative(label)}</span>
        ))}
      </div>
      <p>{publicNarrative(authority.summary)}</p>
    </article>
  );
}

function InstitutionalCtaBlock({
  cta,
  onNavigate,
}: {
  cta: InstitutionalCtaView;
  onNavigate: LinkClickHandler;
}) {
  return (
    <article className="public-section institutional-cta-block">
      <h2>Institutional use</h2>
      <p>{cta.body}</p>
      <a className="secondary-button" href={cta.href} onClick={(event) => onNavigate(event, cta.href)}>
        {cta.label}
      </a>
    </article>
  );
}

function PublicBenchmarksPage({
  benchmarksState,
  onNavigate,
}: {
  benchmarksState: LoadState<PublicBenchmarkListPayload>;
  onNavigate: LinkClickHandler;
}) {
  const benchmarks = benchmarksState.envelope?.data?.benchmarks ?? [];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public benchmarks</p>
        <h1>Career market indices</h1>
        <p className="public-lead">
          Category-defining benchmark templates for opportunity geography and career market
          intelligence. Current bounded indices are demo-safe, low-confidence display artifacts
          with explicit methodology, limitations, freshness, warnings, and public provenance.
        </p>
      </section>
      <DemoDisclosure compact />
      {benchmarksState.loading ? <LoadingBlock label="Loading public benchmarks" /> : null}
      {benchmarksState.error ? <ErrorState message={benchmarksState.error} /> : null}
      {benchmarks.length ? (
        <section className="public-section-grid" aria-label="Public benchmark list">
          {benchmarks.map((benchmark) => (
            <article className="public-section public-report-card" key={benchmark.slug}>
              <div className="metadata-row">
                <span className="badge badge-real">{segmentLabel(benchmark.category)}</span>
                <span className="badge badge-unknown">{benchmark.period}</span>
              </div>
              <h2>{benchmark.name}</h2>
              <p>{benchmark.summary}</p>
              <PublicBenchmarkBadgeRow
                confidence={benchmark.confidence}
                freshnessDate={benchmark.freshness_date}
                warningCount={benchmark.warnings.length}
              />
              <a
                className="secondary-button"
                href={publicBenchmarkUrl(benchmark.slug)}
                onClick={(event) => onNavigate(event, publicBenchmarkUrl(benchmark.slug))}
              >
                View index
              </a>
            </article>
          ))}
        </section>
      ) : !benchmarksState.loading && !benchmarksState.error ? (
        <EmptyState
          title="No public benchmarks"
          body="The public benchmark registry did not return benchmark templates."
        />
      ) : null}
    </div>
  );
}

function PublicBenchmarkResultCard({ result }: { result: PublicBenchmarkMarketResult }) {
  return (
    <article className="public-section public-report-result">
      <div className="metadata-row">
        <span className="badge badge-real">
          {result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}
        </span>
        <span className={publicConfidenceClass(result.confidence)}>
          Confidence: {segmentLabel(result.confidence)}
        </span>
        <span className="badge badge-unknown">Freshness date: {formatDateOnly(result.freshness_date)}</span>
      </div>
      <h3>{result.market_label}</h3>
      <div className="score-display-row">
        <strong>{result.score_display.label}</strong>
        <span>{result.score_display.display_value}</span>
        <small>{result.score_display.caveat}</small>
      </div>
      <p>{result.explanation}</p>
      <h4>Subscores</h4>
      <table className="benchmark-table">
        <thead>
          <tr>
            <th>Subscore</th>
            <th>Display</th>
            <th>Explanation</th>
          </tr>
        </thead>
        <tbody>
          {result.subscores.map((subscore) => (
            <tr key={subscore.key}>
              <td>{subscore.label}</td>
              <td>{subscore.display_value}</td>
              <td>{subscore.explanation}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.warnings.length ? (
        <div className="warning-list" aria-label={`${result.market_label} benchmark warnings`}>
          {result.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Benchmark warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PublicBenchmarkDetailPage({
  detailState,
  slug,
  onNavigate,
}: {
  detailState: LoadState<PublicBenchmark>;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  const benchmark = detailState.envelope?.data ?? null;
  if (detailState.loading) {
    return <LoadingBlock label="Loading public benchmark" />;
  }
  if (detailState.error) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Public benchmark</p>
          <h1>Benchmark not found</h1>
          <p className="public-lead">
            No public benchmark is registered for {slug}. Use the benchmark index to choose a
            published template.
          </p>
          <a
            className="secondary-button"
            href={publicPageUrl("benchmarks")}
            onClick={(event) => onNavigate(event, publicPageUrl("benchmarks"))}
          >
            Back to benchmarks
          </a>
        </section>
        <ErrorState message={detailState.error} />
      </div>
    );
  }
  if (!benchmark) {
    return <EmptyState title="No benchmark loaded" body="The public benchmark detail has not loaded yet." />;
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public benchmark · {segmentLabel(benchmark.category)}</p>
        <h1>{benchmark.name}</h1>
        <p className="public-lead">{benchmark.summary}</p>
        <PublicBenchmarkBadgeRow
          confidence={benchmark.confidence}
          freshnessDate={benchmark.freshness_date}
          freshnessStatus={benchmark.freshness_status}
          warningCount={benchmark.warnings.length}
        />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${benchmark.name} detail`}>
        <SourceAuthorityLabel authority={publicAuthorityView(benchmark.source_authority)} />
        <ShareSummaryCard summary={publicShareSummaryView(benchmark.share_summary)} />
        <CitationBlock citation={publicCitationView(benchmark.suggested_citation)} />
        <InstitutionalCtaBlock
          cta={publicInstitutionalCtaView(benchmark.institutional_cta)}
          onNavigate={onNavigate}
        />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{publicNarrative(benchmark.methodology_summary)}</p>
        </article>
        <article className="public-section">
          <h2>Score display</h2>
          <table className="benchmark-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Result</th>
                <th>Score display</th>
                <th>Caveat</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.market_results.map((result) => (
                <tr key={result.market_id}>
                  <td>{result.market_label}</td>
                  <td>{result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}</td>
                  <td>{result.score_display.display_value}</td>
                  <td>{result.score_display.caveat}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="public-section">
          <h2>Featured market table</h2>
          <div className="public-report-result-list">
            {benchmark.market_results.map((result) => (
              <PublicBenchmarkResultCard key={result.market_id} result={result} />
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {benchmark.limitations.map((limitation) => (
              <li key={limitation}>{publicNarrative(limitation)}</li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          <div className="warning-list" aria-label="Benchmark warnings">
            {benchmark.warnings.map((warning) => (
              <div className="warning-item" key={warning}>
                <div className="warning-header">
                  <span className="warning-code">Benchmark warning</span>
                </div>
                <p>{publicNarrative(warning)}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Source and provenance summary</h2>
          <p>
            {segmentLabel(benchmark.source_provenance_summary.data_basis)} ·{" "}
            {benchmark.source_provenance_summary.source_count} public source category reference(s)
          </p>
          <ul>
            {[
              ...benchmark.source_provenance_summary.source_categories,
              ...benchmark.source_provenance_summary.provenance_notes,
            ].map((item) => (
              <li key={item}>{publicNarrative(item)}</li>
            ))}
          </ul>
        </article>
        {benchmark.related_links.length ? (
          <article className="public-section">
            <h2>Related links</h2>
            <div className="public-link-list">
              {benchmark.related_links.map((link) => (
                <a href={link.href} key={`${link.link_type}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
                  {link.label}
                </a>
              ))}
            </div>
          </article>
        ) : null}
      </section>
    </div>
  );
}

function usePublicSeoMetadata(page: PublicSeoPage | null) {
  useEffect(() => {
    if (!page || typeof document === "undefined") return;
    const previousTitle = document.title;
    const previousDescription = document
      .querySelector('meta[name="description"]')
      ?.getAttribute("content") ?? null;
    const previousCanonical = document
      .querySelector('link[rel="canonical"]')
      ?.getAttribute("href") ?? null;
    const description = ensureHeadElement("meta", "name", "description");
    description.setAttribute("content", page.seo.description);
    const canonical = ensureHeadElement("link", "rel", "canonical");
    canonical.setAttribute("href", page.seo.canonicalPath);
    document.title = page.seo.title;
    return () => {
      document.title = previousTitle;
      if (previousDescription === null) {
        description.remove();
      } else {
        description.setAttribute("content", previousDescription);
      }
      if (previousCanonical === null) {
        canonical.remove();
      } else {
        canonical.setAttribute("href", previousCanonical);
      }
    };
  }, [page]);
}

function ensureHeadElement<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  attr: string,
  value: string,
): HTMLElementTagNameMap[K] {
  const existing = document.querySelector(`${tagName}[${attr}="${value}"]`);
  if (existing) return existing as HTMLElementTagNameMap[K];
  const element = document.createElement(tagName);
  element.setAttribute(attr, value);
  document.head.appendChild(element);
  return element;
}

function PublicSeoBadgeRow({ page }: { page: PublicSeoPage }) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(page.confidence)}>
        Confidence: {segmentLabel(page.confidence)}
      </span>
      <span className="badge badge-unknown">Content period: {page.contentPeriod}</span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(page.freshnessDate)}</span>
      <span className="badge badge-warning">{page.warnings.length} warning(s)</span>
    </div>
  );
}

function PublicSeoLinkList({
  links,
  onNavigate,
}: {
  links: PublicSeoLink[];
  onNavigate: LinkClickHandler;
}) {
  if (!links.length) return null;
  return (
    <div className="public-link-list">
      {links.map((link) => (
        <a href={link.href} key={`${link.linkType}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
          {link.label}
        </a>
      ))}
    </div>
  );
}

function PublicSeoMarketList({ page }: { page: PublicSeoPage }) {
  if (!page.featuredMarkets.length) return null;
  return (
    <article className="public-section">
      <h2>{page.pageFamily === "best_cities" ? "Featured cities" : "Market examples"}</h2>
      <div className="seo-market-grid">
        {page.featuredMarkets.map((market) => (
          <section className="seo-market-card" key={`${page.slug}:${market.marketLabel}`}>
            <div className="metadata-row">
              <span className="badge badge-real">
                {market.resultType === "ranked" ? `Rank ${market.rank}` : "Featured"}
              </span>
              {market.marketId ? <span className="badge badge-unknown">{market.marketId}</span> : null}
            </div>
            <h3>{market.marketLabel}</h3>
            <strong>{market.headline}</strong>
            <p>{market.explanation}</p>
            <div className="metadata-row">
              {market.signals.map((signal) => (
                <span className="badge badge-unknown" key={signal}>{signal}</span>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}

function PublicSeoComparisonBlocks({ page }: { page: PublicSeoPage }) {
  if (page.pageFamily !== "city_comparison") return null;
  return (
    <>
      <article className="public-section">
        <h2>Market-by-market sections</h2>
        <div className="seo-market-grid">
          {(page.comparisonMarkets ?? []).map((market) => (
            <section className="seo-market-card" key={market.marketLabel}>
              <h3>{market.marketLabel}</h3>
              <p>{market.summary}</p>
              <strong>Best for</strong>
              <ul>
                {market.bestFor.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <strong>Tradeoffs</strong>
              <ul>
                {market.tradeoffs.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
          ))}
        </div>
      </article>
      <article className="public-section">
        <h2>Best-for guidance</h2>
        <ul>
          {(page.bestFor ?? []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </article>
      <article className="public-section">
        <h2>Tradeoffs</h2>
        <ul>
          {(page.tradeoffs ?? []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </article>
    </>
  );
}

function PublicSeoListingPage({ onNavigate }: { onNavigate: LinkClickHandler }) {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Career market guides</p>
        <h1>Opportunity geography guides</h1>
        <p className="public-lead">
          Public SEO/content pages for career market intelligence. These guides use bounded
          language, public report links, and public benchmark links without creating production
          rankings or hidden scoring authority.
        </p>
      </section>
      <DemoDisclosure compact />
      <section className="public-section-grid" aria-label="Career market guide list">
        {PUBLIC_SEO_PAGES.map((page) => (
          <article className="public-section public-report-card" key={page.slug}>
            <div className="metadata-row">
              <span className="badge badge-real">{segmentLabel(page.pageFamily)}</span>
              <span className="badge badge-warning">Confidence: {segmentLabel(page.confidence)}</span>
            </div>
            <h2>{page.title}</h2>
            <p>{page.summary}</p>
            <a
              className="secondary-button"
              href={publicSeoPageUrl(page)}
              onClick={(event) => onNavigate(event, publicSeoPageUrl(page))}
            >
              Read guide
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function PublicSeoDetailPage({
  page,
  slug,
  onNavigate,
}: {
  page: PublicSeoPage | null;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  usePublicSeoMetadata(page);
  if (!page) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Career market guide</p>
          <h1>Guide not found</h1>
          <p className="public-lead">
            No public career market guide is registered for {slug}. Use the guide index to choose
            a published public page.
          </p>
          <a
            className="secondary-button"
            href={publicPageUrl("guides")}
            onClick={(event) => onNavigate(event, publicPageUrl("guides"))}
          >
            Back to guides
          </a>
        </section>
      </div>
    );
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Career market guide · {segmentLabel(page.pageFamily)}</p>
        <h1>{page.title}</h1>
        <p className="public-lead">{page.summary}</p>
        <PublicSeoBadgeRow page={page} />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${page.title} detail`}>
        <SourceAuthorityLabel authority={page.sourceAuthority} />
        <ShareSummaryCard summary={page.shareSummary} />
        <CitationBlock citation={page.suggestedCitation} />
        <InstitutionalCtaBlock cta={page.institutionalCta} onNavigate={onNavigate} />
        <article className="public-section">
          <h2>{page.pageFamily === "city_comparison" ? "Comparison summary" : page.primarySections[0]?.title ?? "Overview"}</h2>
          <p>{page.primarySections[0]?.body ?? page.summary}</p>
        </article>
        {page.primarySections.slice(1).map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : null}
          </article>
        ))}
        <PublicSeoMarketList page={page} />
        <PublicSeoComparisonBlocks page={page} />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{page.methodologySummary}</p>
          <PublicSeoLinkList links={[page.methodologyLink]} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {page.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          <div className="warning-list" aria-label="SEO page warnings">
            {page.warnings.map((warning) => (
              <div className="warning-item" key={warning}>
                <div className="warning-header">
                  <span className="warning-code">Guide warning</span>
                </div>
                <p>{warning}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Category language</h2>
          <div className="metadata-row">
            {page.canonicalCategoryLanguage.map((term) => (
              <span className="badge badge-unknown" key={term}>{term}</span>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Related reports</h2>
          <PublicSeoLinkList links={page.relatedReports} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Related benchmarks</h2>
          <PublicSeoLinkList links={page.relatedBenchmarks} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Related methodology and glossary</h2>
          <PublicSeoLinkList
            links={[...page.relatedLinks, ...relatedSeoPages(page.slug)]}
            onNavigate={onNavigate}
          />
        </article>
      </section>
    </div>
  );
}

function PublicReportsPage({
  reportsState,
  onNavigate,
}: {
  reportsState: LoadState<PublicReportListPayload>;
  onNavigate: LinkClickHandler;
}) {
  const reports = reportsState.envelope?.data?.reports ?? [];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public reports</p>
        <h1>Market intelligence reports</h1>
        <p className="public-lead">
          Recurring public report templates for opportunity geography and career market intelligence.
          Current public reports are demo-safe artifacts with explicit methodology, limitations,
          freshness, confidence, warnings, and public provenance summaries.
        </p>
      </section>
      <DemoDisclosure compact />
      {reportsState.loading ? <LoadingBlock label="Loading public reports" /> : null}
      {reportsState.error ? <ErrorState message={reportsState.error} /> : null}
      {reports.length ? (
        <section className="public-section-grid" aria-label="Public report list">
          {reports.map((report) => (
            <article className="public-section public-report-card" key={report.slug}>
              <div className="metadata-row">
                <span className="badge badge-real">{segmentLabel(report.category)}</span>
                <span className="badge badge-unknown">{report.report_period}</span>
              </div>
              <h2>{report.title}</h2>
              <p>{report.summary}</p>
              <PublicReportBadgeRow
                confidence={report.confidence}
                freshnessDate={report.freshness_date}
                warningCount={report.warnings.length}
              />
              <a
                className="secondary-button"
                href={publicReportUrl(report.slug)}
                onClick={(event) => onNavigate(event, publicReportUrl(report.slug))}
              >
                Read report
              </a>
            </article>
          ))}
        </section>
      ) : !reportsState.loading && !reportsState.error ? (
        <EmptyState
          title="No public reports"
          body="The public report registry did not return report templates."
        />
      ) : null}
    </div>
  );
}

function PublicReportResultCard({ result }: { result: PublicReportMarketResult }) {
  return (
    <article className="public-section public-report-result">
      <div className="metadata-row">
        <span className="badge badge-real">{result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}</span>
        <span className={publicConfidenceClass(result.confidence)}>
          Confidence: {segmentLabel(result.confidence)}
        </span>
        <span className="badge badge-unknown">Freshness date: {formatDateOnly(result.freshness_date)}</span>
      </div>
      <h2>{result.market_label}</h2>
      <strong>{result.headline}</strong>
      <p>{result.rationale}</p>
      <div className="metadata-row">
        {result.evidence_signals.map((signal) => (
          <span className="badge badge-unknown" key={signal}>{signal}</span>
        ))}
      </div>
      {result.warnings.length ? (
        <div className="warning-list" aria-label={`${result.market_label} warnings`}>
          {result.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PublicReportDetailPage({
  detailState,
  slug,
  onNavigate,
}: {
  detailState: LoadState<PublicReport>;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  const report = detailState.envelope?.data ?? null;
  if (detailState.loading) {
    return <LoadingBlock label="Loading public report" />;
  }
  if (detailState.error) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Public report</p>
          <h1>Report not found</h1>
          <p className="public-lead">
            No public report is registered for {slug}. Use the report index to choose a published template.
          </p>
          <a className="secondary-button" href={publicPageUrl("reports")} onClick={(event) => onNavigate(event, publicPageUrl("reports"))}>
            Back to reports
          </a>
        </section>
        <ErrorState message={detailState.error} />
      </div>
    );
  }
  if (!report) {
    return <EmptyState title="No report loaded" body="The public report detail has not loaded yet." />;
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public report · {segmentLabel(report.category)}</p>
        <h1>{report.title}</h1>
        <p className="public-lead">{report.summary}</p>
        <PublicReportBadgeRow
          confidence={report.confidence}
          freshnessDate={report.freshness_date}
          freshnessStatus={report.freshness_status}
          warningCount={report.warnings.length}
        />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${report.title} detail`}>
        <SourceAuthorityLabel authority={publicAuthorityView(report.source_authority)} />
        <ShareSummaryCard summary={publicShareSummaryView(report.share_summary)} />
        <CitationBlock citation={publicCitationView(report.suggested_citation)} />
        <InstitutionalCtaBlock
          cta={publicInstitutionalCtaView(report.institutional_cta)}
          onNavigate={onNavigate}
        />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{publicNarrative(report.methodology_summary)}</p>
        </article>
        <article className="public-section">
          <h2>Markets covered</h2>
          <ul>
            {report.markets_covered.map((market) => (
              <li key={market.market_id}>
                <strong>{market.market_label}</strong>: {market.coverage_note}
              </li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Featured market results</h2>
          <div className="public-report-result-list">
            {report.market_results.map((result) => (
              <PublicReportResultCard key={result.market_id} result={result} />
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {report.limitations.map((limitation) => (
              <li key={limitation}>{publicNarrative(limitation)}</li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          {report.warnings.length ? (
            <div className="warning-list" aria-label="Report warnings">
              {report.warnings.map((warning) => (
                <div className="warning-item" key={warning}>
                  <div className="warning-header">
                    <span className="warning-code">Report warning</span>
                  </div>
                  <p>{publicNarrative(warning)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p>No report warnings were returned.</p>
          )}
        </article>
        <article className="public-section">
          <h2>Source and provenance summary</h2>
          <p>
            {segmentLabel(report.source_provenance_summary.data_basis)} ·{" "}
            {report.source_provenance_summary.source_count} public source category reference(s)
          </p>
          <ul>
            {[
              ...report.source_provenance_summary.source_categories,
              ...report.source_provenance_summary.provenance_notes,
            ].map((item) => (
              <li key={item}>{publicNarrative(item)}</li>
            ))}
          </ul>
        </article>
        {report.related_links.length ? (
          <article className="public-section">
            <h2>Related links</h2>
            <div className="public-link-list">
              {report.related_links.map((link) => (
                <a href={link.href} key={`${link.link_type}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
                  {link.label}
                </a>
              ))}
            </div>
          </article>
        ) : null}
      </section>
    </div>
  );
}

function PredictiveForecastCard({ forecast }: { forecast: PredictiveReportForecast }) {
  return (
    <article className="public-section public-report-result forecast-card">
      <div className="metadata-row">
        <span className="badge badge-real">Forecast</span>
        <span className={publicConfidenceClass(forecast.confidence.level)}>
          Confidence: {segmentLabel(forecast.confidence.level)} ({Math.round(forecast.confidence.score * 100)}%)
        </span>
        <span className="badge badge-unknown">
          Time horizon: {segmentLabel(forecast.time_horizon)}
        </span>
      </div>
      <h2>{forecast.forecast_title}</h2>
      <strong>{forecast.forecast_label}</strong>
      <p>{forecast.safe_display_summary}</p>
      <p className="meta-copy">{forecast.why_this_forecast_exists}</p>
      <div className="metadata-row">
        <span className="badge badge-unknown">
          Historical depth: {forecast.historical_depth.observation_count} observation(s)
        </span>
        <span className="badge badge-unknown">
          Source basis: {forecast.source_basis.source_count} signal input(s)
        </span>
        <span className="badge badge-unknown">
          Uncertainty: {segmentLabel(forecast.uncertainty.level)}
        </span>
      </div>
      <div className="forecast-detail-grid">
        <section className="forecast-detail-block">
          <h3>Source basis</h3>
          <p>
            {segmentLabel(forecast.source_basis.data_basis)} -{" "}
            {forecast.source_basis.source_categories.map(segmentLabel).join(", ") || "No source categories"}
          </p>
          <p className="meta-copy">
            Window: {formatDateOnly(forecast.historical_depth.window_start)} to{" "}
            {formatDateOnly(forecast.historical_depth.window_end)}
          </p>
        </section>
        <section className="forecast-detail-block">
          <h3>Uncertainty</h3>
          <ul>
            {forecast.uncertainty.known_uncertainties.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="forecast-detail-block">
          <h3>Reasoning trail</h3>
          <ol>
            {forecast.reasoning_trail.map((step) => (
              <li key={step.code}>{step.summary}</li>
            ))}
          </ol>
        </section>
        <section className="forecast-detail-block">
          <h3>Supporting signals</h3>
          <ul>
            {forecast.supporting_signals.map((signal) => (
              <li key={signal.signal_key}>
                <strong>{segmentLabel(signal.signal_kind)}</strong>:{" "}
                {segmentLabel(signal.signal_type)} - {segmentLabel(signal.signal_status)}.{" "}
                {signal.summary}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </article>
  );
}

function PredictiveReportSectionBlock({ section }: { section: PredictiveReportSection }) {
  return (
    <article className="public-section">
      <h2>{section.title}</h2>
      <p>{section.summary}</p>
      <p className="meta-copy">{section.why_this_section_exists}</p>
      {section.forecasts.length ? (
        <div className="public-report-result-list">
          {section.forecasts.map((forecast) => (
            <PredictiveForecastCard forecast={forecast} key={forecast.forecast_id} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No forecast emitted"
          body="The available historical evidence did not produce a forecast for this section."
        />
      )}
    </article>
  );
}

function PredictiveReportsPage({
  reportState,
}: {
  reportState: LoadState<PredictiveReportPayload>;
}) {
  const report = reportState.envelope?.data ?? null;
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Predictive reports</p>
        <h1>Labor-market forecasts</h1>
        <p className="public-lead">
          Forecast cards translate historical trend, emerging-market, and warning signals
          into bounded directional intelligence with confidence, uncertainty, source basis,
          historical depth, and reasoning trail.
        </p>
      </section>
      <DemoDisclosure compact />
      {reportState.loading ? <LoadingBlock label="Loading predictive forecasts" /> : null}
      {reportState.error ? <ErrorState message={reportState.error} /> : null}
      {report ? (
        <section className="public-document-list" aria-label={`${report.title} detail`}>
          <article className="public-section">
            <div className="metadata-row">
              <span className="badge badge-real">Forecast report</span>
              <span className="badge badge-unknown">Generated: {formatDateTime(report.generated_at)}</span>
              <span className="badge badge-unknown">Horizon: {segmentLabel(report.time_horizon)}</span>
            </div>
            <h2>{report.title}</h2>
            <p>{report.forecast_disclaimer}</p>
            <p>{report.methodology_summary}</p>
          </article>
          {report.sections.map((section) => (
            <PredictiveReportSectionBlock section={section} key={section.section_key} />
          ))}
          <article className="public-section">
            <h2>Limitations</h2>
            <ul>
              {report.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : !reportState.loading && !reportState.error ? (
        <EmptyState
          title="No predictive report loaded"
          body="The predictive report endpoint did not return a report payload."
        />
      ) : null}
    </div>
  );
}

export function PublicRouteView({
  route,
  onNavigate,
  publicBenchmarkListState,
  publicBenchmarkDetailState,
  publicReportListState,
  publicReportDetailState,
  predictiveReportState,
}: {
  route: RouteState;
  onNavigate: LinkClickHandler;
  publicBenchmarkListState: LoadState<PublicBenchmarkListPayload>;
  publicBenchmarkDetailState: LoadState<PublicBenchmark>;
  publicReportListState: LoadState<PublicReportListPayload>;
  publicReportDetailState: LoadState<PublicReport>;
  predictiveReportState: LoadState<PredictiveReportPayload>;
}) {
  if (route.page === "embed-region-comparison" || route.page === "embed-market-score-card") {
    return <PlatformEmbedView page={route.page} />;
  }
  const activePage = route.page as PublicPage;
  return (
    <PublicShell activePage={activePage} onNavigate={onNavigate}>
      <LazyRoute>
        {activePage === "landing" ? (
          <LandingPage onNavigate={onNavigate} unknownPath={route.unknownPath} />
        ) : activePage === "developers" ? (
          <DevelopersPage onNavigate={onNavigate} />
        ) : activePage === "data-licensing" ? (
          <DataLicensingPage />
        ) : activePage === "data-standards" ? (
          <DataStandardsPage />
        ) : isDeveloperDocPage(activePage) ? (
          <DeveloperDocsPage page={activePage} onNavigate={onNavigate} />
        ) : activePage === "guides" ? (
          route.seoPageSlug ? (
            <PublicSeoDetailPage
              onNavigate={onNavigate}
              page={getPublicSeoPageBySlug(route.seoPageSlug)}
              slug={route.seoPageSlug}
            />
          ) : (
            <PublicSeoListingPage onNavigate={onNavigate} />
          )
        ) : activePage === "benchmarks" ? (
          route.benchmarkSlug ? (
            <PublicBenchmarkDetailPage
              detailState={publicBenchmarkDetailState}
              onNavigate={onNavigate}
              slug={route.benchmarkSlug}
            />
          ) : (
            <PublicBenchmarksPage
              benchmarksState={publicBenchmarkListState}
              onNavigate={onNavigate}
            />
          )
        ) : activePage === "reports" ? (
          route.reportSlug ? (
            <PublicReportDetailPage
              detailState={publicReportDetailState}
              onNavigate={onNavigate}
              slug={route.reportSlug}
            />
          ) : (
            <PublicReportsPage
              onNavigate={onNavigate}
              reportsState={publicReportListState}
            />
          )
        ) : activePage === "forecasts" ? (
          <PredictiveReportsPage reportState={predictiveReportState} />
        ) : (
          <LegalPage page={activePage as LegalPublicPage} />
        )}
      </LazyRoute>
    </PublicShell>
  );
}

function RouteLoadingFallback() {
  return (
    <div className="route-loading-state" role="status" aria-live="polite">
      Loading workspace
    </div>
  );
}

function LazyRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteLoadingFallback />}>{children}</Suspense>;
}

function isDeveloperDocPage(page: PublicPage): page is DeveloperDocPageKey {
  return page.startsWith("developer-doc");
}

function publicNarrative(value: string): string {
  return value
    .replace(/No production benchmark\/index scoring is performed in Layer \d+[A-Z]?\./gi, "No benchmark or index score is presented here.")
    .replace(/No benchmark\/index scoring is performed in Layer \d+[A-Z]?\./gi, "No benchmark or index score is presented here.")
    .replace(/\bLayer \d+[A-Z]?\b/gi, "public")
    .replace(/\bdisplay artifact\b/gi, "preview")
    .replace(/\bproduction rankings?\b/gi, "supported rankings")
    .replace(/\bproduction scoring authority\b/gi, "scoring authority")
    .replace(/not supported ranking truth/gi, "not a supported ranking")
    .replace(/not production benchmark truth/gi, "not a supported benchmark");
}
