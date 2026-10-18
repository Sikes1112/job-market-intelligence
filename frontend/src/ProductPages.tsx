import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ApiError,
  createCareerIdentityFact,
  deleteCareerIdentityFact,
  getCareerIdentity,
  initializeCareerIdentity,
  updateCareerIdentityPrivacy,
  updateCareerIdentityFact,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import type { CareerIdentity, CareerIdentityFact } from "./types";
import { exploreUrl } from "./urlState";

export { default as MySearchPage } from "./MySearchPage";

type CommonProps = { auth: FrontendAuthContextValue; onNavigate: (url: string) => void };

function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : "The request could not be completed.";
}
function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function factText(fact: CareerIdentityFact): string {
  const preferred = ["description", "role_title", "function", "employment_type", "seniority", "arrangement", "location", "industry", "name", "title", "institution"];
  const values = preferred.flatMap((key) => {
    const value = fact.payload[key];
    return typeof value === "string" ? [pretty(value)] : Array.isArray(value) ? value.map(String).map(pretty) : [];
  });
  return Array.from(new Set(values)).slice(0, 4).join(" · ") || pretty(fact.normalized_key);
}

function facts(identity: CareerIdentity | null, types: Array<keyof CareerIdentity["facts"]>): CareerIdentityFact[] {
  return types.flatMap((type) => identity?.facts[type] ?? []);
}

