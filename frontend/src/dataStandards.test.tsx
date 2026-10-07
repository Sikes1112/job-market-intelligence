// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function definitionsPayload() {
  return {
    version: "27.1.0",
    definitions: [
      {
        term: "entry-level role",
        canonical_name: "entry_level_role",
        description: "A role intended for candidates at the beginning of a career path.",
        inclusion_criteria: ["Entry-level label"],
        exclusion_criteria: ["Senior role"],
        examples: ["Software Engineer I"],
        related_terms: ["internship"],
        version: "27.1.0",
        status: "active",
      },
    ],
  };
}

function partnerSchemaPayload() {
  return {
    schema_version: "partner_submission_v1",
    supported_submitter_types: ["employer", "workforce_board"],
    supported_record_types: ["company", "region", "hiring_signal"],
    validation_statuses: ["received", "validated", "rejected"],
    required_submission_fields: ["submission_id", "partner_id", "records", "source_refs", "freshness", "confidence"],
    required_fields_by_record_type: {
      company: ["company_name", "company_website"],
    },
    source_refs_required_for_record_types: ["company", "region", "hiring_signal"],
    freshness_required: true,
    confidence_required: true,
  };
}

function partnersPayload() {
  return {
    version: "27.3.0",
    supported_partner_types: ["university", "employer"],
    verification_statuses: ["unverified", "pending_review", "verified", "suspended", "revoked"],
    trust_tiers: ["tier_1_verified_institutional", "tier_4_limited_partner", "untrusted"],
    partners: [
      {
        partner_id: "partner_state_university",
        name: "State University Career Center",
        partner_type: "university",
        region_scope: ["statewide"],
        verification_status: "verified",
        allowed_submission_types: ["early_career_program", "hiring_signal"],
        trust_tier: "tier_1_verified_institutional",
        public_contact_metadata: {
          website_url: "https://state-university.example/career-center",
          contact_page_url: "https://state-university.example/contact",
          public_contact_label: "Career center public contact page",
          public_notes: null,
        },
        created_at: "2026-06-30T00:00:00Z",
        updated_at: "2026-06-30T00:00:00Z",
      },
    ],
  };
}

function qualityLabelsPayload() {
  return {
    version: "27.4.0",
    labels: [
      {
        label: "low_confidence_signal",
        display_name: "Low Confidence Signal",
        description: "Records with weak, stale, incomplete, or low-confidence evidence.",
        allowed_sources: ["*"],
        minimum_confidence: "unknown",
        requires_source_refs: false,
        requires_partner_verification: false,
        ranking_influence_allowed: false,
        public_display_allowed: true,
        warning_copy: "Low-confidence signals are not ranking inputs and require review before any downstream use.",
        trust_explanation: trustExplanation("quality_label:low_confidence_signal"),
      },
      {
        label: "self_reported_employer_data",
        display_name: "Self-Reported Employer Data",
        description: "Employer-provided data that remains self-reported.",
        allowed_sources: ["employer_official"],
        minimum_confidence: "low",
        requires_source_refs: true,
        requires_partner_verification: false,
        ranking_influence_allowed: false,
        public_display_allowed: true,
        warning_copy: "This is self-reported employer data and should be reviewed before being used as canonical market evidence.",
        trust_explanation: trustExplanation("quality_label:self_reported_employer_data"),
      },
    ],
  };
}

function trustExplanation(subjectId: string) {
  return {
    subject_type: "data_standard_fact",
    subject_id: subjectId,
    trust_tier: "ranking_ineligible",
    trust_label: "Excluded from rankings",
    trust_summary: "This quality label is visible data-standard metadata.",
    risk_level: "low",
    risk_label: "Low risk",
    risk_summary: "This label is safe to display, but it is not ranking evidence.",
    routing_outcome: "auto_accept_non_ranking",
    routing_label: "Visible, not used in rankings",
    routing_summary: "This label can be shown to users.",
    ranking_influence_allowed: false,
    ranking_influence_decision: "denied",
    ranking_influence_label: "Excluded from rankings",
    ranking_influence_reason:
      "Data-standard quality labels are informational metadata and do not affect rankings.",
    evidence_requirements_met: [],
    evidence_requirements_missing: [],
    evidence_requirements_failed: [],
    trust_warnings: [],
    user_facing_warnings: [],
    last_checked_at: null,
    decided_at: null,
    next_recheck_at: null,
    explanation_version: "30C",
  };
}

function governancePayload() {
  return {
    version: "27.5.0",
    status: "framework_defined",
    governance_records: [
      {
        area: "bias_review",
        display_name: "Bias Review",
        description: "Guidance for identifying hidden employer or partner bias.",
        review_questions: ["Could partner status be mistaken for data certification?"],
        risk_flags: ["partner_verification_confused_with_certification"],
        recommended_controls: ["Keep all quality labels non-ranking until a consumer contract exists."],
        status: "framework_defined",
        version: "27.5.0",
        public_summary: "Bias-review scaffolding is defined, but no active governance board or external approval process is claimed.",
      },
    ],
  };
}

function payloadFor(input: RequestInfo | URL) {
  const url = String(input);
  if (url === "/data-standards/definitions") return definitionsPayload();
  if (url === "/data-standards/partner-schema") return partnerSchemaPayload();
  if (url === "/data-standards/partners") return partnersPayload();
  if (url === "/data-standards/quality-labels") return qualityLabelsPayload();
  if (url === "/data-standards/governance-framework") return governancePayload();
  return {};
}

function stubFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) =>
    new Response(JSON.stringify(envelope(payloadFor(input))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  window.history.pushState(null, "", "/data-standards");
  return render(
    <FrontendAuthProvider>
      <App />
    </FrontendAuthProvider>,
  );
}

describe("Layer 27 data standards page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("/data-standards renders backend-connected standards surface and boundaries", async () => {
    const fetchMock = stubFetch();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Data standards and partner governance" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Standard Definitions" })).toBeTruthy();
    expect(await screen.findByText("entry-level role")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Partner Submission Format" })).toBeTruthy();
    expect(screen.getByText("partner_submission_v1")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Verified Partner Network" })).toBeTruthy();
    expect(screen.getByText("State University Career Center")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Data Quality Labels" })).toBeTruthy();
    expect(screen.getByText("Low Confidence Signal")).toBeTruthy();
    expect(screen.getByText("Self-Reported Employer Data")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Governance Framework" })).toBeTruthy();
    expect(screen.getByText("Bias Review")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Submission Validation Preview" })).toBeTruthy();

    expect(screen.getByText("Controlled merge only")).toBeTruthy();
    expect(screen.getByText(/Layer 28 adds controlled reviewer-approved canonical merge/i)).toBeTruthy();
    expect(screen.getByText(/partner-submitted data never mutates canonical truth directly/i)).toBeTruthy();
    expect(screen.getByText(/quality labels do not currently alter rankings, recommendations, forecasts, policy outputs, career-agent outputs, public reports, or market scores/i)).toBeTruthy();
    expect(screen.getAllByText(/Low-confidence signals are not ranking inputs/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/self-reported employer data/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Trust: Excluded from rankings").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Risk: Low risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Visible, not used in rankings").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Report information issue").length).toBeGreaterThan(0);
    expect(screen.getByText(/Governance is currently a framework, not an active governance board/i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/board_active|board_approved|externally_governed/);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/data-standards/definitions",
      "/data-standards/partner-schema",
      "/data-standards/partners",
      "/data-standards/quality-labels",
      "/data-standards/governance-framework",
    ]);
  });
});
