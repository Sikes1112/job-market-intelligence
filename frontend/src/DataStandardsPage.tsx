import { useEffect, useMemo, useState } from "react";
import {
  getDataStandardDefinitions,
  getDataStandardsGovernanceFramework,
  getDataStandardsPartnerSchema,
  getDataStandardsPartners,
  getDataStandardsQualityLabels,
} from "./api";
import type {
  ApiEnvelope,
  DataQualityLabelListPayload,
  DataStandardDefinitionListPayload,
  GovernanceFrameworkPayload,
  PartnerRegistryPayload,
  PartnerSubmissionSchemaPayload,
} from "./types";

type DataStandardsLoadState = {
  loading: boolean;
  definitions: ApiEnvelope<DataStandardDefinitionListPayload> | null;
  partnerSchema: ApiEnvelope<PartnerSubmissionSchemaPayload> | null;
  partners: ApiEnvelope<PartnerRegistryPayload> | null;
  qualityLabels: ApiEnvelope<DataQualityLabelListPayload> | null;
  governance: ApiEnvelope<GovernanceFrameworkPayload> | null;
  error: string | null;
};

const EMPTY_STATE: DataStandardsLoadState = {
  loading: true,
  definitions: null,
  partnerSchema: null,
  partners: null,
  qualityLabels: null,
  governance: null,
  error: null,
};

