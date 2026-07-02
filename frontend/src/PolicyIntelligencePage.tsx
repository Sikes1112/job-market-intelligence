import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from "react";
import {
  getPolicyEarlyCareerReport,
  getPolicyEconomicDevelopment,
  getPolicyEducationAlignment,
  getPolicyPeerComparison,
  getPolicyWorkforceDashboard,
} from "./api";
import type {
  ApiEnvelope,
  CompanyAttractionFit,
  EconomicDevelopmentProfile,
  EducationWorkforceAlignmentProfile,
  EmployerBaseRiskFinding,
  PeerComparisonProfile,
  PeerMetroComparison,
  PolicyFinding,
  PolicyMetric,
  PolicyWarning,
  ProgramDemandAlignment,
  PublicReport,
  RegionListItem,
  SectorGapFinding,
  WorkforceDashboardPayload,
} from "./types";
import type { PolicyView } from "./urlState";
import {
  policyEconomicDevelopmentUrl,
  policyEducationAlignmentUrl,
  policyLandingUrl,
  policyPeerComparisonUrl,
  policyRegionUrl,
  policyReportUrl,
} from "./urlState";

type LoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};

type PolicyIntelligencePageProps = {
  policyView: PolicyView;
  regionId: string;
  regions: RegionListItem[];
  onNavigate: (event: MouseEvent<HTMLAnchorElement>, url: string) => void;
};

function emptyLoadState<T>(): LoadState<T> {
  return { loading: false, envelope: null, error: null };
}

export default function PolicyIntelligencePage({
  policyView,
  regionId,
  regions,
  onNavigate,
}: PolicyIntelligencePageProps) {
  const [workforceState, setWorkforceState] =
    useState<LoadState<WorkforceDashboardPayload>>(emptyLoadState);
  const [economicState, setEconomicState] =
    useState<LoadState<EconomicDevelopmentProfile>>(emptyLoadState);
  const [peerState, setPeerState] =
    useState<LoadState<PeerComparisonProfile>>(emptyLoadState);
  const [educationState, setEducationState] =
    useState<LoadState<EducationWorkforceAlignmentProfile>>(emptyLoadState);
  const [reportState, setReportState] =
    useState<LoadState<PublicReport>>(emptyLoadState);
  const regionKnown = useMemo(
    () => !regions.length || regions.some((region) => region.region_id === regionId),
    [regionId, regions],
  );

  useEffect(() => {
    if (policyView !== "workforce" || !regionId || !regionKnown) return;
    void loadPolicyPayload(getPolicyWorkforceDashboard, regionId, setWorkforceState);
  }, [policyView, regionId, regionKnown]);

  useEffect(() => {
    if (policyView !== "economic-development" || !regionId || !regionKnown) return;
    void loadPolicyPayload(getPolicyEconomicDevelopment, regionId, setEconomicState);
  }, [policyView, regionId, regionKnown]);

  useEffect(() => {
    if (policyView !== "peer-comparison" || !regionId || !regionKnown) return;
    void loadPolicyPayload(getPolicyPeerComparison, regionId, setPeerState);
  }, [policyView, regionId, regionKnown]);

  useEffect(() => {
    if (policyView !== "education-alignment" || !regionId || !regionKnown) return;
    void loadPolicyPayload(getPolicyEducationAlignment, regionId, setEducationState);
  }, [policyView, regionId, regionKnown]);

  useEffect(() => {
    if (policyView !== "report" || !regionId || !regionKnown) return;
    void loadPolicyPayload(getPolicyEarlyCareerReport, regionId, setReportState);
  }, [policyView, regionId, regionKnown]);

  if (policyView === "landing") {
    return (
      <PolicyLanding
        onNavigate={onNavigate}
        regionId={regionId}
        regions={regions}
      />
    );
  }

  if (!regionKnown) {
    return (
      <div className="policy-page">
        <PolicyHeader
          eyebrow="Policy intelligence"
          title="Region not found"
          summary={`No region list entry is available for ${regionId}.`}
          onNavigate={onNavigate}
          regionId={regionId}
        />
        <PolicyEmpty
          title="Missing region"
          body="Choose a known region before opening Layer 24 policy dashboards."
        />
      </div>
    );
  }

  return (
    <div className="policy-page">
      <PolicyHeader
        eyebrow="Layer 24 policy intelligence"
        title={policyTitle(policyView)}
        summary={policySummary(policyView)}
        onNavigate={onNavigate}
        regionId={regionId}
      />
      {policyView === "workforce" ? (
        <RegionalPolicyDashboard state={workforceState} />
      ) : null}
      {policyView === "economic-development" ? (
        <EconomicDevelopmentDashboard state={economicState} />
      ) : null}
      {policyView === "education-alignment" ? (
        <EducationAlignmentDashboard state={educationState} />
      ) : null}
      {policyView === "peer-comparison" ? (
        <PeerComparisonDashboard state={peerState} />
      ) : null}
      {policyView === "report" ? (
        <PolicyReportDashboard state={reportState} />
      ) : null}
    </div>
  );
}

