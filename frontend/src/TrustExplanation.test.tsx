// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import {
  EvidenceExplanationPanel,
  ExceptionStatusBadge,
  RankingInfluenceBadge,
  RiskBadge,
  TrustBadge,
  TrustExplanationPanel,
} from "./TrustExplanation";
import type { TrustExplanation } from "./types";

function explanation(): TrustExplanation {
  return {
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
    evidence_requirements_met: [
      {
        code: "valid_fields",
        status: "met",
        message: "Required fields are present.",
        source: "test",
      },
    ],
    evidence_requirements_missing: [
      {
        code: "independent_verification",
        status: "missing",
        message: "Independent verification is missing.",
        source: "test",
      },
    ],
    evidence_requirements_failed: [
      {
        code: "ranking_evidence_sufficient",
        status: "failed",
        message: "Ranking evidence is not sufficient.",
        source: "test",
      },
    ],
    trust_warnings: [],
    user_facing_warnings: [
      {
        warning_code: "PARTNER_SUBMITTED_NOT_VERIFIED",
        severity: "info",
        title: "Partner-submitted",
        message: "This item has not been independently verified.",
      },
    ],
    last_checked_at: "2026-07-04T12:00:00Z",
    decided_at: "2026-07-04T12:00:00Z",
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
      updated_at: "2026-07-04T12:00:00Z",
      resolved_at: null,
    },
    explanation_version: "30C",
  };
}

describe("TrustExplanation components", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders backend-provided trust, risk, ranking, warning, and evidence copy", () => {
    render(<TrustExplanationPanel explanation={explanation()} />);

    expect(screen.getByText("Trust: Partner-submitted")).toBeTruthy();
    expect(screen.getByText("Risk: Use with caution")).toBeTruthy();
    expect(screen.getByText("Visible with warning")).toBeTruthy();
    expect(screen.getByText("Excluded from rankings")).toBeTruthy();
    expect(screen.getByText("Exception: Blocked")).toBeTruthy();
    expect(screen.getByText(/critical risk signals remain/i)).toBeTruthy();
    expect(screen.getByText(/visible for awareness/i)).toBeTruthy();
    expect(screen.getAllByText("Partner-submitted").length).toBeGreaterThan(0);
    expect(screen.getByText("Met 1")).toBeTruthy();
    expect(screen.getByText("Missing 1")).toBeTruthy();
    expect(screen.getByText("Failed 1")).toBeTruthy();
    expect(screen.getByText("valid fields")).toBeTruthy();
    expect(screen.getByText("independent verification")).toBeTruthy();
    expect(screen.getByText("ranking evidence sufficient")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/approve|reject|moderate/i);
  });

  test("renders badges from provided explanation payload only", () => {
    const payload = explanation();

    render(
      <>
        <TrustBadge explanation={payload} />
        <RiskBadge explanation={payload} />
        <RankingInfluenceBadge explanation={payload} />
        <ExceptionStatusBadge status={payload.exception_status} />
      </>,
    );

    expect(screen.getByText("Trust: Partner-submitted")).toBeTruthy();
    expect(screen.getByText("Risk: Use with caution")).toBeTruthy();
    expect(screen.getByText("Excluded from rankings")).toBeTruthy();
    expect(screen.getByText("Exception: Blocked")).toBeTruthy();
  });

  test("renders honest null states without inferred trust state", () => {
    render(
      <>
        <TrustBadge explanation={null} />
        <RiskBadge explanation={null} />
        <RankingInfluenceBadge explanation={null} />
        <TrustExplanationPanel explanation={null} />
        <EvidenceExplanationPanel explanation={null} />
      </>,
    );

    expect(screen.getByText("Trust: not available")).toBeTruthy();
    expect(screen.getByText("Risk: not available")).toBeTruthy();
    expect(screen.getByText("Ranking influence: not available")).toBeTruthy();
    expect(screen.getByText("Trust explanation unavailable")).toBeTruthy();
    expect(screen.getByText("Evidence explanation unavailable")).toBeTruthy();
  });
});
