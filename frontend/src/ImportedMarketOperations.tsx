import type { ReactNode } from "react";

import type {
  ImportedCoverageGap,
  ImportedDatasetHealthReport,
  ImportedDiffChange,
  ImportedDiffPreview,
  ImportedDiffWarning,
  ImportedFactHealthReport,
  ImportedMarketOperationDetails,
  ImportedMarketOperationsViewPayload,
  ImportedSourceAgingReport,
} from "./types";
import {
  isPublicSafeDisplayToken,
  operationStatusPresentation,
  publicSafeText,
  sanitizePublicValue,
  type StatusKind,
  type StatusTone,
} from "./ImportedMarketOperationsModel";

export function ImportedMarketOperationsPanel({
  payload,
  loading = false,
  error = null,
}: {
  payload?: ImportedMarketOperationsViewPayload | null;
  loading?: boolean;
  error?: string | null;
}) {
  const markets = [...(payload?.overview.markets ?? [])].sort((left, right) => {
    const leftDetails = payload?.details_by_market[left.market_key];
    const rightDetails = payload?.details_by_market[right.market_key];
    const leftScore = leftDetails?.readiness.priority_score ?? -1;
    const rightScore = rightDetails?.readiness.priority_score ?? -1;
    if (leftScore !== rightScore) return rightScore - leftScore;
    return left.market_key.localeCompare(right.market_key);
  });

  return (
    <div className="imported-operations" data-testid="imported-market-operations">
      <div className="imported-operations-copy">
        <p>
          Health describes the current quality and coverage of the dataset. Refresh
          readiness describes whether the current curated files can be safely re-imported.
        </p>
        <p>
          The bundled eight-market repository files are synthetic demonstration fixtures,
          not real or live market evidence. Freshness here describes fixture maintenance only.
        </p>
        <p>Diagnostics are preview-only and do not change imported data.</p>
      </div>
      {loading ? (
        <div className="loading-block" role="status" aria-live="polite">
          <span />
          Loading imported data operations
        </div>
      ) : null}
      {error ? (
        <div className="error-state">
          <strong>Request failed</strong>
          <p>{publicSafeText(error, "Imported data operations are unavailable.")}</p>
        </div>
      ) : null}
      {!loading && !error && !payload ? (
        <div className="empty-state">
          <strong>No imported data operations loaded</strong>
          <p>Maintenance diagnostics are unavailable for the current backend response.</p>
        </div>
      ) : null}
      {payload ? (
        <>
          <PlatformOperationsOverview payload={payload} />
          {markets.length ? (
            <div className="imported-operations-list">
              {markets.map((market) => (
                <MarketOperationsCard
                  key={market.market_key}
                  details={payload.details_by_market[market.market_key]}
                  health={market}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <strong>No imported markets registered</strong>
              <p>The operations summary returned no registered imported markets.</p>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function PlatformOperationsOverview({
  payload,
}: {
  payload: ImportedMarketOperationsViewPayload;
}) {
  const summary = payload.overview.summary;
  const priorityMarket = findMarketName(
    payload.overview.markets,
    summary.highest_priority_maintenance_market,
  );
  return (
    <section className="imported-operations-overview" aria-labelledby="imported-operations-heading">
      <div className="card-header compact-header">
        <div>
          <p className="card-eyebrow">Imported data health</p>
          <h3 id="imported-operations-heading">Operations overview</h3>
        </div>
        <OperationStatusLabel kind="health" value={summary.overall_health_status} />
      </div>
      <div className="market-summary-strip imported-operations-summary">
        <MetricCell label="markets" value={summary.registered_market_count} />
        <MetricCell label="healthy" value={summary.healthy_market_count} />
        <MetricCell label="limited coverage" value={summary.markets_with_limited_coverage} />
        <MetricCell label="need refresh" value={summary.markets_needing_refresh} />
        <MetricCell label="stale sources" value={summary.total_stale_source_count} />
        <MetricCell label="ranking-excluded facts" value={summary.total_ranking_excluded_fact_count} />
      </div>
      <div className="imported-operations-priority">
        <div>
          <span>Highest-priority market</span>
          <strong>{priorityMarket ?? "None"}</strong>
        </div>
        <div>
          <span>Recommended action</span>
          <p>{publicSafeText(summary.recommended_next_maintenance_action)}</p>
        </div>
      </div>
    </section>
  );
}

function MarketOperationsCard({
  health,
  details,
}: {
  health: ImportedDatasetHealthReport;
  details?: ImportedMarketOperationDetails;
}) {
  const readiness = details?.readiness;
  const gaps = details?.gaps;
  const sources = details?.sources;
  const facts = details?.facts;
  const diff = details?.diff;

  return (
    <article className="market-card market-card-static imported-operations-card">
      <div className="imported-operations-card-header">
        <div>
          <strong>{publicSafeText(health.market_name, health.market_key)}</strong>
          <small>{health.market_key}</small>
        </div>
        <div className="metadata-row imported-operations-statuses">
          <OperationStatusLabel kind="health" value={health.health_status} />
          <OperationStatusLabel kind="readiness" value={readiness?.readiness_status ?? null} />
        </div>
      </div>
      <p className="meta-copy">{publicSafeText(health.coverage_summary)}</p>
      <p className="meta-copy">{publicSafeText(health.freshness_summary)}</p>
      <div className="market-card-metrics imported-market-metrics">
        <MetricCell label="companies" value={health.counts.company_count} />
        <MetricCell label="sources" value={health.counts.source_count} />
        <MetricCell label="facts" value={health.counts.total_fact_count} />
        <MetricCell label="unknown facts" value={health.counts.unknown_fact_count} />
        <MetricCell label="observed-zero facts" value={health.counts.observed_zero_fact_count} />
        <MetricCell label="ranking-excluded" value={health.counts.ranking_excluded_fact_count} />
        <MetricCell label="coverage gaps" value={gaps?.gap_count ?? "Loading"} />
        <MetricCell label="priority" value={readiness ? readiness.maintenance_priority : "Loading"} />
      </div>
      <div className="imported-operations-action">
        <span>Recommended next action</span>
        <p>{publicSafeText(readiness?.recommended_next_action ?? health.recommended_next_action)}</p>
      </div>
      {details ? (
        <details className="imported-ops-details">
          <summary>Diagnostics for {publicSafeText(health.market_name, health.market_key)}</summary>
          <SourceAgingSection sources={sources} />
          <FactHealthSection facts={facts} />
          <CoverageGapSection gaps={gaps} />
          <RankingDiagnosticSection ranking={details.ranking} />
          <RefreshReadinessSection readiness={readiness} />
          {diff ? <DiffPreviewSection diff={diff} /> : null}
        </details>
      ) : (
        <div className="empty-state compact-empty">
          <strong>Detailed diagnostics unavailable</strong>
          <p>Per-market source, gap, ranking, readiness, and diff reports are still loading or unavailable.</p>
        </div>
      )}
    </article>
  );
}

function SourceAgingSection({ sources }: { sources?: ImportedSourceAgingReport }) {
  if (!sources) return null;
  const currentSources = Math.max(
    0,
    sources.source_count - sources.aging_source_count - sources.stale_source_count,
  );
  return (
    <section className="imported-ops-section" aria-label="Source aging">
      <h4>Source aging</h4>
      <div className="market-card-metrics imported-market-metrics">
        <MetricCell label="total sources" value={sources.source_count} />
        <MetricCell label="current" value={currentSources} />
        <MetricCell label="aging" value={sources.aging_source_count} />
        <MetricCell label="stale" value={sources.stale_source_count} />
        <MetricCell label="expired" value={sources.expired_source_count} />
        <MetricCell label="oldest age" value={ageLabel(sources.oldest_source_age_days)} />
      </div>
      {sources.aging_source_count || sources.stale_source_count || sources.expired_source_count ? (
        <DiagnosticList
          items={[...sources.important_stale_sources, ...sources.oldest_sources].slice(0, 5)}
          renderItem={(source) => (
            <>
              <span>{publicSafeText(source.source_label, source.source_id)}</span>
              <OperationStatusLabel kind="source" value={source.freshness_status} />
              <small>
                {formatKeyLabel(source.data_origin ?? "origin not reported")} · {ageLabel(source.age_days)} · {source.fact_usage_count} affected fact(s) ·{" "}
                {source.affects_ranking_eligibility ? "may affect ranking eligibility" : "does not affect ranking eligibility"}
              </small>
              <p>{publicSafeText(source.impact)}</p>
            </>
          )}
        />
      ) : (
        <p className="meta-copy">No sources are currently aging, stale, or expired.</p>
      )}
    </section>
  );
}

function FactHealthSection({ facts }: { facts?: ImportedFactHealthReport }) {
  if (!facts) return null;
  return (
    <section className="imported-ops-section" aria-label="Fact health">
      <h4>Fact health</h4>
      <div className="market-card-metrics imported-market-metrics">
        <MetricCell label="total facts" value={facts.total_facts} />
        <MetricCell label="ranking-eligible" value={facts.ranking_eligible_facts} />
        <MetricCell label="ranking-excluded" value={facts.ranking_excluded_facts} />
        <MetricCell label="stale" value={facts.stale_facts} />
        <MetricCell label="low confidence" value={facts.low_confidence_facts} />
        <MetricCell label="unknown" value={facts.unknown_facts} />
        <MetricCell label="observed zero" value={facts.observed_zero_facts} />
        <MetricCell label="weak source coverage" value={facts.weak_source_coverage_facts} />
      </div>
      {facts.limiting_categories.length ? (
        <p className="meta-copy">
          Limiting categories: {facts.limiting_categories.map((item) => publicSafeText(formatKeyLabel(item))).join(", ")}
        </p>
      ) : (
        <p className="meta-copy">No fact categories are currently limiting market score output quality.</p>
      )}
    </section>
  );
}

function CoverageGapSection({ gaps }: { gaps?: { gaps: ImportedCoverageGap[]; gap_count: number } }) {
  if (!gaps) return null;
  return (
    <section className="imported-ops-section" aria-label="Coverage gaps">
      <h4>Coverage gaps</h4>
      {gaps.gap_count === 0 ? (
        <p className="meta-copy">No coverage gaps were returned for this market.</p>
      ) : (
        <DiagnosticList
          items={gaps.gaps}
          renderItem={(gap) => (
            <>
              <span>{publicSafeText(gap.message)}</span>
              <OperationStatusLabel kind="severity" value={gap.severity} />
              <small>
                {formatKeyLabel(String(gap.affected_area))} · {publicSafeText(formatKeyLabel(gap.estimated_impact))}
              </small>
              <p>{publicSafeText(gap.recommended_action)}</p>
              <MetricSummary metrics={gap.supporting_counts} />
            </>
          )}
        />
      )}
    </section>
  );
}

function RankingDiagnosticSection({
  ranking,
}: {
  ranking: ImportedMarketOperationDetails["ranking"];
}) {
  return (
    <section className="imported-ops-section" aria-label="Ranking diagnostics">
      <h4>Ranking diagnostics</h4>
      <div className="market-card-metrics imported-market-metrics">
        <MetricCell label="excluded facts" value={ranking.excluded_fact_count} />
        <MetricCell label="total facts" value={ranking.total_fact_count} />
        <MetricCell label="limited ratio" value={ratioLabel(ranking.ranking_limited_ratio)} />
      </div>
      {ranking.excluded_fact_count === 0 ? (
        <p className="meta-copy">No imported facts are currently excluded from ranking.</p>
      ) : (
        <>
          <MetricSummary metrics={ranking.reason_counts} />
          <DiagnosticList
            items={ranking.diagnostics.slice(0, 8)}
            renderItem={(diagnostic) => (
              <>
                <span>{publicSafeText(diagnostic.explanation)}</span>
                <small>
                  {formatKeyLabel(String(diagnostic.area))} ·{" "}
                  {diagnostic.reason_categories.map((item) => publicSafeText(formatKeyLabel(item))).join(", ")}
                </small>
              </>
            )}
          />
        </>
      )}
    </section>
  );
}

function RefreshReadinessSection({
  readiness,
}: {
  readiness?: ImportedMarketOperationDetails["readiness"];
}) {
  if (!readiness) return null;
  return (
    <section className="imported-ops-section" aria-label="Refresh readiness">
      <h4>Refresh readiness</h4>
      <div className="metadata-row imported-operations-statuses">
        <OperationStatusLabel kind="readiness" value={readiness.readiness_status} />
        <OperationStatusLabel kind="priority" value={readiness.maintenance_priority} />
      </div>
      <p className="meta-copy">Expected impact: {publicSafeText(formatKeyLabel(readiness.expected_impact))}</p>
      <ConditionList title="Blocking conditions" items={readiness.blocking_conditions} empty="No blocking refresh conditions." />
      <ConditionList title="Warnings" items={readiness.warnings} empty="No non-blocking warnings." />
      <ConditionList title="Ordered actions" items={readiness.ordered_actions} empty="No immediate maintenance action." />
    </section>
  );
}

function DiffPreviewSection({ diff }: { diff: ImportedDiffPreview }) {
  return (
    <section className="imported-ops-section imported-diff-preview" aria-label="Import diff preview">
      <h4>Diff preview</h4>
      <p className="preview-only">Preview only. No imported data has been changed.</p>
      <div className="metadata-row imported-operations-statuses">
        <OperationStatusLabel kind="diff" value={diff.overall_diff_risk} />
        <span className="badge badge-muted">{diff.validation_ok ? "Validation OK" : "Validation failed"}</span>
      </div>
      <p>{publicSafeText(diff.narrative_summary)}</p>
      <ConditionList title="Blocking issues" items={diff.blocking_issues.map((issue) => issue.message)} empty="No blocking diff issues." />
      <DiffWarningList title="Semantic warnings" warnings={diff.warnings} />
      <MetricSummary metrics={diff.summary_counts} />
      {diff.changes.length ? (
        <details className="imported-diff-details">
          <summary>Detailed preview changes</summary>
          <DiagnosticList
            items={diff.changes.slice(0, 24)}
            renderItem={(change) => <DiffChangeItem change={change} />}
          />
        </details>
      ) : (
        <p className="meta-copy">No detailed diff changes were returned.</p>
      )}
    </section>
  );
}

function DiffWarningList({
  title,
  warnings,
}: {
  title: string;
  warnings: ImportedDiffWarning[];
}) {
  if (!warnings.length) {
    return <ConditionList title={title} items={[]} empty="No semantic diff warnings." />;
  }
  return (
    <div className="condition-list">
      <strong>{title}</strong>
      <ul>
        {warnings.map((warning) => (
          <li key={`${warning.code}-${warning.record_id ?? "none"}-${warning.message}`}>
            <OperationStatusLabel kind="diff" value={warning.severity} />
            <span>{publicSafeText(warning.message)}</span>
            <small>{formatKeyLabel(warning.code)}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DiffChangeItem({ change }: { change: ImportedDiffChange }) {
  return (
    <>
      <span>{publicSafeText(change.message)}</span>
      <small>
        {formatKeyLabel(String(change.area))} · {formatKeyLabel(change.change_type)}
        {change.field ? ` · ${formatKeyLabel(change.field)}` : ""}
      </small>
      <div className="diff-value-grid">
        <DiffValue label="Before" value={change.before} />
        <DiffValue label="After" value={change.after} />
      </div>
    </>
  );
}

function OperationStatusLabel({
  kind,
  value,
}: {
  kind: StatusKind;
  value: string | null | undefined;
}) {
  const status = operationStatusPresentation(kind, value);
  return (
    <span
      aria-label={`${status.label}: ${status.explanation}`}
      className={`badge ${badgeClass(status.tone)} imported-status-badge`}
      title={status.explanation}
    >
      {status.label}
    </span>
  );
}

function MetricCell({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="stat-card imported-market-stat">
      <strong>{formatDisplayValue(value)}</strong>
      <span>{label}</span>
    </div>
  );
}

function MetricSummary({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics)
    .filter(([key, value]) => isPublicSafeDisplayToken(key) && isRenderableMetric(value))
    .sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) return null;
  return (
    <div className="count-dimension-list imported-ops-metrics" aria-label="Supporting metrics">
      {entries.map(([key, value]) => (
        <span key={key}>
          {formatKeyLabel(key)}: {formatDisplayValue(value)}
        </span>
      ))}
    </div>
  );
}

function DiagnosticList<T>({
  items,
  renderItem,
}: {
  items: T[];
  renderItem: (item: T) => ReactNode;
}) {
  return (
    <ul className="imported-ops-diagnostic-list">
      {items.map((item, index) => (
        <li key={diagnosticKey(item, index)}>{renderItem(item)}</li>
      ))}
    </ul>
  );
}

function ConditionList({
  title,
  items,
  empty,
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  const safeItems = items.map((item) => publicSafeText(formatKeyLabel(item))).filter(Boolean);
  return (
    <div className="condition-list">
      <strong>{title}</strong>
      {safeItems.length ? (
        <ul>
          {safeItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="meta-copy">{empty}</p>
      )}
    </div>
  );
}

function DiffValue({ label, value }: { label: string; value: unknown }) {
  const sanitized = sanitizePublicValue(value);
  return (
    <div>
      <span>{label}</span>
      <code>{formatDisplayValue(sanitized)}</code>
    </div>
  );
}

function badgeClass(tone: StatusTone): string {
  if (tone === "success") return "badge-success";
  if (tone === "warning") return "badge-warning";
  if (tone === "error") return "badge-error";
  if (tone === "muted") return "badge-muted";
  if (tone === "real") return "badge-real";
  return "badge-unknown";
}

function findMarketName(markets: ImportedDatasetHealthReport[], marketKey: string | null): string | null {
  if (!marketKey) return null;
  const market = markets.find((item) => item.market_key === marketKey);
  return market ? publicSafeText(market.market_name, market.market_key) : marketKey;
}

function formatDisplayValue(value: ReactNode | unknown): string {
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return publicSafeText(value, "Unknown");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined) return "Unknown";
  if (Array.isArray(value) || isRecord(value)) return JSON.stringify(sanitizePublicValue(value));
  return String(value);
}

function ageLabel(value: number | null | undefined): string {
  if (typeof value !== "number") return "Unknown age";
  return `${value.toLocaleString()} day${value === 1 ? "" : "s"}`;
}

function ratioLabel(value: number | null | undefined): string {
  if (typeof value !== "number") return "Unknown";
  return `${Math.round(value * 100)}%`;
}

function formatKeyLabel(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\w/, (letter) => letter.toLocaleUpperCase());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isRenderableMetric(value: unknown): boolean {
  return (
    typeof value === "number"
    || typeof value === "string"
    || typeof value === "boolean"
    || value === null
  );
}

function diagnosticKey(item: unknown, index: number): string {
  if (isRecord(item)) {
    const candidate = item.record_id ?? item.fact_id ?? item.source_id ?? item.gap_code ?? item.code;
    if (typeof candidate === "string") return `${candidate}-${index}`;
  }
  return String(index);
}
