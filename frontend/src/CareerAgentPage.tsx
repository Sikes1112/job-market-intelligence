import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
} from "react";
import {
  approveCareerAgentTool,
  deleteCareerMemory,
  getCareerActionPlan,
  getCareerActionPlanWithMemory,
  getCareerAgentAnswer,
  getCareerMemory,
  previewCareerAgentTool,
  rejectCareerAgentTool,
  updateCareerMemory,
  type ProtectedRequestOptions,
} from "./api";
import type {
  CareerActionPlan,
  CareerActionPlanRequest,
  CareerAgentAnswer,
  CareerAgentEvidenceRef,
  CareerAgentQuestionType,
  CareerAgentRecommendation,
  CareerAgentRequest,
  CareerAgentToolExecution,
  CareerAgentToolPreview,
  CareerAgentToolRequest,
  CareerAgentToolType,
  CareerMemoryCategory,
  CareerMemoryProfile,
  CareerPlanStep,
  CareerPlanType,
} from "./careerAgentTypes";
import type { ApiEnvelope } from "./types";
import { commaList } from "./opportunityRoutes";

type CareerAgentLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<CareerAgentAnswer> | null;
  error: string | null;
};

type CareerActionPlanLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<CareerActionPlan> | null;
  error: string | null;
};

type CareerMemoryLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<CareerMemoryProfile> | null;
  error: string | null;
};

type CareerToolLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<CareerAgentToolPreview> | null;
  executionEnvelope: ApiEnvelope<CareerAgentToolExecution> | null;
  error: string | null;
};

type CareerAgentFormState = {
  questionType: CareerAgentQuestionType;
  goal: string;
  regions: string;
  companies: string;
  roles: string;
  programTypes: string;
  locationModes: string;
  preferredRegions: string;
  preferredCompanies: string;
  constraints: string;
  includeForecasts: boolean;
  limit: number;
};

type CareerMemoryFormState = Record<CareerMemoryCategory, string>;

type CareerAgentPageProps = {
  authenticated?: boolean;
  protectedOptions?: ProtectedRequestOptions;
};

const QUESTION_TYPES: CareerAgentQuestionType[] = [
  "where_should_i_apply",
  "city_fit",
  "companies_to_watch",
  "strongest_market_strategy",
  "what_should_i_do_this_month",
];

const PLAN_TYPES: CareerPlanType[] = [
  "weekly_job_search_plan",
  "regional_targeting_plan",
  "company_research_plan",
  "internship_application_calendar",
  "networking_plan",
];

const MEMORY_CATEGORIES: CareerMemoryCategory[] = [
  "saved_companies",
  "target_regions",
  "applied_roles",
  "preferred_industries",
  "rejected_markets",
  "career_constraints",
  "preferred_role_types",
];

const TOOL_TYPES: CareerAgentToolType[] = [
  "reminder",
  "career_report_export",
  "watchlist_update_suggestion",
  "notification_preference",
  "outreach_message_draft",
  "application_prep_checklist",
  "job_application_submission",
];

const DEFAULT_CAREER_AGENT_REQUEST: CareerAgentRequest = {
  question_type: "what_should_i_do_this_month",
  user_goal: "Early-career software strategy.",
  target_region_ids: ["greater_boston", "atlanta"],
  target_role_families: ["software_engineering", "product_management"],
  preferred_program_types: ["internship", "new_grad_role"],
  preferred_location_modes: ["hybrid", "remote"],
  include_forecasts: true,
  limit: 5,
  preference_snapshot: {
    preferred_role_families: ["software_engineering"],
    preferred_location_modes: ["hybrid", "remote"],
    preferred_program_types: ["internship", "new_grad_role"],
    constraints: ["verify source freshness before acting"],
    counts_as_evidence: false,
  },
};

function initialFormState(): CareerAgentFormState {
  const preferences = DEFAULT_CAREER_AGENT_REQUEST.preference_snapshot;
  return {
    questionType: DEFAULT_CAREER_AGENT_REQUEST.question_type,
    goal: DEFAULT_CAREER_AGENT_REQUEST.user_goal ?? "",
    regions: (DEFAULT_CAREER_AGENT_REQUEST.target_region_ids ?? []).join(", "),
    companies: (DEFAULT_CAREER_AGENT_REQUEST.target_company_ids ?? []).join(", "),
    roles: (DEFAULT_CAREER_AGENT_REQUEST.target_role_families ?? []).join(", "),
    programTypes: (DEFAULT_CAREER_AGENT_REQUEST.preferred_program_types ?? []).join(", "),
    locationModes: (DEFAULT_CAREER_AGENT_REQUEST.preferred_location_modes ?? []).join(", "),
    preferredRegions: (preferences?.preferred_region_ids ?? []).join(", "),
    preferredCompanies: (preferences?.preferred_company_ids ?? []).join(", "),
    constraints: (preferences?.constraints ?? []).join(", "),
    includeForecasts: DEFAULT_CAREER_AGENT_REQUEST.include_forecasts ?? true,
    limit: DEFAULT_CAREER_AGENT_REQUEST.limit ?? 5,
  };
}