async function loadPolicyPayload<T>(
  loader: (regionId: string) => Promise<ApiEnvelope<T>>,
  regionId: string,
  setState: (value: LoadState<T>) => void,
) {
  setState({ loading: true, envelope: null, error: null });
  try {
    const envelope = await loader(regionId);
    setState({ loading: false, envelope, error: null });
  } catch (error) {
    setState({
      loading: false,
      envelope: null,
      error: error instanceof Error ? error.message : "Failed to load policy intelligence",
    });
  }
}

function PolicyLanding({
  regionId,
  regions,
  onNavigate,
}: {
  regionId: string;
  regions: RegionListItem[];
  onNavigate: PolicyIntelligencePageProps["onNavigate"];
}) {
  const selectedLabel =
    regions.find((region) => region.region_id === regionId)?.display_name ?? regionId;
  return (
    <div className="policy-page">
      <section className="section-hero policy-hero">
        <div>
          <p className="eyebrow">Layer 24</p>
          <h2>Policy, workforce, and economic intelligence</h2>
          <p>
            Backend-generated regional signals for workforce teams, economic development
            groups, university career offices, chambers, workforce nonprofits, policy
            researchers, and education funders.
          </p>
        </div>
        <div className="hero-actions">
          <PolicyLink
            href={policyRegionUrl(regionId)}
            label={`Open ${selectedLabel} dashboard`}
            onNavigate={onNavigate}
          />
          <PolicyLink
            href={policyReportUrl(regionId)}
            label="Open representative report"
            onNavigate={onNavigate}
          />
        </div>
      </section>
      <section className="policy-grid" aria-label="Policy use cases">
        {[
          "Public-sector workforce planning",
          "City economic development analysis",
          "University career office strategy",
          "Regional chamber employer mix review",
          "Workforce nonprofit program planning",
          "Policy research and education funding review",
        ].map((label) => (
          <article className="signal-card" key={label}>
            <h3>{label}</h3>
            <p>
              Use Layer 24 outputs as bounded, public-safe interpretation of available
              market signals.
            </p>
          </article>
        ))}
      </section>
      <section className="notice-state">
        <strong>Methodology notice</strong>
        <p>
          Dashboards read backend policy payloads. Metrics, findings, warnings,
          confidence, freshness, and limitations are not generated in the frontend.
        </p>
      </section>
    </div>
  );
}

