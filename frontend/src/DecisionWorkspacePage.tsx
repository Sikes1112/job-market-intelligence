import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  addCareerDecisionOption,
  ApiError,
  compareCareerDecision,
  createCareerActionPlan,
  createCareerApplication,
  createCareerDecision,
  createCareerOutcome,
  createSupportCase,
  generateDeepDecisionAnalysis,
  getCareerDecision,
  getCareerDecisionJournal,
  getCareerIdentity,
  getLatestDeepDecisionAnalysis,
  getMyBetaAccess,
  getMyFeatureAccess,
  getWeeklyCareerReview,
  listCareerDecisions,
  listStrategicCareerReviews,
  recordCommercialExperimentSignal,
  recordDecisionReflection,
  recordProductEvent,
  recordStrategyChange,
  reopenCareerDecision,
  selectCareerDecisionOption,
  submitRecommendationFeedback,
  transitionCareerApplication,
  updateCareerAction,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import type {
  CareerAction,
  CareerActionStatus,
  CareerApplication,
  CareerApplicationStatus,
  CareerDecision,
  CareerDecisionConstraintInput,
  CareerDecisionCreateInput,
  CareerDecisionOption,
  CareerDecisionType,
  CareerDecisionVersion,
  CareerIdentity,
  CareerOutcomeType,
  BetaAccessPayload,
  DeepDecisionAnalysis,
  FeatureAccessDecision,
  DecisionChallenge,
  DecisionFactor,
  DecisionFitOption,
  DecisionRecommendation,
  SupportCaseType,
  StrategicCareerReview,
  WeeklyCareerReview,
} from "./types";

const DECISION_TYPES: Array<{ value: CareerDecisionType; label: string }> = [
  { value: "career_path", label: "Career path" },
  { value: "role_choice", label: "Role choice" },
  { value: "company_choice", label: "Company choice" },
  { value: "location_choice", label: "Location choice" },
  { value: "job_search_strategy", label: "Job search strategy" },
  { value: "education_skill_investment", label: "Education or skill investment" },
  { value: "offer_comparison", label: "Offer comparison" },
  { value: "career_strategy", label: "Career strategy" },
];

const ACTION_STATUSES: CareerActionStatus[] = ["open", "in_progress", "completed", "blocked", "skipped"];
const APPLICATION_STATUSES: CareerApplicationStatus[] = [
  "considering",
  "preparing",
  "applied",
  "response",
  "interview",
  "final_round",
  "rejected",
  "withdrawn",
  "offer",
  "accepted",
  "declined",
];
const OUTCOME_TYPES: CareerOutcomeType[] = [
  "application_progress",
  "offer",
  "rejection",
  "withdrawal",
  "skill_development",
  "research_completed",
  "networking",
  "strategy_change",
  "education",
  "decision_completed",
  "other",
];

const APPLICATION_TRANSITIONS: Record<CareerApplicationStatus, CareerApplicationStatus[]> = {
  considering: ["preparing", "applied", "withdrawn"],
  preparing: ["applied", "withdrawn"],
  applied: ["response", "interview", "rejected", "withdrawn", "offer"],
  response: ["interview", "rejected", "withdrawn"],
  interview: ["final_round", "rejected", "withdrawn", "offer"],
  final_round: ["offer", "rejected", "withdrawn"],
  rejected: [],
  withdrawn: [],
  offer: ["accepted", "declined", "withdrawn"],
  accepted: [],
  declined: [],
};

type DecisionWorkspacePageProps = {
  auth: FrontendAuthContextValue;
  onOpenCareerIdentity?: () => void;
  onOpenExploreComparison?: (comparisonId: string) => void;
};

type CreateDecisionDraft = {
  decisionType: CareerDecisionType;
  title: string;
  description: string;
  timeHorizon: string;
  targetDate: string;
  plannedReviewAt: string;
  priorities: string;
  hardConstraints: string;
  minimumCompensation: string;
};

type OptionDraft = {
  title: string;
  description: string;
  roleFocus: string;
  companyIds: string;
  regions: string;
  industries: string;
  workArrangement: string;
  compensationTarget: string;
  baseSalary: string;
  totalCompensation: string;
  compensationSource: string;
  benefits: string;
  companyProfile: string;
  targetSkills: string;
  educationType: string;
  educationCost: string;
  durationMonths: string;
  skillsTaught: string;
  relocationRequired: boolean;
  costOfLivingIndex: string;
};

type ApplicationDraft = {
  roleTitle: string;
  companyId: string;
  regionId: string;
  optionId: string;
  actionId: string;
  status: CareerApplicationStatus;
  followUpAt: string;
  notes: string;
};

type OutcomeDraft = {
  title: string;
  outcomeType: CareerOutcomeType;
  applicationId: string;
  actionId: string;
  optionId: string;
  reflection: string;
};

type FeedbackDraft = {
  useful: "yes" | "no";
  surprising: boolean;
  changedDecision: boolean;
  missingAlternative: boolean;
  missingAlternativeCategory: string;
  confidenceCalibration: "too_high" | "too_low" | "about_right" | "unsure";
  comment: string;
};

type ReflectionDraft = {
  wouldMakeSameDecision: "yes" | "no" | "unsure" | "not_applicable";
  viewChanged: boolean;
  satisfactionRating: string;
  regretLevel: "none" | "low" | "medium" | "high" | "unsure";
  comment: string;
};

type StrategyDraft = {
  changeType: "target_role" | "geography" | "company_strategy" | "opportunity_type" | "application_strategy" | "other";
  previousValue: string;
  newValue: string;
  reasonCategory: string;
  note: string;
};

type SupportDraft = {
  caseType: SupportCaseType;
  title: string;
  description: string;
};

function emptyDecisionDraft(): CreateDecisionDraft {
  return {
    decisionType: "career_path",
    title: "",
    description: "",
    timeHorizon: "",
    targetDate: "",
    plannedReviewAt: "",
    priorities: "",
    hardConstraints: "",
    minimumCompensation: "",
  };
}

function emptyOptionDraft(): OptionDraft {
  return {
    title: "",
    description: "",
    roleFocus: "",
    companyIds: "",
    regions: "",
    industries: "",
    workArrangement: "",
    compensationTarget: "",
    baseSalary: "",
    totalCompensation: "",
    compensationSource: "",
    benefits: "",
    companyProfile: "",
    targetSkills: "",
    educationType: "",
    educationCost: "",
    durationMonths: "",
    skillsTaught: "",
    relocationRequired: false,
    costOfLivingIndex: "",
  };
}

function emptyApplicationDraft(): ApplicationDraft {
  return {
    roleTitle: "",
    companyId: "",
    regionId: "",
    optionId: "",
    actionId: "",
    status: "applied",
    followUpAt: "",
    notes: "",
  };
}

function emptyOutcomeDraft(): OutcomeDraft {
  return {
    title: "",
    outcomeType: "application_progress",
    applicationId: "",
    actionId: "",
    optionId: "",
    reflection: "",
  };
}

function emptyFeedbackDraft(): FeedbackDraft {
  return {
    useful: "yes",
    surprising: false,
    changedDecision: false,
    missingAlternative: false,
    missingAlternativeCategory: "",
    confidenceCalibration: "about_right",
    comment: "",
  };
}

function emptyReflectionDraft(): ReflectionDraft {
  return {
    wouldMakeSameDecision: "unsure",
    viewChanged: false,
    satisfactionRating: "",
    regretLevel: "unsure",
    comment: "",
  };
}

function emptyStrategyDraft(): StrategyDraft {
  return {
    changeType: "target_role",
    previousValue: "",
    newValue: "",
    reasonCategory: "",
    note: "",
  };
}

function emptySupportDraft(): SupportDraft {
  return {
    caseType: "recommendation_issue",
    title: "",
    description: "",
  };
}

