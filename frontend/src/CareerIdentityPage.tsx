import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  ApiError,
  confirmCareerIdentityFact,
  createCareerIdentityFact,
  deleteCareerIdentityFact,
  discoverPersonalizedFromCareerIdentity,
  getCareerIdentity,
  getCareerIdentityEvaluation,
  getCareerIdentityPrivacy,
  ingestCareerIdentity,
  updateCareerIdentityFact,
  updateCareerIdentityPrivacy,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import type {
  CareerIdentity,
  CareerIdentityCompleteness,
  CareerIdentityFact,
  CareerIdentityFactState,
  CareerIdentityFactType,
  CareerIdentityIngestionResult,
  CareerIdentityPrivacy,
  PersonalizedResult,
} from "./types";

type LoadState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
};

type FieldKind = "text" | "textarea" | "date" | "number" | "select" | "boolean" | "tags";

type FieldConfig = {
  key: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  options?: string[];
};

type FactConfig = {
  type: CareerIdentityFactType;
  label: string;
  section: string;
  summaryKeys: string[];
  fields: FieldConfig[];
};

const FACT_CONFIGS: FactConfig[] = [
  {
    type: "education",
    label: "Education",
    section: "Background",
    summaryKeys: ["institution", "degree_type", "field_of_study"],
    fields: [
      { key: "institution", label: "Institution", kind: "text", required: true },
      { key: "degree_type", label: "Degree or credential", kind: "text" },
      { key: "field_of_study", label: "Field of study", kind: "text" },
      { key: "start_date", label: "Start date", kind: "date" },
      { key: "end_date", label: "End date", kind: "date" },
      { key: "expected_completion_date", label: "Expected completion", kind: "date" },
      { key: "currently_enrolled", label: "Currently enrolled", kind: "boolean" },
      { key: "location", label: "Location", kind: "text" },
      { key: "description", label: "Relevant details", kind: "textarea" },
    ],
  },
  {
    type: "experience",
    label: "Experience",
    section: "Background",
    summaryKeys: ["title", "organization", "start_date"],
    fields: [
      { key: "organization", label: "Organization", kind: "text", required: true },
      { key: "title", label: "Role or title", kind: "text", required: true },
      { key: "engagement_type", label: "Employment type", kind: "text" },
      { key: "start_date", label: "Start date", kind: "date" },
      { key: "end_date", label: "End date", kind: "date" },
      { key: "current_role", label: "Current role", kind: "boolean" },
      { key: "location", label: "Location", kind: "text" },
      {
        key: "work_arrangement",
        label: "Work arrangement",
        kind: "select",
        options: ["", "remote", "hybrid", "onsite", "flexible"],
      },
      { key: "description", label: "Responsibilities", kind: "textarea" },
      { key: "achievements", label: "Achievements", kind: "tags" },
      { key: "skills", label: "Skills used", kind: "tags" },
    ],
  },
  {
    type: "skill",
    label: "Skill",
    section: "Skills and projects",
    summaryKeys: ["name"],
    fields: [
      { key: "name", label: "Skill", kind: "text", required: true },
      { key: "normalized_name", label: "Canonical name", kind: "text" },
      { key: "evidence_refs", label: "Evidence notes", kind: "tags" },
    ],
  },
  {
    type: "project",
    label: "Project",
    section: "Skills and projects",
    summaryKeys: ["name", "role"],
    fields: [
      { key: "name", label: "Project name", kind: "text", required: true },
      { key: "role", label: "Your role", kind: "text" },
      { key: "description", label: "Description", kind: "textarea" },
      { key: "start_date", label: "Start date", kind: "date" },
      { key: "end_date", label: "End date", kind: "date" },
      { key: "technologies", label: "Technologies", kind: "tags" },
      { key: "outcomes", label: "Outcomes", kind: "tags" },
      { key: "links", label: "Links", kind: "tags" },
    ],
  },
  {
    type: "credential",
    label: "Credential",
    section: "Skills and projects",
    summaryKeys: ["name", "issuer"],
    fields: [
      { key: "name", label: "Credential name", kind: "text", required: true },
      { key: "issuer", label: "Issuer", kind: "text" },
      {
        key: "credential_type",
        label: "Credential type",
        kind: "select",
        options: ["", "certification", "license", "award", "formal_credential"],
      },
      { key: "issue_date", label: "Issue date", kind: "date" },
      { key: "expiration_date", label: "Expiration date", kind: "date" },
      { key: "credential_id", label: "Identifier", kind: "text" },
      { key: "url", label: "URL", kind: "text" },
    ],
  },
  {
    type: "career_goal",
    label: "Career goal",
    section: "Goals",
    summaryKeys: ["goal_type", "description"],
    fields: [
      {
        key: "goal_type",
        label: "Goal type",
        kind: "select",
        required: true,
        options: [
          "career_direction",
          "near_term_objective",
          "long_term_objective",
          "role_progression",
          "learning_development",
        ],
      },
      { key: "description", label: "Goal", kind: "textarea", required: true },
      { key: "target_date", label: "Target date", kind: "date" },
      { key: "priority", label: "Priority", kind: "number" },
    ],
  },
  {
    type: "role_preference",
    label: "Role preference",
    section: "Roles and industries",
    summaryKeys: ["role_title", "function", "preference_kind"],
    fields: [
      { key: "role_title", label: "Target role", kind: "text" },
      { key: "function", label: "Function", kind: "text" },
      { key: "seniority", label: "Seniority", kind: "text" },
      { key: "employment_type", label: "Employment type", kind: "text" },
      {
        key: "preference_kind",
        label: "Preference",
        kind: "select",
        options: ["preferred", "excluded", "neutral"],
      },
      { key: "priority", label: "Priority", kind: "number" },
    ],
  },
  {
    type: "industry_preference",
    label: "Industry preference",
    section: "Roles and industries",
    summaryKeys: ["industry", "preference_kind"],
    fields: [
      { key: "industry", label: "Industry", kind: "text", required: true },
      {
        key: "preference_kind",
        label: "Preference",
        kind: "select",
        options: ["preferred", "excluded", "neutral", "historical"],
      },
      { key: "priority", label: "Priority", kind: "number" },
    ],
  },
  {
    type: "geographic_constraint",
    label: "Geography",
    section: "Location and work style",
    summaryKeys: ["constraint_kind", "location", "remote_location_restriction"],
    fields: [
      { key: "location", label: "Location or region id", kind: "text" },
      {
        key: "constraint_kind",
        label: "Constraint",
        kind: "select",
        options: ["target", "acceptable", "excluded", "remote_restriction"],
      },
      {
        key: "relocation_willingness",
        label: "Relocation",
        kind: "select",
        options: ["", "yes", "no", "conditional"],
      },
      { key: "relocation_constraints", label: "Relocation constraints", kind: "textarea" },
      { key: "commute_radius_miles", label: "Commute radius", kind: "number" },
      { key: "remote_location_restriction", label: "Remote restriction", kind: "text" },
    ],
  },
  {
    type: "compensation_constraint",
    label: "Compensation",
    section: "Compensation and timing",
    summaryKeys: ["minimum_amount", "target_amount", "currency", "period"],
    fields: [
      { key: "minimum_amount", label: "Minimum", kind: "number" },
      { key: "target_amount", label: "Target", kind: "number" },
      { key: "currency", label: "Currency", kind: "text" },
      {
        key: "period",
        label: "Period",
        kind: "select",
        options: ["annual", "hourly", "monthly", "project"],
      },
      {
        key: "compensation_type",
        label: "Compensation type",
        kind: "select",
        options: ["salary", "hourly", "total", "contract"],
      },
      { key: "negotiable", label: "Negotiable", kind: "boolean" },
    ],
  },
  {
    type: "timing_preference",
    label: "Timing",
    section: "Compensation and timing",
    summaryKeys: ["timing_type", "date_value", "urgency"],
    fields: [
      {
        key: "timing_type",
        label: "Timing type",
        kind: "select",
        required: true,
        options: [
          "desired_start",
          "availability",
          "search_urgency",
          "graduation",
          "internship_window",
          "seasonal_window",
        ],
      },
      { key: "date_value", label: "Date", kind: "date" },
      { key: "start_date", label: "Window start", kind: "date" },
      { key: "end_date", label: "Window end", kind: "date" },
      {
        key: "urgency",
        label: "Urgency",
        kind: "select",
        options: ["", "low", "medium", "high", "immediate"],
      },
      { key: "description", label: "Details", kind: "textarea" },
    ],
  },
  {
    type: "work_arrangement_preference",
    label: "Work arrangement",
    section: "Location and work style",
    summaryKeys: ["arrangement", "willingness"],
    fields: [
      {
        key: "arrangement",
        label: "Arrangement",
        kind: "select",
        required: true,
        options: ["remote", "hybrid", "onsite", "flexible"],
      },
      {
        key: "willingness",
        label: "Willingness",
        kind: "select",
        required: true,
        options: ["yes", "no", "preferred", "required", "excluded"],
      },
      { key: "constraints", label: "Constraints", kind: "textarea" },
      { key: "priority", label: "Priority", kind: "number" },
    ],
  },
];

