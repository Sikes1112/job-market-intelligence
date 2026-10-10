import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  createCareerAction,
  createCareerActionPlan,
  createCareerApplication,
  getCareerDecision,
  getCareerDecisionJournal,
  getCurrentOpportunityMatches,
  getMySearchWorkspace,
  recordProductEvent,
  trackCurrentOpportunity,
  transitionCareerApplication,
  updateCareerAction,
  updateCareerDecision,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import type {
  CareerApplicationStatus,
  CareerDecision,
  CareerDecisionVersion,
  CurrentOpportunityMatchPayload,
  MySearchApplication,
  MySearchPursuit,
  MySearchWorkspace,
} from "./types";
import {
  decisionsUrl,
  exploreComparisonUrl,
  exploreUrl,
  mySearchApplicationUrl,
  mySearchPursuitUrl,
  mySearchUrl,
  savedExploreComparisonUrl,
} from "./urlState";

type Props = {
  auth: FrontendAuthContextValue;
  onNavigate: (url: string) => void;
  pursuitId?: string;
  applicationId?: string;
};

const APPLICATION_TRANSITIONS: Record<CareerApplicationStatus, CareerApplicationStatus[]> = {
  considering: ["preparing", "applied", "withdrawn"],
  preparing: ["applied", "withdrawn"],
  applied: ["response", "interview", "rejected", "withdrawn", "offer"],
  response: ["interview", "rejected", "withdrawn"],
  interview: ["final_round", "rejected", "withdrawn", "offer"],
  final_round: ["offer", "rejected", "withdrawn"],
  offer: ["accepted", "declined", "withdrawn"],
  rejected: [],
  withdrawn: [],
  accepted: [],
  declined: [],
};

const STATUS_LABELS: Record<CareerApplicationStatus, string> = {
  considering: "Considering",
  preparing: "Preparing",
  applied: "Applied",
  response: "Awaiting response",
  interview: "Interviewing",
  final_round: "Final round",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  offer: "Offer",
  accepted: "Accepted",
  declined: "Declined",
};

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function date(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Date not set";
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : "The request could not be completed.";
}

function safeExternalUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