function initialMemoryFormState(): CareerMemoryFormState {
  return {
    saved_companies: "",
    target_regions: "",
    applied_roles: "",
    preferred_industries: "",
    rejected_markets: "",
    career_constraints: "",
    preferred_role_types: "",
  };
}

function memoryProfileToForm(profile: CareerMemoryProfile): CareerMemoryFormState {
  const next = initialMemoryFormState();
  MEMORY_CATEGORIES.forEach((category) => {
    next[category] = (profile.entries_by_category[category] ?? [])
      .map((entry) => entry.value)
      .join(", ");
  });
  return next;
}

function formToRequest(form: CareerAgentFormState): CareerAgentRequest {
  const preferredRegions = commaList(form.preferredRegions);
  const preferredCompanies = commaList(form.preferredCompanies);
  const roles = commaList(form.roles);
  const locationModes = commaList(form.locationModes);
  const programTypes = commaList(form.programTypes);
  const constraints = commaList(form.constraints);
  return {
    question_type: form.questionType,
    user_goal: form.goal || null,
    target_region_ids: commaList(form.regions),
    target_company_ids: commaList(form.companies),
    target_role_families: roles,
    preferred_program_types: programTypes,
    preferred_location_modes: locationModes,
    include_forecasts: form.includeForecasts,
    limit: form.limit,
    preference_snapshot: {
      preferred_region_ids: preferredRegions,
      preferred_company_ids: preferredCompanies,
      preferred_role_families: roles,
      preferred_location_modes: locationModes,
      preferred_program_types: programTypes,
      constraints,
      counts_as_evidence: false,
    },
  };
}

