// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import * as api from "./api";
import DecisionWorkspacePage from "./DecisionWorkspacePage";
import type {
  ApiEnvelope,
  CareerAction,
  CareerActionPlan,
  CareerApplication,
  CareerApplicationStatus,
  CareerDecision,
  CareerDecisionCreateInput,
  CareerDecisionOptionInput,
  CareerDecisionVersion,
  CareerIdentity,
  CareerOutcome,
  DeepDecisionAnalysis,
  DecisionFactor,
  DecisionRecommendation,
  StrategicCareerReview,
  WeeklyCareerReview,
} from "./types";

const apiState = vi.hoisted(() => ({
  decisions: [] as CareerDecision[],
  journal: {} as Record<string, CareerDecisionVersion[]>,
  identityVersion: 1,
  downstreamConsent: true,
  nextId: 1,
  compareMode: "ready" as "ready" | "abstain" | "conflict",
  failTransition: false,
  review: null as WeeklyCareerReview | null,
  deepAnalysis: null as DeepDecisionAnalysis | null,
  strategicReviews: [] as StrategicCareerReview[],
  deepMode: "rich" as "rich" | "sparse" | "proxy" | "stale" | "clean" | "conflicting",
  feedback: [] as Array<Record<string, unknown>>,
  supportCases: [] as Array<Record<string, unknown>>,
}));