function PolicyHeader({
  eyebrow,
  title,
  summary,
  regionId,
  onNavigate,
}: {
  eyebrow: string;
  title: string;
  summary: string;
  regionId: string;
  onNavigate: PolicyIntelligencePageProps["onNavigate"];
}) {
  return (
    <section className="section-hero policy-hero">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{summary}</p>
      </div>
      <div className="policy-tabs" aria-label="Policy dashboard sections">
        <PolicyLink href={policyLandingUrl()} label="Overview" onNavigate={onNavigate} />
        <PolicyLink href={policyRegionUrl(regionId)} label="Workforce" onNavigate={onNavigate} />
        <PolicyLink
          href={policyEconomicDevelopmentUrl(regionId)}
          label="Economic development"
          onNavigate={onNavigate}
        />
        <PolicyLink
          href={policyEducationAlignmentUrl(regionId)}
          label="Education alignment"
          onNavigate={onNavigate}
        />
        <PolicyLink
          href={policyPeerComparisonUrl(regionId)}
          label="Peer comparison"
          onNavigate={onNavigate}
        />
        <PolicyLink href={policyReportUrl(regionId)} label="Report" onNavigate={onNavigate} />
      </div>
    </section>
  );
}

function RegionalPolicyDashboard({
  state,
}: {
  state: LoadState<WorkforceDashboardPayload>;
}) {
  return (
    <PolicyLoadFrame state={state} emptyTitle="No workforce dashboard">
      {(dashboard) => (
        <>
          <MetadataPanel payload={dashboard} />
          <section className="policy-grid" aria-label="Regional policy metrics">
            {policyMetrics(dashboard).map((metric) => (
              <MetricCard key={metric.metric_id} metric={metric} />
            ))}
          </section>
          <FindingsPanel findings={dashboard.policy_findings} />
          <WarningsPanel warnings={dashboard.warnings} />
          <SourceSafetyPanel payload={dashboard} />
        </>
      )}
    </PolicyLoadFrame>
  );
}

function EconomicDevelopmentDashboard({
  state,
}: {
  state: LoadState<EconomicDevelopmentProfile>;
}) {
  return (
    <PolicyLoadFrame state={state} emptyTitle="No economic development profile">
      {(profile) => (
        <>
          <MetadataPanel payload={profile} />
          <PolicyList
            emptyBody="No sector gaps were returned for this region."
            items={profile.sector_gap_findings}
            renderItem={(finding) => <SectorGapCard finding={finding} />}
            title="Sector gap findings"
          />
          <PolicyList
            emptyBody="No employer-base risk findings were returned for this region."
            items={profile.employer_base_risk_findings}
            renderItem={(finding) => <EmployerRiskCard finding={finding} />}
            title="Employer-base risk"
          />
          <PolicyList
            emptyBody="No company attraction fit candidates were returned."
            items={profile.company_attraction_candidates}
            renderItem={(candidate) => <CompanyCandidateCard candidate={candidate} />}
            title="Strategy-analysis candidates"
          />
          <PolicyList
            emptyBody="No diversification strategy candidates were returned."
            items={profile.diversification_recommendations}
            renderItem={(candidate) => (
              <article className="signal-card">
                <h3>{candidate.title}</h3>
                <p>{candidate.rationale}</p>
                <BadgeRow values={[candidate.candidate_type, candidate.confidence]} />
                <LimitationsList limitations={candidate.limitations} />
              </article>
            )}
            title="Diversification candidates"
          />
          <PeerComparisonList peers={profile.peer_metro_comparisons} />
          <WarningsPanel warnings={profile.warnings} />
          <LimitationsPanel limitations={profile.limitations} />
        </>
      )}
    </PolicyLoadFrame>
  );
}