export default function CareerAgentPage({
  authenticated = false,
  protectedOptions,
}: CareerAgentPageProps) {
  const [form, setForm] = useState<CareerAgentFormState>(() => initialFormState());
  const [planType, setPlanType] = useState<CareerPlanType>("weekly_job_search_plan");
  const [includeMemoryInPlan, setIncludeMemoryInPlan] = useState(false);
  const [toolType, setToolType] = useState<CareerAgentToolType>("reminder");
  const [memoryForm, setMemoryForm] = useState<CareerMemoryFormState>(() => initialMemoryFormState());
  const [state, setState] = useState<CareerAgentLoadState>({
    loading: false,
    envelope: null,
    error: null,
  });
  const [planState, setPlanState] = useState<CareerActionPlanLoadState>({
    loading: false,
    envelope: null,
    error: null,
  });
  const [memoryState, setMemoryState] = useState<CareerMemoryLoadState>({
    loading: false,
    envelope: null,
    error: null,
  });
  const [toolState, setToolState] = useState<CareerToolLoadState>({
    loading: false,
    envelope: null,
    executionEnvelope: null,
    error: null,
  });
  const requestPreview = useMemo(() => formToRequest(form), [form]);
  const answer = state.envelope?.data ?? null;
  const plan = planState.envelope?.data ?? null;
  const toolPreview = toolState.executionEnvelope?.data?.tool_preview ?? toolState.envelope?.data ?? null;
  const memoryProfile = memoryState.envelope?.data ?? null;
  const canUseMemory = authenticated && Boolean(protectedOptions);

  const submit = useCallback(async (request: CareerAgentRequest) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await getCareerAgentAnswer(request);
      setState({ loading: false, envelope, error: null });
    } catch (error) {
      setState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Career agent is unavailable",
      });
    }
  }, []);

  useEffect(() => {
    void submit(DEFAULT_CAREER_AGENT_REQUEST);
  }, [submit]);

  const loadMemory = useCallback(async () => {
    if (!canUseMemory || !protectedOptions) return;
    setMemoryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await getCareerMemory(protectedOptions);
      setMemoryForm(envelope.data ? memoryProfileToForm(envelope.data) : initialMemoryFormState());
      setMemoryState({ loading: false, envelope, error: null });
    } catch (error) {
      setMemoryState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Career memory is unavailable",
      });
    }
  }, [canUseMemory, protectedOptions]);

  useEffect(() => {
    void loadMemory();
  }, [loadMemory]);

  const generatePlan = useCallback(async () => {
    const body: CareerActionPlanRequest = {
      plan_type: planType,
      career_goal: requestPreview.user_goal,
      career_agent_request: requestPreview,
      include_memory: includeMemoryInPlan && canUseMemory,
      limit: requestPreview.limit,
    };
    setPlanState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = body.include_memory && protectedOptions
        ? await getCareerActionPlanWithMemory(body, protectedOptions)
        : await getCareerActionPlan({ ...body, include_memory: false });
      setPlanState({ loading: false, envelope, error: null });
    } catch (error) {
      setPlanState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Career action plan is unavailable",
      });
    }
  }, [canUseMemory, includeMemoryInPlan, planType, protectedOptions, requestPreview]);

  const saveMemory = useCallback(async () => {
    if (!canUseMemory || !protectedOptions) return;
    const entries = MEMORY_CATEGORIES.flatMap((category) =>
      commaList(memoryForm[category]).map((value) => ({ category, value })),
    );
    const enabledCategories = new Set(entries.map((entry) => entry.category));
    setMemoryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await updateCareerMemory(
        {
          explicit_user_permission: true,
          permissions: MEMORY_CATEGORIES.map((category) => ({
            category,
            enabled: enabledCategories.has(category),
            personalize_allowed: enabledCategories.has(category),
            visibility: "private",
          })),
          entries,
          replace_categories: MEMORY_CATEGORIES,
        },
        protectedOptions,
      );
      setMemoryForm(envelope.data ? memoryProfileToForm(envelope.data) : initialMemoryFormState());
      setMemoryState({ loading: false, envelope, error: null });
    } catch (error) {
      setMemoryState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Career memory could not be saved",
      });
    }
  }, [canUseMemory, memoryForm, protectedOptions]);

  const clearMemory = useCallback(async () => {
    if (!canUseMemory || !protectedOptions) return;
    setMemoryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await deleteCareerMemory({ clear_all: true }, protectedOptions);
      setMemoryForm(initialMemoryFormState());
      setMemoryState({ loading: false, envelope, error: null });
    } catch (error) {
      setMemoryState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Career memory could not be cleared",
      });
    }
  }, [canUseMemory, protectedOptions]);

  const createToolPreview = useCallback(async () => {
    if (!canUseMemory || !protectedOptions) {
      setToolState((current) => ({
        ...current,
        error: "Sign in to create protected tool previews.",
      }));
      return;
    }
    const body: CareerAgentToolRequest = {
      tool_type: toolType,
      career_agent_request: requestPreview,
      action_plan_request: plan
        ? {
            plan_type: plan.plan_type,
            career_goal: plan.career_goal,
            career_agent_request: requestPreview,
            include_memory: includeMemoryInPlan && canUseMemory,
            limit: requestPreview.limit,
          }
        : undefined,
      requested_action: toolType === "job_application_submission" ? "submit_application" : "preview",
      include_memory: includeMemoryInPlan && canUseMemory,
      include_private_memory_in_export: false,
      user_context_claims: ["User context must stay separate from product evidence."],
      draft_recipient_role: "career contact",
      limit: requestPreview.limit,
    };
    setToolState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await previewCareerAgentTool(body, protectedOptions);
      setToolState({
        loading: false,
        envelope,
        executionEnvelope: null,
        error: null,
      });
    } catch (error) {
      setToolState({
        loading: false,
        envelope: null,
        executionEnvelope: null,
        error: error instanceof Error ? error.message : "Tool preview is unavailable",
      });
    }
  }, [
    canUseMemory,
    includeMemoryInPlan,
    plan,
    protectedOptions,
    requestPreview,
    toolType,
  ]);

  const approveTool = useCallback(async () => {
    if (!toolPreview || !protectedOptions) return;
    setToolState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await approveCareerAgentTool(
        {
          tool_request_id: toolPreview.tool_request_id,
          explicit_user_approval: true,
        },
        protectedOptions,
      );
      setToolState({
        loading: false,
        envelope: null,
        executionEnvelope: envelope,
        error: null,
      });
    } catch (error) {
      setToolState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "Tool approval failed",
      }));
    }
  }, [protectedOptions, toolPreview]);

  const rejectTool = useCallback(async () => {
    if (!toolPreview || !protectedOptions) return;
    setToolState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await rejectCareerAgentTool(
        {
          tool_request_id: toolPreview.tool_request_id,
          explicit_user_approval: false,
        },
        protectedOptions,
      );
      setToolState({
        loading: false,
        envelope: null,
        executionEnvelope: envelope,
        error: null,
      });
    } catch (error) {
      setToolState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "Tool rejection failed",
      }));
    }
  }, [protectedOptions, toolPreview]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(requestPreview);
  }

  return (
    <div className="view-grid career-agent-view">
      <section className="card career-agent-control">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Career agent</p>
            <h2>Grounded Career Agent</h2>
          </div>
          <span className="badge badge-success">Evidence contract</span>
        </div>

        <form className="career-agent-form-grid" onSubmit={handleSubmit}>
          <label>
            Question
            <select
              value={form.questionType}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  questionType: event.target.value as CareerAgentQuestionType,
                }))
              }
            >
              {QUESTION_TYPES.map((questionType) => (
                <option key={questionType} value={questionType}>
                  {displayLabel(questionType)}
                </option>
              ))}
            </select>
          </label>
          <label className="wide-field">
            Goal
            <input
              value={form.goal}
              onChange={(event) =>
                setForm((current) => ({ ...current, goal: event.target.value }))
              }
            />
          </label>
          <label>
            Regions
            <input
              value={form.regions}
              onChange={(event) =>
                setForm((current) => ({ ...current, regions: event.target.value }))
              }
            />
          </label>
          <label>
            Companies
            <input
              value={form.companies}
              onChange={(event) =>
                setForm((current) => ({ ...current, companies: event.target.value }))
              }
            />
          </label>
          <label>
            Role families
            <input
              value={form.roles}
              onChange={(event) =>
                setForm((current) => ({ ...current, roles: event.target.value }))
              }
            />
          </label>
          <label>
            Program types
            <input
              value={form.programTypes}
              onChange={(event) =>
                setForm((current) => ({ ...current, programTypes: event.target.value }))
              }
            />
          </label>
          <label>
            Location modes
            <input
              value={form.locationModes}
              onChange={(event) =>
                setForm((current) => ({ ...current, locationModes: event.target.value }))
              }
            />
          </label>
          <label>
            Preferred regions
            <input
              value={form.preferredRegions}
              onChange={(event) =>
                setForm((current) => ({ ...current, preferredRegions: event.target.value }))
              }
            />
          </label>
          <label>
            Preferred companies
            <input
              value={form.preferredCompanies}
              onChange={(event) =>
                setForm((current) => ({ ...current, preferredCompanies: event.target.value }))
              }
            />
          </label>
          <label>
            Limit
            <input
              min={1}
              max={10}
              type="number"
              value={form.limit}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  limit: Math.max(1, Math.min(10, Number(event.target.value) || 1)),
                }))
              }
            />
          </label>
          <label className="wide-field">
            Constraints
            <input
              value={form.constraints}
              onChange={(event) =>
                setForm((current) => ({ ...current, constraints: event.target.value }))
              }
            />
          </label>
          <label className="route-check wide-field route-check-inline">
            <input
              checked={form.includeForecasts}
              type="checkbox"
              onChange={(event) =>
                setForm((current) => ({ ...current, includeForecasts: event.target.checked }))
              }
            />
            <span>Include bounded forecasts</span>
          </label>
          <button className="primary-button route-submit" disabled={state.loading} type="submit">
            {state.loading ? "Answering" : "Ask agent"}
          </button>
        </form>

        <div className="career-agent-plan-controls">
          <label>
            Plan type
            <select
              value={planType}
              onChange={(event) => setPlanType(event.target.value as CareerPlanType)}
            >
              {PLAN_TYPES.map((type) => (
                <option key={type} value={type}>
                  {displayLabel(type)}
                </option>
              ))}
            </select>
          </label>
          <label className="route-check route-check-inline">
            <input
              checked={includeMemoryInPlan && canUseMemory}
              disabled={!canUseMemory}
              type="checkbox"
              onChange={(event) => setIncludeMemoryInPlan(event.target.checked)}
            />
            <span>Use opted-in career memory</span>
          </label>
          <button
            className="secondary-button"
            disabled={planState.loading}
            type="button"
            onClick={generatePlan}
          >
            {planState.loading ? "Planning" : "Generate action plan"}
          </button>
        </div>

        <div className="career-agent-tool-controls">
          <label>
            Tool preview
            <select
              value={toolType}
              onChange={(event) => setToolType(event.target.value as CareerAgentToolType)}
            >
              {TOOL_TYPES.map((type) => (
                <option key={type} value={type}>
                  {displayLabel(type)}
                </option>
              ))}
            </select>
          </label>
          <button
            className="secondary-button"
            disabled={!canUseMemory || toolState.loading}
            type="button"
            onClick={createToolPreview}
          >
            {toolState.loading ? "Preparing" : "Preview tool action"}
          </button>
          <p className="meta-copy">
            Tool actions are protected previews. Approval records intent only unless a real backend runtime exists.
          </p>
        </div>
      </section>

      {state.error ? (
        <section className="error-state">
          <strong>Career agent unavailable</strong>
          <p>{state.error}</p>
        </section>
      ) : null}

      {answer ? <CareerAgentAnswerPanel answer={answer} /> : null}
      {planState.error ? (
        <section className="error-state">
          <strong>Action plan unavailable</strong>
          <p>{planState.error}</p>
        </section>
      ) : null}
      {plan ? <CareerActionPlanPanel plan={plan} /> : null}
      {toolState.error ? (
        <section className="error-state">
          <strong>Tool preview unavailable</strong>
          <p>{toolState.error}</p>
        </section>
      ) : null}
      {toolPreview ? (
        <CareerAgentToolPanel
          approveTool={approveTool}
          execution={toolState.executionEnvelope?.data ?? null}
          loading={toolState.loading}
          preview={toolPreview}
          rejectTool={rejectTool}
        />
      ) : null}
      <CareerMemoryPanel
        authenticated={canUseMemory}
        clearMemory={clearMemory}
        loading={memoryState.loading}
        memoryForm={memoryForm}
        memoryProfile={memoryProfile}
        saveMemory={saveMemory}
        setMemoryForm={setMemoryForm}
        error={memoryState.error}
      />
    </div>
  );
}