vi.mock("./api", () => {
  class ApiError extends Error {
    statusCode?: number;

    constructor(message: string, options?: { statusCode?: number }) {
      super(message);
      this.name = "ApiError";
      this.statusCode = options?.statusCode;
    }
  }

  function envelope<T>(data: T): ApiEnvelope<T> {
    return {
      status: "success",
      data,
      metadata: { state: "fresh", source_versions: {}, warnings: [] },
      error: null,
    };
  }

  function clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T;
  }

  function now() {
    return "2026-09-01T12:00:00Z";
  }

  function next(prefix: string) {
    const id = `${prefix}_${apiState.nextId}`;
    apiState.nextId += 1;
    return id;
  }

  function identity(): CareerIdentity {
    return {
      career_identity_id: "ci_test",
      user_id: "user_test",
      current_version: apiState.identityVersion,
      completeness_state: apiState.downstreamConsent ? "partial" : "minimal",
      sufficiency_state: apiState.downstreamConsent ? "sufficient" : "insufficient",
      privacy: {
        ingestion_consent_granted: apiState.downstreamConsent,
        inference_consent_granted: apiState.downstreamConsent,
        downstream_personalization_consent_granted: apiState.downstreamConsent,
        retain_import_metadata: true,
        privacy_visibility: "private",
      },
      completeness: {
        identity_version: apiState.identityVersion,
        overall_score: apiState.downstreamConsent ? 72 : 22,
        completeness_state: apiState.downstreamConsent ? "partial" : "minimal",
        sufficiency_state: apiState.downstreamConsent ? "sufficient" : "insufficient",
        sufficient: apiState.downstreamConsent,
        strong_required_signal_count: apiState.downstreamConsent ? 4 : 1,
        sections: [],
        missing_categories: apiState.downstreamConsent ? [] : ["skills", "role_preferences"],
        weak_categories: [],
        actionable_reason_codes: apiState.downstreamConsent ? [] : ["downstream_personalization_consent_missing"],
      },
      facts: {
        education: [],
        experience: [],
        skill: [],
        project: [],
        credential: [],
        career_goal: [],
        role_preference: [],
        industry_preference: [],
        geographic_constraint: [],
        compensation_constraint: [],
        timing_preference: [],
        work_arrangement_preference: [],
      },
      created_at: now(),
      updated_at: now(),
    };
  }

  function baseReview(): WeeklyCareerReview {
    return {
      window_start: "2026-08-25T00:00:00Z",
      window_end: "2026-09-01T00:00:00Z",
      happened: [],
      changed: [],
      worked: [],
      did_not_work: [],
      stalled: [],
      invalidated_assumptions: [],
      reconsider: [],
      next_actions: [],
      reminders: [],
    };
  }

  function requireDecision(decisionId: string): CareerDecision {
    const decision = apiState.decisions.find((item) => item.decision_id === decisionId);
    if (!decision) throw new Error("Decision not found.");
    return decision;
  }

  function appendJournal(decision: CareerDecision, reason: string, note: string | null = null) {
    decision.current_version += 1;
    const entry: CareerDecisionVersion = {
      decision_version_id: next("version"),
      version_number: decision.current_version,
      version_reason: reason,
      selected_option_id: decision.selected_option_id,
      context_snapshot_id: decision.current_context_snapshot_id,
      decision_snapshot: { status: decision.status, title: decision.title },
      options_snapshot: decision.options.map((option) => ({ option_id: option.option_id, title: option.title })),
      recommendation_snapshot: decision.recommendation ? { recommendation_id: decision.recommendation.recommendation_id } : null,
      user_note: note,
      created_at: now(),
    };
    apiState.journal[decision.decision_id] = [...(apiState.journal[decision.decision_id] ?? []), entry];
  }

  function makeRecommendation(decision: CareerDecision): DecisionRecommendation {
    const first = decision.options[0];
    const second = decision.options[1];
    const abstain = apiState.compareMode === "abstain";
    const conflict = apiState.compareMode === "conflict";
    return {
      recommendation_id: next("rec"),
      decision_id: decision.decision_id,
      context_snapshot_id: decision.current_context_snapshot_id ?? "ctx_1",
      recommended_option_id: abstain ? null : first?.option_id ?? null,
      recommendation_status: abstain ? "abstained" : "ready",
      evidence_sufficiency: abstain ? "insufficient_evidence" : conflict ? "limited_evidence" : "comparison_ready",
      confidence: abstain ? "unknown" : conflict ? "low" : "medium",
      summary: abstain
        ? "Career Identity and option evidence are incomplete."
        : `${first?.title ?? "Option"} is best supported, but user choice remains separate.`,
      fit: {
        options: decision.options.map((option, index) => ({
          option_id: option.option_id,
          title: option.title,
          assessment: abstain ? "unknown" : index === 0 ? "strong" : "moderate",
          confidence: abstain ? "unknown" : "medium",
          dimensions: abstain
            ? []
            : [
                { dimension: "role_fit", assessment: index === 0 ? "strong" : "moderate", evidence_kind: index === 0 ? "direct" : "proxy" },
                { dimension: "market_fit", assessment: "moderate", evidence_kind: "direct" },
              ],
          constraints: [],
          hard_violations: conflict && option.option_id === second?.option_id
            ? [{ key: "minimum_compensation", message: "Compensation minimum is not satisfied." }]
            : [],
          advantages: abstain ? [] : [index === 0 ? "Direct role preference match" : "Broader remote market"],
          disadvantages: [],
          tradeoffs: index === 1 ? ["Larger search pool with weaker direct evidence"] : [],
          important_unknowns: abstain ? ["Company-specific evidence is missing"] : [],
        })),
      },
      comparison: { ranked_option_ids: decision.options.map((option) => option.option_id), abstained: abstain },
      evidence: {
        supporting: abstain ? [] : [{ title: "Role preference match", message: "Direct evidence supports the recommended option." }],
        contrary: conflict ? [{ title: "Constraint conflict", message: "A high-fit option violates compensation." }] : [],
        unavailable: abstain ? [{ title: "Company evidence missing", message: "No company-specific evidence is available." }] : [],
      },
      challenges: [
        ...(abstain ? [{
          code: "insufficient_evidence",
          severity: "blocking",
          message: "No responsible recommendation can be made from current evidence.",
          scope_type: "decision",
          scope_id: decision.decision_id,
        }] : []),
        ...(conflict && second ? [{
          code: "compensation_minimum_violation",
          severity: "blocking",
          message: "Hard constraint not satisfied: minimum compensation.",
          scope_type: "option",
          scope_id: second.option_id,
        }] : []),
      ],
      limitations: abstain ? ["Career Identity is incomplete.", "Company-specific evidence is unavailable."] : ["Unknowns are not treated as poor fit."],
      generated_at: now(),
    };
  }

  function factor(
    decision: CareerDecision,
    overrides: Partial<DecisionFactor>,
  ): DecisionFactor {
    return {
      factor_id: next("factor"),
      decision_id: decision.decision_id,
      option_id: decision.options[0]?.option_id ?? null,
      recommendation_id: decision.recommendation?.recommendation_id ?? null,
      context_snapshot_id: decision.current_context_snapshot_id,
      domain: "company",
      category: "benefit",
      factor_key: "company_evidence",
      label: "Company evidence",
      normalized_value: null,
      raw_value: null,
      direction: "positive",
      importance: null,
      confidence: "medium",
      uncertainty: "medium",
      evidence_strength: "moderate",
      evidence_kind: "direct",
      source_type: null,
      source_id: null,
      provenance: { generated_by: "test" },
      explanation: "Canonical evidence supports this scenario.",
      caveats: [],
      freshness_status: "unknown",
      freshness_expires_at: null,
      generated_at: now(),
      ...overrides,
    };
  }

  function makeDeepAnalysis(decision: CareerDecision): DeepDecisionAnalysis {
    const sparse = apiState.deepMode === "sparse";
    const proxy = apiState.deepMode === "proxy";
    const stale = apiState.deepMode === "stale";
    const clean = apiState.deepMode === "clean";
    const conflicting = apiState.deepMode === "conflicting";
    const factors = sparse ? [
      factor(decision, {
        domain: "company",
        category: "uncertainty",
        factor_key: "company_specific_evidence",
        label: "Company-specific evidence",
        direction: "unknown",
        confidence: "unknown",
        uncertainty: "high",
        evidence_strength: "unavailable",
        evidence_kind: "unavailable",
        explanation: "No company id is present in this scenario.",
        caveats: ["Missing data is unknown, not poor fit."],
      }),
      factor(decision, {
        domain: "skill_gap",
        category: "risk",
        factor_key: "likely_skill_gaps",
        label: "Likely skill gaps",
        direction: "negative",
        confidence: "low",
        uncertainty: "high",
        evidence_strength: "weak",
        evidence_kind: "inferred",
        explanation: "Target skills are not visible in Career Identity; this is a likely gap, not a confirmed absence.",
        caveats: ["Not yet evidenced in Career Identity."],
      }),
    ] : [
      factor(decision, {
        domain: "company",
        label: proxy ? "Company evidence for profile-only company" : "Role-family strength",
        evidence_kind: proxy ? "proxy" : "derived",
        evidence_strength: proxy ? "weak" : "moderate",
        confidence: proxy ? "low" : "medium",
        source_id: proxy ? "profile_only" : "acme_ai",
        freshness_status: stale ? "stale" : "unknown",
        explanation: proxy
          ? "Canonical company exists, but company-region evidence is weak."
          : "Role-family concentration is derived from canonical company-region hiring evidence.",
      }),
      factor(decision, {
        domain: "compensation",
        category: conflicting ? "risk" : "benefit",
        factor_key: conflicting ? "conflicting_compensation_sources" : "nominal_compensation",
        label: conflicting ? "Conflicting compensation evidence" : "Nominal compensation",
        evidence_kind: conflicting ? "conflicting" : "direct",
        evidence_strength: conflicting ? "conflicting" : "moderate",
        normalized_value: { base_salary: 135000, total_compensation: conflicting ? 220000 : 155000 },
        raw_value: { source: proxy ? "estimate" : "user_entered", benefits: null },
        confidence: conflicting ? "low" : "medium",
        direction: conflicting ? "negative" : "positive",
        explanation: conflicting
          ? "Multiple compensation values differ materially; treat compensation conclusions as uncertain."
          : "Compensation is evaluated as one factor, not the whole decision.",
        caveats: ["Benefit data is missing or not quantified."],
      }),
      factor(decision, {
        domain: "skill_gap",
        category: "risk",
        factor_key: "likely_skill_gaps",
        label: "Likely skill gaps",
        evidence_kind: "inferred",
        evidence_strength: "weak",
        confidence: "low",
        direction: "negative",
        normalized_value: { skills: ["ML systems"] },
        explanation: "Target skills are not visible in Career Identity; this is a likely gap, not a confirmed absence.",
        caveats: ["Do not treat missing profile skills as confirmed lack."],
      }),
      factor(decision, {
        domain: "education_roi",
        category: "cost",
        factor_key: "education_cost",
        label: "Education cost",
        evidence_kind: "direct",
        evidence_strength: "moderate",
        normalized_value: { cost: 72000 },
        explanation: "Credential cost is considered alongside role fit, skill-gap reduction, and opportunity cost.",
        caveats: ["High cost without supported upside should not be treated as automatically worthwhile."],
      }),
      factor(decision, {
        domain: "relocation",
        category: "cost",
        factor_key: "relocation_friction",
        label: "Relocation friction",
        evidence_kind: "direct",
        evidence_strength: "moderate",
        normalized_value: { relocation_required: true, cost_of_living_index: 128 },
        explanation: "Relocation and remote constraints are evaluated as tradeoffs with opportunity and compensation.",
      }),
      factor(decision, {
        domain: "timing_pivot",
        category: "evidence_strength",
        factor_key: "application_sample_size",
        label: "Application sample size",
        evidence_kind: "direct",
        evidence_strength: "weak",
        confidence: "low",
        uncertainty: "high",
        normalized_value: { applications: decision.applications.length },
        explanation: "Application history is too sparse for a strong timing or pivot conclusion.",
        caveats: ["No universal rejection threshold is treated as decisive."],
      }),
    ];
    const findings = clean ? [] : [
      {
        advisory_finding_id: next("finding"),
        decision_id: decision.decision_id,
        finding_type: conflicting
          ? "unrealistic_compensation_location_combination"
          : "stated_goal_behavior_mismatch",
        severity: conflicting ? "watch" as const : "warning" as const,
        support_status: "weakly_supported" as const,
        confidence: "low" as const,
        uncertainty: "medium",
        window_start: "2026-08-01T00:00:00Z",
        window_end: now(),
        affected_goal: "Applied AI Product",
        supporting_evidence: [{ type: "explicit_intent", role_preferences: ["Applied AI Product"] }],
        counter_evidence: [{ type: "sample_size_caveat", message: "Evidence remains limited." }],
        explanation: conflicting
          ? "Compensation or relocation assumptions rely on weak, missing, or conflicting evidence."
          : "Observed application pattern differs from your stated target path.",
        suggested_action: "Review whether the application mix still serves the stated target path.",
        acknowledged_at: null,
        dismissed_at: null,
        generated_at: now(),
      },
    ];
    const review: StrategicCareerReview = {
      strategic_review_id: next("review"),
      decision_id: decision.decision_id,
      longitudinal_context_id: "longitudinal_1",
      status: "generated",
      window_start: "2026-08-01T00:00:00Z",
      window_end: now(),
      goals: { decision_title: decision.title, role_preferences: ["Applied AI Product"] },
      strategy_performance: {
        decision_status: decision.status,
        selected_option_id: decision.selected_option_id,
        recommendation_id: decision.current_recommendation_id,
      },
      application_summary: decision.applications.length ? { rejected: 2, offer: 1 } : {},
      outcome_summary: decision.outcomes.length ? { offer: 1, rejection: 2 } : {},
      identity_changes: apiState.identityVersion > 1 ? [{ type: "context_snapshot_changed" }] : [],
      market_changes: stale ? [{ type: "factor", domain: "company" }] : [],
      recommendation_changes: [{ type: stale ? "stale_evidence" : "confidence_changed" }],
      active_risks: factors.filter((item) => item.category === "risk").map((item) => ({ factor_id: item.factor_id, label: item.label })),
      blind_spots: findings.map((finding) => ({ finding_type: finding.finding_type, confidence: finding.confidence })),
      suggested_next_actions: findings.map((finding) => ({ type: "finding", message: finding.suggested_action })),
      confidence: sparse || proxy ? "low" : "medium",
      uncertainty: sparse || proxy ? "high" : "medium",
      generated_at: now(),
    };
    return {
      decision_id: decision.decision_id,
      factors,
      longitudinal_context: {
        longitudinal_context_id: "longitudinal_1",
        decision_id: decision.decision_id,
        window_start: "2026-08-01T00:00:00Z",
        window_end: now(),
        record_count: decision.options.length + decision.applications.length + decision.outcomes.length,
        context: {
          explicit_intent: {
            decision_title: decision.title,
            decision_type: decision.decision_type,
            role_preferences: ["Applied AI Product"],
          },
          observed_behavior: {
            selected_option_id: decision.selected_option_id,
            applications: decision.applications,
          },
          prior_decisions: [],
          system_recommendations: decision.recommendation ? [{ recommendation_id: decision.recommendation.recommendation_id }] : [],
          outcomes: decision.outcomes,
          decision_history: apiState.journal[decision.decision_id] ?? [],
        },
        evidence: {
          bounded: true,
          safety: "Observed behavior is evidence and does not overwrite explicit intent.",
        },
        generated_at: now(),
      },
      recommendation_evolution: decision.recommendation ? {
        evolution_id: next("evolution"),
        decision_id: decision.decision_id,
        previous_recommendation_id: apiState.identityVersion > 1 ? "rec_previous" : null,
        current_recommendation_id: decision.recommendation.recommendation_id,
        change_type: stale ? "stale_prior" : apiState.identityVersion > 1 ? "career_identity_changed" : "confidence_changed",
        meaningful_changes: [{ type: stale ? "stale_evidence" : "confidence_changed", before: "low", after: "medium" }],
        confidence_before: apiState.identityVersion > 1 ? "low" : null,
        confidence_after: decision.recommendation.confidence,
        evidence_basis: { prior_recommendations_are_not_independent_evidence: true },
        uncertainty: sparse ? "high" : "medium",
        explanation: "Recommendation evolution compares persisted snapshots without treating repeated recommendations as new evidence.",
        generated_at: now(),
      } : null,
      advisory_findings: findings,
      strategic_review: review,
    };
  }

  return {
    ApiError,
    getCareerIdentity: vi.fn(async () => envelope(identity())),
    listCareerDecisions: vi.fn(async () => envelope({ decisions: clone(apiState.decisions) })),
    getWeeklyCareerReview: vi.fn(async () => envelope({ review: clone(apiState.review ?? baseReview()) })),
    getLatestDeepDecisionAnalysis: vi.fn(async () => {
      if (!apiState.deepAnalysis) throw new ApiError("Deep decision analysis not found.", { statusCode: 404 });
      return envelope({ analysis: clone(apiState.deepAnalysis) });
    }),
    generateDeepDecisionAnalysis: vi.fn(async (decisionId: string) => {
      const analysis = makeDeepAnalysis(requireDecision(decisionId));
      apiState.deepAnalysis = analysis;
      apiState.strategicReviews = [analysis.strategic_review, ...apiState.strategicReviews].slice(0, 10);
      return envelope({ analysis: clone(analysis) });
    }),
    listStrategicCareerReviews: vi.fn(async () => envelope({ strategic_reviews: clone(apiState.strategicReviews) })),
    getCareerDecision: vi.fn(async (decisionId: string) => envelope({ decision: clone(requireDecision(decisionId)) })),
    getCareerDecisionJournal: vi.fn(async (decisionId: string) => envelope({ journal: clone(apiState.journal[decisionId] ?? []) })),
    createCareerDecision: vi.fn(async (body: CareerDecisionCreateInput) => {
      const decisionId = next("decision");
      const contextId = next("ctx");
      const decision: CareerDecision = {
        decision_id: decisionId,
        decision_type: body.decision_type,
        status: "draft",
        title: body.title,
        description: body.description ?? null,
        decision_date: null,
        target_date: body.target_date ?? null,
        planned_review_at: body.planned_review_at ?? null,
        time_horizon: body.time_horizon ?? null,
        priorities: body.priorities ?? [],
        constraints: body.constraints ?? [],
        selected_option_id: null,
        career_identity_id: "ci_test",
        current_context_snapshot_id: contextId,
        current_recommendation_id: null,
        current_version: 0,
        context: {
          context_snapshot_id: contextId,
          career_identity_id: "ci_test",
          career_identity_version: apiState.identityVersion,
          completeness_state: identity().completeness_state,
          sufficiency_state: identity().sufficiency_state,
          privacy_scope: "owner_decision_only",
          context: {},
          fact_refs: [],
          created_at: now(),
        },
        options: [],
        recommendation: null,
        action_plan: null,
        applications: [],
        outcomes: [],
        created_at: now(),
        updated_at: now(),
      };
      appendJournal(decision, "decision_created");
      apiState.decisions.push(decision);
      return envelope({ decision: clone(decision) });
    }),
    addCareerDecisionOption: vi.fn(async (decisionId: string, body: CareerDecisionOptionInput) => {
      const decision = requireDecision(decisionId);
      decision.options.push({
        option_id: next("option"),
        decision_id: decision.decision_id,
        title: body.title,
        description: body.description ?? null,
        scenario: body.scenario ?? {},
        status: "active",
        position: body.position ?? decision.options.length,
        created_at: now(),
        updated_at: now(),
      });
      appendJournal(decision, "options_updated");
      return envelope({ decision: clone(decision) });
    }),
    compareCareerDecision: vi.fn(async (decisionId: string) => {
      const decision = requireDecision(decisionId);
      const recommendation = makeRecommendation(decision);
      decision.status = "evaluating";
      decision.recommendation = recommendation;
      decision.current_recommendation_id = recommendation.recommendation_id;
      appendJournal(decision, "recommendation_generated");
      return envelope({ recommendation: clone(recommendation) });
    }),
    selectCareerDecisionOption: vi.fn(async (decisionId: string, body: { option_id: string; user_note?: string | null }) => {
      const decision = requireDecision(decisionId);
      decision.selected_option_id = body.option_id;
      decision.status = "decided";
      decision.options = decision.options.map((option) => ({
        ...option,
        status: option.option_id === body.option_id ? "selected" : "rejected",
      }));
      appendJournal(decision, "option_selected", body.user_note ?? null);
      return envelope({ decision: clone(decision) });
    }),
    reopenCareerDecision: vi.fn(async (decisionId: string) => {
      const decision = requireDecision(decisionId);
      decision.status = "reconsidering";
      appendJournal(decision, "decision_reopened");
      return envelope({ decision: clone(decision) });
    }),
    createCareerActionPlan: vi.fn(async (decisionId: string) => {
      const decision = requireDecision(decisionId);
      const plan: CareerActionPlan = {
        action_plan_id: next("plan"),
        decision_id: decisionId,
        selected_option_id: decision.selected_option_id,
        title: `${decision.title} action plan`,
        status: "active",
        plan: { basis: "decision_selection", recommendation_id: decision.current_recommendation_id },
        actions: ["Validate the strongest unknowns", "Prepare first application or outreach", "Review progress and reconsider if evidence changes"].map((title, index): CareerAction => ({
          action_id: next("action"),
          action_plan_id: "plan_pending",
          decision_id: decisionId,
          option_id: decision.selected_option_id,
          action_type: index === 1 ? "application" : index === 2 ? "review_task" : "research",
          status: "open",
          title,
          description: null,
          due_at: null,
          priority: index + 1,
          position: index,
          completed_at: null,
          metadata: {},
          created_at: now(),
          updated_at: now(),
        })),
        created_at: now(),
        updated_at: now(),
      };
      plan.actions = plan.actions.map((action) => ({ ...action, action_plan_id: plan.action_plan_id }));
      decision.action_plan = plan;
      appendJournal(decision, "action_plan_created");
      apiState.review = {
        ...baseReview(),
        next_actions: plan.actions.map((action) => ({ title: action.title, type: "action" })),
      };
      return envelope({ action_plan: clone(plan) });
    }),
    updateCareerAction: vi.fn(async (actionId: string, body: { status?: CareerAction["status"] }) => {
      for (const decision of apiState.decisions) {
        const action = decision.action_plan?.actions.find((candidate) => candidate.action_id === actionId);
        if (action) {
          action.status = body.status ?? action.status;
          action.completed_at = action.status === "completed" ? now() : null;
          return envelope({ action: clone(action) });
        }
      }
      throw new Error("Action not found.");
    }),
    createCareerApplication: vi.fn(async (body: Partial<CareerApplication>) => {
      const decision = requireDecision(body.decision_id ?? "");
      const application: CareerApplication = {
        application_id: next("app"),
        decision_id: decision.decision_id,
        action_id: body.action_id ?? null,
        option_id: body.option_id ?? decision.selected_option_id,
        company_id: body.company_id ?? null,
        region_id: body.region_id ?? null,
        role_title: body.role_title ?? null,
        status: body.status ?? "applied",
        status_started_at: now(),
        applied_at: now(),
        follow_up_at: body.follow_up_at ?? null,
        source_url: null,
        notes: body.notes ?? null,
        metadata: {},
        transitions: [],
        created_at: now(),
        updated_at: now(),
      };
      decision.applications.push(application);
      apiState.review = {
        ...baseReview(),
        changed: [{ title: application.role_title ?? "Application", status: application.status, type: "application" }],
      };
      return envelope({ application: clone(application) });
    }),
    transitionCareerApplication: vi.fn(async (applicationId: string, body: { to_status: CareerApplicationStatus }) => {
      if (apiState.failTransition) throw new Error("Invalid application transition.");
      for (const decision of apiState.decisions) {
        const application = decision.applications.find((candidate) => candidate.application_id === applicationId);
        if (application) {
          application.transitions.push({
            transition_id: next("transition"),
            application_id: application.application_id,
            from_status: application.status,
            to_status: body.to_status,
            reason: null,
            metadata: {},
            transitioned_at: now(),
          });
          application.status = body.to_status;
          application.updated_at = now();
          apiState.review = {
            ...baseReview(),
            changed: [{ title: application.role_title ?? "Application", status: body.to_status, type: "application" }],
            did_not_work: body.to_status === "rejected" ? [{ title: application.role_title ?? "Application rejected", outcome_type: "rejection" }] : [],
          };
          return envelope({ application: clone(application) });
        }
      }
      throw new Error("Application not found.");
    }),
    createCareerOutcome: vi.fn(async (body: { decision_id?: string | null; title: string; outcome_type: CareerOutcome["outcome_type"]; application_id?: string | null; action_id?: string | null; reflection?: string | null }) => {
      const decision = requireDecision(body.decision_id ?? "");
      const outcome: CareerOutcome = {
        outcome_id: next("outcome"),
        decision_id: decision.decision_id,
        action_id: body.action_id ?? null,
        application_id: body.application_id ?? null,
        option_id: decision.selected_option_id,
        recommendation_id: decision.current_recommendation_id,
        outcome_type: body.outcome_type,
        status: "observed",
        title: body.title,
        description: null,
        occurred_at: now(),
        reflection: body.reflection ?? null,
        evidence: {},
        metadata: {},
        created_at: now(),
        updated_at: now(),
      };
      decision.outcomes.push(outcome);
      appendJournal(decision, "outcome_recorded", body.reflection ?? null);
      apiState.review = {
        ...baseReview(),
        happened: [{ title: outcome.title, type: "outcome" }],
        did_not_work: outcome.outcome_type === "rejection" ? [{ title: outcome.title, outcome_type: "rejection" }] : [],
      };
      return envelope({ outcome: clone(outcome) });
    }),
    submitRecommendationFeedback: vi.fn(async (body: Record<string, unknown>) => {
      const feedback = {
        feedback_id: next("feedback"),
        user_id: "user_test",
        ...body,
        created_at: now(),
        updated_at: now(),
      };
      apiState.feedback.push(feedback);
      return envelope({ feedback: clone(feedback) });
    }),
    recordDecisionReflection: vi.fn(async (body: Record<string, unknown>) => {
      return envelope({
        reflection: {
          reflection_id: next("reflection"),
          user_id: "user_test",
          ...body,
          created_at: now(),
          updated_at: now(),
        },
      });
    }),
    recordStrategyChange: vi.fn(async (body: Record<string, unknown>) => {
      return envelope({
        strategy_change: {
          strategy_change_id: next("strategy"),
          user_id: "user_test",
          ...body,
          occurred_at: now(),
          created_at: now(),
          updated_at: now(),
        },
      });
    }),
    createSupportCase: vi.fn(async (body: Record<string, unknown>) => {
      const supportCase = {
        support_case_id: next("support"),
        user_id: "user_test",
        status: "open",
        assigned_operator_id: null,
        resolution: null,
        resolved_at: null,
        closed_at: null,
        ...body,
        created_at: now(),
        updated_at: now(),
      };
      apiState.supportCases.push(supportCase);
      return envelope({ support_case: clone(supportCase) });
    }),
    getMyBetaAccess: vi.fn(async () => envelope({
      cohorts: [
        {
          cohort_key: "private_beta_a",
          name: "Private beta A",
          status: "active",
          membership_status: "active",
          configuration: { decision_feedback: true },
        },
      ],
      feature_gates: [],
    })),
    getMyFeatureAccess: vi.fn(async () => envelope({
      decision: {
        feature_key: "decision_feedback",
        allowed: true,
        reason: "active beta cohort membership allows feature",
        cohort_keys: ["private_beta_a"],
        access_mode: "beta_only",
        entitlement_source: null,
        configuration: {},
      },
    })),
    recordCommercialExperimentSignal: vi.fn(async (body: Record<string, unknown>) => envelope({
      signal: {
        signal_id: next("signal"),
        user_id: "user_test",
        ...body,
        created_at: now(),
      },
    })),
    recordProductEvent: vi.fn(async (body: Record<string, unknown>) => envelope({
      event: {
        event_id: next("product_event"),
        user_id: "user_test",
        ...body,
        created_at: now(),
      },
    })),
  };
});