const FACT_CONFIG_BY_TYPE = new Map(FACT_CONFIGS.map((config) => [config.type, config]));
const ONBOARDING_STEPS = [
  "Background",
  "Skills and projects",
  "Goals",
  "Roles and industries",
  "Location and work style",
  "Compensation and timing",
  "Review",
];

const STATE_LABELS: Record<CareerIdentityFactState, string> = {
  explicit: "Added by you",
  imported: "Imported",
  inferred: "Suggested",
  confirmed: "Confirmed",
};

const EMPTY_PRIVACY: CareerIdentityPrivacy = {
  ingestion_consent_granted: false,
  inference_consent_granted: false,
  downstream_personalization_consent_granted: false,
  retain_import_metadata: true,
  privacy_visibility: "private",
};

function emptyLoad<T>(): LoadState<T> {
  return { loading: false, data: null, error: null };
}

export default function CareerIdentityPage({
  auth,
  defaultRegionIds,
}: {
  auth: FrontendAuthContextValue;
  defaultRegionIds: string[];
}) {
  const authOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );
  const [identityState, setIdentityState] = useState<LoadState<CareerIdentity>>(emptyLoad);
  const [evaluationState, setEvaluationState] = useState<LoadState<CareerIdentityCompleteness>>(emptyLoad);
  const [privacyDraft, setPrivacyDraft] = useState<CareerIdentityPrivacy>(EMPTY_PRIVACY);
  const [activeStep, setActiveStep] = useState(ONBOARDING_STEPS[0]);
  const [activeFactType, setActiveFactType] = useState<CareerIdentityFactType>("skill");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [editingFact, setEditingFact] = useState<CareerIdentityFact | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [importText, setImportText] = useState("");
  const [importSourceType, setImportSourceType] = useState<"resume_text" | "profile_text" | "structured_profile">("resume_text");
  const [importLabel, setImportLabel] = useState("Career profile import");
  const [importResult, setImportResult] = useState<CareerIdentityIngestionResult | null>(null);
  const [recommendationState, setRecommendationState] = useState<LoadState<PersonalizedResult>>(emptyLoad);
  const [recommendationRegions, setRecommendationRegions] = useState(
    (defaultRegionIds.length ? defaultRegionIds : ["greater_boston"]).slice(0, 2).join(", "),
  );
  const [recommendationMetadata, setRecommendationMetadata] = useState<Record<string, unknown> | null>(null);

  const identity = identityState.data;
  const evaluation = evaluationState.data ?? identity?.completeness ?? null;
  const currentVersion = identity?.current_version ?? null;

  const loadCareerIdentity = useCallback(async () => {
    if (!auth.isAuthenticated) return;
    setIdentityState((current) => ({ ...current, loading: true, error: null }));
    setEvaluationState((current) => ({ ...current, loading: true, error: null }));
    try {
      const identityEnvelope = await getCareerIdentity(authOptions);
      if (!identityEnvelope.data) {
        throw new Error("Career Identity response was empty.");
      }
      const [evaluationEnvelope, privacyEnvelope] = await Promise.all([
        getCareerIdentityEvaluation(authOptions),
        getCareerIdentityPrivacy(authOptions),
      ]);
      if (!evaluationEnvelope.data || !privacyEnvelope.data) {
        throw new Error("Career Identity response was empty.");
      }
      setIdentityState({ loading: false, data: identityEnvelope.data, error: null });
      setEvaluationState({ loading: false, data: evaluationEnvelope.data, error: null });
      setPrivacyDraft(privacyEnvelope.data.privacy);
    } catch (error) {
      const message = errorMessage(error, "Failed to load Career Identity.");
      setIdentityState({ loading: false, data: null, error: message });
      setEvaluationState({ loading: false, data: null, error: message });
    }
  }, [auth.isAuthenticated, authOptions]);

  useEffect(() => {
    void loadCareerIdentity();
  }, [loadCareerIdentity]);

  useEffect(() => {
    const candidates = FACT_CONFIGS.filter((config) => config.section === activeStep);
    if (!candidates.some((config) => config.type === activeFactType)) {
      setActiveFactType(candidates[0]?.type ?? "skill");
      setDraft({});
      setEditingFact(null);
    }
  }, [activeFactType, activeStep]);

  function selectStep(step: string) {
    const candidates = FACT_CONFIGS.filter((config) => config.section === step);
    setActiveStep(step);
    if (step !== "Review" && candidates.length) {
      setActiveFactType(candidates[0].type);
      setEditingFact(null);
      setDraft({});
    }
  }

  if (auth.isLoading) {
    return <CareerShell title="Career Identity"><LoadingBlock label="Checking account session" /></CareerShell>;
  }

  if (!auth.isAuthenticated) {
    return (
      <CareerShell title="Career Identity">
        <div className="career-identity-empty">
          <strong>Sign in to manage Career Identity</strong>
          <p>Career Identity is private, user-owned profile data and requires an authenticated account.</p>
          <button type="button" className="primary-button" onClick={() => void auth.login()}>
            Sign in
          </button>
        </div>
      </CareerShell>
    );
  }

  const reviewFacts = allFacts(identity).filter((fact) => fact.state === "imported" || fact.state === "inferred");
  const activeConfigs = activeStep === "Review"
    ? FACT_CONFIGS
    : FACT_CONFIGS.filter((config) => config.section === activeStep);
  const activeConfig = FACT_CONFIG_BY_TYPE.get(activeFactType) ?? FACT_CONFIGS[0];

  async function refreshAfterMutation(message: string) {
    await loadCareerIdentity();
    setActionMessage(message);
  }

  async function handleFactSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentVersion) return;
    setSaving(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const payload = buildPayload(activeConfig, draft);
      if (editingFact) {
        const envelope = await updateCareerIdentityFact(
          editingFact.career_identity_fact_id,
          { payload, state: "explicit", expected_version: currentVersion },
          authOptions,
        );
        if (envelope.data) {
          setIdentityState({ loading: false, data: envelope.data, error: null });
          setEvaluationState({ loading: false, data: envelope.data.completeness, error: null });
        }
        setActionMessage("Career fact corrected.");
      } else {
        const envelope = await createCareerIdentityFact(
          {
            fact_type: activeConfig.type,
            payload,
            state: "explicit",
            expected_version: currentVersion,
          },
          authOptions,
        );
        if (envelope.data?.identity) {
          setIdentityState({ loading: false, data: envelope.data.identity, error: null });
          setEvaluationState({ loading: false, data: envelope.data.identity.completeness, error: null });
        }
        setActionMessage("Career fact saved.");
      }
      setEditingFact(null);
      setDraft({});
    } catch (error) {
      await handleMutationError(error);
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirm(fact: CareerIdentityFact) {
    if (!currentVersion) return;
    setSaving(true);
    setActionError(null);
    try {
      const envelope = await confirmCareerIdentityFact(
        fact.career_identity_fact_id,
        { expected_version: currentVersion },
        authOptions,
      );
      if (envelope.data) {
        setIdentityState({ loading: false, data: envelope.data, error: null });
        setEvaluationState({ loading: false, data: envelope.data.completeness, error: null });
      }
      setActionMessage("Career fact confirmed.");
    } catch (error) {
      await handleMutationError(error);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(fact: CareerIdentityFact) {
    if (!currentVersion) return;
    setSaving(true);
    setActionError(null);
    try {
      await deleteCareerIdentityFact(fact.career_identity_fact_id, currentVersion, authOptions);
      await refreshAfterMutation("Career fact removed.");
    } catch (error) {
      await handleMutationError(error);
    } finally {
      setSaving(false);
    }
  }

  async function handlePrivacySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentVersion) return;
    setSaving(true);
    setActionError(null);
    try {
      const envelope = await updateCareerIdentityPrivacy(
        {
          ingestion_consent_granted: privacyDraft.ingestion_consent_granted,
          inference_consent_granted: privacyDraft.inference_consent_granted,
          downstream_personalization_consent_granted: privacyDraft.downstream_personalization_consent_granted,
          retain_import_metadata: privacyDraft.retain_import_metadata,
          expected_version: currentVersion,
        },
        authOptions,
      );
      if (envelope.data) {
        setIdentityState({ loading: false, data: envelope.data, error: null });
        setEvaluationState({ loading: false, data: envelope.data.completeness, error: null });
        setPrivacyDraft(envelope.data.privacy);
      }
      setActionMessage("Privacy settings saved.");
    } catch (error) {
      await handleMutationError(error);
    } finally {
      setSaving(false);
    }
  }

  async function handleImportSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentVersion) return;
    setSaving(true);
    setActionError(null);
    setActionMessage(null);
    setImportResult(null);
    try {
      const structured = importSourceType === "structured_profile" ? parseStructuredImport(importText) : null;
      const envelope = await ingestCareerIdentity(
        {
          source_type: importSourceType,
          source_label: importLabel || null,
          text: importSourceType === "structured_profile" ? null : importText,
          structured_profile: structured,
          consent_granted: privacyDraft.ingestion_consent_granted,
          expected_version: currentVersion,
        },
        authOptions,
      );
      if (!envelope.data) throw new Error("Import response was empty.");
      setImportResult(envelope.data);
      await refreshAfterMutation(
        envelope.data.status === "duplicate" ? "Duplicate import detected; profile unchanged." : "Career profile imported.",
      );
    } catch (error) {
      await handleMutationError(error);
    } finally {
      setSaving(false);
    }
  }

  async function handleRecommendationPreview() {
    const regionIds = recommendationRegions
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!regionIds.length) {
      setRecommendationState({ loading: false, data: null, error: "Add at least one region id." });
      return;
    }
    setRecommendationState((current) => ({ ...current, loading: true, error: null }));
    setRecommendationMetadata(null);
    try {
      const envelope = await discoverPersonalizedFromCareerIdentity(
        {
          region_ids: regionIds,
          role_targets: [],
          industry_preferences: [],
          career_stage: "entry_level",
          prestige_preference: "medium",
          brand_preference: "medium",
          limit: 10,
        },
        authOptions,
      );
      setRecommendationState({ loading: false, data: envelope.data, error: null });
      setRecommendationMetadata((envelope.metadata as Record<string, unknown>).career_identity_personalization as Record<string, unknown> ?? null);
    } catch (error) {
      setRecommendationState({ loading: false, data: null, error: errorMessage(error, "Failed to refresh personalized recommendations.") });
    }
  }

  function beginEdit(fact: CareerIdentityFact) {
    const config = FACT_CONFIG_BY_TYPE.get(fact.fact_type);
    if (!config) return;
    setActiveStep(config.section);
    setActiveFactType(config.type);
    setEditingFact(fact);
    setDraft(draftFromPayload(config, fact.payload));
    setActionMessage(null);
    setActionError(null);
  }

  async function handleMutationError(error: unknown) {
    const conflict = error instanceof ApiError && error.statusCode === 409;
    if (conflict) {
      setActionError("This profile changed in another request. The latest version was reloaded; review your draft and try again.");
      await loadCareerIdentity();
      return;
    }
    setActionError(errorMessage(error, "Career Identity action failed."));
  }

  return (
    <CareerShell title="Career Identity">
      {identityState.loading ? <LoadingBlock label="Loading Career Identity" /> : null}
      {identityState.error ? <ErrorBlock message={identityState.error} onRetry={loadCareerIdentity} /> : null}
      {identity ? (
        <>
          <section className="career-identity-hero">
            <div>
              <p className="eyebrow">Private profile source of truth</p>
              <h2>Career Identity</h2>
              <p>
                Enter, import, review, and use your career information for personalization.
              </p>
            </div>
            <CompletenessMeter evaluation={evaluation} version={identity.current_version} />
          </section>

          {actionMessage ? <div className="notice-state"><strong>{actionMessage}</strong></div> : null}
          {actionError ? <ErrorBlock message={actionError} onRetry={loadCareerIdentity} /> : null}

          <section className="career-identity-layout">
            <div className="career-identity-sidebar">
              <h3>Onboarding</h3>
              <div className="career-step-list" role="tablist" aria-label="Career Identity onboarding steps">
                {ONBOARDING_STEPS.map((step) => (
                  <button
                    type="button"
                    key={step}
                    className={step === activeStep ? "career-step career-step-active" : "career-step"}
                    onClick={() => selectStep(step)}
                    role="tab"
                    aria-selected={step === activeStep}
                  >
                    <span>{step}</span>
                    <small>{stepStatus(step, identity, evaluation)}</small>
                  </button>
                ))}
              </div>
              <CompletenessGuidance evaluation={evaluation} />
            </div>

            <div className="career-identity-main">
              <section className="career-panel">
                <div className="career-panel-header">
                  <div>
                    <p className="eyebrow">Guided entry</p>
                    <h3>{activeStep}</h3>
                  </div>
                  {activeStep !== "Review" ? (
                    <select
                      aria-label="Career fact type"
                      value={activeFactType}
                      onChange={(event) => {
                        setActiveFactType(event.target.value as CareerIdentityFactType);
                        setEditingFact(null);
                        setDraft({});
                      }}
                    >
                      {activeConfigs.map((config) => (
                        <option key={config.type} value={config.type}>{config.label}</option>
                      ))}
                    </select>
                  ) : null}
                </div>

                {activeStep === "Review" ? (
                  <ReviewQueue
                    facts={reviewFacts}
                    onConfirm={handleConfirm}
                    onDelete={handleDelete}
                    onEdit={beginEdit}
                    saving={saving}
                  />
                ) : (
                  <form className="career-fact-form" onSubmit={handleFactSubmit}>
                    <FactFormFields config={activeConfig} draft={draft} setDraft={setDraft} />
                    <div className="career-form-actions">
                      <button type="submit" className="primary-button" disabled={saving}>
                        {editingFact ? "Save correction" : `Add ${activeConfig.label.toLowerCase()}`}
                      </button>
                      {editingFact ? (
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => {
                            setEditingFact(null);
                            setDraft({});
                          }}
                        >
                          Cancel edit
                        </button>
                      ) : null}
                    </div>
                  </form>
                )}
              </section>

              <ImportPanel
                importLabel={importLabel}
                importSourceType={importSourceType}
                importText={importText}
                result={importResult}
                saving={saving}
                setImportLabel={setImportLabel}
                setImportSourceType={setImportSourceType}
                setImportText={setImportText}
                onSubmit={handleImportSubmit}
              />

              <FactInventory
                identity={identity}
                onConfirm={handleConfirm}
                onDelete={handleDelete}
                onEdit={beginEdit}
                saving={saving}
              />

              <PrivacyPanel
                draft={privacyDraft}
                saving={saving}
                setDraft={setPrivacyDraft}
                onSubmit={handlePrivacySubmit}
              />

              <RecommendationPreview
                metadata={recommendationMetadata}
                regionValue={recommendationRegions}
                setRegionValue={setRecommendationRegions}
                state={recommendationState}
                onRefresh={handleRecommendationPreview}
              />
            </div>
          </section>
        </>
      ) : null}
    </CareerShell>
  );
}

function CareerShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="career-identity-page">
      <header className="section-header">
        <div>
          <p className="eyebrow">Layer 35</p>
          <h2>{title}</h2>
        </div>
      </header>
      {children}
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="loading-block">
      <span />
      {label}
    </div>
  );
}

function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void | Promise<void> }) {
  return (
    <div className="error-state">
      <strong>Request failed</strong>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="secondary-button" onClick={() => void onRetry()}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

function CompletenessMeter({
  evaluation,
  version,
}: {
  evaluation: CareerIdentityCompleteness | null;
  version: number;
}) {
  const score = evaluation?.overall_score ?? 0;
  const percent = Math.round(score);
  return (
    <div className="career-completeness-meter" aria-label="Career Identity completeness">
      <strong>{percent}%</strong>
      <span>{evaluation?.sufficiency_state === "sufficient" ? "Sufficient for personalization" : "Needs more signal"}</span>
      <div className="career-progress-track">
        <span style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
      </div>
      <small>Identity version {evaluation?.identity_version ?? version}</small>
    </div>
  );
}

function CompletenessGuidance({ evaluation }: { evaluation: CareerIdentityCompleteness | null }) {
  if (!evaluation) return null;
  const reasons = evaluation.actionable_reason_codes.slice(0, 4);
  return (
    <div className="career-guidance">
      <strong>Next best inputs</strong>
      {reasons.length ? (
        <ul>
          {reasons.map((reason) => (
            <li key={reason}>{reasonToGuidance(reason)}</li>
          ))}
        </ul>
      ) : (
        <p>Your core Career Identity sections are ready.</p>
      )}
    </div>
  );
}

function FactFormFields({
  config,
  draft,
  setDraft,
}: {
  config: FactConfig;
  draft: Record<string, string>;
  setDraft: (next: Record<string, string>) => void;
}) {
  return (
    <div className="career-form-grid">
      {config.fields.map((field) => {
        const value = draft[field.key] ?? defaultFieldValue(field);
        const id = `career-${config.type}-${field.key}`;
        if (field.kind === "textarea") {
          return (
            <label key={field.key} className="career-field career-field-wide" htmlFor={id}>
              <span>{field.label}{field.required ? " *" : ""}</span>
              <textarea
                id={id}
                value={value}
                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                required={field.required}
                rows={3}
              />
            </label>
          );
        }
        if (field.kind === "select") {
          return (
            <label key={field.key} className="career-field" htmlFor={id}>
              <span>{field.label}{field.required ? " *" : ""}</span>
              <select
                id={id}
                value={value}
                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                required={field.required}
              >
                {(field.options ?? []).map((option) => (
                  <option key={option || "blank"} value={option}>
                    {option ? humanize(option) : "None"}
                  </option>
                ))}
              </select>
            </label>
          );
        }
        if (field.kind === "boolean") {
          return (
            <label key={field.key} className="career-check">
              <input
                type="checkbox"
                checked={value === "true"}
                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.checked ? "true" : "false" })}
              />
              <span>{field.label}</span>
            </label>
          );
        }
        return (
          <label key={field.key} className={field.kind === "tags" ? "career-field career-field-wide" : "career-field"} htmlFor={id}>
            <span>{field.label}{field.required ? " *" : ""}</span>
            <input
              id={id}
              type={field.kind === "date" ? "date" : field.kind === "number" ? "number" : "text"}
              value={value}
              onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
              required={field.required}
              placeholder={field.kind === "tags" ? "Comma-separated values" : undefined}
            />
          </label>
        );
      })}
    </div>
  );
}

