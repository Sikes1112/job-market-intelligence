// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import CareerAgentPage from "./CareerAgentPage";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function freshness(status = "fresh") {
  return {
    freshness_status: status,
    data_basis: "structured_fixture",
    last_updated_at: "2026-06-24T12:00:00Z",
    freshness_expires_at: "2026-07-24T12:00:00Z",
    source_count: 2,
    warnings: [],
  };
}

function uncertainty(forecastBased = false) {
  return {
    confidence_level: "medium",
    confidence_score: 0.67,
    uncertainty_level: "medium",
    reasons: ["Uses structured evidence."],
    limitations: forecastBased
      ? ["Forecast evidence is a bounded directional signal, not a certain outcome."]
      : [],
    forecast_based: forecastBased,
    bounded: true,
  };
}

function answerPayload() {
  return {
    answer_id: "career_answer_demo",
    question_type: "city_fit",
    generated_at: "2026-06-24T12:00:00Z",
    summary:
      "Grounded answer for city_fit: 1 recommendation is supported by structured platform evidence.",
    freshness: freshness(),
    source_freshness: [freshness()],
    uncertainty: uncertainty(true),
    preference_snapshot: {
      preferred_region_ids: ["greater_boston"],
      counts_as_evidence: false,
    },
    guardrails: {
      passed: true,
      evidence_requirement_met: true,
      fabricated_openings_blocked: true,
      preferences_excluded_from_evidence: true,
      forecast_claims_bounded: true,
      private_fields_redacted: true,
      blocked_reasons: [],
      warnings: ["Forecast evidence is a bounded directional signal, not a certain outcome."],
    },
    limitations: ["Some evidence is partial."],
    recommendations: [
      {
        recommendation_id: "career_rec_boston",
        recommendation_type: "city_fit",
        rank: 1,
        target_type: "region",
        target_id: "greater_boston",
        title: "Greater Boston career fit",
        summary:
          "Greater Boston is supported by stored objective opportunity and early-career access.",
        score: 0.82,
        action: "Compare this city against your role, location, and timing constraints.",
        freshness: freshness(),
        uncertainty: uncertainty(true),
        preference_alignment: ["Matches a preferred region."],
        matched_opportunity_ids: [],
        warnings: ["Forecast evidence is a bounded directional signal, not a certain outcome."],
        limitations: [],
        evidence_refs: [
          {
            ref_id: "region_score:score_boston",
            evidence_type: "region_score",
            entity_type: "region_score",
            entity_id: "score_boston",
            label: "Greater Boston market score",
            summary: "Stored region score with objective opportunity 82%.",
            data_basis: "region_market_scores",
            freshness_status: "fresh",
            confidence_label: "structured_score",
            source_count: 2,
            observed_at: "2026-06-24T12:00:00Z",
            public_url: null,
          },
          {
            ref_id: "forecast:forecast_boston",
            evidence_type: "forecast",
            entity_type: "region",
            entity_id: "greater_boston",
            label: "Rising AI market signal",
            summary:
              "Rising AI market signal is supported by observed movement with medium confidence.",
            data_basis: "producer_owned_export",
            freshness_status: "fresh",
            confidence_label: "medium",
            source_count: 4,
            observed_at: "2026-04-01",
            public_url: null,
          },
        ],
      },
    ],
  };
}