function EducationAlignmentDashboard({
  state,
}: {
  state: LoadState<EducationWorkforceAlignmentProfile>;
}) {
  return (
    <PolicyLoadFrame state={state} emptyTitle="No education alignment profile">
      {(profile) => (
        <>
          <MetadataPanel payload={profile} />
          <section className="notice-state">
            <strong>Aggregate-only education alignment</strong>
            <p>
              Outputs are regional, institutional, and program-area summaries. No
              individual student outcomes are inferred, and short-term postings alone
              do not determine program value.
            </p>
          </section>
          <section className="policy-grid" aria-label="Education alignment metrics">
            <MetricCard metric={profile.local_employer_absorption_score} />
            <MetricCard metric={profile.talent_export_pressure_score} />
            {profile.student_interest_market_fit ? (
              <MetricCard metric={profile.student_interest_market_fit} />
            ) : null}
          </section>
          <PolicyList
            emptyBody="No aggregate institution pipeline summaries were returned."
            items={profile.institution_pipeline_summaries}
            renderItem={(pipeline) => (
              <article className="signal-card">
                <h3>{pipeline.institution_name}</h3>
                <p>{pipeline.nearby_early_career_demand_summary}</p>
                <p>{pipeline.internship_access_summary}</p>
                <BadgeRow values={[pipeline.alignment_confidence, ...pipeline.related_demand_sectors]} />
                <LimitationsList limitations={pipeline.limitations} />
              </article>
            )}
            title="Institution pipeline summaries"
          />
          <PolicyList
            emptyBody="No program alignment findings were returned."
            items={profile.program_alignment_findings}
            renderItem={(alignment) => <ProgramAlignmentCard alignment={alignment} />}
            title="Program alignment findings"
          />
          <PolicyList
            emptyBody="No internship alignment gaps were returned."
            items={profile.internship_alignment_gaps}
            renderItem={(finding) => <SectorGapCard finding={finding} />}
            title="Internship alignment gaps"
          />
          <WarningsPanel warnings={profile.warnings} />
          <LimitationsPanel limitations={profile.limitations} />
        </>
      )}
    </PolicyLoadFrame>
  );
}

function PeerComparisonDashboard({
  state,
}: {
  state: LoadState<PeerComparisonProfile>;
}) {
  return (
    <PolicyLoadFrame state={state} emptyTitle="No peer comparison profile">
      {(profile) => (
        <>
          <MetadataPanel payload={profile} />
          <WarningsPanel warnings={profile.warnings} />
          <PeerComparisonList peers={profile.peer_metro_comparisons} />
          <LimitationsPanel limitations={profile.limitations} />
        </>
      )}
    </PolicyLoadFrame>
  );
}