function ReviewQueue({
  facts,
  onConfirm,
  onDelete,
  onEdit,
  saving,
}: {
  facts: CareerIdentityFact[];
  onConfirm: (fact: CareerIdentityFact) => void;
  onDelete: (fact: CareerIdentityFact) => void;
  onEdit: (fact: CareerIdentityFact) => void;
  saving: boolean;
}) {
  if (!facts.length) {
    return (
      <div className="career-identity-empty">
        <strong>No imported or suggested facts need review</strong>
        <p>New imported or inferred information will appear here before it is treated as confirmed by you.</p>
      </div>
    );
  }
  return (
    <div className="career-review-list">
      <p>{facts.length} fact{facts.length === 1 ? "" : "s"} need review.</p>
      {facts.map((fact) => (
        <FactRow
          key={fact.career_identity_fact_id}
          fact={fact}
          onConfirm={onConfirm}
          onDelete={onDelete}
          onEdit={onEdit}
          saving={saving}
        />
      ))}
    </div>
  );
}

function ImportPanel({
  importLabel,
  importSourceType,
  importText,
  result,
  saving,
  setImportLabel,
  setImportSourceType,
  setImportText,
  onSubmit,
}: {
  importLabel: string;
  importSourceType: "resume_text" | "profile_text" | "structured_profile";
  importText: string;
  result: CareerIdentityIngestionResult | null;
  saving: boolean;
  setImportLabel: (value: string) => void;
  setImportSourceType: (value: "resume_text" | "profile_text" | "structured_profile") => void;
  setImportText: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="career-panel">
      <div className="career-panel-header">
        <div>
          <p className="eyebrow">Import</p>
          <h3>Resume or profile import</h3>
        </div>
      </div>
      <form className="career-fact-form" onSubmit={onSubmit}>
        <div className="career-form-grid">
          <label className="career-field" htmlFor="career-import-type">
            <span>Input type</span>
            <select
              id="career-import-type"
              value={importSourceType}
              onChange={(event) => setImportSourceType(event.target.value as "resume_text" | "profile_text" | "structured_profile")}
            >
              <option value="resume_text">Resume text</option>
              <option value="profile_text">Profile text</option>
              <option value="structured_profile">Structured profile JSON</option>
            </select>
          </label>
          <label className="career-field" htmlFor="career-import-label">
            <span>Source label</span>
            <input id="career-import-label" value={importLabel} onChange={(event) => setImportLabel(event.target.value)} />
          </label>
          <label className="career-field career-field-wide" htmlFor="career-import-text">
            <span>{importSourceType === "structured_profile" ? "Structured JSON" : "Text"}</span>
            <textarea
              id="career-import-text"
              rows={6}
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
              placeholder={importSourceType === "structured_profile" ? "{\"skills\":[{\"name\":\"Python\"}]}" : "Paste supported resume or profile text"}
              required
            />
          </label>
        </div>
        <button type="submit" className="primary-button" disabled={saving}>
          Import profile
        </button>
      </form>
      {result ? (
        <div className="career-import-result">
          <strong>{humanize(result.status)}</strong>
          <span>{result.created_fact_count} created, {result.updated_fact_count} updated, {result.protected_fact_count} protected, {result.duplicate_fact_count} duplicate.</span>
        </div>
      ) : null}
    </section>
  );
}