function planPayload() {
  const evidence = answerPayload().recommendations[0].evidence_refs;
  return {
    plan_id: "career_action_plan_demo",
    plan_type: "weekly_job_search_plan",
    generated_at: "2026-06-24T12:00:00Z",
    source_answer_id: "career_answer_demo",
    summary: "Generated a weekly job search plan from grounded career-agent recommendations.",
    career_goal: "Early-career software strategy.",
    time_window: {
      label: "weekly job search plan window",
      start_date: "2026-06-24",
      end_date: "2026-06-30",
    },
    freshness: freshness(),
    source_freshness: [freshness()],
    uncertainty: uncertainty(true),
    evidence_refs: evidence,
    warnings: ["Forecast evidence is a bounded directional signal, not a certain outcome."],
    limitations: [],
    memory_personalization: [
      "Rejected markets memory was used to adjust plan priority only.",
    ],
    guardrails: {
      passed: true,
      evidence_requirement_met: true,
      fabricated_openings_blocked: true,
      preferences_excluded_from_evidence: true,
      forecast_claims_bounded: true,
      private_fields_redacted: true,
      blocked_reasons: [],
      warnings: [],
    },
    risks: [
      {
        risk_id: "risk_forecast",
        severity: "medium",
        summary: "Forecast-backed evidence is directional and uncertain.",
        mitigation: "Use forecasts for prioritization only.",
        evidence_refs: [evidence[1]],
      },
    ],
    steps: [
      {
        step_id: "step_1",
        rank: 1,
        title: "Use Greater Boston career fit as the first weekly priority",
        description: "The system suggests this priority because it is grounded.",
        action_owner: "system_suggested",
        strategic: true,
        milestone: {
          milestone_id: "milestone_1",
          summary: "Evidence-backed priority selected.",
          outcome: "One grounded focus area is identified.",
          target_date: "2026-06-24",
        },
        evidence_refs: evidence,
        evidence_bindings: [
          {
            binding_id: "binding_1",
            step_id: "step_1",
            binding_type: "strategic_basis",
            evidence_refs: evidence,
            note: "This step is grounded in structured evidence refs.",
          },
        ],
        freshness: freshness(),
        uncertainty: uncertainty(true),
        risks: [],
        matched_opportunity_ids: [],
        warnings: ["Forecast evidence is a bounded directional signal, not a certain outcome."],
      },
      {
        step_id: "step_2",
        rank: 2,
        title: "Verify and act on Greater Boston career fit",
        description: "User action: manually verify source freshness and fit.",
        action_owner: "user_action_required",
        strategic: true,
        milestone: {
          milestone_id: "milestone_2",
          summary: "Weekly verification step completed.",
          outcome: "The user has one verified next action.",
          target_date: "2026-06-25",
        },
        evidence_refs: evidence,
        evidence_bindings: [],
        freshness: freshness(),
        uncertainty: uncertainty(true),
        risks: [],
        matched_opportunity_ids: [],
        warnings: [],
      },
    ],
  };
}

