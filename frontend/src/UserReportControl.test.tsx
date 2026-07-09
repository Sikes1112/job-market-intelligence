// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import UserReportControl from "./UserReportControl";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", warnings: [] },
    error: null,
  };
}

function reportResponse() {
  return {
    report: {
      user_report_id: "report_1",
      subject_type: "opportunity",
      subject_id: "opp_1",
      report_type: "outdated",
      report_reason: "Looks stale.",
      reporter_user_id: null,
      reporter_session_id: null,
      severity: "medium",
      status: "queued_for_recheck",
      source_surface: "test_surface",
      related_trust_assessment_id: null,
      related_risk_routing_decision_id: null,
      created_recheck_job_id: "recheck_1",
      created_at: "2026-07-08T12:00:00Z",
      updated_at: "2026-07-08T12:00:00Z",
      resolved_at: null,
    },
    recheck_job: {
      automated_recheck_job_id: "recheck_1",
      subject_type: "opportunity",
      subject_id: "opp_1",
      trigger_type: "stale_source",
      trigger_source: "user_report",
      status: "queued",
      priority: "medium",
      reason_codes: ["reported_outdated"],
      related_user_report_id: "report_1",
      related_trust_assessment_id: null,
      related_risk_routing_decision_id: null,
      scheduled_for: null,
      started_at: null,
      completed_at: null,
      outcome: null,
      outcome_reason: null,
      attempts: 0,
      max_attempts: 3,
      last_error: null,
      created_at: "2026-07-08T12:00:00Z",
      updated_at: "2026-07-08T12:00:00Z",
    },
    status: {
      subject_type: "opportunity",
      subject_id: "opp_1",
      latest_report_status: "queued_for_recheck",
      latest_report_type: "outdated",
      latest_report_severity: "medium",
      latest_reported_at: "2026-07-08T12:00:00Z",
      active_recheck_job_id: "recheck_1",
      recheck_status: "queued",
      recheck_priority: "medium",
      recheck_outcome: null,
      recheck_status_label: "Recheck queued",
      exception_status: null as
        | {
            subject_type: string;
            subject_id: string;
            has_open_exception: boolean;
            exception_case_id: string | null;
            exception_type: string | null;
            status: string | null;
            severity: string | null;
            public_safe_status: string;
            label: string;
            message: string;
            updated_at: string | null;
            resolved_at: string | null;
          }
        | null,
      message: "Report received. Automated recheck is queued.",
    },
    message:
      "Report received. It may trigger an automated deterministic recheck; it does not directly change rankings or source data.",
  };
}

describe("UserReportControl", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  test("submits a report signal and renders backend status without mutation claims", async () => {
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () =>
      new Response(JSON.stringify(envelope(reportResponse())), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <UserReportControl
        sourceSurface="test_surface"
        subjectId="opp_1"
        subjectType="opportunity"
      />,
    );

    fireEvent.change(screen.getByLabelText("Report type"), {
      target: { value: "outdated" },
    });
    fireEvent.change(screen.getByLabelText("Optional reason"), {
      target: { value: "Looks stale." },
    });
    fireEvent.click(screen.getByText("Submit report"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      subject_type: "opportunity",
      subject_id: "opp_1",
      report_type: "outdated",
      report_reason: "Looks stale.",
      severity: "medium",
      source_surface: "test_surface",
    });
    expect(await screen.findByText("Report received")).toBeTruthy();
    expect(screen.getByText("Recheck queued")).toBeTruthy();
    expect(screen.getByText(/does not directly change rankings/i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/corrected|reranked|approved/i);
  });

  test("renders initial backend report and recheck status", () => {
    const response = reportResponse();
    response.status.exception_status = {
      subject_type: "opportunity",
      subject_id: "opp_1",
      has_open_exception: true,
      exception_case_id: "exception_1",
      exception_type: "fraud_spam",
      status: "blocked",
      severity: "critical",
      public_safe_status: "blocked",
      label: "Blocked",
      message: "This item is blocked because unresolved critical risk signals remain.",
      updated_at: "2026-07-08T12:00:00Z",
      resolved_at: null,
    };

    render(
      <UserReportControl
        initialStatus={response.status}
        sourceSurface="test_surface"
        subjectId="opp_1"
        subjectType="opportunity"
      />,
    );

    expect(screen.getByText("Report: queued for recheck")).toBeTruthy();
    expect(screen.getByText("Recheck queued")).toBeTruthy();
    expect(screen.getByText("Exception: Blocked")).toBeTruthy();
    expect(screen.getByText("Report received. Automated recheck is queued.")).toBeTruthy();
    expect(screen.getByText(/critical risk signals remain/i)).toBeTruthy();
  });

  test("public demo renders disabled state and does not submit", () => {
    const fetchMock = vi.fn();
    vi.stubEnv("VITE_PUBLIC_DEMO", "true");
    vi.stubGlobal("fetch", fetchMock);

    render(
      <UserReportControl
        sourceSurface="test_surface"
        subjectId="opp_1"
        subjectType="opportunity"
      />,
    );

    expect(screen.getByText("Reports are disabled in public demo")).toBeTruthy();
    expect(screen.queryByText("Submit report")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