export function ProfileSummaryPage({ auth, onNavigate }: CommonProps) {
  const [identity, setIdentity] = useState<CareerIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ role: "", opportunity: "internship", arrangement: "hybrid", geography: "", careerStage: "entry_level", consent: true });
  const protectedOptions = useMemo<ProtectedRequestOptions>(() => ({ getAccessToken: auth.getAccessTokenSilently }), [auth.getAccessTokenSilently]);

  function load() {
    if (!auth.isAuthenticated) { setLoading(false); return; }
    setLoading(true);
    getCareerIdentity(protectedOptions)
      .catch(() => initializeCareerIdentity(protectedOptions))
      .then((envelope) => { setIdentity(envelope.data); setError(null); })
      .catch((reason) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [auth.isAuthenticated, protectedOptions]);

  useEffect(() => {
    if (!identity || !editing) return;
    const roleFact = identity.facts.role_preference.find((fact) => ["explicit", "confirmed"].includes(fact.state)) ?? identity.facts.role_preference[0];
    const goalFact = identity.facts.career_goal.find((fact) => ["explicit", "confirmed"].includes(fact.state)) ?? identity.facts.career_goal[0];
    const workFact = identity.facts.work_arrangement_preference.find((fact) => ["explicit", "confirmed"].includes(fact.state)) ?? identity.facts.work_arrangement_preference[0];
    const geographyFact = identity.facts.geographic_constraint.find((fact) => ["explicit", "confirmed"].includes(fact.state)) ?? identity.facts.geographic_constraint[0];
    setForm({
      role: String(roleFact?.payload.role_title ?? goalFact?.payload.description ?? ""),
      opportunity: String(roleFact?.payload.employment_type ?? "internship"),
      arrangement: String(workFact?.payload.arrangement ?? "hybrid"),
      geography: String(geographyFact?.payload.location ?? ""),
      careerStage: String(roleFact?.payload.seniority ?? "entry_level"),
      consent: identity.privacy.downstream_personalization_consent_granted,
    });
  }, [editing, identity]);

  const rolePreferences = facts(identity, ["role_preference"]);
  const careerGoals = facts(identity, ["career_goal"]);
  const roleTitles = new Set(rolePreferences.flatMap((fact) => typeof fact.payload.role_title === "string" ? [fact.payload.role_title.trim().toLowerCase()] : []));
  const roles = [
    ...rolePreferences,
    ...careerGoals.filter((fact) => typeof fact.payload.description !== "string" || !roleTitles.has(fact.payload.description.trim().toLowerCase())),
  ];
  const arrangements = facts(identity, ["work_arrangement_preference"]);
  const geographies = facts(identity, ["geographic_constraint"]);
  const industries = facts(identity, ["industry_preference"]);
  const experience = facts(identity, ["experience", "skill", "project", "credential"]);
  const imported = Object.values(identity?.facts ?? {}).flat().filter((fact) => fact.state === "imported" || fact.state === "inferred");
  const primaryRole = rolePreferences[0];
  const primaryGoal = careerGoals[0];
  const roleSummary = typeof primaryRole?.payload.role_title === "string"
    ? pretty(primaryRole.payload.role_title)
    : typeof primaryGoal?.payload.description === "string"
      ? pretty(primaryGoal.payload.description)
      : "a target role";
  const opportunitySummary = rolePreferences.find((fact) => typeof fact.payload.employment_type === "string");
  const summary = `${experience[0] ? factText(experience[0]).split(" · ")[0] : "Career seeker"} seeking ${roleSummary}${opportunitySummary ? ` ${pretty(String(opportunitySummary.payload.employment_type))} opportunities` : " opportunities"}, with ${arrangements[0] ? `a ${factText(arrangements[0])} work preference` : "flexible work arrangements"}${geographies[0] ? ` in ${factText(geographies[0])}` : " across the U.S"}.`;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!identity || !form.role.trim()) return;
    setSaving(true);
    setError(null);
    try {
      let current = identity;
      const payloads: Array<{ fact_type: "career_goal" | "role_preference" | "work_arrangement_preference" | "geographic_constraint"; payload: Record<string, unknown> }> = [
        { fact_type: "career_goal" as const, payload: { goal_type: "near_term_objective", description: form.role.trim() } },
        { fact_type: "role_preference" as const, payload: { role_title: form.role.trim(), seniority: form.careerStage, employment_type: form.opportunity, preference_kind: "preferred" } },
        { fact_type: "work_arrangement_preference" as const, payload: { arrangement: form.arrangement, willingness: "preferred" } },
        ...(form.geography.trim() ? [{ fact_type: "geographic_constraint" as const, payload: { location: form.geography.trim(), constraint_kind: "acceptable" } }] : []),
      ];
      let removedFacts = false;
      const editableTypes = ["career_goal", "role_preference", "work_arrangement_preference", "geographic_constraint"] as const;
      for (const factType of editableTypes) {
        const candidates = current.facts[factType].filter((fact) => ["explicit", "confirmed"].includes(fact.state));
        const remove = factType === "geographic_constraint" && !form.geography.trim() ? candidates : candidates.slice(1);
        for (const fact of remove) {
          await deleteCareerIdentityFact(fact.career_identity_fact_id, undefined, protectedOptions);
          removedFacts = true;
        }
      }
      if (removedFacts) {
        const refreshed = await getCareerIdentity(protectedOptions);
        if (refreshed.data) current = refreshed.data;
      }
      for (const item of payloads) {
        const existing = current.facts[item.fact_type].find((fact) => ["explicit", "confirmed"].includes(fact.state));
        if (existing) {
          const updated = await updateCareerIdentityFact(existing.career_identity_fact_id, { payload: item.payload, expected_version: current.current_version }, protectedOptions);
          if (updated.data) current = updated.data;
        } else {
          const created = await createCareerIdentityFact({ ...item, state: "explicit", expected_version: current.current_version }, protectedOptions);
          if (created.data?.identity) current = created.data.identity;
        }
      }
      const refreshed = await getCareerIdentity(protectedOptions);
      if (refreshed.data) current = refreshed.data;
      if (form.consent !== current.privacy.downstream_personalization_consent_granted) {
        const updated = await updateCareerIdentityPrivacy({ downstream_personalization_consent_granted: form.consent, expected_version: current.current_version }, protectedOptions);
        if (updated.data) current = updated.data;
      }
      setIdentity(current);
      setEditing(false);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="product-empty" role="status">Loading Profile…</div>;
  if (!auth.isAuthenticated) return <div className="product-empty"><h1>Profile</h1><p>Sign in to view and edit your career search.</p><button onClick={() => void auth.login()} type="button">Sign in</button></div>;

  const sections: Array<[string, CareerIdentityFact[], string]> = [
    ["Roles & goals", roles, "Add the work you want to pursue."],
    ["Opportunity type & career stage", rolePreferences, "Add internship, full-time, and career-stage preferences."],
    ["Work arrangement", arrangements, "Add remote, hybrid, or on-site preferences."],
    ["Geographic scope", geographies, "Nationwide until you add a preferred or excluded market."],
    ["Industries & preferences", industries, "Optional context for more relevant matches."],
    ["Experience & skills", experience, "Add evidence that makes your search more specific."],
    ["Imported suggestions", imported, "Imported and inferred suggestions remain reviewable."],
  ];

  return (
    <div className="profile-summary-page">
      <header className="profile-hero"><p className="eyebrow">What the product understands about your search</p><h1>Profile</h1><p>{summary}</p><div><button onClick={() => setEditing((value) => !value)} type="button">{editing ? "Close editor" : "Edit search essentials"}</button><button className="secondary-button" onClick={() => onNavigate(exploreUrl())} type="button">Open Explore</button></div></header>
      {error ? <p className="explore-error" role="alert">{error}</p> : null}
      {!identity?.privacy.downstream_personalization_consent_granted ? <div className="explore-notice explore-notice-warning"><strong>Personalization consent is off</strong><span>Explore will show general market intelligence until you enable it.</span></div> : null}
      {editing ? <form className="profile-essentials-form" onSubmit={submit}><h2>Search essentials</h2><p>This updates Career Identity. Explore filters remain temporary and never write here.</p><label>Target role or goal<input required onChange={(event) => setForm({ ...form, role: event.target.value })} placeholder="AI product manager" value={form.role} /></label><label>Opportunity type<select onChange={(event) => setForm({ ...form, opportunity: event.target.value })} value={form.opportunity}><option value="internship">Internship</option><option value="full_time">Full-time</option><option value="coop">Co-op</option></select></label><label>Career stage<select onChange={(event) => setForm({ ...form, careerStage: event.target.value })} value={form.careerStage}><option value="entry_level">Entry level</option><option value="mid_level">Mid-career</option></select></label><label>Work arrangement<select onChange={(event) => setForm({ ...form, arrangement: event.target.value })} value={form.arrangement}><option value="hybrid">Hybrid</option><option value="remote">Remote</option><option value="onsite">On-site</option><option value="flexible">Flexible</option></select></label><label>Preferred market (optional)<input onChange={(event) => setForm({ ...form, geography: event.target.value })} placeholder="Boston" value={form.geography} /></label><label className="checkbox-label"><input checked={form.consent} onChange={(event) => setForm({ ...form, consent: event.target.checked })} type="checkbox" />Use these facts to personalize Explore</label><button disabled={saving} type="submit">{saving ? "Saving…" : "Save to Profile"}</button></form> : null}
      <div className="profile-section-list">{sections.map(([title, items, empty]) => <section key={title}><header><h2>{title}</h2><span>{items.length || "—"}</span></header>{items.length ? <ul>{items.slice(0, 5).map((fact) => <li key={fact.career_identity_fact_id}>{factText(fact)}{fact.state !== "explicit" ? <small>{pretty(fact.state)}</small> : null}</li>)}</ul> : <p>{empty}</p>}</section>)}</div>
      <details className="profile-advanced"><summary>Advanced, privacy & account</summary><p>Profile version {identity?.current_version}. Privacy visibility: {identity?.privacy.privacy_visibility}. Raw fact identifiers and provenance are available in the legacy Career Identity review surface.</p><a href="/markets/career-identity">Open advanced Career Identity review</a></details>
    </div>
  );
}