export default function MySearchPage({ auth, onNavigate, pursuitId, applicationId }: Props) {
  const [workspace, setWorkspace] = useState<MySearchWorkspace | null>(null);
  const [decision, setDecision] = useState<CareerDecision | null>(null);
  const [journal, setJournal] = useState<CareerDecisionVersion[]>([]);
  const [matches, setMatches] = useState<CurrentOpportunityMatchPayload[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [showActionForm, setShowActionForm] = useState(false);
  const [showApplicationForm, setShowApplicationForm] = useState(false);
  const [actionTitle, setActionTitle] = useState("");
  const [actionDueAt, setActionDueAt] = useState("");
  const [manualApplication, setManualApplication] = useState({ company: "", role: "", location: "", url: "", status: "preparing" as CareerApplicationStatus });
  const actionInputRef = useRef<HTMLInputElement>(null);
  const applicationInputRef = useRef<HTMLInputElement>(null);
  const viewedRef = useRef(false);
  const protectedOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );

  const loadWorkspace = useCallback(async () => {
    if (!auth.isAuthenticated) { setLoading(false); return; }
    setLoading(true);
    try {
      const response = await getMySearchWorkspace(protectedOptions);
      setWorkspace(response.data);
      if (!viewedRef.current) {
        viewedRef.current = true;
        void recordProductEvent({
          event_type: "my_search_viewed",
          event_source: "frontend",
          product_surface: "my_search",
          payload: {
            active_pursuit_count: response.data?.active_pursuits.length ?? 0,
            application_count: response.data?.applications.length ?? 0,
          },
        }, protectedOptions).catch(() => undefined);
      }
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [auth.isAuthenticated, protectedOptions]);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    try {
      const [decisionResponse, journalResponse, matchResponse] = await Promise.all([
        getCareerDecision(id, protectedOptions),
        getCareerDecisionJournal(id, protectedOptions),
        getCurrentOpportunityMatches({ decision_id: id, include_ineligible: false, limit: 6 }, protectedOptions),
      ]);
      setDecision(decisionResponse.data?.decision ?? null);
      setJournal(journalResponse.data?.journal ?? []);
      setMatches(matchResponse.data?.matches ?? []);
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setDetailLoading(false);
    }
  }, [protectedOptions]);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);
  useEffect(() => {
    if (pursuitId && auth.isAuthenticated) void loadDetail(pursuitId);
    else { setDecision(null); setJournal([]); setMatches([]); }
  }, [auth.isAuthenticated, loadDetail, pursuitId]);
  useEffect(() => { if (showActionForm) actionInputRef.current?.focus(); }, [showActionForm]);
  useEffect(() => { if (showApplicationForm) applicationInputRef.current?.focus(); }, [showApplicationForm]);

  const selectedPursuit = workspace?.active_pursuits.find((item) => item.decision_id === pursuitId) ?? null;
  const selectedApplication = workspace?.applications.find((item) => item.application_id === applicationId) ?? null;

  async function refresh(message?: string) {
    await loadWorkspace();
    if (pursuitId) await loadDetail(pursuitId);
    if (message) setAnnouncement(message);
  }

  async function setActionStatus(actionId: string, status: "completed" | "open") {
    setBusy(actionId);
    setError(null);
    try {
      await updateCareerAction(actionId, { status }, protectedOptions);
      await refresh(status === "completed" ? "Action completed. Your next action is ready." : "Action reopened.");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function submitAction(event: FormEvent) {
    event.preventDefault();
    if (!pursuitId || !actionTitle.trim()) return;
    setBusy("new-action");
    try {
      await createCareerAction(pursuitId, {
        action_type: "other",
        title: actionTitle.trim(),
        due_at: actionDueAt ? new Date(`${actionDueAt}T12:00:00`).toISOString() : null,
      }, protectedOptions);
      setActionTitle(""); setActionDueAt(""); setShowActionForm(false);
      await refresh("Action added.");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function generateNextSteps() {
    if (!selectedPursuit) return;
    const focus = selectedPursuit.selected_priority.title;
    setBusy("generate-actions");
    try {
      await createCareerActionPlan(selectedPursuit.decision_id, {
        title: `${focus} next steps`,
        actions: [
          { action_type: "research", title: `Review current ${focus} opportunities`, priority: 1 },
          { action_type: "company_targeting", title: `Choose 10 target employers for ${focus}`, priority: 2 },
          { action_type: "preparation", title: `Prepare application materials for ${focus}`, priority: 3 },
        ],
      }, protectedOptions);
      await refresh("Next steps added to this pursuit.");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function track(opportunityId: string) {
    if (!pursuitId) return;
    setBusy(opportunityId);
    try {
      const response = await trackCurrentOpportunity({ decision_id: pursuitId, opportunity_id: opportunityId, initial_status: "preparing" }, protectedOptions);
      const result = response.data;
      await refresh(result?.created ? "Application tracking started. It is marked Preparing, not Applied." : "This opportunity is already being tracked.");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function submitManualApplication(event: FormEvent) {
    event.preventDefault();
    if (!pursuitId || !manualApplication.company.trim() || !manualApplication.role.trim()) return;
    setBusy("manual-application");
    try {
      await createCareerApplication({
        decision_id: pursuitId,
        option_id: selectedPursuit?.selected_priority.option_id,
        role_title: manualApplication.role.trim(),
        status: manualApplication.status,
        source_url: manualApplication.url.trim() || null,
        metadata: { company_name: manualApplication.company.trim(), location_text: manualApplication.location.trim() || null, source: "manual" },
      }, protectedOptions);
      setManualApplication({ company: "", role: "", location: "", url: "", status: "preparing" });
      setShowApplicationForm(false);
      await refresh("Application added. Its status was not advanced beyond your selection.");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function transitionApplication(application: MySearchApplication, toStatus: CareerApplicationStatus) {
    setBusy(application.application_id);
    try {
      await transitionCareerApplication(application.application_id, { to_status: toStatus }, protectedOptions);
      await refresh(`Application status changed to ${STATUS_LABELS[toStatus]}.`);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  async function closePursuit() {
    if (!pursuitId) return;
    setBusy("close-pursuit");
    try {
      await updateCareerDecision(pursuitId, { status: "completed", user_note: "Closed from My Search." }, protectedOptions);
      await refresh("Pursuit closed. Its history and applications were preserved.");
      onNavigate(mySearchUrl());
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <div className="product-empty" role="status">Loading My Search…</div>;
  if (!auth.isAuthenticated) return <div className="product-empty"><h1>My Search</h1><p>Sign in to manage your active search.</p><button onClick={() => void auth.login()} type="button">Sign in</button></div>;
  if (!workspace) return <div className="product-empty"><h1>My Search</h1><p role="alert">{error ?? "Your search workspace is unavailable."}</p><button onClick={() => void loadWorkspace()} type="button">Try again</button></div>;
  if (applicationId) return <ApplicationDetail announcement={announcement} application={selectedApplication} busy={busy} error={error} onBack={() => onNavigate(selectedApplication?.decision_id ? mySearchPursuitUrl(selectedApplication.decision_id) : mySearchUrl())} onTransition={transitionApplication} />;
  if (pursuitId) return <PursuitDetail announcement={announcement} pursuit={selectedPursuit} decision={decision} journal={journal} matches={matches} loading={detailLoading} busy={busy} error={error} showActionForm={showActionForm} showApplicationForm={showApplicationForm} actionTitle={actionTitle} actionDueAt={actionDueAt} manualApplication={manualApplication} actionInputRef={actionInputRef} applicationInputRef={applicationInputRef} onNavigate={onNavigate} onActionStatus={setActionStatus} onActionTitle={setActionTitle} onActionDueAt={setActionDueAt} onManualApplication={setManualApplication} onShowAction={setShowActionForm} onShowApplication={setShowApplicationForm} onSubmitAction={submitAction} onGenerate={generateNextSteps} onTrack={track} onSubmitApplication={submitManualApplication} onTransition={transitionApplication} onClose={closePursuit} />;

  const attention = workspace.applications.filter((item) => item.needs_attention);
  return (
    <div className="my-search-page my-search-workspace">
      <p aria-live="polite" className="sr-only">{announcement}</p>
      <header className="my-search-hero"><p className="eyebrow">What you’re pursuing and what to do next</p><h1>My Search</h1><p>Active priorities and execution state from your Decisions, actions, and applications.</p></header>
      {error ? <p className="explore-error" role="alert">{error}</p> : null}
      {!workspace.active_pursuits.length && !workspace.saved_comparisons.length && !workspace.saved_items.length ? <section className="my-search-empty-state"><h2>Nothing active yet.</h2><p>Explore markets to find where you want to focus.</p><button onClick={() => onNavigate(exploreUrl())} type="button">Explore markets</button></section> : null}

      <section aria-labelledby="active-pursuits-heading" className="my-search-section my-search-primary-section">
        <div className="my-search-section-heading"><div><p className="eyebrow">Active</p><h2 id="active-pursuits-heading">Active priorities</h2></div><span>{workspace.active_pursuits.length}</span></div>
        {workspace.active_pursuits.length ? <div className="pursuit-grid">{workspace.active_pursuits.map((pursuit) => <ActivePursuitCard key={pursuit.decision_id} pursuit={pursuit} busy={busy} onComplete={setActionStatus} onOpen={() => onNavigate(mySearchPursuitUrl(pursuit.decision_id))} />)}</div> : <div className="my-search-empty"><p>No active priorities. Saved research remains below until you choose what to pursue.</p><button onClick={() => onNavigate(exploreUrl())} type="button">Explore markets</button></div>}
      </section>

      <section aria-labelledby="applications-heading" className="my-search-section">
        <div className="my-search-section-heading"><div><p className="eyebrow">In motion</p><h2 id="applications-heading">Applications requiring attention</h2></div><span>{attention.length}</span></div>
        {attention.length ? <div className="application-card-list">{attention.slice(0, 6).map((application) => <ApplicationCard application={application} key={application.application_id} onOpen={() => onNavigate(mySearchApplicationUrl(application.application_id))} />)}</div> : <p className="section-empty-copy">No applications need action right now.</p>}
      </section>

      <section aria-labelledby="saved-heading" className="my-search-section my-search-secondary-section">
        <div className="my-search-section-heading"><div><p className="eyebrow">Saved</p><h2 id="saved-heading">Saved for later</h2></div><span>{workspace.saved_comparisons.length + workspace.saved_items.length}</span></div>
        {workspace.saved_comparisons.length ? <ul className="saved-research-list">{workspace.saved_comparisons.map((item) => <li key={item.comparison_id}><button onClick={() => onNavigate(savedExploreComparisonUrl(item.comparison_id))} type="button"><strong>{item.market_names.join(" vs ")}</strong><small>{pretty(item.recommendation_state)} · saved {date(item.saved_at)}</small><span>{item.context_summary}</span></button></li>)}</ul> : null}
        {workspace.saved_items.length ? <ul className="saved-item-row">{workspace.saved_items.map((item) => <li key={item.saved_artifact_id}><button onClick={() => onNavigate(item.artifact_type === "region" ? exploreUrl({ focus: item.public_slug ?? item.artifact_ref }) : exploreUrl())} type="button">{item.label ?? item.display_name ?? pretty(item.artifact_ref)}<small>{pretty(item.artifact_type)}</small></button></li>)}</ul> : null}
        {!workspace.saved_comparisons.length && !workspace.saved_items.length ? <p className="section-empty-copy">No saved research yet.</p> : null}
      </section>

      <section aria-labelledby="history-heading" className="my-search-section my-search-secondary-section">
        <div className="my-search-section-heading"><div><p className="eyebrow">History</p><h2 id="history-heading">Recent progress</h2></div></div>
        {workspace.history.length ? <ol className="search-history-list">{workspace.history.slice(0, 10).map((item) => <li key={item.history_id}><span aria-hidden="true" className="history-marker" /><div><strong>{item.title}</strong>{item.detail ? <span>{item.detail}</span> : null}<time dateTime={item.occurred_at}>{date(item.occurred_at)}</time></div></li>)}</ol> : <p className="section-empty-copy">Meaningful progress will appear here as you work your search.</p>}
      </section>
    </div>
  );
}

function ActivePursuitCard({ pursuit, busy, onComplete, onOpen }: { pursuit: MySearchPursuit; busy: string | null; onComplete: (id: string, status: "completed") => void; onOpen: () => void }) {
  const source = pursuit.source_comparison;
  const recommendation = source?.system_recommendation.join(" · ");
  const reason = source?.current_choice_matches_recommendation === false
    ? `You currently prioritize ${source.current_user_choice}; the original comparison favored ${recommendation || "another market"}.`
    : source?.current_choice_matches_recommendation === true
      ? `You currently prioritize ${source.current_user_choice}. The original comparison also favored ${recommendation || source.current_user_choice}.`
      : source?.recommendation_state === "near_tie"
        ? `You currently prioritize ${source.current_user_choice} from a near tie.`
        : `You currently prioritize ${source?.current_user_choice}.`;
  return <article className="active-pursuit-card"><div className="pursuit-card-top"><div><p className="eyebrow">{pursuit.target_context ?? pretty(pursuit.decision_type)}</p><h3>{pursuit.selected_priority.title}</h3></div><span className="status-chip">{pretty(pursuit.status)}</span></div><p className="pursuit-date">Prioritized {date(pursuit.prioritized_at)}</p>{source ? <p className="pursuit-reason">{reason}</p> : null}{pursuit.alternatives.length ? <p className="pursuit-alternatives"><span>Compared with</span>{pursuit.alternatives.map((item) => item.title).join(" · ")}</p> : null}<div className="next-action-block"><span>Next action</span>{pursuit.next_action ? <label><input checked={false} disabled={busy === pursuit.next_action.action_id} onChange={() => void onComplete(pursuit.next_action!.action_id, "completed")} type="checkbox" /><strong>{pursuit.next_action.title}</strong>{pursuit.next_action.due_at ? <small>Due {date(pursuit.next_action.due_at)}</small> : null}</label> : <p>No next action yet.</p>}</div><div className="pursuit-stats"><span>{pursuit.active_application_count} active application{pursuit.active_application_count === 1 ? "" : "s"}</span><span>{pursuit.current_opportunities.coverage_status === "unsupported" ? "Opportunity coverage unavailable" : `${pursuit.current_opportunities.ranking_eligible_count} current matches`}</span></div><button className="pursuit-open-button" onClick={onOpen} type="button">Open pursuit</button></article>;
}

type PursuitDetailProps = {
  announcement: string;
  pursuit: MySearchPursuit | null; decision: CareerDecision | null; journal: CareerDecisionVersion[]; matches: CurrentOpportunityMatchPayload[]; loading: boolean; busy: string | null; error: string | null;
  showActionForm: boolean; showApplicationForm: boolean; actionTitle: string; actionDueAt: string; manualApplication: { company: string; role: string; location: string; url: string; status: CareerApplicationStatus };
  actionInputRef: React.RefObject<HTMLInputElement | null>; applicationInputRef: React.RefObject<HTMLInputElement | null>; onNavigate: (url: string) => void; onActionStatus: (id: string, status: "completed" | "open") => void; onActionTitle: (value: string) => void; onActionDueAt: (value: string) => void; onManualApplication: (value: PursuitDetailProps["manualApplication"]) => void; onShowAction: (value: boolean) => void; onShowApplication: (value: boolean) => void; onSubmitAction: (event: FormEvent) => void; onGenerate: () => void; onTrack: (id: string) => void; onSubmitApplication: (event: FormEvent) => void; onTransition: (application: MySearchApplication, status: CareerApplicationStatus) => void; onClose: () => void;
};

function PursuitDetail(props: PursuitDetailProps) {
  const { pursuit, decision } = props;
  if (props.loading && !pursuit) return <div className="product-empty" role="status">Loading pursuit…</div>;
  if (!pursuit) return <div className="product-empty"><h1>Pursuit not found</h1><p>This pursuit is closed, unavailable, or does not belong to your account.</p><button onClick={() => props.onNavigate(mySearchUrl())} type="button">Back to My Search</button></div>;
  const actions = decision?.action_plan?.actions ?? [];
  const source = pursuit.source_comparison;
  const compareAgain = [pursuit.selected_priority, ...pursuit.alternatives].map((item) => item.public_slug).filter((value): value is string => Boolean(value));
  return <div className="pursuit-detail-page"><p aria-live="polite" className="sr-only">{props.announcement}</p><nav aria-label="Breadcrumb"><button className="text-button" onClick={() => props.onNavigate(mySearchUrl())} type="button">My Search</button><span aria-hidden="true">/</span><span>{pursuit.selected_priority.title}</span></nav>{props.error ? <p className="explore-error" role="alert">{props.error}</p> : null}<header className="pursuit-detail-hero"><div><p className="eyebrow">Active pursuit · {pursuit.target_context ?? pretty(pursuit.decision_type)}</p><h1>{pursuit.selected_priority.title}</h1><p>{source?.recommendation_summary ?? "This priority is backed by your durable Decision and remains active until you close it."}</p></div><div><button className="secondary-button" onClick={() => props.onNavigate(decisionsUrl(pursuit.decision_id))} type="button">Advanced Decision view</button><button className="danger-secondary-button" disabled={props.busy === "close-pursuit"} onClick={() => void props.onClose()} type="button">Close pursuit</button></div></header>
    {source ? <section className="pursuit-detail-section source-comparison-panel"><div className="section-title-row"><div><p className="eyebrow">Decision context</p><h2>Source comparison</h2></div><button onClick={() => props.onNavigate(savedExploreComparisonUrl(source.comparison_id))} type="button">View source comparison</button></div><dl><div><dt>Current priority</dt><dd>{source.current_user_choice}</dd></div>{source.original_user_choice !== source.current_user_choice ? <div><dt>Original priority</dt><dd>{source.original_user_choice}</dd></div> : null}<div><dt>System recommendation</dt><dd>{source.system_recommendation.join(" · ") || "No winner named"}</dd></div><div><dt>Compared markets</dt><dd>{source.compared_markets.join(" · ")}</dd></div></dl>{source.current_choice_matches_recommendation === false ? <p className="honest-choice-note">You currently prioritize {source.current_user_choice}. The original comparison favored {source.system_recommendation.join(" · ") || "another market"}. That is a user decision, not an error.</p> : source.original_user_choice !== source.current_user_choice ? <p className="honest-choice-note">Your current priority now matches the original comparison. You originally prioritized {source.original_user_choice}.</p> : null}{compareAgain.length >= 2 ? <button className="text-button" onClick={() => props.onNavigate(exploreComparisonUrl({ selected: compareAgain }))} type="button">Compare again with current evidence</button> : null}</section> : null}
    <section className="pursuit-detail-section"><div className="section-title-row"><div><p className="eyebrow">Execution</p><h2>Next actions</h2></div><div><button className="secondary-button" onClick={() => props.onShowAction(!props.showActionForm)} type="button">Add action</button>{!actions.length ? <button disabled={props.busy === "generate-actions"} onClick={() => void props.onGenerate()} type="button">Generate next steps</button> : null}</div></div>{props.showActionForm ? <form className="inline-action-form" onSubmit={props.onSubmitAction}><label>Action title<input ref={props.actionInputRef} required value={props.actionTitle} onChange={(event) => props.onActionTitle(event.target.value)} placeholder={`Review ${pursuit.selected_priority.title} openings`} /></label><label>Due date (optional)<input type="date" value={props.actionDueAt} onChange={(event) => props.onActionDueAt(event.target.value)} /></label><button disabled={props.busy === "new-action"} type="submit">Add action</button></form> : null}{actions.length ? <ul className="action-list">{actions.map((action) => <li className={action.status === "completed" ? "action-completed" : ""} key={action.action_id}><label><input checked={action.status === "completed"} disabled={props.busy === action.action_id} onChange={() => void props.onActionStatus(action.action_id, action.status === "completed" ? "open" : "completed")} type="checkbox" /><span><strong>{action.title}</strong><small>{pretty(action.action_type)}{action.due_at ? ` · Due ${date(action.due_at)}` : ""} · {pretty(action.status)}</small></span></label></li>)}</ul> : <p className="section-empty-copy">No next action is required by the system. Add one or generate concrete starting steps.</p>}</section>
    <section className="pursuit-detail-section"><div className="section-title-row"><div><p className="eyebrow">Current opportunity inventory</p><h2>Current opportunities</h2></div></div><div className={`coverage-callout coverage-${pursuit.current_opportunities.coverage_status}`}><strong>{pretty(pursuit.current_opportunities.coverage_status)} coverage</strong><span>{pursuit.current_opportunities.coverage_rationale}</span>{pursuit.current_opportunities.coverage_limitations.map((item) => <small key={item}>{item}</small>)}</div>{props.matches.length ? <div className="opportunity-track-list">{props.matches.map(({ opportunity, strategic_relevance }) => <article key={opportunity.opportunity_id}><div><span>{pretty(strategic_relevance)}</span><h3>{opportunity.normalized_title}</h3><p>{opportunity.company_name} · {opportunity.market_label ?? opportunity.location_text ?? "Location unavailable"}</p><small>{pretty(opportunity.freshness_state)} · {pretty(opportunity.coverage_status)}</small></div><div><button disabled={props.busy === opportunity.opportunity_id} onClick={() => void props.onTrack(opportunity.opportunity_id)} type="button">Apply and track</button>{safeExternalUrl(opportunity.application_url) ? <a href={safeExternalUrl(opportunity.application_url)!} rel="noopener noreferrer" target="_blank">Open application site <span className="sr-only">(does not mark applied)</span></a> : null}</div></article>)}</div> : <p className="section-empty-copy">No current matching opportunities are available for this pursuit. This does not change or remove the priority.</p>}</section>
    <section className="pursuit-detail-section"><div className="section-title-row"><div><p className="eyebrow">Your tracking state</p><h2>Applications</h2></div><button onClick={() => props.onShowApplication(!props.showApplicationForm)} type="button">Add application</button></div>{props.showApplicationForm ? <form className="manual-application-form" onSubmit={props.onSubmitApplication}><label>Company<input ref={props.applicationInputRef} required value={props.manualApplication.company} onChange={(event) => props.onManualApplication({ ...props.manualApplication, company: event.target.value })} /></label><label>Role<input required value={props.manualApplication.role} onChange={(event) => props.onManualApplication({ ...props.manualApplication, role: event.target.value })} /></label><label>Location (optional)<input value={props.manualApplication.location} onChange={(event) => props.onManualApplication({ ...props.manualApplication, location: event.target.value })} /></label><label>Application URL (optional)<input inputMode="url" value={props.manualApplication.url} onChange={(event) => props.onManualApplication({ ...props.manualApplication, url: event.target.value })} /></label><label>Status<select value={props.manualApplication.status} onChange={(event) => props.onManualApplication({ ...props.manualApplication, status: event.target.value as CareerApplicationStatus })}><option value="considering">Considering</option><option value="preparing">Preparing</option><option value="applied">Applied</option></select></label><button disabled={props.busy === "manual-application"} type="submit">Track application</button></form> : null}{pursuit.applications.length ? <div className="application-card-list">{pursuit.applications.map((application) => <ApplicationCard application={application} key={application.application_id} onOpen={() => props.onNavigate(mySearchApplicationUrl(application.application_id))} onTransition={props.onTransition} busy={props.busy} />)}</div> : <p className="section-empty-copy">No applications tracked under this pursuit yet.</p>}</section>
    <section className="pursuit-detail-section"><div className="section-title-row"><div><p className="eyebrow">Progress</p><h2>Notes and history</h2></div><button className="secondary-button" onClick={() => props.onNavigate(decisionsUrl(pursuit.decision_id))} type="button">Analyze deeper</button></div>{props.journal.length ? <ol className="compact-journal">{props.journal.slice(-8).reverse().map((item) => <li key={item.decision_version_id}><strong>{pretty(item.version_reason)}</strong><span>{date(item.created_at)}</span>{item.user_note ? <p>{item.user_note}</p> : null}</li>)}</ol> : <p className="section-empty-copy">No Decision history is available.</p>}</section>
  </div>;
}

function ApplicationCard({ application, onOpen, onTransition, busy }: { application: MySearchApplication; onOpen: () => void; onTransition?: (application: MySearchApplication, status: CareerApplicationStatus) => void; busy?: string | null }) {
  const next = APPLICATION_TRANSITIONS[application.status];
  return <article className="application-card"><button className="application-main" onClick={onOpen} type="button"><span className={`application-status application-status-${application.status}`}>{STATUS_LABELS[application.status]}</span><strong>{application.company_name}</strong><span>{application.role_title}{application.market_name ? ` · ${application.market_name}` : ""}</span>{application.attention_reason ? <small className="attention-label">{application.attention_reason}</small> : null}</button>{onTransition && next.length ? <label className="application-transition-label">Update status<select aria-label={`Update ${application.company_name} application status`} disabled={busy === application.application_id} value="" onChange={(event) => { if (event.target.value) onTransition(application, event.target.value as CareerApplicationStatus); }}><option value="">Choose…</option>{next.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}</select></label> : null}</article>;
}

function ApplicationDetail({ announcement, application, busy, error, onBack, onTransition }: { announcement: string; application: MySearchApplication | null; busy: string | null; error: string | null; onBack: () => void; onTransition: (application: MySearchApplication, status: CareerApplicationStatus) => void }) {
  if (!application) return <div className="product-empty"><h1>Application not found</h1><p>It may be closed, unavailable, or owned by another account.</p><button onClick={onBack} type="button">Back to My Search</button></div>;
  const external = safeExternalUrl(application.source_url);
  return <div className="application-detail-page"><p aria-live="polite" className="sr-only">{announcement}</p><button className="text-button" onClick={onBack} type="button">← Back to pursuit</button>{error ? <p className="explore-error" role="alert">{error}</p> : null}<header><p className="eyebrow">Application</p><h1>{application.role_title}</h1><p>{application.company_name}{application.market_name ? ` · ${application.market_name}` : ""}</p><span className={`application-status application-status-${application.status}`}>{STATUS_LABELS[application.status]}</span></header><section><h2>Tracking</h2><dl><div><dt>Current status</dt><dd>{STATUS_LABELS[application.status]}</dd></div><div><dt>Started tracking</dt><dd>{date(application.created_at)}</dd></div><div><dt>Applied</dt><dd>{application.applied_at ? date(application.applied_at) : "Not confirmed"}</dd></div><div><dt>Next follow-up</dt><dd>{application.follow_up_at ? date(application.follow_up_at) : "Not scheduled"}</dd></div></dl>{APPLICATION_TRANSITIONS[application.status].length ? <label>Update application status<select aria-label="Update application status" disabled={busy === application.application_id} value="" onChange={(event) => { if (event.target.value) void onTransition(application, event.target.value as CareerApplicationStatus); }}><option value="">Choose a valid next status…</option>{APPLICATION_TRANSITIONS[application.status].map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}</select></label> : <p>This application is in a terminal state.</p>}{external ? <div className="external-apply-note"><a href={external} rel="noopener noreferrer" target="_blank">Open application site</a><small>Opening this link does not mark the application Applied. Confirm that explicitly above after submitting.</small></div> : null}</section></div>;
}