function CareerAgentToolPanel({
  approveTool,
  execution,
  loading,
  preview,
  rejectTool,
}: {
  approveTool: () => void;
  execution: CareerAgentToolExecution | null;
  loading: boolean;
  preview: CareerAgentToolPreview;
  rejectTool: () => void;
}) {
  const approvalRequired = preview.approval_requirement.approval_required;
  const canTransition = approvalRequired && preview.status === "awaiting_user_approval";
  return (
    <section className="card career-agent-tool-panel">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Tool preview</p>
          <h2>{displayLabel(preview.tool_type)}</h2>
        </div>
        <span className={`badge badge-${preview.status === "blocked" ? "error" : "success"}`}>
          {displayLabel(preview.status)}
        </span>
      </div>
      <p className="lead-copy">{preview.proposed_action_summary}</p>
      <div className="career-agent-meta-grid">
        <MetaTile label="Approval" value={approvalRequired ? "Required" : "Not required"} />
        <MetaTile label="Privacy" value={displayLabel(preview.privacy_classification)} />
        <MetaTile label="Boundary" value={displayLabel(preview.action_boundary)} />
        <MetaTile label="Freshness" value={displayLabel(preview.freshness.freshness_status)} />
        <MetaTile label="Confidence" value={displayLabel(preview.uncertainty.confidence_level)} />
        <MetaTile label="Runtime" value={preview.runtime_execution_performed ? "Executed" : "No runtime execution"} />
      </div>

      <section className="route-section">
        <h3>Approval gate</h3>
        <p className="meta-copy">{preview.approval_requirement.reason}</p>
        <div className="badge-stack">
          <span className="badge">
            Explicit approval: {String(preview.approval_requirement.explicit_user_approval_required)}
          </span>
          <span className="badge">
            Runtime available: {String(preview.approval_requirement.runtime_execution_available)}
          </span>
        </div>
        {approvalRequired ? (
          <div className="career-agent-tool-actions">
            <button
              className="primary-button"
              disabled={!canTransition || loading}
              type="button"
              onClick={approveTool}
            >
              {loading ? "Recording" : preview.approval_requirement.approval_button_label ?? "Approve"}
            </button>
            <button
              className="text-button danger-text"
              disabled={!canTransition || loading}
              type="button"
              onClick={rejectTool}
            >
              Reject
            </button>
          </div>
        ) : null}
      </section>

      <ToolPreviewContent preview={preview} />

      <section className="route-section">
        <h3>Evidence refs</h3>
        <div className="career-agent-evidence-list">
          {preview.evidence_refs.map((ref) => (
            <EvidenceRow key={ref.ref_id} evidenceRef={ref} />
          ))}
        </div>
      </section>

      {preview.warnings.length || preview.uncertainty.limitations.length ? (
        <section className="route-section">
          <h3>Warnings / uncertainty</h3>
          <ul className="warning-list">
            {[...preview.warnings, ...preview.uncertainty.limitations].map((warning, index) => (
              <li className="warning-item" key={`preview-warning-${index}-${warning}`}>
                {warning}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {execution ? (
        <section className="notice-state">
          <strong>{displayLabel(execution.status)}</strong>
          <p>{execution.summary}</p>
          <p className="meta-copy">
            Runtime execution performed: {String(execution.runtime_execution_performed)}
          </p>
          {execution.warnings.length ? (
            <ul className="warning-list">
              {execution.warnings.map((warning) => (
                <li className="warning-item" key={warning}>
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function ToolPreviewContent({ preview }: { preview: CareerAgentToolPreview }) {
  const payload = redactedPreviewPayload(preview.user_visible_preview);
  const draftBody = stringValue(payload.draft_body);
  const exportPayload = recordValue(payload.public_export_payload);
  const checklistItems = stringArrayValue(payload.checklist_items);
  const suggestions = arrayValue(payload.suggestions);
  const rules = arrayValue(payload.rules);
  const blockedReason = stringValue(payload.reason);

  return (
    <section className="route-section">
      <h3>User-visible preview</h3>
      {blockedReason ? (
        <div className="error-state career-agent-tool-blocked">
          <strong>Blocked autonomous application</strong>
          <p>{blockedReason}</p>
        </div>
      ) : null}
      {draftBody ? (
        <div className="career-agent-preview-block">
          <strong>{stringValue(payload.draft_subject) ?? "Outreach draft"}</strong>
          <p className="career-agent-draft-body">{draftBody}</p>
          <span className="badge">Send enabled: {String(Boolean(payload.send_enabled))}</span>
        </div>
      ) : null}
      {exportPayload ? (
        <div className="career-agent-preview-block">
          <strong>Export-safe payload</strong>
          <PreviewRecord value={exportPayload} />
          {"private_memory_payload" in preview.user_visible_preview ? (
            <p className="meta-copy">Private memory is redacted from this public-safe preview.</p>
          ) : null}
        </div>
      ) : null}
      {checklistItems.length ? (
        <ul className="route-next-steps">
          {checklistItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {suggestions.length ? (
        <PreviewArray title="Watchlist suggestions" values={suggestions} />
      ) : null}
      {rules.length ? <PreviewArray title="Notification rules" values={rules} /> : null}
      {!blockedReason && !draftBody && !exportPayload && !checklistItems.length && !suggestions.length && !rules.length ? (
        <PreviewRecord value={payload} />
      ) : null}
    </section>
  );
}

function PreviewArray({ title, values }: { title: string; values: unknown[] }) {
  return (
    <div className="career-agent-preview-block">
      <strong>{title}</strong>
      {values.map((value, index) => (
        <PreviewRecord key={`${title}-${index}`} value={recordValue(value) ?? { value }} />
      ))}
    </div>
  );
}

function PreviewRecord({ value }: { value: Record<string, unknown> }) {
  return (
    <div className="career-agent-preview-record">
      {Object.entries(redactedPreviewPayload(value)).map(([key, item]) => (
        <div key={key}>
          <span>{displayLabel(key)}</span>
          <strong>{previewDisplayValue(item)}</strong>
        </div>
      ))}
    </div>
  );
}

function redactedPreviewPayload(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !isPrivatePreviewKey(key))
      .map(([key, item]) => [key, redactPreviewValue(item)]),
  );
}

function redactPreviewValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => redactPreviewValue(item));
  }
  if (value && typeof value === "object") {
    return redactedPreviewPayload(value as Record<string, unknown>);
  }
  return value;
}

function isPrivatePreviewKey(key: string): boolean {
  return [
    "private_memory_payload",
    "private_metadata",
    "internal_review_notes",
    "unsafe_source_metadata",
  ].includes(key);
}

function previewDisplayValue(value: unknown): string {
  if (value === null || value === undefined) return "N/A";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringArrayValue(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function CareerAgentAnswerPanel({ answer }: { answer: CareerAgentAnswer }) {
  return (
    <>
      <section className="notice-state career-agent-summary">
        <strong>{displayLabel(answer.question_type)}</strong>
        <p>{answer.summary}</p>
        <div className="career-agent-meta-grid">
          <MetaTile label="Freshness" value={displayLabel(answer.freshness.freshness_status)} />
          <MetaTile label="Sources" value={String(answer.freshness.source_count)} />
          <MetaTile label="Confidence" value={displayLabel(answer.uncertainty.confidence_level)} />
          <MetaTile label="Uncertainty" value={displayLabel(answer.uncertainty.uncertainty_level)} />
        </div>
      </section>

      <section className="route-card-list career-agent-recommendations" aria-label="Career Agent Recommendations">
        {answer.recommendations.map((recommendation) => (
          <CareerAgentRecommendationCard
            key={recommendation.recommendation_id}
            recommendation={recommendation}
          />
        ))}
        {answer.recommendations.length === 0 ? (
          <div className="empty-state">
            <strong>No grounded recommendations</strong>
            <p>{answer.limitations.join(" ")}</p>
          </div>
        ) : null}
      </section>

      <section className="card career-agent-guardrails">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Guardrails</p>
            <h2>Evidence Status</h2>
          </div>
          <span className={`badge badge-${answer.guardrails.passed ? "success" : "error"}`}>
            {answer.guardrails.passed ? "Passed" : "Blocked"}
          </span>
        </div>
        <div className="badge-stack">
          <span className="badge">Evidence refs: {String(answer.guardrails.evidence_requirement_met)}</span>
          <span className="badge">Openings blocked: {String(answer.guardrails.fabricated_openings_blocked)}</span>
          <span className="badge">Preferences excluded: {String(answer.guardrails.preferences_excluded_from_evidence)}</span>
          <span className="badge">Forecasts bounded: {String(answer.guardrails.forecast_claims_bounded)}</span>
          <span className="badge">Private fields redacted: {String(answer.guardrails.private_fields_redacted)}</span>
        </div>
        {answer.limitations.length || answer.guardrails.warnings.length ? (
          <ul className="warning-list career-agent-warning-list">
            {[...answer.limitations, ...answer.guardrails.warnings].map((warning, index) => (
              <li className="warning-item" key={`answer-warning-${index}-${warning}`}>
                {warning}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </>
  );
}

function CareerActionPlanPanel({ plan }: { plan: CareerActionPlan }) {
  return (
    <section className="card career-agent-plan-panel">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Action plan</p>
          <h2>{displayLabel(plan.plan_type)}</h2>
        </div>
        <span className="badge">{plan.time_window.start_date} to {plan.time_window.end_date}</span>
      </div>
      <p className="lead-copy">{plan.summary}</p>
      <div className="career-agent-meta-grid">
        <MetaTile label="Freshness" value={displayLabel(plan.freshness.freshness_status)} />
        <MetaTile label="Confidence" value={displayLabel(plan.uncertainty.confidence_level)} />
        <MetaTile label="Uncertainty" value={displayLabel(plan.uncertainty.uncertainty_level)} />
        <MetaTile label="Evidence refs" value={String(plan.evidence_refs.length)} />
      </div>

      {plan.memory_personalization.length ? (
        <div className="badge-stack">
          {plan.memory_personalization.map((item) => (
            <span className="badge" key={item}>
              {item}
            </span>
          ))}
        </div>
      ) : null}

      <div className="career-agent-plan-steps">
        {plan.steps.map((step) => (
          <CareerPlanStepCard key={step.step_id} step={step} />
        ))}
      </div>

      {plan.warnings.length || plan.risks.length ? (
        <section className="route-section">
          <h3>Warnings / risks</h3>
          <ul className="warning-list">
            {plan.warnings.map((warning) => (
              <li className="warning-item" key={warning}>
                {warning}
              </li>
            ))}
            {plan.risks.map((risk) => (
              <li className="warning-item" key={risk.risk_id}>
                {displayLabel(risk.severity)} risk: {risk.summary} {risk.mitigation}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

function CareerPlanStepCard({ step }: { step: CareerPlanStep }) {
  return (
    <article className="career-agent-plan-step">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Step {step.rank}</p>
          <h3>{step.title}</h3>
        </div>
        <span className="badge">{displayLabel(step.action_owner)}</span>
      </div>
      <p>{step.description}</p>
      <div className="career-agent-meta-grid">
        <MetaTile label="Milestone" value={step.milestone.summary} />
        <MetaTile label="Freshness" value={displayLabel(step.freshness.freshness_status)} />
        <MetaTile label="Confidence" value={displayLabel(step.uncertainty.confidence_level)} />
        <MetaTile label="Evidence refs" value={String(step.evidence_refs.length)} />
      </div>
      <p className="meta-copy">{step.milestone.outcome}</p>

      <section className="route-section">
        <h3>Evidence refs</h3>
        <div className="career-agent-evidence-list">
          {step.evidence_refs.map((ref) => (
            <EvidenceRow key={ref.ref_id} evidenceRef={ref} />
          ))}
        </div>
      </section>

      {step.warnings.length || step.risks.length ? (
        <section className="route-section">
          <h3>Warnings / uncertainty</h3>
          <ul className="warning-list">
            {step.warnings.map((warning) => (
              <li className="warning-item" key={warning}>
                {warning}
              </li>
            ))}
            {step.risks.map((risk) => (
              <li className="warning-item" key={risk.risk_id}>
                {displayLabel(risk.severity)} risk: {risk.summary}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

function CareerMemoryPanel({
  authenticated,
  clearMemory,
  error,
  loading,
  memoryForm,
  memoryProfile,
  saveMemory,
  setMemoryForm,
}: {
  authenticated: boolean;
  clearMemory: () => void;
  error: string | null;
  loading: boolean;
  memoryForm: CareerMemoryFormState;
  memoryProfile: CareerMemoryProfile | null;
  saveMemory: () => void;
  setMemoryForm: Dispatch<SetStateAction<CareerMemoryFormState>>;
}) {
  return (
    <section className="card career-agent-memory-panel">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Career memory</p>
          <h2>Progress Memory</h2>
        </div>
        <span className={`badge badge-${memoryProfile?.memory_enabled ? "success" : "muted"}`}>
          {memoryProfile?.memory_enabled ? "Opted in" : "Off"}
        </span>
      </div>
      <p className="meta-copy">
        Memory is optional. Saved career context is private, user-provided, and never counted as market evidence.
      </p>
      {!authenticated ? (
        <p className="meta-copy">Sign in to save or clear career memory.</p>
      ) : null}
      {error ? <p className="error-copy">{error}</p> : null}
      <div className="career-agent-memory-grid">
        {MEMORY_CATEGORIES.map((category) => (
          <label key={category}>
            {displayLabel(category)}
            <input
              disabled={!authenticated || loading}
              value={memoryForm[category]}
              onChange={(event) =>
                setMemoryForm((current) => ({
                  ...current,
                  [category]: event.target.value,
                }))
              }
            />
          </label>
        ))}
      </div>
      <div className="career-agent-memory-actions">
        <button
          className="secondary-button"
          disabled={!authenticated || loading}
          type="button"
          onClick={saveMemory}
        >
          {loading ? "Saving" : "Save memory"}
        </button>
        <button
          className="text-button danger-text"
          disabled={!authenticated || loading || !memoryProfile?.memory_enabled}
          type="button"
          onClick={clearMemory}
        >
          Clear memory
        </button>
      </div>
      {memoryProfile?.entries.length ? (
        <div className="career-agent-memory-list">
          {memoryProfile.entries.map((entry) => (
            <span className="badge" key={entry.memory_entry_id}>
              {displayLabel(entry.category)}: {entry.value}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CareerAgentRecommendationCard({
  recommendation,
}: {
  recommendation: CareerAgentRecommendation;
}) {
  return (
    <article className="card opportunity-route-card career-agent-card">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Rank {recommendation.rank}</p>
          <h2>{recommendation.title}</h2>
        </div>
        <div className="route-score-pill">
          <span>{recommendation.score === null ? "N/A" : formatPercent(recommendation.score)}</span>
          <small>{displayLabel(recommendation.uncertainty.confidence_level)} confidence</small>
        </div>
      </div>

      <p className="lead-copy">{recommendation.summary}</p>
      {recommendation.action ? <p>{recommendation.action}</p> : null}

      <div className="career-agent-meta-grid">
        <MetaTile label="Freshness" value={displayLabel(recommendation.freshness.freshness_status)} />
        <MetaTile label="Sources" value={String(recommendation.freshness.source_count)} />
        <MetaTile label="Uncertainty" value={displayLabel(recommendation.uncertainty.uncertainty_level)} />
      </div>

      {recommendation.preference_alignment.length ? (
        <section className="route-section">
          <h3>Preference alignment</h3>
          <div className="badge-stack">
            {recommendation.preference_alignment.map((item) => (
              <span className="badge" key={item}>
                {item}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="route-section">
        <h3>Evidence refs</h3>
        <div className="career-agent-evidence-list">
          {recommendation.evidence_refs.map((ref) => (
            <EvidenceRow key={ref.ref_id} evidenceRef={ref} />
          ))}
        </div>
      </section>

      {recommendation.warnings.length || recommendation.limitations.length ? (
        <section className="route-section">
          <h3>Warnings / limitations</h3>
          <ul className="warning-list">
            {[...recommendation.warnings, ...recommendation.limitations].map((warning, index) => (
              <li className="warning-item" key={`recommendation-warning-${index}-${warning}`}>
                {warning}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

function MetaTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="score-card score-card-compact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EvidenceRow({ evidenceRef }: { evidenceRef: CareerAgentEvidenceRef }) {
  return (
    <div className="career-agent-evidence-row">
      <div>
        <strong>{evidenceRef.label}</strong>
        <span>
          {displayLabel(evidenceRef.evidence_type)} · {displayLabel(evidenceRef.freshness_status)}
          {evidenceRef.confidence_label ? ` · ${displayLabel(evidenceRef.confidence_label)}` : ""}
        </span>
        <p>{evidenceRef.summary}</p>
      </div>
      {evidenceRef.public_url ? <a href={evidenceRef.public_url}>Source</a> : null}
    </div>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function displayLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}
