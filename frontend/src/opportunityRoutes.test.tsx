// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import OpportunityRoutesPage from "./OpportunityRoutesPage";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function routePayload() {
  return {
    route_count: 1,
    route_generation_note: "Routes are grouped strategic recommendations.",
    non_goal_disclosures: [
      "No scraping was performed.",
      "Paid partner status does not boost route or opportunity fit scores.",
    ],
    routes: [
      {
        route_id: "route_boston_software",
        route_title: "Greater Boston Software Engineering route",
        target_region: "greater_boston",
        target_role_family: "software_engineering",
        recommended_company_types: ["Software employers"],
        market_fit_score: 0.72,
        region_fit_score: 0.68,
        company_type_fit_score: 0.7,
        opportunity_fit_score: 0.89,
        role_family_fit_score: 0.85,
        overall_route_fit_score: 0.76,
        confidence: "high",
        explanation: "This route connects the profile to software engineering in Greater Boston.",
        warnings: ["Partner-submitted records remain labeled in matched programs."],
        next_steps: [
          "Review the route explanation against your region, role-family, and location preferences.",
          "Open matched program source pages manually and verify eligibility, deadline, and location details.",
        ],
        source_summary: {
          data_basis: "stored_market_intelligence_and_trusted_opportunity_records",
          source_categories: [
            "region_market_scores",
            "opportunity_records",
            "review_derived_trust_state",
          ],
          source_count: 3,
          notes: ["Objective intelligence scores are read-only context."],
        },
        sponsored_or_partner_disclosure:
          "Some attached opportunities are partner-submitted or paid partner records. Disclosure is shown per program, and paid status does not affect scoring.",
        matched_opportunities: [
          {
            opportunity_id: "opp_demo",
            employer_name: "Company A",
            program_name: "Platform Internship",
            program_type: "internship",
            region: "Greater Boston",
            metro: "Boston-Cambridge",
            role_family: "software_engineering",
            location_mode: "hybrid",
            trust_label: "verified",
            review_status: "approved",
            expiration_state: "active",
            partner_submitted: true,
            paid_partner: true,
            application_url: "https://example.com/apply",
            source_url: "https://example.com/source",
            fit_score: 0.89,
            fit_explanation: "Fit is based on region binding, role-family binding, and verified trust.",
            warnings: [
              "Partner-submitted metadata is preserved in this route.",
              "Paid partner relationship disclosed; paid status did not affect fit.",
            ],
            trust_tier: "partner_submitted",
            risk_level: "medium",
            routing_outcome: "visible_with_warning",
            ranking_influence_allowed: false,
            ranking_influence_decision: "denied",
            ranking_influence_reason:
              "Partner-submitted items are visible for awareness but excluded from rankings until stronger independent evidence is available.",
            ranking_influence_reason_codes: ["partner_submitted_not_verified"],
            trust_explanation: {
              subject_type: "opportunity",
              subject_id: "opp_demo",
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
              explanation_version: "30C",
            },
          },
        ],
      },
    ],
  };
}

describe("OpportunityRoutesPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  test("renders route cards, explanations, trust labels, warnings, and next steps", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(envelope(routePayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<OpportunityRoutesPage />);

    expect(await screen.findByText("Recommended Opportunity Routes")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/opportunities/routes",
      expect.objectContaining({ method: "POST" }),
    ));

    expect(screen.getByText("Greater Boston Software Engineering route")).toBeTruthy();
    expect(screen.getByText(/This route connects the profile/i)).toBeTruthy();
    expect(screen.getByText("Platform Internship")).toBeTruthy();
    expect(screen.getByText("verified")).toBeTruthy();
    expect(screen.getByText("Paid partner disclosed")).toBeTruthy();
    expect(screen.getByText("Trust: Partner-submitted")).toBeTruthy();
    expect(screen.getByText("Risk: Use with caution")).toBeTruthy();
    expect(screen.getByText("Excluded from rankings")).toBeTruthy();
    expect(screen.getByText("Report information issue")).toBeTruthy();
    expect(screen.getByText("Partner / paid disclosure")).toBeTruthy();
    expect(screen.getByText(/Partner-submitted records remain labeled/i)).toBeTruthy();
    expect(screen.getByText(/Open matched program source pages manually/i)).toBeTruthy();
    expect(screen.getByText("Source summary")).toBeTruthy();
  });

  test("does not render generic listing controls", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(envelope(routePayload())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    ));

    render(<OpportunityRoutesPage />);
    await screen.findByText("Greater Boston Software Engineering route");

    expect(screen.queryByText(/All jobs/i)).toBeNull();
    expect(screen.queryByText(/Search jobs/i)).toBeNull();
    expect(screen.queryByText(/Sort by newest/i)).toBeNull();
    expect(screen.queryByText(/Apply now/i)).toBeNull();
  });

  test("public-demo mode renders unavailable state without calling blocked route", () => {
    const fetchMock = vi.fn();
    vi.stubEnv("VITE_PUBLIC_DEMO", "true");
    vi.stubGlobal("fetch", fetchMock);

    render(<OpportunityRoutesPage />);

    expect(screen.getByText("Opportunity routes are not available in public demo")).toBeTruthy();
    expect(screen.getByText(/public-demo backend intentionally blocks opportunity routing/i)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