function label(value: string | null | undefined): string {
  if (!value) return "Not set";
  if (value === "region_ids") return "Markets";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateInputToIso(value: string): string | null {
  return value ? `${value}T00:00:00Z` : null;
}

function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function truthyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function compactDate(value: string | null | undefined): string {
  if (!value) return "No date";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function isOverdue(value: string | null | undefined): boolean {
  if (!value) return false;
  const due = new Date(value).getTime();
  if (!Number.isFinite(due)) return false;
  return due < Date.now();
}

function itemTitle(item: Record<string, unknown>): string {
  return truthyString(item.title)
    ?? truthyString(item.label)
    ?? truthyString(item.message)
    ?? truthyString(item.reference_type)
    ?? truthyString(item.type)
    ?? truthyString(item.kind)
    ?? "Recorded item";
}

function readableEvidenceLabel(value: string): string {
  return value.includes("_") && !value.includes(" ") ? label(value) : value;
}

function itemBody(item: Record<string, unknown>): string | null {
  return truthyString(item.message)
    ?? truthyString(item.description)
    ?? truthyString(item.reason)
    ?? truthyString(item.note)
    ?? null;
}

export default function DecisionWorkspacePage({
  auth,
  onOpenCareerIdentity,
  onOpenExploreComparison,
}: DecisionWorkspacePageProps) {
  const protectedOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );
  const [identity, setIdentity] = useState<CareerIdentity | null>(null);
  const [decisions, setDecisions] = useState<CareerDecision[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [decision, setDecision] = useState<CareerDecision | null>(null);
  const [journal, setJournal] = useState<CareerDecisionVersion[]>([]);
  const [deepAnalysis, setDeepAnalysis] = useState<DeepDecisionAnalysis | null>(null);
  const [strategicReviews, setStrategicReviews] = useState<StrategicCareerReview[]>([]);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyCareerReview | null>(null);
  const [betaAccess, setBetaAccess] = useState<BetaAccessPayload | null>(null);
  const [decisionFeedbackAccess, setDecisionFeedbackAccess] = useState<FeatureAccessDecision | null>(null);
  const [loading, setLoading] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [decisionDraft, setDecisionDraft] = useState<CreateDecisionDraft>(emptyDecisionDraft);
  const [optionDraft, setOptionDraft] = useState<OptionDraft>(() => emptyOptionDraft());
  const [selectionNote, setSelectionNote] = useState("");
  const [applicationDraft, setApplicationDraft] = useState<ApplicationDraft>(emptyApplicationDraft);
  const [outcomeDraft, setOutcomeDraft] = useState<OutcomeDraft>(emptyOutcomeDraft);
  const [feedbackDraft, setFeedbackDraft] = useState<FeedbackDraft>(emptyFeedbackDraft);
  const [reflectionDraft, setReflectionDraft] = useState<ReflectionDraft>(emptyReflectionDraft);
  const [strategyDraft, setStrategyDraft] = useState<StrategyDraft>(emptyStrategyDraft);
  const [supportDraft, setSupportDraft] = useState<SupportDraft>(emptySupportDraft);
  const [viewedRecommendationIds, setViewedRecommendationIds] = useState<Set<string>>(() => new Set());

  const selected = decision ?? decisions.find((item) => item.decision_id === selectedDecisionId) ?? decisions[0] ?? null;
  const recommendedOption = selected?.recommendation
    ? selected.options.find((option) => option.option_id === selected.recommendation?.recommended_option_id) ?? null
    : null;
  const selectedOption = selected?.selected_option_id
    ? selected.options.find((option) => option.option_id === selected.selected_option_id) ?? null
    : null;

  const loadDeepDecisionState = useCallback(async (decisionId: string) => {
    setDeepLoading(true);
    setDeepError(null);
    try {
      const [analysisEnvelope, reviewsEnvelope] = await Promise.all([
        getLatestDeepDecisionAnalysis(decisionId, protectedOptions),
        listStrategicCareerReviews(protectedOptions, { decisionId, limit: 10 }),
      ]);
      setDeepAnalysis(analysisEnvelope.data?.analysis ?? null);
      setStrategicReviews(reviewsEnvelope.data?.strategic_reviews ?? []);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.statusCode === 404) {
        setDeepAnalysis(null);
        setStrategicReviews([]);
      } else {
        setDeepError(errorMessage(loadError, "Deep advisor analysis could not load."));
      }
    } finally {
      setDeepLoading(false);
    }
  }, [protectedOptions]);

  const refreshDecision = useCallback(async (decisionId: string) => {
    const [decisionEnvelope, journalEnvelope] = await Promise.all([
      getCareerDecision(decisionId, protectedOptions),
      getCareerDecisionJournal(decisionId, protectedOptions),
    ]);
    const nextDecision = decisionEnvelope.data?.decision ?? null;
    setDecision(nextDecision);
    if (nextDecision) {
      setDecisions((items) => {
        const index = items.findIndex((item) => item.decision_id === nextDecision.decision_id);
        if (index < 0) return [nextDecision, ...items];
        return items.map((item) => item.decision_id === nextDecision.decision_id ? nextDecision : item);
      });
    }
    setSelectedDecisionId(nextDecision?.decision_id ?? decisionId);
    setJournal(journalEnvelope.data?.journal ?? []);
    await loadDeepDecisionState(nextDecision?.decision_id ?? decisionId);
    return nextDecision;
  }, [loadDeepDecisionState, protectedOptions]);

  const loadWorkspace = useCallback(async () => {
    if (!auth.isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const [identityEnvelope, decisionsEnvelope, reviewEnvelope] = await Promise.all([
        getCareerIdentity(protectedOptions),
        listCareerDecisions(protectedOptions),
        getWeeklyCareerReview(protectedOptions),
      ]);
      const nextDecisions = decisionsEnvelope.data?.decisions ?? [];
      setIdentity(identityEnvelope.data ?? null);
      setDecisions(nextDecisions);
      setWeeklyReview(reviewEnvelope.data?.review ?? null);
      const nextSelected = selectedDecisionId
        ? nextDecisions.find((item) => item.decision_id === selectedDecisionId)
        : nextDecisions[0];
      if (nextSelected) {
        await refreshDecision(nextSelected.decision_id);
      } else {
        setDecision(null);
        setSelectedDecisionId(null);
        setJournal([]);
        setDeepAnalysis(null);
        setStrategicReviews([]);
      }
    } catch (loadError) {
      setError(errorMessage(loadError, "Decision Workspace could not load."));
    } finally {
      setLoading(false);
    }
  }, [auth.isAuthenticated, protectedOptions, refreshDecision, selectedDecisionId]);

  const loadBetaAccess = useCallback(async () => {
    if (!auth.isAuthenticated) return;
    try {
      const [betaEnvelope, featureEnvelope] = await Promise.all([
        getMyBetaAccess(protectedOptions),
        getMyFeatureAccess("decision_feedback", protectedOptions),
      ]);
      setBetaAccess(betaEnvelope.data ?? null);
      setDecisionFeedbackAccess(featureEnvelope.data?.decision ?? null);
    } catch {
      setBetaAccess(null);
      setDecisionFeedbackAccess(null);
    }
  }, [auth.isAuthenticated, protectedOptions]);

  useEffect(() => {
    void loadWorkspace();
    void loadBetaAccess();
  }, [loadBetaAccess, loadWorkspace]);

  useEffect(() => {
    const recommendation = selected?.recommendation;
    if (!auth.isAuthenticated || !recommendation || viewedRecommendationIds.has(recommendation.recommendation_id)) {
      return;
    }
    setViewedRecommendationIds((previous) => {
      if (previous.has(recommendation.recommendation_id)) return previous;
      const next = new Set(previous);
      next.add(recommendation.recommendation_id);
      return next;
    });
    const cohortKey = betaAccess?.cohorts[0]?.cohort_key ?? null;
    const baseEvent = {
      event_source: "frontend" as const,
      product_surface: "decision_workspace",
      decision_id: selected.decision_id,
      recommendation_id: recommendation.recommendation_id,
      cohort_key: cohortKey,
      confidence_bucket: recommendation.confidence,
      coverage_status: recommendation.evidence_sufficiency,
      recommendation_state: recommendation.recommendation_status,
    };
    const events = [
      recordProductEvent({
        ...baseEvent,
        event_type: "recommendation_viewed",
        payload: {
          recommended_option_present: recommendation.recommended_option_id !== null,
          option_count: selected.options.length,
        },
      }, protectedOptions),
      recordProductEvent({
        ...baseEvent,
        event_type: "trust_explanation_viewed",
        payload: {
          confidence_bucket: recommendation.confidence,
          evidence_sufficiency: recommendation.evidence_sufficiency,
          challenge_count: recommendation.challenges.length,
        },
      }, protectedOptions),
    ];
    if (
      recommendation.limitations.length
      || recommendation.evidence_sufficiency !== "comparison_ready"
      || recommendation.confidence === "low"
      || recommendation.confidence === "unknown"
    ) {
      events.push(recordProductEvent({
        ...baseEvent,
        event_type: "coverage_limitation_viewed",
        payload: {
          limitation_count: recommendation.limitations.length,
          evidence_sufficiency: recommendation.evidence_sufficiency,
          confidence_bucket: recommendation.confidence,
        },
      }, protectedOptions));
    }
    void Promise.all(events).catch(() => undefined);
  }, [
    auth.isAuthenticated,
    betaAccess?.cohorts,
    protectedOptions,
    selected?.decision_id,
    selected?.options.length,
    selected?.recommendation,
    viewedRecommendationIds,
  ]);

  async function mutate(work: () => Promise<void>, success: string) {
    setSaving(true);
    setActionError(null);
    setMessage(null);
    try {
      await work();
      setMessage(success);
    } catch (mutationError) {
      setActionError(errorMessage(mutationError, "Decision Workspace action failed."));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateDecision(event: FormEvent) {
    event.preventDefault();
    const priorities = commaList(decisionDraft.priorities).map((priority, index) => ({
      key: priority.toLowerCase().replaceAll(" ", "_"),
      label: priority,
      weight: Math.max(1, 5 - index),
      hard: false,
    }));
    const constraints: CareerDecisionConstraintInput[] = commaList(decisionDraft.hardConstraints).map((constraint) => ({
      key: constraint.toLowerCase().replaceAll(" ", "_"),
      field: "scenario",
      operator: "contains",
      value: constraint,
      hard: true,
      label: constraint,
    }));
    if (decisionDraft.minimumCompensation) {
      constraints.push({
        key: "minimum_compensation",
        field: "compensation_min",
        operator: "gte",
        value: Number(decisionDraft.minimumCompensation),
        hard: true,
        label: "Minimum compensation",
      });
    }
    const body: CareerDecisionCreateInput = {
      decision_type: decisionDraft.decisionType,
      title: decisionDraft.title,
      description: decisionDraft.description || null,
      time_horizon: decisionDraft.timeHorizon || null,
      target_date: dateInputToIso(decisionDraft.targetDate),
      planned_review_at: dateInputToIso(decisionDraft.plannedReviewAt),
      priorities,
      constraints,
      options: [],
    };
    await mutate(async () => {
      const envelope = await createCareerDecision(body, protectedOptions);
      const created = envelope.data?.decision;
      if (!created) return;
      setDecisionDraft(emptyDecisionDraft());
      setSelectedDecisionId(created.decision_id);
      await loadWorkspace();
      await refreshDecision(created.decision_id);
    }, "Decision created.");
  }

  async function handleAddOption(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    const scenario: Record<string, unknown> = {
      role_focus: optionDraft.roleFocus || undefined,
      roles: commaList(optionDraft.roleFocus),
      company_ids: commaList(optionDraft.companyIds),
      region_ids: commaList(optionDraft.regions),
      industries: commaList(optionDraft.industries),
      work_arrangement: optionDraft.workArrangement || undefined,
      compensation_target: optionDraft.compensationTarget || undefined,
      base_salary: optionDraft.baseSalary || undefined,
      total_compensation: optionDraft.totalCompensation || undefined,
      compensation_source: optionDraft.compensationSource || undefined,
      benefits: optionDraft.benefits || undefined,
      company_profile: optionDraft.companyProfile || undefined,
      required_skills: commaList(optionDraft.targetSkills),
      education_type: optionDraft.educationType || undefined,
      education_cost: optionDraft.educationCost || undefined,
      duration_months: optionDraft.durationMonths || undefined,
      skills_taught: commaList(optionDraft.skillsTaught),
      relocation_required: optionDraft.relocationRequired || undefined,
      cost_of_living_index: optionDraft.costOfLivingIndex || undefined,
    };
    await mutate(async () => {
      const envelope = await addCareerDecisionOption(selected.decision_id, {
        title: optionDraft.title,
        description: optionDraft.description || null,
        position: selected.options.length,
        scenario: Object.fromEntries(Object.entries(scenario).filter(([, value]) => Array.isArray(value) ? value.length : value)),
      }, protectedOptions);
      const nextDecision = envelope.data?.decision;
      if (nextDecision) {
        setDecision(nextDecision);
        setDecisions((items) => items.map((item) => item.decision_id === nextDecision.decision_id ? nextDecision : item));
      }
      setOptionDraft(emptyOptionDraft());
    }, "Scenario option added.");
  }

  async function handleCompare() {
    if (!selected) return;
    await mutate(async () => {
      await compareCareerDecision(selected.decision_id, protectedOptions);
      await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      await refreshDecision(selected.decision_id);
    }, "Comparison refreshed.");
  }

  async function handleGenerateDeepAnalysis() {
    if (!selected) return;
    await mutate(async () => {
      const envelope = await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      setDeepAnalysis(envelope.data?.analysis ?? null);
      const reviewsEnvelope = await listStrategicCareerReviews(protectedOptions, {
        decisionId: selected.decision_id,
        limit: 10,
      });
      setStrategicReviews(reviewsEnvelope.data?.strategic_reviews ?? []);
    }, "Deep advisor analysis generated.");
  }

  async function handleSelectOption(optionId: string) {
    if (!selected) return;
    await mutate(async () => {
      await selectCareerDecisionOption(selected.decision_id, {
        option_id: optionId,
        user_note: selectionNote || null,
      }, protectedOptions);
      await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      setSelectionNote("");
      await refreshDecision(selected.decision_id);
    }, "Choice saved to the journal.");
  }

  async function handleReopen() {
    if (!selected) return;
    await mutate(async () => {
      await reopenCareerDecision(selected.decision_id, protectedOptions);
      setDeepAnalysis(null);
      setStrategicReviews([]);
      await refreshDecision(selected.decision_id);
      const identityEnvelope = await getCareerIdentity(protectedOptions);
      setIdentity(identityEnvelope.data ?? null);
    }, "Decision reopened for reconsideration.");
  }

  async function handleCreatePlan() {
    if (!selected) return;
    const selectedId = selected.selected_option_id;
    await mutate(async () => {
      await createCareerActionPlan(selected.decision_id, {
        title: `${selected.title} action plan`,
        actions: [
          {
            action_type: "research",
            title: "Validate the strongest unknowns",
            description: "Research the evidence gaps and assumptions surfaced in the comparison.",
            option_id: selectedId,
            priority: 1,
            position: 0,
          },
          {
            action_type: "application",
            title: "Prepare first application or outreach",
            description: "Turn the selected option into a concrete application, outreach, or next career move.",
            option_id: selectedId,
            priority: 2,
            position: 1,
          },
          {
            action_type: "review_task",
            title: "Review progress and reconsider if evidence changes",
            description: "Check whether the original assumptions still hold after initial action.",
            option_id: selectedId,
            priority: 3,
            position: 2,
          },
        ],
      }, protectedOptions);
      await refreshDecision(selected.decision_id);
    }, "Action plan created.");
  }

  async function handleUpdateAction(action: CareerAction, status: CareerActionStatus) {
    if (!selected) return;
    await mutate(async () => {
      await updateCareerAction(action.action_id, { status }, protectedOptions);
      await refreshDecision(selected.decision_id);
      const reviewEnvelope = await getWeeklyCareerReview(protectedOptions);
      setWeeklyReview(reviewEnvelope.data?.review ?? null);
    }, `Action marked ${label(status).toLowerCase()}.`);
  }

  async function handleCreateApplication(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate(async () => {
      await createCareerApplication({
        decision_id: selected.decision_id,
        action_id: applicationDraft.actionId || null,
        option_id: applicationDraft.optionId || selected.selected_option_id,
        company_id: applicationDraft.companyId || null,
        region_id: applicationDraft.regionId || null,
        role_title: applicationDraft.roleTitle || null,
        status: applicationDraft.status,
        follow_up_at: dateInputToIso(applicationDraft.followUpAt),
        notes: applicationDraft.notes || null,
      }, protectedOptions);
      await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      setApplicationDraft(emptyApplicationDraft());
      await refreshDecision(selected.decision_id);
    }, "Application state recorded.");
  }

  async function handleTransitionApplication(application: CareerApplication, toStatus: CareerApplicationStatus) {
    if (!selected || toStatus === application.status) return;
    await mutate(async () => {
      await transitionCareerApplication(application.application_id, { to_status: toStatus }, protectedOptions);
      await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      await refreshDecision(selected.decision_id);
      const reviewEnvelope = await getWeeklyCareerReview(protectedOptions);
      setWeeklyReview(reviewEnvelope.data?.review ?? null);
    }, `Application moved to ${label(toStatus).toLowerCase()}.`);
  }

  async function handleCreateOutcome(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate(async () => {
      await createCareerOutcome({
        decision_id: selected.decision_id,
        action_id: outcomeDraft.actionId || null,
        application_id: outcomeDraft.applicationId || null,
        option_id: outcomeDraft.optionId || selected.selected_option_id,
        recommendation_id: selected.current_recommendation_id,
        outcome_type: outcomeDraft.outcomeType,
        title: outcomeDraft.title,
        reflection: outcomeDraft.reflection || null,
      }, protectedOptions);
      await generateDeepDecisionAnalysis(selected.decision_id, {}, protectedOptions);
      setOutcomeDraft(emptyOutcomeDraft());
      await refreshDecision(selected.decision_id);
      const reviewEnvelope = await getWeeklyCareerReview(protectedOptions);
      setWeeklyReview(reviewEnvelope.data?.review ?? null);
    }, "Outcome recorded.");
  }

  async function handleSubmitFeedback(event: FormEvent) {
    event.preventDefault();
    if (!selected?.recommendation) return;
    await mutate(async () => {
      await submitRecommendationFeedback({
        decision_id: selected.decision_id,
        recommendation_id: selected.recommendation!.recommendation_id,
        useful: feedbackDraft.useful === "yes",
        surprising: feedbackDraft.surprising,
        changed_decision: feedbackDraft.changedDecision,
        missing_alternative: feedbackDraft.missingAlternative,
        missing_alternative_category: feedbackDraft.missingAlternativeCategory || null,
        confidence_calibration: feedbackDraft.confidenceCalibration,
        feedback_comment: feedbackDraft.comment || null,
        cohort_key: betaAccess?.cohorts[0]?.cohort_key ?? null,
      }, protectedOptions);
      setFeedbackDraft(emptyFeedbackDraft());
      await refreshDecision(selected.decision_id);
    }, "Recommendation feedback recorded.");
  }

  async function handleRecordReflection(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate(async () => {
      await recordDecisionReflection({
        decision_id: selected.decision_id,
        recommendation_id: selected.current_recommendation_id,
        outcome_id: selected.outcomes[0]?.outcome_id ?? null,
        would_make_same_decision: reflectionDraft.wouldMakeSameDecision,
        view_changed: reflectionDraft.viewChanged,
        satisfaction_rating: reflectionDraft.satisfactionRating ? Number(reflectionDraft.satisfactionRating) : null,
        regret_level: reflectionDraft.regretLevel,
        reflection_comment: reflectionDraft.comment || null,
      }, protectedOptions);
      setReflectionDraft(emptyReflectionDraft());
    }, "Decision reflection recorded.");
  }

  async function handleRecordStrategyChange(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate(async () => {
      await recordStrategyChange({
        decision_id: selected.decision_id,
        recommendation_id: selected.current_recommendation_id,
        change_type: strategyDraft.changeType,
        previous_state: strategyDraft.previousValue ? { value: strategyDraft.previousValue } : null,
        new_state: { value: strategyDraft.newValue },
        reason_category: strategyDraft.reasonCategory || null,
        note: strategyDraft.note || null,
      }, protectedOptions);
      setStrategyDraft(emptyStrategyDraft());
      const reviewEnvelope = await getWeeklyCareerReview(protectedOptions);
      setWeeklyReview(reviewEnvelope.data?.review ?? null);
    }, "Strategy change recorded.");
  }

  async function handleCreateSupportCase(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate(async () => {
      await createSupportCase({
        case_type: supportDraft.caseType,
        title: supportDraft.title,
        description: supportDraft.description || null,
        decision_id: selected.decision_id,
        recommendation_id: supportDraft.caseType === "recommendation_issue"
          ? selected.current_recommendation_id
          : null,
        subject_type: supportDraft.caseType === "bad_data" ? "decision_context" : null,
        subject_id: supportDraft.caseType === "bad_data" ? selected.current_context_snapshot_id : null,
        privacy_request_type: supportDraft.caseType === "privacy_issue" ? "user_data_request" : null,
      }, protectedOptions);
      setSupportDraft(emptySupportDraft());
    }, "Support case submitted.");
  }

  async function handleCommercialInterest(signalType: "interested" | "not_interested" | "learn_more") {
    await mutate(async () => {
      await recordCommercialExperimentSignal({
        experiment_key: "decision_workspace_offer_test",
        variant_key: "lightweight_offer_panel",
        offer_key: "one_time_decision_report",
        signal_type: signalType,
        product_surface: "decision_workspace",
      }, protectedOptions);
    }, "Commercial interest signal recorded.");
  }

  if (!auth.isAuthenticated) {
    return (
      <section className="decision-workspace">
        <header className="section-header">
          <div>
            <p className="eyebrow">Private career planning</p>
            <h2>Decision Workspace</h2>
          </div>
        </header>
        <div className="notice-state">
          <strong>Authentication required</strong>
          <p>Career decisions, actions, applications, and outcomes are private account data.</p>
          <button type="button" className="primary-button" onClick={() => void auth.login()}>
            Sign in
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="decision-workspace">
      <header className="decision-workspace-hero">
        <div>
          <p className="eyebrow">Decision</p>
          <h1>{selected?.title ?? "Compare a real career choice"}</h1>
          <p>{selected
            ? `${selected.options.length} alternatives · ${selectedOption ? `${selectedOption.title} selected` : "choice still open"} · ${selected.action_plan?.actions.length ?? 0} next actions`
            : "Compare alternatives and turn your choice into an action plan."}</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => void loadWorkspace()} disabled={loading}>
          Refresh
        </button>
      </header>

      {loading ? <LoadingBlock label="Loading Decision Workspace" /> : null}
      {error ? <ErrorBlock message={error} onRetry={loadWorkspace} /> : null}
      {message ? <div className="notice-state"><strong>{message}</strong></div> : null}
      {actionError ? (
        <ErrorBlock
          message={actionError}
          onRetry={selected ? async () => { await refreshDecision(selected.decision_id); } : loadWorkspace}
        />
      ) : null}

      <IdentityBridge identity={identity} decision={selected} onOpenCareerIdentity={onOpenCareerIdentity} />

      <div className="decision-workspace-grid">
        <aside className="decision-home-panel" aria-label="Career decisions">
          <h3>Decisions</h3>
          {decisions.length ? (
            <div className="decision-list">
              {decisions.map((item) => (
                <button
                  type="button"
                  className={item.decision_id === selected?.decision_id ? "decision-list-item decision-list-item-active" : "decision-list-item"}
                  key={item.decision_id}
                  onClick={() => void refreshDecision(item.decision_id)}
                >
                  <span>{item.title}</span>
                  <small>{label(item.status)} · {item.options.length} options · {item.action_plan?.actions.length ?? 0} actions</small>
                </button>
              ))}
            </div>
          ) : (
            <EmptyBlock
              title="No career decisions yet"
              body="Create a decision, add realistic options, and compare their trade-offs."
            />
          )}

          <details className="decision-disclosure">
            <summary>Start another decision</summary>
            <CreateDecisionForm
              draft={decisionDraft}
              saving={saving}
              setDraft={setDecisionDraft}
              onSubmit={handleCreateDecision}
            />
          </details>
        </aside>

        <div className="decision-flow">
          {selected ? (
            <>
              <DecisionSummary
                decision={selected}
                selectedOption={selectedOption}
                recommendedOption={recommendedOption}
                onOpenExploreComparison={onOpenExploreComparison}
              />
              <OptionBuilder
                decision={selected}
                draft={optionDraft}
                saving={saving}
                setDraft={setOptionDraft}
                onSubmit={handleAddOption}
              />
              <RecommendationSurface
                decision={selected}
                recommendedOption={recommendedOption}
                onCompare={handleCompare}
                saving={saving}
              />
              <SelectionPanel
                decision={selected}
                recommendedOption={recommendedOption}
                selectionNote={selectionNote}
                setSelectionNote={setSelectionNote}
                saving={saving}
                onSelect={handleSelectOption}
                onReopen={handleReopen}
              />
              <ActionPlanPanel
                decision={selected}
                saving={saving}
                onCreatePlan={handleCreatePlan}
                onUpdateAction={handleUpdateAction}
              />
              <details className="decision-disclosure"><summary>Decision history</summary><JournalPanel journal={journal} options={selected.options} /></details>
              <details className="decision-disclosure"><summary>Applications and outcomes</summary>
                <ApplicationPanel decision={selected} draft={applicationDraft} saving={saving} setDraft={setApplicationDraft} onCreateApplication={handleCreateApplication} onTransitionApplication={handleTransitionApplication} />
                <OutcomePanel decision={selected} draft={outcomeDraft} saving={saving} setDraft={setOutcomeDraft} onCreateOutcome={handleCreateOutcome} />
              </details>
              <details className="decision-disclosure"><summary>Advanced analysis and review tools</summary>
                <DeepAdvisorPanel analysis={deepAnalysis} decision={selected} loading={deepLoading} error={deepError} reviews={strategicReviews} saving={saving} onGenerate={handleGenerateDeepAnalysis} onRetry={() => loadDeepDecisionState(selected.decision_id)} />
                <MeasurementFeedbackPanel decision={selected} feedbackAccess={decisionFeedbackAccess} draft={feedbackDraft} saving={saving} setDraft={setFeedbackDraft} onSubmit={handleSubmitFeedback} />
                <DecisionReviewOperationsPanel decision={selected} reflectionDraft={reflectionDraft} strategyDraft={strategyDraft} supportDraft={supportDraft} saving={saving} setReflectionDraft={setReflectionDraft} setStrategyDraft={setStrategyDraft} setSupportDraft={setSupportDraft} onRecordReflection={handleRecordReflection} onRecordStrategyChange={handleRecordStrategyChange} onCreateSupportCase={handleCreateSupportCase} />
              </details>
            </>
          ) : !loading ? (
            <EmptyBlock
              title="Start with a decision question"
              body="Create a decision to compare alternatives and plan your next actions."
            />
          ) : null}
          <details className="decision-disclosure"><summary>Weekly review</summary><WeeklyReviewPanel review={weeklyReview} /></details>
        </div>
      </div>
      <details className="decision-advanced-tools evidence-disclosure">
        <summary>Feedback and research settings</summary>
        <BetaAccessStrip
          betaAccess={betaAccess}
          feedbackAccess={decisionFeedbackAccess}
          saving={saving}
          onCommercialInterest={handleCommercialInterest}
        />
      </details>
    </section>
  );
}

function BetaAccessStrip({
  betaAccess,
  feedbackAccess,
  saving,
  onCommercialInterest,
}: {
  betaAccess: BetaAccessPayload | null;
  feedbackAccess: FeatureAccessDecision | null;
  saving: boolean;
  onCommercialInterest: (signalType: "interested" | "not_interested" | "learn_more") => Promise<void>;
}) {
  const cohorts = betaAccess?.cohorts ?? [];
  const cohortLabels = cohorts.length
    ? cohorts.map((cohort) => `${cohort.name} (${label(cohort.membership_status)})`).join(", ")
    : "No beta cohort assigned";
  return (
    <section className="decision-identity-bridge" aria-label="Local feature access and product research settings">
      <div>
        <p className="eyebrow">Optional</p>
        <h3>Feedback and research</h3>
        <p>
          {feedbackAccess
            ? `${label(feedbackAccess.feature_key)} is ${feedbackAccess.allowed ? "available" : "not available"}: ${feedbackAccess.reason}.`
            : "Feedback access is unavailable."}
        </p>
        <small>{cohortLabels}</small>
      </div>
      <div className="choice-button-row">
        <button type="button" className="secondary-button" disabled={saving} onClick={() => void onCommercialInterest("learn_more")}>
          Learn more
        </button>
        <button type="button" className="secondary-button" disabled={saving} onClick={() => void onCommercialInterest("interested")}>
          Interested
        </button>
        <button type="button" className="secondary-button" disabled={saving} onClick={() => void onCommercialInterest("not_interested")}>
          Not interested
        </button>
      </div>
    </section>
  );
}

function IdentityBridge({
  identity,
  decision,
  onOpenCareerIdentity,
}: {
  identity: CareerIdentity | null;
  decision: CareerDecision | null;
  onOpenCareerIdentity?: () => void;
}) {
  const evaluation = identity?.completeness;
  const consent = identity?.privacy.downstream_personalization_consent_granted;
  return (
    <section className="decision-identity-bridge" aria-label="Career Identity decision context">
      <div>
        <p className="eyebrow">Personalization</p>
        <h3>
          {evaluation?.sufficiency_state === "sufficient" ? "Career Identity ready" : "Add details for stronger personalization"}
        </h3>
        <p>
          {consent
            ? "Your Career Identity can inform new comparisons."
            : "Personalization is off, so recommendations may use limited context."}
        </p>
        {decision?.context ? (
          <small>
            {decision.context.sufficiency_state === "sufficient"
              ? "Created with sufficient Career Identity context"
              : "Created with limited Career Identity context"}
          </small>
        ) : identity ? (
          <small>{identity.sufficiency_state === "sufficient" ? "Sufficient profile context" : "Limited profile context"}</small>
        ) : null}
      </div>
      {onOpenCareerIdentity ? (
        <button type="button" className="secondary-button" onClick={onOpenCareerIdentity}>
          Open Career Identity
        </button>
      ) : null}
    </section>
  );
}

function MeasurementFeedbackPanel({
  decision,
  feedbackAccess,
  draft,
  saving,
  setDraft,
  onSubmit,
}: {
  decision: CareerDecision;
  feedbackAccess: FeatureAccessDecision | null;
  draft: FeedbackDraft;
  saving: boolean;
  setDraft: (draft: FeedbackDraft) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  if (!decision.recommendation) {
    return (
      <section className="decision-panel">
        <div className="decision-panel-header">
          <div>
            <p className="eyebrow">Recommendation Feedback</p>
            <h3>Recommendation feedback</h3>
          </div>
        </div>
        <EmptyBlock title="No recommendation to evaluate" body="Feedback is tied to the exact recommendation version that was generated." />
      </section>
    );
  }
  if (feedbackAccess && !feedbackAccess.allowed) {
    return (
      <section className="decision-panel">
        <div className="decision-panel-header">
          <div>
            <p className="eyebrow">Recommendation Feedback</p>
            <h3>Recommendation feedback</h3>
          </div>
          <Badge label="Unavailable" tone="warning" />
        </div>
        <p className="meta-copy">{feedbackAccess.reason}</p>
      </section>
    );
  }
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Recommendation Feedback</p>
          <h3>Recommendation feedback</h3>
        </div>
        <Badge label={`Recommendation ${decision.recommendation.recommendation_id}`} tone="neutral" />
      </div>
      <p className="meta-copy">
        Feedback and later outcomes are association evidence only; they do not prove the recommendation caused an outcome.
      </p>
      <form className="application-form" onSubmit={onSubmit}>
        <div className="decision-form-row">
          <label>
            Useful
            <select value={draft.useful} onChange={(event) => setDraft({ ...draft, useful: event.target.value as FeedbackDraft["useful"] })}>
              <option value="yes">Useful</option>
              <option value="no">Not useful</option>
            </select>
          </label>
          <label>
            Confidence felt
            <select
              value={draft.confidenceCalibration}
              onChange={(event) => setDraft({ ...draft, confidenceCalibration: event.target.value as FeedbackDraft["confidenceCalibration"] })}
            >
              <option value="about_right">About right</option>
              <option value="too_high">Too high</option>
              <option value="too_low">Too low</option>
              <option value="unsure">Unsure</option>
            </select>
          </label>
        </div>
        <div className="decision-form-row">
          <label className="decision-checkbox-label">
            <input
              type="checkbox"
              checked={draft.surprising}
              onChange={(event) => setDraft({ ...draft, surprising: event.target.checked })}
            />
            Surprising
          </label>
          <label className="decision-checkbox-label">
            <input
              type="checkbox"
              checked={draft.changedDecision}
              onChange={(event) => setDraft({ ...draft, changedDecision: event.target.checked })}
            />
            Changed my decision
          </label>
          <label className="decision-checkbox-label">
            <input
              type="checkbox"
              checked={draft.missingAlternative}
              onChange={(event) => setDraft({ ...draft, missingAlternative: event.target.checked })}
            />
            Missing alternative
          </label>
        </div>
        {draft.missingAlternative ? (
          <label>
            Missing alternative category
            <input
              value={draft.missingAlternativeCategory}
              onChange={(event) => setDraft({ ...draft, missingAlternativeCategory: event.target.value })}
              placeholder="role, company, geography, offer, education"
            />
          </label>
        ) : null}
        <label>
          Optional note
          <textarea value={draft.comment} onChange={(event) => setDraft({ ...draft, comment: event.target.value })} />
        </label>
        <button type="submit" className="secondary-button" disabled={saving}>
          Submit feedback
        </button>
      </form>
    </section>
  );
}

function CreateDecisionForm({
  draft,
  saving,
  setDraft,
  onSubmit,
}: {
  draft: CreateDecisionDraft;
  saving: boolean;
  setDraft: (draft: CreateDecisionDraft) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="decision-form" onSubmit={onSubmit}>
      <h3>Create Decision</h3>
      <label>
        Decision type
        <select
          value={draft.decisionType}
          onChange={(event) => setDraft({ ...draft, decisionType: event.target.value as CareerDecisionType })}
        >
          {DECISION_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
        </select>
      </label>
      <label>
        Decision question
        <input
          required
          value={draft.title}
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          placeholder="Choose my next product role focus"
        />
      </label>
      <label>
        Context
        <textarea
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          placeholder="What makes this decision important now?"
        />
      </label>
      <label>
        Time horizon
        <input
          value={draft.timeHorizon}
          onChange={(event) => setDraft({ ...draft, timeHorizon: event.target.value })}
          placeholder="Next 3 months"
        />
      </label>
      <label>
        Priorities
        <input
          value={draft.priorities}
          onChange={(event) => setDraft({ ...draft, priorities: event.target.value })}
          placeholder="role fit, compensation, learning"
        />
      </label>
      <label>
        Hard constraints
        <input
          value={draft.hardConstraints}
          onChange={(event) => setDraft({ ...draft, hardConstraints: event.target.value })}
          placeholder="hybrid only, no relocation"
        />
      </label>
      <label>
        Minimum compensation
        <input
          inputMode="numeric"
          value={draft.minimumCompensation}
          onChange={(event) => setDraft({ ...draft, minimumCompensation: event.target.value })}
          placeholder="120000"
        />
      </label>
      <div className="decision-form-row">
        <label>
          Target date
          <input
            type="date"
            value={draft.targetDate}
            onChange={(event) => setDraft({ ...draft, targetDate: event.target.value })}
          />
        </label>
        <label>
          Review date
          <input
            type="date"
            value={draft.plannedReviewAt}
            onChange={(event) => setDraft({ ...draft, plannedReviewAt: event.target.value })}
          />
        </label>
      </div>
      <button type="submit" className="primary-button" disabled={saving || !draft.title.trim()}>
        Create decision
      </button>
    </form>
  );
}

function DecisionSummary({
  decision,
  selectedOption,
  recommendedOption,
  onOpenExploreComparison,
}: {
  decision: CareerDecision;
  selectedOption: CareerDecisionOption | null;
  recommendedOption: CareerDecisionOption | null;
  onOpenExploreComparison?: (comparisonId: string) => void;
}) {
  return (
    <section className="decision-panel decision-summary-panel">
      <div>
        <p className="eyebrow">What am I deciding?</p>
        <h3>{decision.title}</h3>
        {decision.description ? <p>{decision.description}</p> : null}
      </div>
      <div className="decision-state-strip">
        <Badge label={label(decision.status)} tone={decision.status === "decided" ? "success" : "neutral"} />
        <Badge label={label(decision.decision_type)} tone="neutral" />
        {decision.time_horizon ? <Badge label={decision.time_horizon} tone="neutral" /> : null}
      </div>
      <div className="decision-quick-facts">
        <Fact label="Recommendation" value={recommendedOption?.title ?? (decision.recommendation?.recommendation_status === "abstained" ? "Abstained" : "Not generated")} />
        <Fact label="Your choice" value={selectedOption?.title ?? "Not selected"} />
        <Fact label="Target" value={compactDate(decision.target_date)} />
        <Fact label="Review" value={compactDate(decision.planned_review_at)} />
      </div>
      {decision.explore_comparison_provenance && onOpenExploreComparison ? (
        <button
          className="secondary-button"
          onClick={() => onOpenExploreComparison(decision.explore_comparison_provenance!.comparison_id)}
          type="button"
        >
          Open source comparison
        </button>
      ) : null}
    </section>
  );
}

function OptionBuilder({
  decision,
  draft,
  saving,
  setDraft,
  onSubmit,
}: {
  decision: CareerDecision;
  draft: OptionDraft;
  saving: boolean;
  setDraft: (draft: OptionDraft) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Your Options</p>
          <h3>Scenario Builder</h3>
        </div>
        <Badge label={`${decision.options.length} options`} tone="neutral" />
      </div>
      {decision.options.length ? (
        <div className="decision-option-grid">
          {decision.options.map((option) => <OptionCard key={option.option_id} option={option} />)}
        </div>
      ) : (
        <EmptyBlock title="No scenario options yet" body="Add at least two realistic paths before comparing tradeoffs." />
      )}
      <details className="decision-option-editor evidence-disclosure">
        <summary>Add another scenario</summary>
      <form className="scenario-form" onSubmit={onSubmit}>
        <label>
          Scenario name
          <input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder="Remote AI product roles" />
        </label>
        <label>
          Description
          <textarea value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} />
        </label>
        <div className="decision-form-row">
          <label>
            Role focus
            <input value={draft.roleFocus} onChange={(event) => setDraft({ ...draft, roleFocus: event.target.value })} placeholder="AI Product" />
          </label>
          <label>
            Company IDs
            <input value={draft.companyIds} onChange={(event) => setDraft({ ...draft, companyIds: event.target.value })} placeholder="acme_ai, profile_only" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Regions
            <input value={draft.regions} onChange={(event) => setDraft({ ...draft, regions: event.target.value })} placeholder="greater_boston, remote" />
          </label>
          <label>
            Industries
            <input value={draft.industries} onChange={(event) => setDraft({ ...draft, industries: event.target.value })} placeholder="ai, software" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Work arrangement
            <input value={draft.workArrangement} onChange={(event) => setDraft({ ...draft, workArrangement: event.target.value })} placeholder="remote, hybrid, onsite" />
          </label>
          <label>
            Compensation target
            <input value={draft.compensationTarget} onChange={(event) => setDraft({ ...draft, compensationTarget: event.target.value })} placeholder="130k+" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Base salary
            <input value={draft.baseSalary} onChange={(event) => setDraft({ ...draft, baseSalary: event.target.value })} placeholder="135000 or estimate" />
          </label>
          <label>
            Total compensation
            <input value={draft.totalCompensation} onChange={(event) => setDraft({ ...draft, totalCompensation: event.target.value })} placeholder="155000" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Compensation source
            <input value={draft.compensationSource} onChange={(event) => setDraft({ ...draft, compensationSource: event.target.value })} placeholder="user_entered, estimate, external" />
          </label>
          <label>
            Benefits evidence
            <input value={draft.benefits} onChange={(event) => setDraft({ ...draft, benefits: event.target.value })} placeholder="known, missing, not quantified" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Target skills
            <input value={draft.targetSkills} onChange={(event) => setDraft({ ...draft, targetSkills: event.target.value })} placeholder="Product analytics, ML systems" />
          </label>
          <label>
            Skills taught
            <input value={draft.skillsTaught} onChange={(event) => setDraft({ ...draft, skillsTaught: event.target.value })} placeholder="ML systems, portfolio project" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Education path
            <input value={draft.educationType} onChange={(event) => setDraft({ ...draft, educationType: event.target.value })} placeholder="course, certificate, master's" />
          </label>
          <label>
            Education cost
            <input value={draft.educationCost} onChange={(event) => setDraft({ ...draft, educationCost: event.target.value })} placeholder="1500" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Duration months
            <input value={draft.durationMonths} onChange={(event) => setDraft({ ...draft, durationMonths: event.target.value })} placeholder="2" />
          </label>
          <label>
            COL index
            <input value={draft.costOfLivingIndex} onChange={(event) => setDraft({ ...draft, costOfLivingIndex: event.target.value })} placeholder="128" />
          </label>
        </div>
        <label className="decision-checkbox-label">
          <input
            type="checkbox"
            checked={draft.relocationRequired}
            onChange={(event) => setDraft({ ...draft, relocationRequired: event.target.checked })}
          />
          Relocation required for this scenario
        </label>
        <label>
          Company profile
          <input value={draft.companyProfile} onChange={(event) => setDraft({ ...draft, companyProfile: event.target.value })} placeholder="mid-size AI platform companies" />
        </label>
        <button type="submit" className="secondary-button" disabled={saving || !draft.title.trim()}>
          Add scenario
        </button>
      </form>
      </details>
    </section>
  );
}

function OptionCard({ option }: { option: CareerDecisionOption }) {
  const scenarioEntries = Object.entries(option.scenario).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0;
    return value !== null && value !== undefined && value !== "";
  });
  return (
    <article className="decision-option-card">
      <div>
        <h4>{option.title}</h4>
        <Badge label={label(option.status)} tone={option.status === "selected" ? "success" : "neutral"} />
      </div>
      {option.description ? <p>{option.description}</p> : null}
      {scenarioEntries.length ? (
        <dl>
          {scenarioEntries.map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>{scenarioDisplayValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : <p className="meta-copy">Scenario details not provided.</p>}
    </article>
  );
}

const SCENARIO_VALUE_LABELS: Record<string, string> = {
  sf_bay_area: "San Francisco Bay Area",
  greater_seattle: "Greater Seattle",
  greater_boston: "Greater Boston",
  greater_nyc: "New York City",
  washington_dc: "Washington, DC",
};

function scenarioDisplayValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(scenarioDisplayValue).join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return SCENARIO_VALUE_LABELS[value] ?? label(value);
  return String(value);
}

function RecommendationSurface({
  decision,
  recommendedOption,
  onCompare,
  saving,
}: {
  decision: CareerDecision;
  recommendedOption: CareerDecisionOption | null;
  onCompare: () => void;
  saving: boolean;
}) {
  const recommendation = decision.recommendation;
  const fitOptions = recommendation?.fit.options ?? [];
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Recommendation</p>
          <h3>Tradeoffs & Evidence</h3>
        </div>
        <button type="button" className="primary-button" onClick={() => void onCompare()} disabled={saving || decision.options.length < 2}>
          Compare scenarios
        </button>
      </div>
      {!recommendation ? (
        <EmptyBlock title="No recommendation yet" body="Add multiple options, then compare to create a reproducible recommendation against the current decision context." />
      ) : recommendation.recommendation_status === "abstained" ? (
        <div className="decision-abstention" role="status">
          <strong>There is not enough evidence yet to recommend one path confidently.</strong>
          <p>{recommendation.summary ?? "There is not enough evidence to name a winner."}</p>
          <EvidenceMeta recommendation={recommendation} />
        </div>
      ) : (
        <div className="decision-recommendation-result">
          <div>
            <strong>System recommendation</strong>
            <h4>{recommendedOption?.title ?? "Recommendation available"}</h4>
            <p>{recommendation.summary ?? "Recommendation generated from decision context and available evidence."}</p>
          </div>
          <EvidenceMeta recommendation={recommendation} />
        </div>
      )}
      {recommendation ? (
        <>
          <ChallengeList challenges={recommendation.challenges} options={decision.options} />
          <details className="evidence-disclosure decision-evidence-disclosure">
            <summary>Inspect scenario scoring and supporting evidence</summary>
            <p className="meta-copy">Preserved context snapshot: {recommendation.context_snapshot_id}</p>
            <ScenarioComparison fitOptions={fitOptions} options={decision.options} />
            <EvidencePanel recommendation={recommendation} />
          </details>
        </>
      ) : null}
    </section>
  );
}

function EvidenceMeta({ recommendation }: { recommendation: DecisionRecommendation }) {
  return (
    <div className="decision-state-strip">
      <Badge label={`Confidence: ${label(recommendation.confidence)}`} tone={recommendation.confidence === "high" ? "success" : recommendation.confidence === "low" ? "warning" : "neutral"} />
      <Badge label={`Evidence: ${label(recommendation.evidence_sufficiency)}`} tone={recommendation.evidence_sufficiency === "comparison_ready" ? "success" : "warning"} />
      <Badge label={recommendation.recommendation_status === "abstained" ? "Abstained" : "Ready"} tone={recommendation.recommendation_status === "abstained" ? "warning" : "success"} />
    </div>
  );
}

function ChallengeList({ challenges, options }: { challenges: DecisionChallenge[]; options: CareerDecisionOption[] }) {
  if (!challenges.length) return null;
  return (
    <div className="decision-challenge-list">
      <h4>Challenges</h4>
      {challenges.map((challenge, index) => {
        const option = options.find((item) => item.option_id === challenge.scope_id);
        return (
          <article className={`decision-challenge challenge-${challenge.severity}`} key={`${challenge.code}:${index}`}>
            <Badge label={label(challenge.severity)} tone={challenge.severity === "critical" ? "danger" : challenge.severity === "warning" ? "warning" : "neutral"} />
            <strong>{label(challenge.code)}</strong>
            <p>{challenge.message}</p>
            {option ? <small>Affects {option.title}</small> : null}
          </article>
        );
      })}
    </div>
  );
}

function ScenarioComparison({ fitOptions, options }: { fitOptions: DecisionFitOption[]; options: CareerDecisionOption[] }) {
  if (!fitOptions.length) return null;
  return (
    <div className="scenario-comparison" aria-label="Scenario comparison">
      <h4>Scenario Comparison</h4>
      <div className="scenario-comparison-grid">
        {fitOptions.map((fit) => {
          const option = options.find((candidate) => candidate.option_id === fit.option_id);
          return (
            <article className="scenario-fit-card" key={fit.option_id}>
              <h5>{option?.title ?? fit.title ?? fit.option_id}</h5>
              <div className="decision-state-strip">
                <Badge label={label(fit.assessment)} tone={fit.assessment === "strong" ? "success" : fit.assessment === "misaligned" ? "danger" : "neutral"} />
                {fit.confidence ? <Badge label={`Confidence: ${label(fit.confidence)}`} tone="neutral" /> : null}
              </div>
              <DimensionList dimensions={fit.dimensions} />
              <TextList title="Advantages" items={fit.advantages} empty="No advantages supported by current evidence." />
              <TextList title="Tradeoffs" items={fit.tradeoffs} empty="No tradeoffs identified yet." />
              <TextList title="Unknowns" items={fit.important_unknowns} empty="No important unknowns recorded." />
              {(fit.hard_violations?.length ?? 0) > 0 ? (
                <div className="hard-violation-list">
                  <strong>Hard constraints violated</strong>
                  {fit.hard_violations?.map((violation, index) => <p key={index}>{itemTitle(violation)}</p>)}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function DimensionList({ dimensions }: { dimensions?: Array<Record<string, unknown>> }) {
  if (!dimensions?.length) {
    return <p className="meta-copy">Dimension evidence unavailable; unknown is not treated as poor fit.</p>;
  }
  return (
    <dl className="dimension-list">
      {dimensions.map((dimension, index) => {
        const key = truthyString(dimension.dimension) ?? truthyString(dimension.key) ?? `Dimension ${index + 1}`;
        const assessment = truthyString(dimension.assessment) ?? truthyString(dimension.status) ?? "unknown";
        const evidenceKind = truthyString(dimension.evidence_kind) ?? truthyString(dimension.kind);
        return (
          <div key={`${key}:${index}`}>
            <dt>{label(key)}</dt>
            <dd>{label(assessment)}{evidenceKind ? ` · ${label(evidenceKind)} evidence` : ""}</dd>
          </div>
        );
      })}
    </dl>
  );
}

function EvidencePanel({ recommendation }: { recommendation: DecisionRecommendation }) {
  return (
    <div className="decision-evidence-grid">
      <EvidenceBucket title="Supporting evidence" items={recommendation.evidence.supporting ?? []} empty="No supporting evidence recorded." />
      <EvidenceBucket title="Contrary evidence" items={recommendation.evidence.contrary ?? []} empty="No contrary evidence recorded." />
      <EvidenceBucket title="Unavailable evidence" items={recommendation.evidence.unavailable ?? []} empty="No unavailable evidence recorded." />
      <TextList title="Limitations" items={recommendation.limitations} empty="No additional limitations recorded." />
    </div>
  );
}

function EvidenceBucket({ title, items, empty }: { title: string; items: Array<Record<string, unknown>>; empty: string }) {
  return (
    <div className="decision-evidence-bucket">
      <h4>{title}</h4>
      {items.length ? items.map((item, index) => (
        <p key={index}>
          <strong>{readableEvidenceLabel(itemTitle(item))}</strong>
          {itemBody(item) ? <span> {itemBody(item)}</span> : null}
        </p>
      )) : <p className="meta-copy">{empty}</p>}
    </div>
  );
}

function DeepAdvisorPanel({
  analysis,
  decision,
  loading,
  error,
  reviews,
  saving,
  onGenerate,
  onRetry,
}: {
  analysis: DeepDecisionAnalysis | null;
  decision: CareerDecision;
  loading: boolean;
  error: string | null;
  reviews: StrategicCareerReview[];
  saving: boolean;
  onGenerate: () => Promise<void>;
  onRetry: () => Promise<void>;
}) {
  return (
    <section className="decision-panel deep-advisor-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Decision analysis</p>
          <h3>Deep Decision Intelligence</h3>
        </div>
        <button
          type="button"
          className="primary-button"
          onClick={() => void onGenerate()}
          disabled={saving || loading}
        >
          Generate advisor analysis
        </button>
      </div>
      {loading ? <LoadingBlock label="Loading deep advisor analysis" /> : null}
      {error ? <ErrorBlock message={error} onRetry={onRetry} /> : null}
      {!analysis && !loading && !error ? (
        <EmptyBlock
          title="No deep analysis yet"
          body="Generate advisor analysis after scenarios or recommendations exist. Sparse history is allowed; unsupported insight will remain empty."
        />
      ) : null}
      {analysis ? (
        <>
          <DeepFactorSummary analysis={analysis} decision={decision} />
          <RecommendationEvolutionPanel evolution={analysis.recommendation_evolution} />
          <AdvisorFindingsPanel findings={analysis.advisory_findings} />
          <LongitudinalContextPanel context={analysis.longitudinal_context} />
          <StrategicReviewPanel current={analysis.strategic_review} reviews={reviews} />
        </>
      ) : null}
    </section>
  );
}

function DeepFactorSummary({
  analysis,
  decision,
}: {
  analysis: DeepDecisionAnalysis;
  decision: CareerDecision;
}) {
  const grouped = groupFactors(analysis.factors);
  const summary = factorSummary(analysis.factors);
  return (
    <div className="deep-factor-summary">
      <div className="deep-summary-strip" aria-label="Deep factor summary">
        <Fact label="Benefits" value={String(summary.benefit)} />
        <Fact label="Costs" value={String(summary.cost)} />
        <Fact label="Risks" value={String(summary.risk)} />
        <Fact label="Unknown/stale/proxy" value={String(summary.limited)} />
      </div>
      <div className="deep-domain-grid">
        {DOMAIN_ORDER.map((domain) => (
          <FactorDomainSection
            key={domain}
            domain={domain}
            factors={grouped[domain] ?? []}
            decision={decision}
          />
        ))}
      </div>
    </div>
  );
}

function FactorDomainSection({
  domain,
  factors,
  decision,
}: {
  domain: string;
  factors: DecisionFactor[];
  decision: CareerDecision;
}) {
  if (!factors.length) {
    return (
      <article className="deep-domain-section">
        <h4>{domainLabel(domain)}</h4>
        <p className="meta-copy">No supported factors for this domain yet.</p>
      </article>
    );
  }
  return (
    <article className="deep-domain-section">
      <div className="decision-panel-header">
        <h4>{domainLabel(domain)}</h4>
        <Badge label={`${factors.length} factors`} tone="neutral" />
      </div>
      {factors.slice(0, 4).map((factor) => (
        <FactorCard key={factor.factor_id} factor={factor} decision={decision} />
      ))}
      {factors.length > 4 ? (
        <p className="meta-copy">{factors.length - 4} additional factors are available.</p>
      ) : null}
    </article>
  );
}

function FactorCard({ factor, decision }: { factor: DecisionFactor; decision: CareerDecision }) {
  const option = decision.options.find((item) => item.option_id === factor.option_id);
  return (
    <article className={`deep-factor-card factor-${factor.category}`}>
      <div className="deep-factor-topline">
        <div>
          <strong>{factor.label}</strong>
          <small>
            {label(factor.category)} · {label(factor.direction)}
            {option ? ` · ${option.title}` : ""}
          </small>
        </div>
        <EvidenceBadge factor={factor} />
      </div>
      <p>{factor.explanation}</p>
      {valueSummary(factor.normalized_value ?? factor.raw_value) ? (
        <small>{valueSummary(factor.normalized_value ?? factor.raw_value)}</small>
      ) : null}
      {factor.caveats.length ? (
        <ul className="compact-list">
          {factor.caveats.slice(0, 2).map((caveat) => <li key={caveat}>{caveat}</li>)}
        </ul>
      ) : null}
    </article>
  );
}

function EvidenceBadge({ factor }: { factor: DecisionFactor }) {
  const freshnessTone = factor.freshness_status === "stale" ? "warning" : "neutral";
  const confidenceTone = factor.confidence === "high" ? "success" : factor.confidence === "low" || factor.confidence === "unknown" ? "warning" : "neutral";
  const evidenceTone = factor.evidence_kind === "direct" || factor.evidence_kind === "derived"
    ? "success"
    : factor.evidence_kind === "unavailable" || factor.evidence_kind === "conflicting"
      ? "warning"
      : "neutral";
  return (
    <div className="decision-state-strip" aria-label={`${factor.label} evidence metadata`}>
      <Badge label={label(factor.evidence_kind)} tone={evidenceTone} />
      <Badge label={`Strength: ${label(factor.evidence_strength)}`} tone={evidenceTone} />
      <Badge label={`Confidence: ${label(factor.confidence)}`} tone={confidenceTone} />
      <Badge label={`Uncertainty: ${label(factor.uncertainty)}`} tone={confidenceTone} />
      {factor.freshness_status === "stale" ? <Badge label="Stale evidence" tone={freshnessTone} /> : null}
    </div>
  );
}

function RecommendationEvolutionPanel({ evolution }: { evolution: DeepDecisionAnalysis["recommendation_evolution"] }) {
  return (
    <div className="deep-subpanel">
      <div className="decision-panel-header">
        <div>
          <h4>Recommendation Evolution</h4>
          <p className="meta-copy">Current and prior recommendation snapshots remain distinct.</p>
        </div>
        {evolution ? <Badge label={label(evolution.change_type)} tone="neutral" /> : null}
      </div>
      {!evolution ? (
        <EmptyBlock
          title="No recommendation history yet"
          body="Changes will appear after this decision has recommendation snapshots to compare."
        />
      ) : (
        <div className="evolution-grid">
          <Fact label="Previous" value={evolution.previous_recommendation_id ?? "None"} />
          <Fact label="Current" value={evolution.current_recommendation_id ?? "None"} />
          <Fact label="Confidence before" value={label(evolution.confidence_before)} />
          <Fact label="Confidence now" value={label(evolution.confidence_after)} />
          <p>{evolution.explanation}</p>
          {evolution.evidence_basis.prior_recommendations_are_not_independent_evidence ? (
            <p className="meta-copy">Prior recommendations are not counted as independent evidence.</p>
          ) : null}
          <TimelineItems
            items={evolution.meaningful_changes}
            empty="No meaningful recommendation changes detected."
          />
        </div>
      )}
    </div>
  );
}

function AdvisorFindingsPanel({ findings }: { findings: DeepDecisionAnalysis["advisory_findings"] }) {
  const prioritized = [...findings].sort((a, b) => severityRank(b.severity) - severityRank(a.severity)).slice(0, 5);
  return (
    <div className="deep-subpanel">
      <div className="decision-panel-header">
        <div>
          <h4>Advisor Challenges</h4>
          <p className="meta-copy">Challenges are evidence-backed strategy observations, not personality judgments.</p>
        </div>
        <Badge label={`${prioritized.length} visible`} tone={prioritized.length ? "warning" : "success"} />
      </div>
      {!prioritized.length ? (
        <EmptyBlock
          title="No advisory findings"
          body="No forced blind spot was generated from the available evidence."
        />
      ) : (
        <div className="advisor-finding-list">
          {prioritized.map((finding) => (
            <article className={`advisor-finding advisor-${finding.severity}`} key={finding.advisory_finding_id}>
              <div className="decision-panel-header">
                <div>
                  <strong>{label(finding.finding_type)}</strong>
                  <small>{compactDate(finding.generated_at)} · {label(finding.support_status)}</small>
                </div>
                <div className="decision-state-strip">
                  <Badge label={label(finding.severity)} tone={finding.severity === "warning" || finding.severity === "blocking" ? "warning" : "neutral"} />
                  <Badge label={`Confidence: ${label(finding.confidence)}`} tone={finding.confidence === "medium" || finding.confidence === "high" ? "success" : "warning"} />
                  <Badge label={`Uncertainty: ${label(finding.uncertainty)}`} tone="neutral" />
                </div>
              </div>
              <p>{finding.explanation}</p>
              {finding.affected_goal ? <small>Affected stated goal: {finding.affected_goal}</small> : null}
              {finding.suggested_action ? <p><strong>Reconsider:</strong> {finding.suggested_action}</p> : null}
              <EvidenceObjectList title="Supporting evidence" items={finding.supporting_evidence} />
              <EvidenceObjectList title="Counter-evidence / uncertainty" items={finding.counter_evidence} />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function LongitudinalContextPanel({ context }: { context: DeepDecisionAnalysis["longitudinal_context"] }) {
  const payload = context.context;
  const explicitIntent = asRecord(payload.explicit_intent);
  const observedBehavior = asRecord(payload.observed_behavior);
  return (
    <div className="deep-subpanel">
      <div className="decision-panel-header">
        <div>
          <h4>Longitudinal Context</h4>
          <p className="meta-copy">This snapshot separates stated intent, observed behavior, recommendations, and outcomes.</p>
        </div>
        <Badge label={`${context.record_count} bounded records`} tone="neutral" />
      </div>
      <div className="longitudinal-grid">
        <ContextCard title="Stated intent" record={explicitIntent} />
        <ContextCard title="Observed behavior" record={observedBehavior} />
        <TimelineItems
          title="Prior decisions"
          items={asRecordArray(payload.prior_decisions)}
          empty="No prior decisions in the bounded context."
        />
        <TimelineItems
          title="Recommendation snapshots"
          items={asRecordArray(payload.system_recommendations)}
          empty="No recommendation snapshots yet."
        />
        <TimelineItems
          title="Outcomes"
          items={asRecordArray(payload.outcomes)}
          empty="No outcomes in this review window."
        />
        <TimelineItems
          title="Decision history"
          items={asRecordArray(payload.decision_history)}
          empty="No decision history entries available."
        />
      </div>
      {typeof context.evidence.safety === "string" ? (
        <p className="meta-copy">{context.evidence.safety}</p>
      ) : null}
    </div>
  );
}

function StrategicReviewPanel({
  current,
  reviews,
}: {
  current: StrategicCareerReview;
  reviews: StrategicCareerReview[];
}) {
  const history = reviews.length ? reviews : [current];
  return (
    <div className="deep-subpanel">
      <div className="decision-panel-header">
        <div>
          <h4>Strategic Reviews</h4>
          <p className="meta-copy">Reviews are generated snapshots and are not rewritten with current data.</p>
        </div>
        <Badge label={`${history.length} reviews`} tone="neutral" />
      </div>
      <div className="strategic-review-list">
        {history.slice(0, 4).map((review) => (
          <article className="strategic-review-card" key={review.strategic_review_id}>
            <div className="decision-panel-header">
              <div>
                <strong>{compactDate(review.generated_at)}</strong>
                <small>{compactDate(review.window_start)} to {compactDate(review.window_end)}</small>
              </div>
              <div className="decision-state-strip">
                <Badge label={`Confidence: ${label(review.confidence)}`} tone={review.confidence === "low" || review.confidence === "unknown" ? "warning" : "success"} />
                <Badge label={`Uncertainty: ${label(review.uncertainty)}`} tone="neutral" />
              </div>
            </div>
            <div className="deep-summary-strip">
              <Fact label="Applications" value={recordCountSummary(review.application_summary)} />
              <Fact label="Outcomes" value={recordCountSummary(review.outcome_summary)} />
              <Fact label="Risks" value={String(review.active_risks.length)} />
              <Fact label="Blind spots" value={String(review.blind_spots.length)} />
            </div>
            <TimelineItems
              title="Recommendation changes"
              items={review.recommendation_changes}
              empty="No recommendation changes recorded in this review."
            />
            <TimelineItems
              title="Suggested adjustments"
              items={review.suggested_next_actions}
              empty="No suggested adjustment was generated."
            />
          </article>
        ))}
      </div>
    </div>
  );
}

function SelectionPanel({
  decision,
  recommendedOption,
  selectionNote,
  setSelectionNote,
  saving,
  onSelect,
  onReopen,
}: {
  decision: CareerDecision;
  recommendedOption: CareerDecisionOption | null;
  selectionNote: string;
  setSelectionNote: (value: string) => void;
  saving: boolean;
  onSelect: (optionId: string) => Promise<void>;
  onReopen: () => Promise<void>;
}) {
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Your Choice</p>
          <h3>Select an Option</h3>
        </div>
        {decision.status === "decided" ? (
          <button type="button" className="secondary-button" onClick={() => void onReopen()} disabled={saving}>
            Reopen
          </button>
        ) : null}
      </div>
      <p className="meta-copy">
        The recommendation is advisory. You can choose a different option and keep the recommendation visible in history.
      </p>
      <label>
        Reasoning or reflection
        <textarea value={selectionNote} onChange={(event) => setSelectionNote(event.target.value)} />
      </label>
      <div className="choice-button-row">
        {decision.options.map((option) => (
          <button
            type="button"
            className={option.option_id === decision.selected_option_id ? "primary-button" : "secondary-button"}
            key={option.option_id}
            onClick={() => void onSelect(option.option_id)}
            disabled={saving}
          >
            Choose {option.title}{recommendedOption?.option_id === option.option_id ? " · recommended" : ""}
          </button>
        ))}
      </div>
    </section>
  );
}

function JournalPanel({ journal, options }: { journal: CareerDecisionVersion[]; options: CareerDecisionOption[] }) {
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Decision Journal</p>
          <h3>History</h3>
        </div>
        <Badge label={`${journal.length} entries`} tone="neutral" />
      </div>
      {journal.length ? (
        <ol className="decision-journal">
          {journal.map((entry) => {
            const selected = options.find((option) => option.option_id === entry.selected_option_id);
            return (
              <li key={entry.decision_version_id}>
                <strong>v{entry.version_number} · {label(entry.version_reason)}</strong>
                <span>{compactDate(entry.created_at)}</span>
                {selected ? <p>Selected option: {selected.title}</p> : null}
                {entry.user_note ? <p>{entry.user_note}</p> : null}
                {entry.context_snapshot_id ? <small>Context snapshot {entry.context_snapshot_id}</small> : null}
              </li>
            );
          })}
        </ol>
      ) : <EmptyBlock title="No journal entries yet" body="History will appear as the decision changes, options are selected, or the decision is reopened." />}
    </section>
  );
}

function ActionPlanPanel({
  decision,
  saving,
  onCreatePlan,
  onUpdateAction,
}: {
  decision: CareerDecision;
  saving: boolean;
  onCreatePlan: () => Promise<void>;
  onUpdateAction: (action: CareerAction, status: CareerActionStatus) => Promise<void>;
}) {
  const actions = decision.action_plan?.actions ?? [];
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Action Plan</p>
          <h3>Act on the Choice</h3>
        </div>
        {!decision.action_plan ? (
          <button type="button" className="primary-button" disabled={saving || !decision.selected_option_id} onClick={() => void onCreatePlan()}>
            Create action plan
          </button>
        ) : null}
      </div>
      {!decision.selected_option_id ? <p className="meta-copy">Select an option before creating execution tasks.</p> : null}
      {decision.action_plan && !actions.length ? <EmptyBlock title="Plan exists without actions" body="Add focused next actions for this career decision." /> : null}
      {actions.length ? (
        <div className="action-list">
          {actions.map((action) => (
            <article className="action-row" key={action.action_id}>
              <div>
                <strong>{action.title}</strong>
                <small>{label(action.action_type)} · {action.due_at ? compactDate(action.due_at) : "No due date"}</small>
                {isOverdue(action.due_at) && action.status !== "completed" ? <Badge label="Overdue" tone="danger" /> : null}
                {action.description ? <p>{action.description}</p> : null}
              </div>
              <label>
                Action status
                <select
                  value={action.status}
                  onChange={(event) => void onUpdateAction(action, event.target.value as CareerActionStatus)}
                  disabled={saving}
                >
                  {ACTION_STATUSES.map((status) => <option key={status} value={status}>{label(status)}</option>)}
                </select>
              </label>
            </article>
          ))}
        </div>
      ) : !decision.action_plan ? (
        <EmptyBlock title="No action plan yet" body="After a choice, create a small career-focused plan instead of a generic project board." />
      ) : null}
    </section>
  );
}

function ApplicationPanel({
  decision,
  draft,
  saving,
  setDraft,
  onCreateApplication,
  onTransitionApplication,
}: {
  decision: CareerDecision;
  draft: ApplicationDraft;
  saving: boolean;
  setDraft: (draft: ApplicationDraft) => void;
  onCreateApplication: (event: FormEvent) => void;
  onTransitionApplication: (application: CareerApplication, toStatus: CareerApplicationStatus) => Promise<void>;
}) {
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Applications / Progress</p>
          <h3>Personal Application State</h3>
        </div>
        <Badge label={`${decision.applications.length} tracked`} tone="neutral" />
      </div>
      {decision.applications.length ? (
        <div className="application-list">
          {decision.applications.map((application) => {
            const transitions = APPLICATION_TRANSITIONS[application.status];
            return (
              <article className="application-row" key={application.application_id}>
                <div>
                  <strong>{application.role_title ?? application.company_id ?? "Application"}</strong>
                  <small>{label(application.status)} · Started {compactDate(application.status_started_at)}</small>
                  {application.follow_up_at ? <Badge label={`Follow up ${compactDate(application.follow_up_at)}`} tone={isOverdue(application.follow_up_at) ? "danger" : "warning"} /> : null}
                  {application.notes ? <p>{application.notes}</p> : null}
                </div>
                <label>
                  Move to
                  <select
                    aria-label={`Move ${application.role_title ?? application.application_id} to status`}
                    value=""
                    onChange={(event) => void onTransitionApplication(application, event.target.value as CareerApplicationStatus)}
                    disabled={saving || transitions.length === 0}
                  >
                    <option value="">Choose status</option>
                    {transitions.map((status) => <option key={status} value={status}>{label(status)}</option>)}
                  </select>
                </label>
              </article>
            );
          })}
        </div>
      ) : <EmptyBlock title="No applications tracked" body="Record personal progress when this decision leads to an application, outreach, or opportunity." />}
      <form className="application-form" onSubmit={onCreateApplication}>
        <label>
          Role title
          <input value={draft.roleTitle} onChange={(event) => setDraft({ ...draft, roleTitle: event.target.value })} placeholder="AI Product Manager" />
        </label>
        <div className="decision-form-row">
          <label>
            Company ID
            <input value={draft.companyId} onChange={(event) => setDraft({ ...draft, companyId: event.target.value })} placeholder="company_ai" />
          </label>
          <label>
            Region ID
            <input value={draft.regionId} onChange={(event) => setDraft({ ...draft, regionId: event.target.value })} placeholder="greater_boston" />
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Option
            <select value={draft.optionId} onChange={(event) => setDraft({ ...draft, optionId: event.target.value })}>
              <option value="">Selected option</option>
              {decision.options.map((option) => <option key={option.option_id} value={option.option_id}>{option.title}</option>)}
            </select>
          </label>
          <label>
            Related action
            <select value={draft.actionId} onChange={(event) => setDraft({ ...draft, actionId: event.target.value })}>
              <option value="">No action link</option>
              {(decision.action_plan?.actions ?? []).map((action) => <option key={action.action_id} value={action.action_id}>{action.title}</option>)}
            </select>
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Current status
            <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as CareerApplicationStatus })}>
              {APPLICATION_STATUSES.map((status) => <option key={status} value={status}>{label(status)}</option>)}
            </select>
          </label>
          <label>
            Follow-up date
            <input type="date" value={draft.followUpAt} onChange={(event) => setDraft({ ...draft, followUpAt: event.target.value })} />
          </label>
        </div>
        <label>
          Notes
          <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
        </label>
        <button type="submit" className="secondary-button" disabled={saving || !draft.roleTitle.trim()}>
          Record application
        </button>
      </form>
    </section>
  );
}

function OutcomePanel({
  decision,
  draft,
  saving,
  setDraft,
  onCreateOutcome,
}: {
  decision: CareerDecision;
  draft: OutcomeDraft;
  saving: boolean;
  setDraft: (draft: OutcomeDraft) => void;
  onCreateOutcome: (event: FormEvent) => void;
}) {
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Outcomes & Reflection</p>
          <h3>What Happened?</h3>
        </div>
        <Badge label={`${decision.outcomes.length} outcomes`} tone="neutral" />
      </div>
      {decision.outcomes.length ? (
        <div className="outcome-list">
          {decision.outcomes.map((outcome) => (
            <article className="outcome-row" key={outcome.outcome_id}>
              <strong>{outcome.title}</strong>
              <small>{label(outcome.outcome_type)} · {compactDate(outcome.occurred_at)}</small>
              {outcome.reflection ? <p>{outcome.reflection}</p> : null}
              <small>
                Linked to decision{outcome.application_id ? ` · application ${outcome.application_id}` : ""}{outcome.action_id ? ` · action ${outcome.action_id}` : ""}
              </small>
            </article>
          ))}
        </div>
      ) : <EmptyBlock title="No outcomes recorded" body="Record outcomes from applications, research, networking, skill work, or strategy changes without forcing reflection." />}
      <form className="outcome-form" onSubmit={onCreateOutcome}>
        <label>
          Outcome title
          <input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder="Rejected after application" />
        </label>
        <div className="decision-form-row">
          <label>
            Outcome type
            <select value={draft.outcomeType} onChange={(event) => setDraft({ ...draft, outcomeType: event.target.value as CareerOutcomeType })}>
              {OUTCOME_TYPES.map((type) => <option key={type} value={type}>{label(type)}</option>)}
            </select>
          </label>
          <label>
            Application
            <select value={draft.applicationId} onChange={(event) => setDraft({ ...draft, applicationId: event.target.value })}>
              <option value="">No application link</option>
              {decision.applications.map((application) => <option key={application.application_id} value={application.application_id}>{application.role_title ?? application.application_id}</option>)}
            </select>
          </label>
        </div>
        <div className="decision-form-row">
          <label>
            Action
            <select value={draft.actionId} onChange={(event) => setDraft({ ...draft, actionId: event.target.value })}>
              <option value="">No action link</option>
              {(decision.action_plan?.actions ?? []).map((action) => <option key={action.action_id} value={action.action_id}>{action.title}</option>)}
            </select>
          </label>
          <label>
            Option
            <select value={draft.optionId} onChange={(event) => setDraft({ ...draft, optionId: event.target.value })}>
              <option value="">Selected option</option>
              {decision.options.map((option) => <option key={option.option_id} value={option.option_id}>{option.title}</option>)}
            </select>
          </label>
        </div>
        <label>
          Reflection
          <textarea value={draft.reflection} onChange={(event) => setDraft({ ...draft, reflection: event.target.value })} />
        </label>
        <button type="submit" className="secondary-button" disabled={saving || !draft.title.trim()}>
          Record outcome
        </button>
      </form>
    </section>
  );
}

function DecisionReviewOperationsPanel({
  decision,
  reflectionDraft,
  strategyDraft,
  supportDraft,
  saving,
  setReflectionDraft,
  setStrategyDraft,
  setSupportDraft,
  onRecordReflection,
  onRecordStrategyChange,
  onCreateSupportCase,
}: {
  decision: CareerDecision;
  reflectionDraft: ReflectionDraft;
  strategyDraft: StrategyDraft;
  supportDraft: SupportDraft;
  saving: boolean;
  setReflectionDraft: (draft: ReflectionDraft) => void;
  setStrategyDraft: (draft: StrategyDraft) => void;
  setSupportDraft: (draft: SupportDraft) => void;
  onRecordReflection: (event: FormEvent) => void;
  onRecordStrategyChange: (event: FormEvent) => void;
  onCreateSupportCase: (event: FormEvent) => void;
}) {
  const recommendation = decision.recommendation;
  const trustWarnings = [
    ...(recommendation?.limitations ?? []),
    ...(recommendation?.evidence_sufficiency === "insufficient_evidence" ? ["Evidence coverage is insufficient for a confident recommendation."] : []),
    ...(recommendation?.confidence === "low" || recommendation?.confidence === "unknown" ? ["Recommendation confidence is limited or unknown."] : []),
  ];
  return (
    <section className="decision-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Trust / Operations</p>
          <h3>Review, Correct, or Challenge</h3>
        </div>
        <Badge label={recommendation ? label(recommendation.evidence_sufficiency) : "No recommendation"} tone={recommendation?.evidence_sufficiency === "comparison_ready" ? "success" : "warning"} />
      </div>

      <div className="decision-evidence-grid">
        <div className="decision-evidence-bucket">
          <h4>Product limitations</h4>
          {trustWarnings.length ? (
            trustWarnings.map((warning) => <p key={warning}>{warning}</p>)
          ) : (
            <p className="meta-copy">No additional limitation was supplied by the current recommendation record.</p>
          )}
          <p className="meta-copy">
            Unsupported or stale data should be treated as unavailable evidence, not as evidence that an option is bad.
          </p>
        </div>

        <form className="application-form" onSubmit={onCreateSupportCase}>
          <h4>Support or dispute</h4>
          <label>
            Case type
            <select
              value={supportDraft.caseType}
              onChange={(event) => setSupportDraft({ ...supportDraft, caseType: event.target.value as SupportCaseType })}
            >
              <option value="recommendation_issue">Recommendation dispute</option>
              <option value="bad_data">Bad data report</option>
              <option value="privacy_issue">Privacy request</option>
              <option value="product_issue">Product issue</option>
              <option value="account_access_issue">Account/access issue</option>
              <option value="billing_issue">Billing issue</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            Title
            <input
              required
              value={supportDraft.title}
              onChange={(event) => setSupportDraft({ ...supportDraft, title: event.target.value })}
              placeholder="Recommendation missed a local alternative"
            />
          </label>
          <label>
            Details
            <textarea value={supportDraft.description} onChange={(event) => setSupportDraft({ ...supportDraft, description: event.target.value })} />
          </label>
          <button type="submit" className="secondary-button" disabled={saving || !supportDraft.title.trim()}>
            Submit case
          </button>
        </form>
      </div>

      <div className="decision-evidence-grid">
        <form className="application-form" onSubmit={onRecordStrategyChange}>
          <h4>Strategy change</h4>
          <div className="decision-form-row">
            <label>
              Change type
              <select
                value={strategyDraft.changeType}
                onChange={(event) => setStrategyDraft({ ...strategyDraft, changeType: event.target.value as StrategyDraft["changeType"] })}
              >
                <option value="target_role">Target role</option>
                <option value="geography">Geography</option>
                <option value="company_strategy">Company strategy</option>
                <option value="opportunity_type">Opportunity type</option>
                <option value="application_strategy">Application strategy</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              Reason category
              <input value={strategyDraft.reasonCategory} onChange={(event) => setStrategyDraft({ ...strategyDraft, reasonCategory: event.target.value })} placeholder="outcome, new evidence, constraint" />
            </label>
          </div>
          <div className="decision-form-row">
            <label>
              Previous
              <input value={strategyDraft.previousValue} onChange={(event) => setStrategyDraft({ ...strategyDraft, previousValue: event.target.value })} />
            </label>
            <label>
              New
              <input required value={strategyDraft.newValue} onChange={(event) => setStrategyDraft({ ...strategyDraft, newValue: event.target.value })} />
            </label>
          </div>
          <label>
            Note
            <textarea value={strategyDraft.note} onChange={(event) => setStrategyDraft({ ...strategyDraft, note: event.target.value })} />
          </label>
          <button type="submit" className="secondary-button" disabled={saving || !strategyDraft.newValue.trim()}>
            Record strategy change
          </button>
        </form>

        <form className="application-form" onSubmit={onRecordReflection}>
          <h4>Later reflection</h4>
          <div className="decision-form-row">
            <label>
              Same decision again
              <select
                value={reflectionDraft.wouldMakeSameDecision}
                onChange={(event) => setReflectionDraft({ ...reflectionDraft, wouldMakeSameDecision: event.target.value as ReflectionDraft["wouldMakeSameDecision"] })}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unsure">Unsure</option>
                <option value="not_applicable">Not applicable</option>
              </select>
            </label>
            <label>
              Satisfaction
              <input
                type="number"
                min="1"
                max="5"
                value={reflectionDraft.satisfactionRating}
                onChange={(event) => setReflectionDraft({ ...reflectionDraft, satisfactionRating: event.target.value })}
                placeholder="1-5"
              />
            </label>
          </div>
          <div className="decision-form-row">
            <label>
              Regret
              <select
                value={reflectionDraft.regretLevel}
                onChange={(event) => setReflectionDraft({ ...reflectionDraft, regretLevel: event.target.value as ReflectionDraft["regretLevel"] })}
              >
                <option value="none">None</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="unsure">Unsure</option>
              </select>
            </label>
            <label className="decision-checkbox-label">
              <input
                type="checkbox"
                checked={reflectionDraft.viewChanged}
                onChange={(event) => setReflectionDraft({ ...reflectionDraft, viewChanged: event.target.checked })}
              />
              View changed
            </label>
          </div>
          <label>
            Reflection note
            <textarea value={reflectionDraft.comment} onChange={(event) => setReflectionDraft({ ...reflectionDraft, comment: event.target.value })} />
          </label>
          <button type="submit" className="secondary-button" disabled={saving}>
            Record reflection
          </button>
        </form>
      </div>
    </section>
  );
}

function WeeklyReviewPanel({ review }: { review: WeeklyCareerReview | null }) {
  const sections: Array<{ title: string; items: Array<Record<string, unknown>>; empty: string }> = review ? [
    { title: "What happened", items: review.happened, empty: "No events recorded this week." },
    { title: "What changed", items: review.changed, empty: "No changes recorded this week." },
    { title: "What worked", items: review.worked, empty: "No positive outcomes recorded this week." },
    { title: "What did not work", items: review.did_not_work, empty: "No negative outcomes recorded this week." },
    { title: "Stalled", items: review.stalled, empty: "No stalled applications or actions detected." },
    { title: "Reconsider", items: review.reconsider, empty: "No decisions require reconsideration." },
    { title: "Needs action next", items: review.next_actions, empty: "No next actions due." },
    { title: "Reminders", items: review.reminders, empty: "No reminder signals." },
  ] : [];
  const hasActivity = sections.some((section) => section.items.length > 0);
  return (
    <section className="decision-panel weekly-review-panel">
      <div className="decision-panel-header">
        <div>
          <p className="eyebrow">Weekly Review</p>
          <h3>Learn From the Loop</h3>
        </div>
        {review ? <Badge label={`${compactDate(review.window_start)} to ${compactDate(review.window_end)}`} tone="neutral" /> : null}
      </div>
      {!review ? <EmptyBlock title="Weekly review unavailable" body="No review is available yet." /> : null}
      {review && !hasActivity ? <EmptyBlock title="Quiet week" body="No decision activity was recorded in this review window." /> : null}
      {review ? (
        <div className="weekly-review-grid">
          {sections.map((section) => (
            <article className="weekly-review-section" key={section.title}>
              <h4>{section.title}</h4>
              {section.items.length ? section.items.map((item, index) => (
                <p key={index}>
                  <strong>{itemTitle(item)}</strong>
                  {itemBody(item) ? <span> {itemBody(item)}</span> : null}
                </p>
              )) : <p className="meta-copy">{section.empty}</p>}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

const DOMAIN_ORDER = [
  "company",
  "compensation",
  "skill_gap",
  "education_roi",
  "relocation",
  "timing_pivot",
];

function groupFactors(factors: DecisionFactor[]): Record<string, DecisionFactor[]> {
  return factors.reduce<Record<string, DecisionFactor[]>>((groups, factor) => {
    groups[factor.domain] = [...(groups[factor.domain] ?? []), factor];
    return groups;
  }, {});
}

function factorSummary(factors: DecisionFactor[]) {
  return factors.reduce(
    (summary, factor) => {
      if (factor.category === "benefit") summary.benefit += 1;
      if (factor.category === "cost") summary.cost += 1;
      if (factor.category === "risk") summary.risk += 1;
      if (
        factor.category === "uncertainty"
        || factor.evidence_kind === "proxy"
        || factor.evidence_kind === "unavailable"
        || factor.freshness_status === "stale"
      ) {
        summary.limited += 1;
      }
      return summary;
    },
    { benefit: 0, cost: 0, risk: 0, limited: 0 },
  );
}

function domainLabel(domain: string): string {
  const labels: Record<string, string> = {
    company: "Company evidence",
    compensation: "Compensation / offers",
    skill_gap: "Skill strategy",
    education_roi: "Education scenarios",
    relocation: "Relocation",
    timing_pivot: "Timing / pivot",
  };
  return labels[domain] ?? label(domain);
}

function valueSummary(value: Record<string, unknown> | null): string | null {
  if (!value) return null;
  const entries = Object.entries(value)
    .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== "")
    .slice(0, 4);
  if (!entries.length) return null;
  return entries
    .map(([key, entryValue]) => `${label(key)}: ${formatValue(entryValue)}`)
    .join(" · ");
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(1);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  if (value && typeof value === "object") return valueSummary(value as Record<string, unknown>) ?? "Structured evidence";
  return "Unknown";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function severityRank(value: string): number {
  if (value === "blocking") return 4;
  if (value === "warning") return 3;
  if (value === "watch") return 2;
  return 1;
}

function recordCountSummary(value: Record<string, unknown>): string {
  const entries = Object.entries(value).filter(([, entryValue]) => Number(entryValue) > 0);
  if (!entries.length) return "None";
  return entries.map(([key, entryValue]) => `${label(key)} ${entryValue}`).join(", ");
}

function ContextCard({ title, record }: { title: string; record: Record<string, unknown> }) {
  const entries = Object.entries(record).filter(([, value]) => value !== null && value !== undefined).slice(0, 5);
  return (
    <article className="context-card">
      <h5>{title}</h5>
      {entries.length ? (
        <dl className="dimension-list">
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : <p className="meta-copy">No data in this snapshot.</p>}
    </article>
  );
}

function TimelineItems({
  title,
  items,
  empty,
}: {
  title?: string;
  items: Array<Record<string, unknown>>;
  empty: string;
}) {
  return (
    <div className="timeline-items">
      {title ? <h5>{title}</h5> : null}
      {items.length ? (
        <ol>
          {items.slice(0, 6).map((item, index) => (
            <li key={`${itemTitle(item)}:${index}`}>
              <strong>{itemTitle(item)}</strong>
              {itemBody(item) ? <span> {itemBody(item)}</span> : null}
              {valueSummary(item) ? <small>{valueSummary(item)}</small> : null}
            </li>
          ))}
        </ol>
      ) : <p className="meta-copy">{empty}</p>}
    </div>
  );
}

function EvidenceObjectList({ title, items }: { title: string; items: Array<Record<string, unknown>> }) {
  return (
    <div className="evidence-object-list">
      <h5>{title}</h5>
      {items.length ? (
        <ul className="compact-list">
          {items.slice(0, 4).map((item, index) => (
            <li key={index}>{valueSummary(item) ?? itemTitle(item)}</li>
          ))}
        </ul>
      ) : <p className="meta-copy">No entries recorded.</p>}
    </div>
  );
}

function textListItem(item: string | Record<string, unknown>): string {
  if (typeof item === "string") return item;
  const code = truthyString(item.code);
  const detail = truthyString(item.detail);
  if (code) return `${label(code)}${detail ? ` — ${detail.includes("_") && !detail.includes(" ") ? label(detail) : detail}` : ""}`;
  return truthyString(item.note)
    ?? truthyString(item.message)
    ?? truthyString(item.description)
    ?? valueSummary(item)
    ?? itemTitle(item);
}

function TextList({
  title,
  items,
  empty,
}: {
  title: string;
  items?: Array<string | Record<string, unknown>>;
  empty: string;
}) {
  return (
    <div className="decision-text-list">
      <h4>{title}</h4>
      {items?.length ? (
        <ul>
          {items.map((item, index) => {
            const text = textListItem(item);
            return <li key={`${text}:${index}`}>{text}</li>;
          })}
        </ul>
      ) : <p className="meta-copy">{empty}</p>}
    </div>
  );
}

function Fact({ label: factLabel, value }: { label: string; value: string }) {
  return (
    <div className="decision-fact">
      <span>{factLabel}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Badge({ label: badgeLabel, tone }: { label: string; tone: "neutral" | "success" | "warning" | "danger" }) {
  return <span className={`decision-badge decision-badge-${tone}`}>{badgeLabel}</span>;
}

function EmptyBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void | Promise<void> }) {
  return (
    <div className="error-state" role="alert">
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

function LoadingBlock({ label: loadingLabel }: { label: string }) {
  return (
    <div className="loading-block" role="status">
      <span />
      {loadingLabel}
    </div>
  );
}
