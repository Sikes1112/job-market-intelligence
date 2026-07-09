import type {
  EvidenceRequirementResult,
  ExceptionSubjectStatus,
  TrustExplanation,
  TrustExplanationWarning,
} from "./types";

type ExplanationProps = {
  explanation?: TrustExplanation | null;
  compact?: boolean;
};

export function TrustBadge({ explanation }: ExplanationProps) {
  if (!explanation) {
    return <span className="badge badge-unknown">Trust: not available</span>;
  }
  return (
    <span className={`badge ${trustBadgeClass(explanation.trust_tier)}`}>
      Trust: {explanation.trust_label}
    </span>
  );
}

export function RiskBadge({ explanation }: ExplanationProps) {
  if (!explanation?.risk_label) {
    return <span className="badge badge-unknown">Risk: not available</span>;
  }
  return (
    <span className={`badge ${riskBadgeClass(explanation.risk_level)}`}>
      Risk: {explanation.risk_label}
    </span>
  );
}

export function RankingInfluenceBadge({ explanation }: ExplanationProps) {
  if (!explanation) {
    return <span className="badge badge-unknown">Ranking influence: not available</span>;
  }
  return (
    <span
      className={
        explanation.ranking_influence_allowed
          ? "badge badge-success"
          : "badge badge-warning"
      }
    >
      {explanation.ranking_influence_label}
    </span>
  );
}

export function ExceptionStatusBadge({
  status,
}: {
  status?: ExceptionSubjectStatus | null;
}) {
  if (!status) return null;
  return (
    <span className={`badge ${exceptionBadgeClass(status.public_safe_status)}`}>
      Exception: {status.label}
    </span>
  );
}

export function RiskWarningCard({ warning }: { warning: TrustExplanationWarning }) {
  return (
    <article className={`trust-warning-card ${warningClass(warning.severity)}`}>
      <div className="warning-header">
        <span className="warning-code">{warning.title}</span>
        <span className={warningBadgeClass(warning.severity)}>{warning.severity}</span>
      </div>
      <p>{warning.message}</p>
      <small>{warning.warning_code}</small>
    </article>
  );
}

export function EvidenceExplanationPanel({ explanation }: ExplanationProps) {
  if (!explanation) {
    return (
      <div className="trust-evidence-panel trust-empty-state">
        <strong>Evidence explanation unavailable</strong>
        <p>No backend explanation payload was returned for this item.</p>
      </div>
    );
  }

  const met = explanation.evidence_requirements_met ?? [];
  const missing = explanation.evidence_requirements_missing ?? [];
  const failed = explanation.evidence_requirements_failed ?? [];
  const total = met.length + missing.length + failed.length;

  return (
    <section className="trust-evidence-panel" aria-label="Evidence requirements">
      <div className="trust-evidence-summary">
        <span className="badge badge-success">Met {met.length}</span>
        <span className="badge badge-warning">Missing {missing.length}</span>
        <span className="badge badge-error">Failed {failed.length}</span>
      </div>
      {total === 0 ? (
        <p className="meta-copy">No structured evidence requirements were returned.</p>
      ) : (
        <div className="trust-evidence-columns">
          <EvidenceList title="Met" items={met} />
          <EvidenceList title="Missing" items={missing} />
          <EvidenceList title="Failed" items={failed} />
        </div>
      )}
    </section>
  );
}

export function TrustExplanationPanel({ explanation, compact = false }: ExplanationProps) {
  if (!explanation) {
    return (
      <section className="trust-explanation-panel trust-empty-state">
        <strong>Trust explanation unavailable</strong>
        <p>No backend-provided trust explanation is available for this item.</p>
      </section>
    );
  }

  return (
    <section className="trust-explanation-panel" aria-label="Trust explanation">
      <div className="badge-stack">
        <TrustBadge explanation={explanation} />
        <RiskBadge explanation={explanation} />
        {explanation.routing_label ? (
          <span className="badge badge-unknown">{explanation.routing_label}</span>
        ) : null}
        <RankingInfluenceBadge explanation={explanation} />
        <ExceptionStatusBadge status={explanation.exception_status ?? null} />
      </div>
      <p>{explanation.trust_summary}</p>
      {explanation.risk_summary ? <p>{explanation.risk_summary}</p> : null}
      <p className="meta-copy">{explanation.ranking_influence_reason}</p>
      {explanation.user_facing_warnings.length ? (
        <div className="trust-warning-list">
          {explanation.user_facing_warnings.map((warning) => (
            <RiskWarningCard
              key={`${warning.warning_code}:${warning.title}`}
              warning={warning}
            />
          ))}
        </div>
      ) : null}
      {compact ? <EvidenceSummaryLine explanation={explanation} /> : (
        <EvidenceExplanationPanel explanation={explanation} />
      )}
      {explanation.report_recheck_status ? (
        <div className="report-recheck-status">
          <div className="badge-stack">
            {explanation.report_recheck_status.latest_report_status ? (
              <span className="badge badge-unknown">
                Report: {displayLabel(explanation.report_recheck_status.latest_report_status)}
              </span>
            ) : null}
            {explanation.report_recheck_status.recheck_status_label ? (
              <span className="badge badge-warning">
                {explanation.report_recheck_status.recheck_status_label}
              </span>
            ) : null}
          </div>
          <p className="meta-copy">{explanation.report_recheck_status.message}</p>
        </div>
      ) : null}
      {explanation.exception_status ? (
        <div className="notice-state">
          <strong>{explanation.exception_status.label}</strong>
          <p>{explanation.exception_status.message}</p>
        </div>
      ) : null}
    </section>
  );
}

function EvidenceSummaryLine({ explanation }: { explanation: TrustExplanation }) {
  return (
    <small>
      Evidence met {explanation.evidence_requirements_met.length} | missing{" "}
      {explanation.evidence_requirements_missing.length} | failed{" "}
      {explanation.evidence_requirements_failed.length}
    </small>
  );
}

function EvidenceList({
  items,
  title,
}: {
  items: EvidenceRequirementResult[];
  title: string;
}) {
  if (!items.length) return null;
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={`${item.code}:${item.status}:${item.message}`}>
            <strong>{item.code.replaceAll("_", " ")}</strong>
            <span>{item.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function displayLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function trustBadgeClass(tier: string): string {
  if (tier === "trusted" || tier === "verified") return "badge-success";
  if (tier === "blocked" || tier === "quarantined" || tier === "conflicting") {
    return "badge-error";
  }
  if (tier === "not_assessed") return "badge-unknown";
  return "badge-warning";
}

function riskBadgeClass(level: string | null): string {
  if (level === "low") return "badge-success";
  if (level === "critical" || level === "high") return "badge-error";
  if (level === "medium") return "badge-warning";
  return "badge-unknown";
}

function warningClass(severity: string): string {
  if (severity === "critical") return "trust-warning-critical";
  if (severity === "warning") return "trust-warning-warning";
  return "trust-warning-info";
}

function warningBadgeClass(severity: string): string {
  if (severity === "critical") return "badge badge-error";
  if (severity === "warning") return "badge badge-warning";
  return "badge badge-unknown";
}

function exceptionBadgeClass(status: string): string {
  if (status === "blocked" || status === "quarantined") return "badge-error";
  if (status === "resolved_by_system" || status === "closed") return "badge-success";
  if (status === "no_exception") return "badge-unknown";
  return "badge-warning";
}