export default function DataStandardsPage() {
  const [state, setState] = useState<DataStandardsLoadState>(() => EMPTY_STATE);

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    Promise.all([
      getDataStandardDefinitions(),
      getDataStandardsPartnerSchema(),
      getDataStandardsPartners(),
      getDataStandardsQualityLabels(),
      getDataStandardsGovernanceFramework(),
    ])
      .then(([definitions, partnerSchema, partners, qualityLabels, governance]) => {
        if (cancelled) return;
        setState({
          loading: false,
          definitions,
          partnerSchema,
          partners,
          qualityLabels,
          governance,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          loading: false,
          definitions: null,
          partnerSchema: null,
          partners: null,
          qualityLabels: null,
          governance: null,
          error: error instanceof Error ? error.message : "Failed to load data standards",
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const definitions = state.definitions?.data?.definitions ?? [];
  const schema = state.partnerSchema?.data ?? null;
  const partners = state.partners?.data?.partners ?? [];
  const qualityLabels = state.qualityLabels?.data?.labels ?? [];
  const governanceRecords = state.governance?.data?.governance_records ?? [];
  const lowConfidence = qualityLabels.find((label) => label.label === "low_confidence_signal");
  const selfReported = qualityLabels.find((label) => label.label === "self_reported_employer_data");
  const activeBoardClaim = useMemo(() => {
    const text = JSON.stringify(state.governance?.data ?? {}).toLocaleLowerCase();
    return /board_active|board_approved|externally_governed/.test(text);
  }, [state.governance]);

  return (
    <div className="public-page public-document data-standards-page">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Layer 27 standards surface</p>
        <h1>Data standards and partner governance</h1>
        <p className="public-lead">
          Layer 27 defines standards and intake quality. Layer 28 adds controlled
          reviewer-approved canonical merge for eligible candidate facts, but
          partner-submitted data never mutates canonical truth directly and quality
          labels do not currently alter rankings, recommendations, forecasts, policy
          outputs, career-agent outputs, public reports, or market scores.
        </p>
        <div className="metadata-row">
          <span className="badge badge-real">Backend standards API</span>
          <span className="badge badge-warning">Controlled merge only</span>
          <span className="badge badge-unknown">Admin API review path</span>
        </div>
      </section>

      {state.loading ? <p className="meta-copy">Loading Layer 27 standards metadata...</p> : null}
      {state.error ? (
        <div className="error-state">
          <strong>Unable to load standards metadata</strong>
          <p>{state.error}</p>
        </div>
      ) : null}

      <section className="public-document-list" aria-label="Layer 27 data standards">
        <article className="public-section">
          <h2>Standard Definitions</h2>
          <p>
            Canonical terms are metadata for shared understanding. Layer 27 validation
            does not mutate canonical company, region, opportunity, recommendation,
            forecast, policy, career-agent, public report, contribution, or market-score
            records; Layer 28 merge requires internal review and provenance binding.
          </p>
          <div className="standards-grid">
            {definitions.map((definition) => (
              <div className="standards-item" key={definition.canonical_name}>
                <div className="metadata-row">
                  <span className="badge badge-real">{definition.status}</span>
                  <span className="badge badge-unknown">{definition.version}</span>
                </div>
                <h3>{definition.term}</h3>
                <p>{definition.description}</p>
                <small>Examples: {definition.examples.join(", ")}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="public-section">
          <h2>Partner Submission Format</h2>
          <p>
            Submission validation checks structure, source refs, freshness, confidence, and
            warnings. Validation is separate from certification and canonical acceptance.
          </p>
          {schema ? (
            <dl className="authority-detail-list">
              <div>
                <dt>Schema version</dt>
                <dd>{schema.schema_version}</dd>
              </div>
              <div>
                <dt>Record types</dt>
                <dd>{schema.supported_record_types.map(prettyLabel).join(", ")}</dd>
              </div>
              <div>
                <dt>Required submission fields</dt>
                <dd>{schema.required_submission_fields.join(", ")}</dd>
              </div>
              <div>
                <dt>Freshness and confidence</dt>
                <dd>
                  Freshness required: {schema.freshness_required ? "yes" : "no"}; confidence
                  required: {schema.confidence_required ? "yes" : "no"}.
                </dd>
              </div>
            </dl>
          ) : null}
        </article>

        <article className="public-section">
          <h2>Verified Partner Network</h2>
          <p>
            Partner verification is registry metadata. A verified partner may submit data,
            but the submitted records still require validation, source refs, confidence,
            freshness, warnings, and quality-label evaluation.
          </p>
          <div className="standards-grid">
            {partners.map((partner) => (
              <div className="standards-item" key={partner.partner_id}>
                <div className="metadata-row">
                  <span className="badge badge-real">{prettyLabel(partner.partner_type)}</span>
                  <span className="badge badge-warning">{prettyLabel(partner.verification_status)}</span>
                  <span className="badge badge-unknown">{prettyLabel(partner.trust_tier)}</span>
                </div>
                <h3>{partner.name}</h3>
                <p>Region scope: {partner.region_scope.map(prettyLabel).join(", ")}</p>
                <small>
                  Allowed submissions: {partner.allowed_submission_types.map(prettyLabel).join(", ")}
                </small>
              </div>
            ))}
          </div>
        </article>

        <article className="public-section">
          <h2>Data Quality Labels</h2>
          <p>
            Quality labels are currently non-ranking metadata. They do not currently alter
            rankings, recommendations, forecasts, policy outputs, career-agent outputs, public
            reports, or market scores.
          </p>
          <div className="standards-grid">
            {qualityLabels.map((label) => (
              <div className="standards-item" key={label.label}>
                <div className="metadata-row">
                  <span className="badge badge-real">{label.minimum_confidence}</span>
                  <span className="badge badge-warning">
                    Ranking influence: {label.ranking_influence_allowed ? "allowed" : "disabled"}
                  </span>
                </div>
                <h3>{label.display_name}</h3>
                <p>{label.description}</p>
                <p className="meta-copy">{label.warning_copy}</p>
              </div>
            ))}
          </div>
          <div className="warning-list" aria-label="Quality label warnings">
            {lowConfidence ? (
              <div className="warning-item">
                <div className="warning-header">
                  <span className="warning-code">Low-confidence warning</span>
                </div>
                <p>{lowConfidence.warning_copy}</p>
              </div>
            ) : null}
            {selfReported ? (
              <div className="warning-item">
                <div className="warning-header">
                  <span className="warning-code">Self-reported employer warning</span>
                </div>
                <p>{selfReported.warning_copy}</p>
              </div>
            ) : null}
          </div>
        </article>

        <article className="public-section">
          <h2>Governance Framework</h2>
          <p>
            Governance is currently a framework, not an active governance board.
            The status is {state.governance?.data?.status ?? "framework_defined"}.
          </p>
          {activeBoardClaim ? (
            <div className="error-state">
              <strong>Unsafe governance claim detected</strong>
              <p>The backend returned board-active language for a framework-only page.</p>
            </div>
          ) : null}
          <div className="standards-grid">
            {governanceRecords.map((record) => (
              <div className="standards-item" key={record.area}>
                <div className="metadata-row">
                  <span className="badge badge-unknown">{record.status}</span>
                  <span className="badge badge-unknown">{record.version}</span>
                </div>
                <h3>{record.display_name}</h3>
                <p>{record.public_summary}</p>
                <details>
                  <summary>Review controls</summary>
                  <ul>
                    {record.recommended_controls.map((control) => (
                      <li key={control}>{control}</li>
                    ))}
                  </ul>
                </details>
              </div>
            ))}
          </div>
        </article>

        <article className="public-section">
          <h2>Submission Validation Preview</h2>
          <p>
            This preview is schema-only and does not create partner submissions. It shows
            validation expectations, not automatic acceptance, data certification, or canonical
            merge.
          </p>
          {schema ? (
            <ul>
              <li>Supported record type example: {prettyLabel(schema.supported_record_types[0] ?? "company")}</li>
              <li>Source refs are required for: {schema.source_refs_required_for_record_types.map(prettyLabel).join(", ")}</li>
              <li>Validation statuses include: {schema.validation_statuses.map(prettyLabel).join(", ")}</li>
            </ul>
          ) : null}
        </article>
      </section>
    </div>
  );
}

function prettyLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
