import type {
  CountStatus,
  ImportDisplayMetadata,
  MarketCoverageSummary,
} from "./types";
import {
  formatCountStatus,
  formatCountStatusDimension,
  freshnessDisplayLabel,
} from "./importedMarketFormat";

export function CountStatusValue({
  value,
  status,
}: {
  value: number | null | undefined;
  status?: CountStatus | null;
}) {
  return (
    <span className={countStatusClass(status)}>
      {formatCountStatus(value, status)}
    </span>
  );
}

export function ImportedMarketBadges({
  metadata,
}: {
  metadata?: ImportDisplayMetadata | null;
}) {
  if (!metadata) return null;
  const labels = [
    metadata.imported_data_label,
    metadata.source_label,
    metadata.coverage_label,
    metadata.freshness_label,
    metadata.trust_label ? `Trust: ${metadata.trust_label}` : null,
    metadata.risk_label ? `Risk: ${metadata.risk_label}` : null,
    metadata.ranking_label,
  ].filter((label): label is string => Boolean(label));

  return (
    <div className="metadata-row imported-market-badges" data-testid="imported-market-badges">
      {labels.map((label) => (
        <span className={labelBadgeClass(label)} key={label}>
          {label}
        </span>
      ))}
    </div>
  );
}

export function ImportedMarketCoveragePanel({
  markets,
}: {
  markets: MarketCoverageSummary[];
}) {
  if (!markets.length) {
    return (
      <div className="empty-state">
        <strong>No imported markets loaded</strong>
        <p>Coverage summaries are unavailable for the current backend response.</p>
      </div>
    );
  }

  const totalSources = markets.reduce((sum, market) => sum + market.source_count, 0);
  const totalRankingExcluded = markets.reduce(
    (sum, market) => sum + market.ranking_excluded_fact_count,
    0,
  );
  const totalUnknownDimensions = markets.reduce(
    (sum, market) => sum + market.unknown_count_dimensions,
    0,
  );
  const comparisonCount = markets.filter((market) => market.comparison_available).length;

  return (
    <div className="imported-market-coverage" data-testid="imported-market-coverage">
      <div className="market-summary-strip imported-market-summary">
        <div>
          <strong>{markets.length}</strong>
          <span>imported markets</span>
        </div>
        <div>
          <strong>{totalSources}</strong>
          <span>source refs</span>
        </div>
        <div>
          <strong>{totalRankingExcluded}</strong>
          <span>ranking-excluded facts</span>
        </div>
        <div>
          <strong>{totalUnknownDimensions}</strong>
          <span>unknown dimensions</span>
        </div>
      </div>
      <p className="meta-copy">
        {comparisonCount} imported market(s) currently have enough refreshed facts for comparison outputs.
      </p>
      <div className="market-card-grid imported-market-list">
        {markets.map((market) => (
          <ImportedMarketCoverageCard key={market.market_key} market={market} />
        ))}
      </div>
    </div>
  );
}

function ImportedMarketCoverageCard({ market }: { market: MarketCoverageSummary }) {
  const factCount = (
    market.presence_fact_count
    + market.hiring_fact_count
    + market.entry_level_fact_count
  );
  const countBreakdown = Object.entries(market.count_status_breakdown ?? {})
    .filter((entry): entry is [CountStatus, number] => typeof entry[1] === "number")
    .sort(([left], [right]) => left.localeCompare(right));

  const labels = [
    market.imported_data_label,
    market.source_label,
    market.coverage_label,
    freshnessDisplayLabel(market.freshness_label),
    market.trust_label ? `Trust: ${market.trust_label}` : null,
    market.risk_label ? `Risk: ${market.risk_label}` : null,
    market.ranking_label,
    market.comparison_label,
  ].filter((label): label is string => Boolean(label));

  return (
    <article className="market-card market-card-static imported-market-card">
      <div className="market-card-topline">
        <span>{market.market_key.replaceAll("_", " ")}</span>
        {labels.slice(0, 2).map((label) => (
          <MarketBadge key={label} label={label} />
        ))}
      </div>
      <div>
        <strong>{market.display_name}</strong>
        <small>
          {market.region_id} · curated {market.last_curated_at}
        </small>
      </div>
      <div className="metadata-row imported-market-badges">
        {labels.slice(2).map((label) => (
          <MarketBadge key={label} label={label} />
        ))}
      </div>
      <div className="market-card-metrics imported-market-metrics">
        <Metric label="Companies" value={market.company_count} />
        <Metric label="Sources" value={market.source_count} />
        <Metric label="Facts" value={factCount} />
        <Metric label="Ranking eligible" value={market.ranking_eligible_fact_count} />
        <Metric label="Ranking excluded" value={market.ranking_excluded_fact_count} />
      </div>
      <div className="count-dimension-list" aria-label={`${market.display_name} count statuses`}>
        <span>{formatCountStatusDimension("unknown", market.unknown_count_dimensions)}</span>
        <span>
          {formatCountStatusDimension("zero_observed", market.observed_zero_count_dimensions)}
        </span>
        {countBreakdown.map(([status, count]) => (
          <span key={status}>{formatCountStatusDimension(status, count)}</span>
        ))}
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card imported-market-stat">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  );
}

function MarketBadge({ label }: { label: string }) {
  return <span className={labelBadgeClass(label)}>{label}</span>;
}

function countStatusClass(status?: CountStatus | null): string {
  if (status === "zero_observed" || status === "positive_observed") {
    return "count-status count-status-observed";
  }
  if (status === "stale" || status === "conflicting" || status === "low_confidence") {
    return "count-status count-status-warning";
  }
  return "count-status count-status-unknown";
}

function labelBadgeClass(label: string): string {
  const normalized = label.toLocaleLowerCase();
  if (
    normalized.includes("real imported")
    || normalized.includes("source-backed")
    || normalized.includes("ranking-safe")
    || normalized.includes("verified")
    || normalized.includes("current")
  ) {
    return "badge badge-real";
  }
  if (
    normalized.includes("partial")
    || normalized.includes("stale")
    || normalized.includes("excluded")
    || normalized.includes("low confidence")
    || normalized.includes("caution")
  ) {
    return "badge badge-warning";
  }
  if (normalized.includes("unknown") || normalized.includes("not assessed")) {
    return "badge badge-unknown";
  }
  return "badge";
}