function memoryPayload(enabled = true) {
  const permissions = [
    "saved_companies",
    "target_regions",
    "applied_roles",
    "preferred_industries",
    "rejected_markets",
    "career_constraints",
    "preferred_role_types",
  ].map((category) => ({
    category,
    enabled,
    personalize_allowed: enabled,
    visibility: "private",
  }));
  const entries = enabled
    ? [
        {
          memory_entry_id: "mem_company",
          category: "saved_companies",
          value: "comp_a",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_region",
          category: "target_regions",
          value: "greater_boston",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_applied",
          category: "applied_roles",
          value: "software_engineering_internship",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_industry",
          category: "preferred_industries",
          value: "software",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_rejected",
          category: "rejected_markets",
          value: "greater_sf",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_constraint",
          category: "career_constraints",
          value: "hybrid only",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
        {
          memory_entry_id: "mem_role_type",
          category: "preferred_role_types",
          value: "new_grad_role",
          label: null,
          notes: null,
          visibility: "private",
          source: "user_provided",
          counts_as_evidence: false,
          created_at: "2026-06-24T12:00:00Z",
          updated_at: "2026-06-24T12:00:00Z",
        },
      ]
    : [];
  const entriesByCategory = Object.fromEntries(
    permissions.map((permission) => [
      permission.category,
      entries.filter((entry) => entry.category === permission.category),
    ]),
  );
  return {
    user_id: "user_memory",
    memory_enabled: enabled,
    permissions,
    entries,
    entries_by_category: entriesByCategory,
    audit_events: [],
  };
}

function toolPreviewPayload(overrides: Record<string, unknown> = {}) {
  const evidence = answerPayload().recommendations[0].evidence_refs;
  return {
    tool_request_id: "career_tool_reminder",
    tool_type: "reminder",
    proposed_action_summary: "Prepare a reminder suggestion for Greater Boston career fit.",
    user_visible_preview: {
      title: "Review Greater Boston career fit",
      suggested_date: "2026-06-26",
      runtime_wired: false,
      execution_note: "Approval stores a tool record only; no reminder runtime is wired in Layer 26C.",
    },
    evidence_refs: evidence,
    freshness: freshness(),
    uncertainty: uncertainty(true),
    warnings: [
      "Reminder runtime is not wired; approval records only the prepared action.",
      "Forecast evidence is a bounded directional signal, not a certain outcome.",
    ],
    approval_requirement: {
      approval_required: true,
      explicit_user_approval_required: true,
      reason: "Creating a reminder changes user-owned state and requires approval.",
      boundary: "reminder_creation",
      approval_button_label: "Approve prepared action",
      runtime_execution_available: false,
    },
    action_boundary: "reminder_creation",
    status: "awaiting_user_approval",
    privacy_classification: "user_private",
    source_answer_id: "career_answer_demo",
    source_plan_id: null,
    user_id: "user_tool",
    runtime_execution_performed: false,
    created_at: "2026-06-24T12:00:00Z",
    updated_at: "2026-06-24T12:00:00Z",
    audit_events: [
      {
        event_type: "preview_created",
        occurred_at: "2026-06-24T12:00:00Z",
        summary: "Career-agent tool preview created.",
      },
    ],
    ...overrides,
  };
}

function toolExecutionPayload(status = "approved") {
  return {
    tool_request_id: "career_tool_reminder",
    status,
    runtime_execution_performed: false,
    executed_at: null,
    summary: status === "approved"
      ? "Approval recorded. This Layer 26C flow stores an approval record and does not execute external integrations."
      : "Tool action rejected. No runtime execution was performed.",
    warnings: status === "approved"
      ? ["No reminder, export, notification, watchlist, outreach, or application runtime was executed."]
      : [],
    tool_preview: toolPreviewPayload({ status }),
  };
}

function careerAgentFetchMock(toolPreview = toolPreviewPayload()) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/me/career-memory") {
      return new Response(JSON.stringify(envelope(memoryPayload(true))), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    if (url === "/me/career-agent/tools/approve") {
      return new Response(JSON.stringify(envelope(toolExecutionPayload("approved"))), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    if (url === "/me/career-agent/tools/reject") {
      return new Response(JSON.stringify(envelope(toolExecutionPayload("rejected"))), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    if (url === "/me/career-agent/tools/preview") {
      return new Response(JSON.stringify(envelope(toolPreview)), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    if (url === "/career-agent/action-plans") {
      return new Response(JSON.stringify(envelope(planPayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    return new Response(JSON.stringify(envelope(answerPayload())), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("CareerAgentPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("renders grounded answer metadata, evidence refs, uncertainty, and guardrails", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(envelope(answerPayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<CareerAgentPage />);

    expect(await screen.findByText("Career planning")).toBeTruthy();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/career-agent/answers",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    expect(screen.getByText("Greater Boston career fit")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Quality checks" })).toBeTruthy();
    expect(screen.getByText("Greater Boston market score")).toBeTruthy();
    expect(screen.getByText("Rising AI market signal")).toBeTruthy();
    expect(screen.getByText("Private fields protected")).toBeTruthy();
    expect(screen.getByText("Career context")).toBeTruthy();
    expect(screen.getByText("Off")).toBeTruthy();
    expect(screen.getAllByText(/not a certain outcome/i).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("internal_review_notes");
    expect(document.body.textContent).not.toContain("Internal-only");
  });

  test("renders action plan summary, steps, milestones, evidence, freshness, warnings, and uncertainty", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/career-agent/action-plans") {
        return new Response(JSON.stringify(envelope(planPayload())), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      return new Response(JSON.stringify(envelope(answerPayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<CareerAgentPage />);
    await screen.findByText("Greater Boston career fit");

    fireEvent.click(screen.getByText("Generate action plan"));

    expect(await screen.findByText("weekly job search plan")).toBeTruthy();
    expect(screen.getByText("Generated a weekly job search plan from grounded career-agent recommendations.")).toBeTruthy();
    expect(screen.getByText("Use Greater Boston career fit as the first weekly priority")).toBeTruthy();
    expect(screen.getByText("Evidence-backed priority selected.")).toBeTruthy();
    expect(screen.getByText("user action required")).toBeTruthy();
    expect(screen.getAllByText("Greater Boston market score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Freshness").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not a certain outcome/i).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("internal_review_notes");
  });

  test("memory controls render opted-in categories and clear memory through protected API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/me/career-memory" && init?.method === "DELETE") {
        return new Response(JSON.stringify(envelope(memoryPayload(false))), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      if (url === "/me/career-memory") {
        return new Response(JSON.stringify(envelope(memoryPayload(true))), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      return new Response(JSON.stringify(envelope(answerPayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    expect(await screen.findByText("Opted in")).toBeTruthy();
    expect(screen.getByDisplayValue("comp_a")).toBeTruthy();
    expect(screen.getByDisplayValue("greater_boston")).toBeTruthy();
    expect(screen.getByDisplayValue("software_engineering_internship")).toBeTruthy();
    expect(screen.getByDisplayValue("software")).toBeTruthy();
    expect(screen.getByDisplayValue("greater_sf")).toBeTruthy();
    expect(screen.getByDisplayValue("hybrid only")).toBeTruthy();
    expect(screen.getByDisplayValue("new_grad_role")).toBeTruthy();

    fireEvent.click(screen.getByText("Clear memory"));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/career-memory",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
    expect(await screen.findByText("Off")).toBeTruthy();
    expect(document.body.textContent).not.toContain("private_metadata");
    expect(document.body.textContent).not.toContain("internal_review_notes");
  });

  test("tool preview renders action summary, approval status, evidence, freshness, warnings, and uncertainty", async () => {
    const fetchMock = careerAgentFetchMock();

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.click(screen.getByText("Preview tool action"));

    expect(await screen.findByText("Prepare a reminder suggestion for Greater Boston career fit.")).toBeTruthy();
    expect(screen.getByText("Approval gate")).toBeTruthy();
    expect(screen.getByText("Creating a reminder changes user-owned state and requires approval.")).toBeTruthy();
    expect(screen.getByText("Runtime available: false")).toBeTruthy();
    expect(screen.getByText("No runtime execution")).toBeTruthy();
    expect(screen.getAllByText("Greater Boston market score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Freshness").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not a certain outcome/i).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      "/me/career-agent/tools/preview",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer token" }),
      }),
    );
  });

  test("approve control calls backend and does not fake runtime execution", async () => {
    const fetchMock = careerAgentFetchMock();

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.click(screen.getByText("Preview tool action"));
    await screen.findByText("Prepare a reminder suggestion for Greater Boston career fit.");

    fireEvent.click(screen.getByText("Approve prepared action"));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/career-agent/tools/approve",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText(/stores an approval record/i)).toBeTruthy();
    expect(screen.getByText("Runtime execution performed: false")).toBeTruthy();
    expect(document.body.textContent).not.toContain("runtime execution performed: true");
  });

  test("reject control calls backend approval contract", async () => {
    const fetchMock = careerAgentFetchMock();

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.click(screen.getByText("Preview tool action"));
    await screen.findByText("Prepare a reminder suggestion for Greater Boston career fit.");

    fireEvent.click(screen.getByText("Reject"));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/career-agent/tools/reject",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText("Tool action rejected. No runtime execution was performed.")).toBeTruthy();
  });

  test("blocked autonomous application preview renders backend guardrail message", async () => {
    careerAgentFetchMock(toolPreviewPayload({
      tool_request_id: "career_tool_blocked_application",
      tool_type: "job_application_submission",
      proposed_action_summary: "Blocked career-agent tool action",
      user_visible_preview: {
        blocked: true,
        reason: "Autonomous job applications are prohibited.",
        runtime_execution_performed: false,
      },
      approval_requirement: {
        approval_required: true,
        explicit_user_approval_required: true,
        reason: "This action is blocked because the career agent cannot submit applications or contact employers.",
        boundary: "application_submission",
        approval_button_label: "Approve prepared action",
        runtime_execution_available: false,
      },
      action_boundary: "application_submission",
      status: "blocked",
      privacy_classification: "blocked",
      warnings: ["Autonomous job applications are blocked."],
    }));

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.change(screen.getByLabelText("Tool preview"), {
      target: { value: "job_application_submission" },
    });
    fireEvent.click(screen.getByText("Preview tool action"));

    expect(await screen.findByText("Blocked autonomous application")).toBeTruthy();
    expect(screen.getByText("Autonomous job applications are prohibited.")).toBeTruthy();
    expect(screen.getAllByText("blocked").length).toBeGreaterThan(0);
  });

  test("outreach draft preview renders without send behavior", async () => {
    careerAgentFetchMock(toolPreviewPayload({
      tool_request_id: "career_tool_outreach",
      tool_type: "outreach_message_draft",
      proposed_action_summary: "Draft an outreach message using grounded context for Greater Boston career fit.",
      user_visible_preview: {
        draft_subject: "Question about Greater Boston career fit",
        draft_body: "Hello career contact,\n\nEvidence-backed context: Greater Boston market score.",
        send_enabled: false,
        evidence_backed_claims: ["Greater Boston market score."],
        user_provided_claims: ["User context must stay separate from product evidence."],
        execution_note: "No outreach sending mechanism is invoked by Layer 26C.",
      },
      approval_requirement: {
        approval_required: false,
        explicit_user_approval_required: false,
        reason: "Drafting outreach text is a read-only preparation action.",
        boundary: "read_only_preview",
        approval_button_label: null,
        runtime_execution_available: false,
      },
      action_boundary: "read_only_preview",
      status: "drafted",
    }));

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.change(screen.getByLabelText("Tool preview"), {
      target: { value: "outreach_message_draft" },
    });
    fireEvent.click(screen.getByText("Preview tool action"));

    expect(await screen.findByText("Question about Greater Boston career fit")).toBeTruthy();
    expect(screen.getByText(/Evidence-backed context: Greater Boston market score/i)).toBeTruthy();
    expect(screen.getByText("Send enabled: false")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
  });

  test("export preview redacts private fields by default", async () => {
    careerAgentFetchMock(toolPreviewPayload({
      tool_request_id: "career_tool_export",
      tool_type: "career_report_export",
      proposed_action_summary: "Prepare a career report export preview for Greater Boston career fit.",
      user_visible_preview: {
        public_export_payload: {
          report_title: "Career Agent Report: Greater Boston career fit",
          summary: "Grounded public-safe summary.",
          private_memory_included: false,
        },
        private_memory_payload: {
          saved_companies: ["private_company"],
        },
        internal_review_notes: "do not render",
        runtime_wired: false,
      },
      action_boundary: "user_data_export",
      status: "awaiting_user_approval",
    }));

    render(
      <CareerAgentPage
        authenticated
        protectedOptions={{ getAccessToken: async () => "token" }}
      />,
    );

    await screen.findByText("Greater Boston career fit");
    fireEvent.change(screen.getByLabelText("Tool preview"), {
      target: { value: "career_report_export" },
    });
    fireEvent.click(screen.getByText("Preview tool action"));

    expect(await screen.findByText("Export preview")).toBeTruthy();
    expect(screen.getByText("Career Agent Report: Greater Boston career fit")).toBeTruthy();
    expect(screen.getByText("Private memory is redacted from this public-safe preview.")).toBeTruthy();
    expect(document.body.textContent).not.toContain("private_company");
    expect(document.body.textContent).not.toContain("do not render");
  });
});