function FactInventory({
  identity,
  onConfirm,
  onDelete,
  onEdit,
  saving,
}: {
  identity: CareerIdentity;
  onConfirm: (fact: CareerIdentityFact) => void;
  onDelete: (fact: CareerIdentityFact) => void;
  onEdit: (fact: CareerIdentityFact) => void;
  saving: boolean;
}) {
  return (
    <section className="career-panel">
      <div className="career-panel-header">
        <div>
          <p className="eyebrow">Profile editor</p>
          <h3>Current Career Identity facts</h3>
        </div>
      </div>
      <div className="career-fact-groups">
        {FACT_CONFIGS.map((config) => {
          const facts = identity.facts[config.type] ?? [];
          return (
            <section key={config.type} className="career-fact-group">
              <h4>{config.label}</h4>
              {facts.length ? facts.map((fact) => (
                <FactRow
                  key={fact.career_identity_fact_id}
                  fact={fact}
                  onConfirm={onConfirm}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  saving={saving}
                />
              )) : <p className="muted-copy">No {config.label.toLowerCase()} facts yet.</p>}
            </section>
          );
        })}
      </div>
    </section>
  );
}

function FactRow({
  fact,
  onConfirm,
  onDelete,
  onEdit,
  saving,
}: {
  fact: CareerIdentityFact;
  onConfirm: (fact: CareerIdentityFact) => void;
  onDelete: (fact: CareerIdentityFact) => void;
  onEdit: (fact: CareerIdentityFact) => void;
  saving: boolean;
}) {
  const config = FACT_CONFIG_BY_TYPE.get(fact.fact_type);
  return (
    <article className="career-fact-row">
      <div>
        <div className="career-fact-title">
          <strong>{summarizeFact(fact)}</strong>
          <span className={`career-state-badge career-state-${fact.state}`}>{STATE_LABELS[fact.state]}</span>
        </div>
        <p>{config?.label ?? humanize(fact.fact_type)}{fact.source_label ? ` from ${fact.source_label}` : ""}</p>
      </div>
      <div className="career-fact-actions">
        {fact.state !== "confirmed" ? (
          <button type="button" className="secondary-button" onClick={() => onConfirm(fact)} disabled={saving}>
            Confirm
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={() => onEdit(fact)} disabled={saving}>
          Edit
        </button>
        <button type="button" className="secondary-button danger-button" onClick={() => onDelete(fact)} disabled={saving}>
          Remove
        </button>
      </div>
    </article>
  );
}

function PrivacyPanel({
  draft,
  saving,
  setDraft,
  onSubmit,
}: {
  draft: CareerIdentityPrivacy;
  saving: boolean;
  setDraft: (draft: CareerIdentityPrivacy) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="career-panel">
      <div className="career-panel-header">
        <div>
          <p className="eyebrow">Privacy</p>
          <h3>Consent controls</h3>
        </div>
      </div>
      <form className="career-privacy-form" onSubmit={onSubmit}>
        <ConsentToggle
          checked={draft.ingestion_consent_granted}
          label="Allow resume/profile ingestion"
          description="Required before imported resume or profile text can become Career Identity facts."
          onChange={(checked) => setDraft({ ...draft, ingestion_consent_granted: checked })}
        />
        <ConsentToggle
          checked={draft.inference_consent_granted}
          label="Allow inferred suggestions"
          description="Controls whether system-derived suggestions can be stored for your review."
          onChange={(checked) => setDraft({ ...draft, inference_consent_granted: checked })}
        />
        <ConsentToggle
          checked={draft.downstream_personalization_consent_granted}
          label="Use Career Identity for recommendations"
          description="Allows the recommendation layer to read your Career Identity as its career-preference source."
          onChange={(checked) => setDraft({ ...draft, downstream_personalization_consent_granted: checked })}
        />
        <ConsentToggle
          checked={draft.retain_import_metadata}
          label="Retain safe import metadata"
          description="Keeps source labels and diagnostics, not raw imported text."
          onChange={(checked) => setDraft({ ...draft, retain_import_metadata: checked })}
        />
        <button type="submit" className="primary-button" disabled={saving}>
          Save privacy controls
        </button>
      </form>
    </section>
  );
}

function ConsentToggle({
  checked,
  description,
  label,
  onChange,
}: {
  checked: boolean;
  description: string;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="career-consent-toggle">
      <input
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
    </label>
  );
}

function RecommendationPreview({
  metadata,
  onRefresh,
  regionValue,
  setRegionValue,
  state,
}: {
  metadata: Record<string, unknown> | null;
  onRefresh: () => void;
  regionValue: string;
  setRegionValue: (value: string) => void;
  state: LoadState<PersonalizedResult>;
}) {
  const companies = state.data?.ranked_companies ?? [];
  return (
    <section className="career-panel">
      <div className="career-panel-header">
        <div>
          <p className="eyebrow">Recommendations</p>
          <h3>Career Identity personalization preview</h3>
        </div>
      </div>
      <div className="career-recommendation-controls">
        <label className="career-field" htmlFor="career-recommendation-regions">
          <span>Region ids</span>
          <input
            id="career-recommendation-regions"
            value={regionValue}
            onChange={(event) => setRegionValue(event.target.value)}
          />
        </label>
        <button type="button" className="primary-button" onClick={onRefresh} disabled={state.loading}>
          Refresh recommendations
        </button>
      </div>
      {state.loading ? <LoadingBlock label="Refreshing personalized recommendations" /> : null}
      {state.error ? <ErrorBlock message={state.error} /> : null}
      {metadata ? (
        <p className="career-source-rule">
          Source: {String(metadata.source)}; Career Identity applied: {String(metadata.career_identity_applied)}
        </p>
      ) : null}
      {companies.length ? (
        <div className="career-recommendation-list">
          {companies.slice(0, 3).map((company) => (
            <article key={`${company.company_id}:${company.region_id}`} className="career-recommendation-row">
              <strong>{company.company_name}</strong>
              <span>{company.region_display_name}</span>
              <small>Score {Math.round(company.personal_company_score * 100)}%</small>
              <p>{company.match_notes.length ? company.match_notes.join(", ") : "No specific match note returned."}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="career-identity-empty">
          <strong>No recommendation preview loaded</strong>
          <p>Refresh after adding target roles, industries, locations, and recommendation consent.</p>
        </div>
      )}
    </section>
  );
}

function buildPayload(config: FactConfig, draft: Record<string, string>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of config.fields) {
    const raw = draft[field.key] ?? defaultFieldValue(field);
    if (field.kind === "boolean") {
      payload[field.key] = raw === "true";
      continue;
    }
    if (!raw.trim() && !field.required) continue;
    if (field.kind === "number") {
      if (!raw.trim()) continue;
      payload[field.key] = Number(raw);
      continue;
    }
    if (field.kind === "tags") {
      payload[field.key] = raw.split(",").map((item) => item.trim()).filter(Boolean);
      continue;
    }
    payload[field.key] = raw.trim();
  }
  if (config.type === "compensation_constraint" && !payload.currency) payload.currency = "USD";
  if (config.type === "compensation_constraint" && !payload.period) payload.period = "annual";
  if (config.type === "compensation_constraint" && !payload.compensation_type) payload.compensation_type = "salary";
  if (config.type === "role_preference" && !payload.preference_kind) payload.preference_kind = "preferred";
  if (config.type === "industry_preference" && !payload.preference_kind) payload.preference_kind = "preferred";
  if (config.type === "geographic_constraint" && !payload.constraint_kind) payload.constraint_kind = "target";
  return payload;
}

function draftFromPayload(config: FactConfig, payload: Record<string, unknown>): Record<string, string> {
  const draft: Record<string, string> = {};
  for (const field of config.fields) {
    const value = payload[field.key];
    if (Array.isArray(value)) {
      draft[field.key] = value.join(", ");
    } else if (typeof value === "boolean") {
      draft[field.key] = value ? "true" : "false";
    } else if (value !== null && value !== undefined) {
      draft[field.key] = String(value);
    }
  }
  return draft;
}

function defaultFieldValue(field: FieldConfig): string {
  if (field.kind === "boolean") return "false";
  if (field.kind === "select") return field.options?.[0] ?? "";
  return "";
}

function allFacts(identity: CareerIdentity | null): CareerIdentityFact[] {
  if (!identity) return [];
  return FACT_CONFIGS.flatMap((config) => identity.facts[config.type] ?? []);
}

function summarizeFact(fact: CareerIdentityFact): string {
  const config = FACT_CONFIG_BY_TYPE.get(fact.fact_type);
  const values = (config?.summaryKeys ?? [])
    .map((key) => fact.payload[key])
    .filter((value) => value !== null && value !== undefined && String(value).trim())
    .map(String);
  return values.length ? values.join(" / ") : humanize(fact.fact_type);
}

function stepStatus(
  step: string,
  identity: CareerIdentity,
  evaluation: CareerIdentityCompleteness | null,
): string {
  if (step === "Review") {
    const count = allFacts(identity).filter((fact) => fact.state === "imported" || fact.state === "inferred").length;
    return count ? `${count} to review` : "clear";
  }
  const hasFacts = FACT_CONFIGS.some((config) => config.section === step && (identity.facts[config.type] ?? []).length);
  if (hasFacts) return "started";
  const missing = evaluation?.missing_categories ?? [];
  return missing.some((category) => step.toLowerCase().includes(category.replaceAll("_", " "))) ? "needed" : "optional";
}

function reasonToGuidance(reason: string): string {
  const labels: Record<string, string> = {
    missing_background: "Add education or experience.",
    missing_skills: "Add relevant skills.",
    missing_goals: "Add a career goal.",
    missing_role_preferences: "Choose target roles.",
    missing_industry_preferences: "Choose target industries.",
    missing_geography: "Add preferred work locations.",
    missing_work_arrangement: "Choose remote, hybrid, or onsite preferences.",
    missing_compensation: "Add compensation constraints if they matter.",
    missing_timing: "Add availability or search timing.",
  };
  return labels[reason] ?? humanize(reason);
}

function parseStructuredImport(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Structured profile must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.envelope?.error?.message ?? error.message;
  }
  if (error instanceof SyntaxError) {
    return "Structured profile JSON is malformed.";
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