const auth = {
  isConfigured: true,
  isAuthenticated: true,
  isLoading: false,
  error: null,
  user: { email: "decision@example.com", sub: "auth0|decision" },
  login: vi.fn(async () => undefined),
  logout: vi.fn(),
  getAccessTokenSilently: vi.fn(async () => "decision-token"),
};

function resetApiState() {
  apiState.decisions = [];
  apiState.journal = {};
  apiState.identityVersion = 1;
  apiState.downstreamConsent = true;
  apiState.nextId = 1;
  apiState.compareMode = "ready";
  apiState.failTransition = false;
  apiState.review = null;
  apiState.deepAnalysis = null;
  apiState.strategicReviews = [];
  apiState.deepMode = "rich";
  apiState.feedback = [];
  apiState.supportCases = [];
}

afterEach(() => {
  cleanup();
  resetApiState();
  vi.clearAllMocks();
});

async function addScenario(title: string, role: string, region: string) {
  fireEvent.change(screen.getByLabelText("Scenario name"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("Role focus"), { target: { value: role } });
  fireEvent.change(screen.getByLabelText("Regions"), { target: { value: region } });
  fireEvent.change(screen.getByLabelText("Industries"), { target: { value: "ai, software" } });
  fireEvent.change(screen.getByLabelText("Work arrangement"), { target: { value: title.includes("Remote") ? "remote" : "hybrid" } });
  fireEvent.click(screen.getByRole("button", { name: "Add scenario" }));
  await screen.findByText("Scenario option added.");
}

describe("DecisionWorkspacePage", () => {
  test("returns a prioritized Decision to its source Explore comparison", async () => {
    const onOpenExploreComparison = vi.fn();
    render(
      <DecisionWorkspacePage
        auth={auth}
        onOpenExploreComparison={onOpenExploreComparison}
      />,
    );

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), {
      target: { value: "Prioritize Greater Boston" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    apiState.decisions[0].explore_comparison_provenance = {
      comparison_id: "explore_comparison_42",
      context_fingerprint: "sha256:context",
      system_recommendation_state: "clear_recommendation",
      system_recommended_region_ids: ["greater_nyc"],
      user_selected_region_id: "greater_boston",
      choice_matches_recommendation: false,
    };
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    fireEvent.click(
      await screen.findByRole("button", { name: "Open source comparison" }),
    );
    expect(onOpenExploreComparison).toHaveBeenCalledWith("explore_comparison_42");
  });

  test("drives the authenticated Career Identity to decision to action to outcome product loop", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Choose next product path" } });
    fireEvent.change(screen.getByLabelText("Priorities"), { target: { value: "role fit, compensation, learning" } });
    fireEvent.change(screen.getByLabelText("Minimum compensation"), { target: { value: "120000" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));

    await screen.findByText("Decision created.");
    await addScenario("Boston AI product", "product", "greater_boston");
    await addScenario("Remote broad product", "product", "remote");

    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    expect(await screen.findByText("System recommendation")).toBeInTheDocument();
    expect(screen.getByText("Role preference match")).toBeInTheDocument();
    expect(screen.getAllByText("Unknowns are not treated as poor fit.").length).toBeGreaterThan(0);
    await waitFor(() => expect(vi.mocked(api.recordProductEvent)).toHaveBeenCalledTimes(3));
    expect(vi.mocked(api.recordProductEvent).mock.calls.map(([event]) => event.event_type)).toEqual([
      "recommendation_viewed",
      "trust_explanation_viewed",
      "coverage_limitation_viewed",
    ]);

    fireEvent.change(screen.getByLabelText("Reasoning or reflection"), { target: { value: "Remote flexibility matters more right now." } });
    fireEvent.click(screen.getByRole("button", { name: "Choose Remote broad product" }));
    await screen.findByText("Choice saved to the journal.");
    expect(screen.getByText("Selected option: Remote broad product")).toBeInTheDocument();
    expect(screen.getByText("Remote flexibility matters more right now.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create action plan" }));
    await screen.findByText("Action plan created.");
    expect(screen.getAllByText("Validate the strongest unknowns").length).toBeGreaterThan(0);

    fireEvent.change(screen.getAllByLabelText("Action status")[0], { target: { value: "completed" } });
    await screen.findByText("Action marked completed.");

    fireEvent.change(screen.getByLabelText("Role title"), { target: { value: "AI Product Manager" } });
    fireEvent.change(screen.getByLabelText("Company ID"), { target: { value: "company_ai" } });
    fireEvent.change(screen.getByLabelText("Region ID"), { target: { value: "greater_boston" } });
    fireEvent.click(screen.getByRole("button", { name: "Record application" }));
    await screen.findByText("Application state recorded.");

    fireEvent.change(screen.getByLabelText("Move AI Product Manager to status"), { target: { value: "rejected" } });
    await screen.findByText("Application moved to rejected.");
    expect(screen.getByText(/Rejected · Started/)).toBeInTheDocument();
    expect(screen.getByLabelText("Move AI Product Manager to status")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Outcome title"), { target: { value: "Rejected after application" } });
    fireEvent.change(screen.getByLabelText("Outcome type"), { target: { value: "rejection" } });
    fireEvent.change(screen.getByLabelText("Application"), { target: { value: apiState.decisions[0].applications[0].application_id } });
    fireEvent.change(screen.getByLabelText("Reflection"), { target: { value: "Need stronger company-specific positioning." } });
    fireEvent.click(screen.getByRole("button", { name: "Record outcome" }));
    await screen.findByText("Outcome recorded.");

    expect(screen.getAllByText("Rejected after application").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Need stronger company-specific positioning.").length).toBeGreaterThan(0);
    expect(screen.getByText("What happened")).toBeInTheDocument();
    expect(within(screen.getByText("What happened").closest("article") as HTMLElement).getByText("Rejected after application")).toBeInTheDocument();
  }, 10000);

  test("shows abstention without inventing a winner", async () => {
    apiState.compareMode = "abstain";
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Choose a city" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Unknown city path", "", "");
    await addScenario("Another unknown path", "", "");

    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));

    expect(await screen.findByText("There is not enough evidence yet to recommend one path confidently.")).toBeInTheDocument();
    expect(screen.getByText("No responsible recommendation can be made from current evidence.")).toBeInTheDocument();
    expect(screen.queryByText("System recommendation")).not.toBeInTheDocument();
    expect(screen.getAllByText(/unknown is not treated as poor fit/i).length).toBeGreaterThan(0);
  });

  test("surfaces hard constraint challenges and preserves user agency", async () => {
    apiState.compareMode = "conflict";
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Compare offer paths" } });
    fireEvent.change(screen.getByLabelText("Minimum compensation"), { target: { value: "150000" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Boston AI product", "product", "greater_boston");
    await addScenario("Remote lower salary", "product", "remote");

    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    expect(await screen.findByText("Compensation Minimum Violation")).toBeInTheDocument();
    expect(screen.getByText("Hard constraint not satisfied: minimum compensation.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Choose Remote lower salary" }));
    await screen.findByText("Choice saved to the journal.");
    expect(screen.getByText("Your choice")).toBeInTheDocument();
    expect(screen.getByText("Selected option: Remote lower salary")).toBeInTheDocument();
  });

  test("supports reopening without erasing historical context after identity changes", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Choose strategy" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Strategy A", "product", "greater_boston");
    await addScenario("Strategy B", "product", "remote");
    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    await screen.findByText("System recommendation");
    fireEvent.click(screen.getByRole("button", { name: /Choose Strategy A/ }));
    await screen.findByText("Choice saved to the journal.");

    apiState.identityVersion = 3;
    apiState.downstreamConsent = false;
    fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
    await screen.findByText("Decision reopened for reconsideration.");

    expect(screen.getByText(/This decision is using Career Identity v1/)).toBeInTheDocument();
    expect(screen.getByText(/Downstream personalization consent is off/)).toBeInTheDocument();
    expect(screen.getAllByText("Selected option: Strategy A").length).toBeGreaterThan(0);
    expect(screen.queryByText("private_salary_expectation")).not.toBeInTheDocument();
  });

  test("preserves UI state and shows backend validation errors for rejected transitions", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Track an application" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Application path", "product", "greater_boston");
    await addScenario("Backup path", "product", "remote");
    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    await screen.findByText("System recommendation");
    fireEvent.click(screen.getByRole("button", { name: /Choose Application path/ }));
    await screen.findByText("Choice saved to the journal.");

    fireEvent.change(screen.getByLabelText("Role title"), { target: { value: "Product Associate" } });
    fireEvent.click(screen.getByRole("button", { name: "Record application" }));
    await screen.findByText("Application state recorded.");

    apiState.failTransition = true;
    fireEvent.change(screen.getByLabelText("Move Product Associate to status"), { target: { value: "interview" } });
    await screen.findByText("Invalid application transition.");
    expect(screen.getByText(/Applied · Started/)).toBeInTheDocument();
  });

  test("renders quiet review without manufacturing activity", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("Quiet week");
    expect(screen.getByText(/No activity was manufactured/)).toBeInTheDocument();
  });

  test("renders shared factors for company compensation skills education relocation and timing", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Compare deep paths" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    fireEvent.change(screen.getByLabelText("Scenario name"), { target: { value: "Boston AI offer" } });
    fireEvent.change(screen.getByLabelText("Role focus"), { target: { value: "Applied AI Product" } });
    fireEvent.change(screen.getByLabelText("Company IDs"), { target: { value: "acme_ai" } });
    fireEvent.change(screen.getByLabelText("Regions"), { target: { value: "boston" } });
    fireEvent.change(screen.getByLabelText("Base salary"), { target: { value: "135000" } });
    fireEvent.change(screen.getByLabelText("Total compensation"), { target: { value: "155000" } });
    fireEvent.change(screen.getByLabelText("Target skills"), { target: { value: "Product analytics, ML systems" } });
    fireEvent.change(screen.getByLabelText("Education path"), { target: { value: "course" } });
    fireEvent.change(screen.getByLabelText("Education cost"), { target: { value: "1500" } });
    fireEvent.change(screen.getByLabelText("Duration months"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("Relocation required for this scenario"));
    fireEvent.click(screen.getByRole("button", { name: "Add scenario" }));
    await screen.findByText("Scenario option added.");
    await addScenario("Remote option", "Applied AI Product", "remote");

    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));

    expect(await screen.findByText("Deep Decision Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Company evidence")).toBeInTheDocument();
    expect(screen.getByText("Compensation / offers")).toBeInTheDocument();
    expect(screen.getByText("Skill strategy")).toBeInTheDocument();
    expect(screen.getByText("Education scenarios")).toBeInTheDocument();
    expect(screen.getByText("Relocation")).toBeInTheDocument();
    expect(screen.getByText("Timing / pivot")).toBeInTheDocument();
    expect(screen.getByText(/Compensation is evaluated as one factor/)).toBeInTheDocument();
    expect(screen.getByText(/not a confirmed absence/)).toBeInTheDocument();
  });

  test("keeps proxy stale and conflicting evidence visible without false precision", async () => {
    apiState.deepMode = "stale";
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Check evidence quality" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Company path", "product", "boston");
    await addScenario("Estimated offer", "product", "remote");

    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    expect(await screen.findAllByText("Stale evidence")).toHaveLength(1);
    expect(screen.getByText("Stale Prior")).toBeInTheDocument();
    expect(screen.queryByText(/72\.381%/)).not.toBeInTheDocument();

    apiState.deepMode = "proxy";
    fireEvent.click(screen.getByRole("button", { name: "Generate advisor analysis" }));
    expect(await screen.findAllByText("Proxy")).not.toHaveLength(0);
    expect(screen.getAllByText(/Confidence: Low/).length).toBeGreaterThan(0);

    apiState.deepMode = "conflicting";
    fireEvent.click(screen.getByRole("button", { name: "Generate advisor analysis" }));
    expect(await screen.findByText("Conflicting compensation evidence")).toBeInTheDocument();
    expect(screen.getByText(/treat compensation conclusions as uncertain/i)).toBeInTheDocument();
    expect(screen.getByText("Unrealistic Compensation Location Combination")).toBeInTheDocument();
  });

  test("sparse history shows empty longitudinal and advisor states without unsupported findings", async () => {
    apiState.deepMode = "sparse";
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Sparse decision" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Explore", "", "");
    await addScenario("Explore elsewhere", "", "");

    fireEvent.click(screen.getByRole("button", { name: "Generate advisor analysis" }));

    expect(await screen.findByText("Company-specific evidence")).toBeInTheDocument();
    expect(screen.getByText(/Missing data is unknown, not poor fit/)).toBeInTheDocument();
    expect(screen.getByText("No recommendation history yet")).toBeInTheDocument();
    expect(screen.getByText("No prior decisions in the bounded context.")).toBeInTheDocument();
    expect(screen.queryByText(/you lack/i)).not.toBeInTheDocument();
  });

  test("no blind spot case stays quiet instead of adding filler challenges", async () => {
    apiState.deepMode = "clean";
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Coherent path" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Aligned option", "Applied AI Product", "boston");
    await addScenario("Backup option", "Applied AI Product", "remote");

    fireEvent.click(screen.getByRole("button", { name: "Generate advisor analysis" }));

    expect(await screen.findByText("No advisory findings")).toBeInTheDocument();
    expect(screen.getByText(/No forced blind spot/)).toBeInTheDocument();
  });

  test("longitudinal view separates explicit intent from behavior after temporary exploration", async () => {
    render(<DecisionWorkspacePage auth={auth} />);

    await screen.findByText("No career decisions yet");
    fireEvent.change(screen.getByLabelText("Decision question"), { target: { value: "Protect intent" } });
    fireEvent.click(screen.getByRole("button", { name: "Create decision" }));
    await screen.findByText("Decision created.");
    await addScenario("Applied AI Product", "Applied AI Product", "boston");
    await addScenario("Temporary software exploration", "Software Engineer", "remote");
    fireEvent.click(screen.getByRole("button", { name: "Compare scenarios" }));
    await screen.findByText("System recommendation");
    fireEvent.click(screen.getByRole("button", { name: "Choose Temporary software exploration" }));
    await screen.findByText("Choice saved to the journal.");

    expect(await screen.findByText("Stated intent")).toBeInTheDocument();
    expect(screen.getByText("Observed behavior")).toBeInTheDocument();
    expect(screen.getByText(/does not overwrite explicit intent/)).toBeInTheDocument();
    expect(screen.getByText(/Observed application pattern differs from your stated target path/)).toBeInTheDocument();
    expect(screen.queryByText(/You're/)).not.toBeInTheDocument();
    expect(screen.queryByText(/irrational|obsessed|indecisive|afraid/i)).not.toBeInTheDocument();
  });
});
