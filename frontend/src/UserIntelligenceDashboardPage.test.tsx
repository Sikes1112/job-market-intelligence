// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import UserIntelligenceDashboardPage from "./UserIntelligenceDashboardPage";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function dashboardPayload() {
  return {
    generated_at: "2026-07-02T12:00:00Z",
    dashboard_version: "30.1",
    summary: {
      headline: "Your current market intelligence",
      description: "Personalized recommendations, warnings, and next actions based on available data.",
      warning_count: 2,
      recommendation_count: 3,
    },
    recommended_regions: [
      {
        region_id: "greater_boston",
        region_name: "Greater Boston",
        score: 0.82,
        confidence: "warning",
        freshness: "unknown",
        warnings: ["Source evidence is unknown or incomplete."],
        why_recommended: "Existing region score metadata shows a comparatively strong objective opportunity score.",
        ranking_influence_allowed: null,
        trust_tier: null,
        risk_level: null,
        routing_outcome: null,
        ranking_influence_decision: null,
        ranking_influence_reason: null,
        ranking_influence_reason_codes: [],
      },
    ],
    recommended_companies: [
      {
        company_id: "comp_alpha",
        company_name: "Alpha Systems",
        score: null,
        confidence: "metadata_available",
        freshness: "fresh",
        warnings: [],
        why_recommended: "Existing company metadata shows current hiring.",
        ranking_influence_allowed: null,
        trust_tier: null,
        risk_level: null,
        routing_outcome: null,
        ranking_influence_decision: null,
        ranking_influence_reason: null,
        ranking_influence_reason_codes: [],
      },
    ],
    recommended_opportunities: [
      {
        opportunity_id: "opp_partner",
        title: "Partner Submitted Analyst Internship",
        company_name: "Alpha Systems",
        region_name: "Greater Boston",
        trust_label: "partner_submitted",
        review_status: "pending_review",
        partner_submitted: true,
        ranking_influence_allowed: false,
        expiration_state: "active",
        source_type: "partner_submitted",
        warnings: [
          "Partner-submitted opportunity; verify source details before acting.",
          "Visible opportunity is not allowed to influence rankings.",
        ],
        why_recommended: "Existing opportunity metadata marks this record as active and available to display.",
        trust_tier: "partner_submitted",
        evidence_summary: {
          trust_tier: "partner_submitted",
          met_count: 6,
          missing_count: 2,
          failed_count: 1,
          warning_count: 2,
        },
        risk_level: "low",
        routing_outcome: "auto_accept_non_ranking",
        ranking_influence_decision: "denied",
        ranking_influence_reason: "Partner-submitted evidence is not independently ranking-eligible by default.",
        ranking_influence_reason_codes: [
          "partner_submitted_not_verified",
          "ranking_default_denied",
        ],
        trust_explanation: {
          subject_type: "opportunity",
          subject_id: "opp_partner",
          trust_tier: "partner_submitted",
          trust_label: "Partner-submitted",
          trust_summary: "This item was submitted by a partner and has not been independently verified.",
          risk_level: "medium",
          risk_label: "Use with caution",
          risk_summary: "Use this item with caution and review its warnings.",
          routing_outcome: "visible_with_warning",
          routing_label: "Visible with warning",
          routing_summary: "This item can be visible, but warnings should be reviewed first.",
          ranking_influence_allowed: false,
          ranking_influence_decision: "denied",
          ranking_influence_label: "Excluded from rankings",
          ranking_influence_reason:
            "Partner-submitted items are visible for awareness but excluded from rankings until stronger independent evidence is available.",
          evidence_requirements_met: [],
          evidence_requirements_missing: [],
          evidence_requirements_failed: [],
          trust_warnings: [],
          user_facing_warnings: [
            {
              warning_code: "PARTNER_SUBMITTED_NOT_VERIFIED",
              severity: "info",
              title: "Partner-submitted",
              message: "This item has not been independently verified.",
            },
          ],
          last_checked_at: "2026-07-02T12:00:00Z",
          decided_at: "2026-07-02T12:00:00Z",
          next_recheck_at: null,
          exception_status: {
            subject_type: "opportunity",
            subject_id: "opp_partner",
            has_open_exception: true,
            exception_case_id: "exception_1",
            exception_type: "fraud_spam",
            status: "blocked",
            severity: "critical",
            public_safe_status: "blocked",
            label: "Blocked",
            message: "This item is blocked because unresolved critical risk signals remain.",
            updated_at: "2026-07-02T12:00:00Z",
            resolved_at: null,
          },
          explanation_version: "30C",
        },
        exception_status: {
          subject_type: "opportunity",
          subject_id: "opp_partner",
          has_open_exception: true,
          exception_case_id: "exception_1",
          exception_type: "fraud_spam",
          status: "blocked",
          severity: "critical",
          public_safe_status: "blocked",
          label: "Blocked",
          message: "This item is blocked because unresolved critical risk signals remain.",
          updated_at: "2026-07-02T12:00:00Z",
          resolved_at: null,
        },
      },
    ],
    market_warnings: [
      {
        warning_code: "region_metadata_warning_1",
        severity: "warning",
        title: "Greater Boston data warning",
        message: "Source evidence is unknown or incomplete.",
        subject_type: "region",
        subject_id: "greater_boston",
        source: "region_search_metadata",
      },
    ],
    forecast_changes: [
      {
        subject_type: "region",
        subject_id: "greater_boston",
        title: "Possible weakening forecast for Greater Boston",
        summary: "Forecast is bounded and directional.",
        confidence: "low",
        freshness: "unknown",
        warnings: ["Evidence is limited."],
      },
    ],
    saved_items: [
      {
        item_id: "saved_region_boston",
        item_type: "region",
        label: "Greater Boston",
        target_route: "/markets/region/greater_boston",
        metadata: {},
      },
    ],
    recommended_next_actions: [
      {
        action_code: "inspect_market_warnings",
        label: "Inspect market warnings",
        description: "Review weak confidence and stale freshness warnings before relying on a result.",
        priority: "high",
        target_route: "/markets/dashboard#warnings",
      },
    ],
    trust_context: {
      uses_existing_metadata_only: false,
      layer_30_full_trust_engine_available: true,
      message:
        "This dashboard displays available confidence, freshness, source, trust, evidence, risk, ranking, explanation, report, recheck, and safe exception metadata.",
    },
  };
}

describe("UserIntelligenceDashboardPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("renders dashboard modules from backend payload", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(envelope(dashboardPayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<UserIntelligenceDashboardPage />);

    expect(await screen.findByText("Your current market intelligence")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/user-intelligence/dashboard",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
    ));

    expect(screen.getByText("Recommended Regions")).toBeTruthy();
    expect(screen.getAllByText("Greater Boston").length).toBeGreaterThan(0);
    expect(screen.getByText("Recommended Companies")).toBeTruthy();
    expect(screen.getAllByText("Alpha Systems").length).toBeGreaterThan(0);
    expect(screen.getByText("Recommended Opportunities")).toBeTruthy();
    expect(screen.getByText("Partner Submitted Analyst Internship")).toBeTruthy();
    expect(screen.getByText("Partner submitted")).toBeTruthy();
    expect(screen.getByText("Trust tier: partner submitted")).toBeTruthy();
    expect(screen.getByText("Risk: low")).toBeTruthy();
    expect(screen.getByText("Routing: auto accept non ranking")).toBeTruthy();
    expect(screen.getByText("Ranking decision: denied")).toBeTruthy();
    expect(screen.getByText(/Ranking reason: Partner-submitted evidence/i)).toBeTruthy();
    expect(screen.getByText(/partner submitted not verified/i)).toBeTruthy();
    expect(screen.getByText(/Evidence met 6/i)).toBeTruthy();
    expect(screen.getByText("Trust: Partner-submitted")).toBeTruthy();
    expect(screen.getByText("Risk: Use with caution")).toBeTruthy();
    expect(screen.getByText("Excluded from rankings")).toBeTruthy();
    expect(screen.getAllByText("Exception: Blocked").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/critical risk signals remain/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/visible for awareness/i)).toBeTruthy();
    expect(screen.getByText("Report information issue")).toBeTruthy();
    expect(screen.getByText(/Reports are signals for automated recheck/i)).toBeTruthy();
    expect(screen.getByText("Ranking influence: not allowed")).toBeTruthy();
    expect(screen.getByText("Market Warnings")).toBeTruthy();
    expect(screen.getByText("Forecast Changes or Market Movement")).toBeTruthy();
    expect(screen.getByText("Saved or Relevant Items")).toBeTruthy();
    expect(screen.getByText("Recommended Next Actions")).toBeTruthy();
    expect(screen.getByText("Full trust engine available: true")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/approval queue|internal_notes/i);
  });

  test("renders honest empty states without client-fabricated intelligence", async () => {
    const emptyPayload = {
      ...dashboardPayload(),
      summary: {
        headline: "Your current market intelligence",
        description: "No data was available.",
        warning_count: 0,
        recommendation_count: 0,
      },
      recommended_regions: [],
      recommended_companies: [],
      recommended_opportunities: [],
      market_warnings: [],
      forecast_changes: [],
      saved_items: [],
      recommended_next_actions: [],
    };
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(envelope(emptyPayload)), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    ));

    render(<UserIntelligenceDashboardPage />);

    expect(await screen.findByText("No recommended regions")).toBeTruthy();
    expect(screen.getByText("No scored market recommendations are available.")).toBeTruthy();
    expect(screen.getByText("No recommended companies")).toBeTruthy();
    expect(screen.getByText("No recommended opportunities")).toBeTruthy();
    expect(screen.getByText("No market warnings")).toBeTruthy();
    expect(screen.getByText("No forecast changes")).toBeTruthy();
    expect(screen.getByText("No saved items in this dashboard")).toBeTruthy();
    expect(screen.getByText("No next actions")).toBeTruthy();
    expect(screen.queryByText("Trust tier:")).toBeNull();
  });
});
