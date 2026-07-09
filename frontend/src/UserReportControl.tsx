import { useState, type FormEvent } from "react";
import { submitUserReport } from "./api";
import { isPublicDemoMode } from "./demoMode";
import { ExceptionStatusBadge } from "./TrustExplanation";
import type {
  ExceptionSubjectStatus,
  ReportRecheckStatus,
  UserReportSeverity,
  UserReportSubmissionResult,
  UserReportType,
} from "./types";

type UserReportControlProps = {
  subjectType: string;
  subjectId: string;
  sourceSurface: string;
  initialStatus?: ReportRecheckStatus | null;
  exceptionStatus?: ExceptionSubjectStatus | null;
};

const REPORT_TYPES: { label: string; value: UserReportType }[] = [
  { label: "Outdated", value: "outdated" },
  { label: "Incorrect", value: "incorrect" },
  { label: "Duplicate", value: "duplicate" },
  { label: "Spam", value: "spam" },
  { label: "Misleading", value: "misleading" },
  { label: "Expired opportunity", value: "expired_opportunity" },
  { label: "Wrong company", value: "wrong_company" },
  { label: "Wrong region", value: "wrong_region" },
  { label: "Suspicious ranking", value: "suspicious_ranking" },
  { label: "Other", value: "other" },
];

export default function UserReportControl({
  initialStatus = null,
  exceptionStatus = null,
  sourceSurface,
  subjectId,
  subjectType,
}: UserReportControlProps) {
  const publicDemoMode = isPublicDemoMode();
  const [reportType, setReportType] = useState<UserReportType>("outdated");
  const [severity, setSeverity] = useState<UserReportSeverity>("medium");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<UserReportSubmissionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const status = result?.status ?? initialStatus ?? null;
  const safeExceptionStatus =
    result?.status.exception_status ?? status?.exception_status ?? exceptionStatus;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (publicDemoMode) return;
    setSubmitting(true);
    setError(null);
    try {
      const envelope = await submitUserReport({
        subject_type: subjectType,
        subject_id: subjectId,
        report_type: reportType,
        report_reason: reason.trim() || null,
        severity,
        source_surface: sourceSurface,
      });
      setResult(envelope.data);
      setReason("");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Report could not be submitted");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="user-report-control" aria-label="Report information issue">
      <div>
        <strong>Report information issue</strong>
        <p className="meta-copy">
          Reports are signals for automated recheck. They do not directly change
          truth, trust labels, rankings, or ranking influence.
        </p>
      </div>
      {publicDemoMode ? (
        <div className="notice-state">
          <strong>Reports are disabled in public demo</strong>
          <p>Public demo remains read-only and does not store report signals.</p>
        </div>
      ) : (
        <form className="user-report-form" onSubmit={onSubmit}>
          <label>
            Report type
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value as UserReportType)}
            >
              {REPORT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Severity
            <select
              value={severity}
              onChange={(event) => setSeverity(event.target.value as UserReportSeverity)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <label className="wide-field">
            Optional reason
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button className="secondary-button" disabled={submitting} type="submit">
            {submitting ? "Submitting report" : "Submit report"}
          </button>
        </form>
      )}
      {result ? (
        <div className="notice-state">
          <strong>Report received</strong>
          <p>{result.message}</p>
        </div>
      ) : null}
      {status ? <ReportRecheckStatusView status={status} /> : null}
      {safeExceptionStatus ? (
        <div className="report-recheck-status">
          <ExceptionStatusBadge status={safeExceptionStatus} />
          <p className="meta-copy">{safeExceptionStatus.message}</p>
        </div>
      ) : null}
      {error ? (
        <div className="error-state">
          <strong>Report unavailable</strong>
          <p>{error}</p>
        </div>
      ) : null}
    </section>
  );
}

export function ReportRecheckStatusView({ status }: { status: ReportRecheckStatus }) {
  return (
    <div className="report-recheck-status">
      <div className="badge-stack">
        {status.latest_report_status ? (
          <span className="badge badge-unknown">
            Report: {displayLabel(status.latest_report_status)}
          </span>
        ) : null}
        {status.recheck_status_label ? (
          <span className="badge badge-warning">{status.recheck_status_label}</span>
        ) : null}
        {status.recheck_outcome ? (
          <span className="badge">Outcome: {displayLabel(status.recheck_outcome)}</span>
        ) : null}
      </div>
      <p className="meta-copy">{status.message}</p>
    </div>
  );
}

function displayLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}