function PolicyReportDashboard({ state }: { state: LoadState<PublicReport> }) {
  return (
    <PolicyLoadFrame state={state} emptyTitle="No policy report">
      {(report) => (
        <>
          <section className="signal-card">
            <p className="eyebrow">Layer 24 report</p>
            <h3>{report.title}</h3>
            <p>{report.summary}</p>
            <BadgeRow
              values={[
                `Confidence ${report.confidence}`,
                `Freshness ${report.freshness_status}`,
                report.report_period,
              ]}
            />
          </section>
          <section className="signal-card">
            <h3>Methodology</h3>
            <p>{report.methodology_summary}</p>
          </section>
          <PolicyList
            emptyBody="No report findings were returned."
            items={report.market_results}
            renderItem={(result) => (
              <article className="signal-card">
                <h3>{result.market_label}</h3>
                <strong>{result.headline}</strong>
                <p>{result.rationale}</p>
                <BadgeRow values={result.evidence_signals} />
                {result.warnings.length ? (
                  <ul className="coverage-notes">
                    {result.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                ) : null}
              </article>
            )}
            title="Report findings"
          />
          <LimitationsPanel limitations={report.limitations} />
          <section className="signal-card">
            <h3>Share summary</h3>
            <p>{report.share_summary.takeaway}</p>
            <p>{report.share_summary.warning}</p>
          </section>
        </>
      )}
    </PolicyLoadFrame>
  );
}

function PolicyLoadFrame<T>({
  state,
  emptyTitle,
  children,
}: {
  state: LoadState<T>;
  emptyTitle: string;
  children: (value: T) => ReactNode;
}) {
  if (state.loading) return <PolicyLoading label="Loading Layer 24 policy intelligence" />;
  if (state.error) return <PolicyError message={state.error} />;
  if (!state.envelope?.data) {
    return (
      <PolicyEmpty
        title={emptyTitle}
        body="The backend did not return a payload for this policy surface."
      />
    );
  }
  return <>{children(state.envelope.data)}</>;
}

function MetricCard({ metric }: { metric: PolicyMetric }) {
  return (
    <article className="signal-card">
      <div className="metadata-row">
        <span className={metric.polarity === "higher_is_risk" ? "badge badge-warning" : "badge badge-real"}>
          {pretty(metric.band)}
        </span>
        <span className="badge badge-unknown">{metric.score === null ? "Unknown" : `${Math.round(metric.score * 100)}%`}</span>
      </div>
      <h3>{metric.label}</h3>
      <p>{metric.interpretation_label}</p>
      <LimitationsList limitations={metric.limitations} />
    </article>
  );
}

function FindingsPanel({ findings }: { findings: PolicyFinding[] }) {
  return (
    <PolicyList
      emptyBody="No policy findings were returned for this region."
      items={findings}
      renderItem={(finding) => (
        <article className="signal-card">
          <div className="metadata-row">
            <span className={`badge ${finding.severity === "high" ? "badge-warning" : "badge-real"}`}>
              {pretty(finding.severity)}
            </span>
            <span className="badge badge-unknown">{pretty(finding.finding_type)}</span>
          </div>
          <h3>{finding.title}</h3>
          <p>{finding.summary}</p>
          <p>{finding.recommended_interpretation}</p>
          <LimitationsList limitations={finding.limitations} />
        </article>
      )}
      title="Policy findings"
    />
  );
}

function SectorGapCard({ finding }: { finding: SectorGapFinding }) {
  return (
    <article className="signal-card">
      <div className="metadata-row">
        <span className="badge badge-warning">{pretty(finding.severity)}</span>
        <span className="badge badge-unknown">{pretty(finding.gap_type)}</span>
      </div>
      <h3>{pretty(finding.sector)}</h3>
      <p>{finding.interpretation}</p>
      <p>{finding.recommended_strategy_candidate}</p>
      <BadgeRow values={finding.evidence_references} />
      <LimitationsList limitations={finding.limitations} />
    </article>
  );
}

function EmployerRiskCard({ finding }: { finding: EmployerBaseRiskFinding }) {
  return (
    <article className="signal-card">
      <div className="metadata-row">
        <span className="badge badge-warning">{pretty(finding.severity)}</span>
        <span className="badge badge-unknown">{pretty(finding.risk_type)}</span>
      </div>
      <h3>{pretty(finding.risk_type)}</h3>
      <p>{finding.interpretation}</p>
      <p>{finding.strategy_candidate}</p>
      <BadgeRow values={finding.evidence_references} />
      <LimitationsList limitations={finding.limitations} />
    </article>
  );
}

function CompanyCandidateCard({ candidate }: { candidate: CompanyAttractionFit }) {
  return (
    <article className="signal-card">
      <div className="metadata-row">
        <span className="badge badge-real">Strategy-analysis candidate</span>
        <span className="badge badge-unknown">{pretty(candidate.fit_band)}</span>
      </div>
      <h3>{candidate.company_name}</h3>
      <p>{candidate.fit_rationale}</p>
      <p>{candidate.early_career_or_internship_relevance}</p>
      <p>{candidate.diversification_impact}</p>
      <LimitationsList limitations={candidate.limitations} />
    </article>
  );
}

function ProgramAlignmentCard({ alignment }: { alignment: ProgramDemandAlignment }) {
  return (
    <article className="signal-card">
      <div className="metadata-row">
        <span className="badge badge-real">{pretty(alignment.alignment_band)}</span>
        <span className="badge badge-unknown">{pretty(alignment.confidence)}</span>
      </div>
      <h3>{alignment.program_area}</h3>
      <p>{alignment.finding}</p>
      <MetricMini metric={alignment.nearby_employer_demand} />
      <MetricMini metric={alignment.internship_pipeline_strength} />
      <MetricMini metric={alignment.early_career_access} />
      <LimitationsList limitations={alignment.limitations} />
    </article>
  );
}

function MetricMini({ metric }: { metric: PolicyMetric }) {
  return (
    <p className="meta-copy">
      <strong>{metric.label}:</strong> {metric.interpretation_label}
    </p>
  );
}

function PeerComparisonList({ peers }: { peers: PeerMetroComparison[] }) {
  return (
    <PolicyList
      emptyBody="No peer metros were returned. Low-coverage warnings remain visible above when provided by the backend."
      items={peers}
      renderItem={(peer) => (
        <article className="signal-card">
          <div className="metadata-row">
            <span className="badge badge-real">
              Similarity {peer.similarity_score === null ? "unknown" : `${Math.round(peer.similarity_score * 100)}%`}
            </span>
            <span className="badge badge-unknown">{pretty(peer.confidence)}</span>
          </div>
          <h3>{peer.peer_region_name}</h3>
          <p>{peer.similarity_rationale}</p>
          <div className="policy-table-wrap">
            <table className="policy-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Target</th>
                  <th>Peer</th>
                  <th>Comparison</th>
                </tr>
              </thead>
              <tbody>
                {peer.metrics_compared.map((metric) => (
                  <tr key={metric.metric_id}>
                    <td>{pretty(metric.metric_id)}</td>
                    <td>{formatScore(metric.target_value)}</td>
                    <td>{formatScore(metric.peer_value)}</td>
                    <td>{pretty(metric.comparison)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <BadgeRow values={["Stronger", ...peer.target_region_stronger]} />
          <BadgeRow values={["Weaker", ...peer.target_region_weaker]} />
          <LimitationsList limitations={peer.limitations} />
        </article>
      )}
      title="Peer metro comparisons"
    />
  );
}

function MetadataPanel({
  payload,
}: {
  payload: {
    confidence: { label: string; level: string; score: number };
    freshness: { freshness_status: string; generated_at: string; notes?: string[] };
    source_summary: { source_count: number; source_categories: string[]; evidence_summary?: string[] };
    warnings: PolicyWarning[];
    limitations?: string[];
    public_safety?: { student_level_data_exposed: false };
  };
}) {
  return (
    <section className="signal-card policy-metadata">
      <h3>Confidence, freshness, and sources</h3>
      <div className="metadata-row">
        <span className="badge badge-real">
          Confidence: {payload.confidence.label}
        </span>
        <span className="badge badge-unknown">
          Freshness: {pretty(payload.freshness.freshness_status)}
        </span>
        <span className="badge">
          Sources: {payload.source_summary.source_count}
        </span>
      </div>
      <p>{payload.source_summary.source_categories.join(", ") || "No source categories returned."}</p>
      {payload.freshness.notes?.length ? (
        <ul className="coverage-notes">
          {payload.freshness.notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      ) : null}
      {payload.public_safety ? (
        <p className="meta-copy">
          Public-safe payload. Student-level data exposed:{" "}
          {String(payload.public_safety.student_level_data_exposed)}.
        </p>
      ) : null}
    </section>
  );
}

function WarningsPanel({ warnings }: { warnings: PolicyWarning[] }) {
  return (
    <PolicyList
      emptyBody="No policy warnings were returned."
      items={warnings}
      renderItem={(warning) => (
        <article className="warning-item">
          <div className="warning-header">
            <span className="warning-code">{pretty(warning.code)}</span>
            <span className="badge badge-warning">{pretty(warning.severity)}</span>
          </div>
          <p>{warning.message}</p>
          <p>{warning.public_interpretation}</p>
        </article>
      )}
      title="Warnings"
    />
  );
}

function LimitationsPanel({ limitations }: { limitations: string[] }) {
  return (
    <section className="signal-card">
      <h3>Limitations</h3>
      <LimitationsList limitations={limitations} />
    </section>
  );
}

function SourceSafetyPanel({
  payload,
}: {
  payload: WorkforceDashboardPayload;
}) {
  return (
    <section className="signal-card">
      <h3>Public-safe metadata</h3>
      <p>
        Partner submission internals exposed:{" "}
        {String(payload.public_safety.partner_submission_internals_exposed)}.
      </p>
      <p>
        Private review fields exposed: {String(payload.public_safety.private_review_fields_exposed)}.
      </p>
      <BadgeRow values={payload.public_safety.redacted_internal_fields} />
    </section>
  );
}

function PolicyList<T>({
  title,
  items,
  renderItem,
  emptyBody,
}: {
  title: string;
  items: T[];
  renderItem: (item: T) => ReactNode;
  emptyBody: string;
}) {
  return (
    <section className="policy-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="policy-grid">
          {items.map((item, index) => (
            <div key={policyListKey(item, index)}>{renderItem(item)}</div>
          ))}
        </div>
      ) : (
        <PolicyEmpty title={`No ${title.toLowerCase()}`} body={emptyBody} />
      )}
    </section>
  );
}

function LimitationsList({ limitations }: { limitations: string[] }) {
  if (!limitations.length) return null;
  return (
    <ul className="coverage-notes" aria-label="Limitations">
      {limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
    </ul>
  );
}

function BadgeRow({ values }: { values: string[] }) {
  const cleaned = values.filter(Boolean).slice(0, 8);
  if (!cleaned.length) return null;
  return (
    <div className="metadata-row">
      {cleaned.map((value) => (
        <span className="badge badge-unknown" key={value}>{pretty(value)}</span>
      ))}
    </div>
  );
}

function PolicyLink({
  href,
  label,
  onNavigate,
}: {
  href: string;
  label: string;
  onNavigate: PolicyIntelligencePageProps["onNavigate"];
}) {
  return (
    <a className="secondary-button" href={href} onClick={(event) => onNavigate(event, href)}>
      {label}
    </a>
  );
}

function PolicyLoading({ label }: { label: string }) {
  return (
    <div className="loading-block" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}

function PolicyError({ message }: { message: string }) {
  return (
    <div className="error-state" role="alert">
      <strong>Unable to load policy intelligence</strong>
      <p>{message}</p>
    </div>
  );
}

function PolicyEmpty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function policyMetrics(dashboard: WorkforceDashboardPayload): PolicyMetric[] {
  return [
    dashboard.core_metrics.opportunity_concentration_score,
    dashboard.core_metrics.early_career_access_score,
    dashboard.core_metrics.internship_pipeline_score,
    dashboard.core_metrics.employer_dependency_score,
    dashboard.core_metrics.sector_diversity_score,
    dashboard.core_metrics.talent_export_risk_score,
  ];
}

function policyTitle(view: PolicyView): string {
  if (view === "economic-development") return "Economic development dashboard";
  if (view === "education-alignment") return "Education-to-workforce alignment";
  if (view === "peer-comparison") return "Peer metro comparison";
  if (view === "report") return "Layer 24 public report";
  return "Regional policy dashboard";
}

function policySummary(view: PolicyView): string {
  if (view === "economic-development") {
    return "Sector gaps, employer-base risk, peer comparisons, and strategy-analysis candidates from backend Layer 24 payloads.";
  }
  if (view === "education-alignment") {
    return "Aggregate institution, program-area, internship, and local absorption signals from backend Layer 24 payloads.";
  }
  if (view === "peer-comparison") {
    return "Explainable comparison against peer metros using available Layer 24 policy metrics.";
  }
  if (view === "report") {
    return "A representative public report generated from backend Layer 24 workforce dashboard data.";
  }
  return "Regional workforce, access, concentration, diversity, and talent export risk metrics from backend Layer 24 payloads.";
}

function policyListKey(item: unknown, index: number): string {
  if (item && typeof item === "object") {
    const record = item as Record<string, unknown>;
    for (const key of [
      "metric_id",
      "finding_id",
      "code",
      "peer_region_id",
      "company_id",
      "program_area",
      "institution_id",
      "title",
      "risk_type",
      "gap_type",
      "market_id",
    ]) {
      const value = record[key];
      if (typeof value === "string" && value) return `${key}:${value}`;
    }
  }
  return `item:${index}`;
}

function formatScore(value: number | null): string {
  return value === null ? "Unknown" : `${Math.round(value * 100)}%`;
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
