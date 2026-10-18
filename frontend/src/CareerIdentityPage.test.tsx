// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import CareerIdentityPage from "./CareerIdentityPage";
import {
  createCareerIdentityFact,
  discoverPersonalizedFromCareerIdentity,
  updateCareerIdentityPrivacy,
} from "./api";
import type {
  ApiEnvelope,
  CareerIdentity,
  CareerIdentityCompleteness,
  CareerIdentityFact,
  CareerIdentityFactInput,
  CareerIdentityFactType,
  CareerIdentityPrivacy,
  PersonalizedResult,
} from "./types";

const apiState = vi.hoisted(() => ({
  identity: null as CareerIdentity | null,
  nextId: 1,
  lastImportText: "",
  failNextCreate: null as "conflict" | "validation" | null,
}));

vi.mock("./api", () => {
  class ApiError extends Error {
    envelope?: ApiEnvelope<unknown>;
    statusCode?: number;

    constructor(
      message: string,
      options?: { envelope?: ApiEnvelope<unknown>; statusCode?: number },
    ) {
      super(message);
      this.name = "ApiError";
      this.envelope = options?.envelope;
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

  function requireIdentity(): CareerIdentity {
    if (!apiState.identity) apiState.identity = makeIdentity();
    return apiState.identity;
  }

  return {
    ApiError,
    getCareerIdentity: vi.fn(async () => envelope(requireIdentity())),
    getCareerIdentityEvaluation: vi.fn(async () => envelope(requireIdentity().completeness)),
    getCareerIdentityPrivacy: vi.fn(async () =>
      envelope({
        career_identity_id: requireIdentity().career_identity_id,
        identity_version: requireIdentity().current_version,
        privacy: requireIdentity().privacy,
      }),
    ),
    createCareerIdentityFact: vi.fn(async (body: CareerIdentityFactInput) => {
      if (apiState.failNextCreate === "conflict") {
        apiState.failNextCreate = null;
        throw new ApiError("Version conflict", {
          statusCode: 409,
          envelope: {
            status: "error",
            data: null,
            metadata: { state: "fresh" },
            error: { code: "VERSION_CONFLICT", message: "Career identity version conflict." },
          },
        });
      }
      if (apiState.failNextCreate === "validation") {
        apiState.failNextCreate = null;
        throw new ApiError("Invalid Career Identity input.", {
          statusCode: 422,
          envelope: {
            status: "error",
            data: null,
            metadata: { state: "fresh" },
            error: { code: "VALIDATION_ERROR", message: "Invalid Career Identity input." },
          },
        });
      }
      const identity = requireIdentity();
      const fact = makeFact(body.fact_type, body.payload, body.state ?? "explicit");
      identity.facts[body.fact_type].push(fact);
      identity.current_version += 1;
      identity.completeness = completeEvaluation(identity.current_version);
      return envelope({
        career_identity_fact_id: fact.career_identity_fact_id,
        outcome: "created",
        version_changed: true,
        identity,
      });
    }),
    updateCareerIdentityFact: vi.fn(async (factId: string, body: { payload?: Record<string, unknown>; state?: string }) => {
      const identity = requireIdentity();
      const fact = allFacts(identity).find((candidate) => candidate.career_identity_fact_id === factId);
      if (fact && body.payload) {
        fact.payload = body.payload;
        fact.state = "explicit";
        identity.current_version += 1;
      }
      return envelope(identity);
    }),
    confirmCareerIdentityFact: vi.fn(async (factId: string) => {
      const identity = requireIdentity();
      const fact = allFacts(identity).find((candidate) => candidate.career_identity_fact_id === factId);
      if (fact) {
        fact.state = "confirmed";
        fact.confirmed_at = "2026-08-28T12:00:00Z";
        identity.current_version += 1;
      }
      return envelope(identity);
    }),
    deleteCareerIdentityFact: vi.fn(async (factId: string) => {
      const identity = requireIdentity();
      for (const facts of Object.values(identity.facts)) {
        const index = facts.findIndex((fact) => fact.career_identity_fact_id === factId);
        if (index >= 0) facts.splice(index, 1);
      }
      identity.current_version += 1;
      return envelope({ deleted_career_identity_facts: 1 });
    }),
    updateCareerIdentityPrivacy: vi.fn(async (body: Partial<CareerIdentityPrivacy>) => {
      const identity = requireIdentity();
      identity.privacy = { ...identity.privacy, ...body };
      identity.current_version += 1;
      return envelope(identity);
    }),
    ingestCareerIdentity: vi.fn(async (body: { text?: string | null; consent_granted: boolean }) => {
      const identity = requireIdentity();
      if (!body.consent_granted) {
        throw new ApiError("career identity ingestion requires explicit ingestion consent", {
          statusCode: 422,
          envelope: {
            status: "error",
            data: null,
            metadata: { state: "fresh" },
            error: {
              code: "ingestion_consent_required",
              message: "career identity ingestion requires explicit ingestion consent",
            },
          },
        });
      }
      if (body.text === apiState.lastImportText) {
        return envelope({
          career_identity_import_id: "cii_duplicate",
          identity_version: identity.current_version,
          status: "duplicate",
          imported_fact_count: 2,
          created_fact_count: 0,
          updated_fact_count: 0,
          protected_fact_count: 0,
          duplicate_fact_count: 2,
          diagnostics: [],
          completeness: identity.completeness,
        });
      }
      apiState.lastImportText = body.text ?? "";
      identity.facts.skill.push(makeFact("skill", { name: "Python" }, "imported"));
      identity.facts.project.push(makeFact("project", { name: "Resume Dashboard" }, "imported"));
      identity.current_version += 1;
      identity.completeness = completeEvaluation(identity.current_version);
      return envelope({
        career_identity_import_id: "cii_1",
        identity_version: identity.current_version,
        status: "completed",
        imported_fact_count: 2,
        created_fact_count: 2,
        updated_fact_count: 0,
        protected_fact_count: 0,
        duplicate_fact_count: 0,
        diagnostics: [],
        completeness: identity.completeness,
      });
    }),
    discoverPersonalizedFromCareerIdentity: vi.fn(async () => {
      const response: ApiEnvelope<PersonalizedResult> = envelope({
        ranked_regions: [
          {
            region_id: "greater_boston",
            display_name: "Greater Boston",
            personal_market_score: 0.86,
            objective_opportunity_score: 0.74,
            coverage: undefined,
            priority_market: null,
            match_notes: ["region_score_missing"],
          },
        ],
        ranked_companies: [
          {
            company_id: "comp_ai",
            company_name: "AI Product Co",
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            personal_company_score: 0.92,
            role_fit: 1,
            industry_fit: 1,
            prestige_fit: 0.5,
            brand_fit: 0.5,
            match_notes: ["role:product", "industry_primary:ai"],
          },
        ],
      });
      (response.metadata as Record<string, unknown>).career_identity_personalization = {
        source: "career_identity",
        career_identity_applied: true,
      };
      return response;
    }),
  };
});

const auth = {
  isConfigured: true,
  isAuthenticated: true,
  isLoading: false,
  error: null,
  user: { email: "career@example.com", sub: "auth0|career" },
  login: vi.fn(async () => undefined),
  logout: vi.fn(),
  getAccessTokenSilently: vi.fn(async () => "token"),
};

afterEach(() => {
  cleanup();
  apiState.identity = null;
  apiState.nextId = 1;
  apiState.lastImportText = "";
  apiState.failNextCreate = null;
  vi.clearAllMocks();
});

describe("CareerIdentityPage", () => {
  test("supports guided manual entry and preserves backend state across reload", async () => {
    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);

    await screen.findByText("Career Identity");
    fireEvent.click(screen.getByRole("tab", { name: /Roles and industries/i }));
    fireEvent.change(screen.getByLabelText("Function"), { target: { value: "product" } });
    fireEvent.click(screen.getByRole("button", { name: /Add role preference/i }));

    await screen.findByText("Career fact saved.");
    expect(createCareerIdentityFact).toHaveBeenCalledWith(
      expect.objectContaining({
        fact_type: "role_preference",
        payload: expect.objectContaining({ function: "product", preference_kind: "preferred" }),
      }),
      expect.any(Object),
    );

    cleanup();
    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);
    await screen.findByText(/product/i);
  });

  test("imports profile facts and supports review confirm edit and remove", async () => {
    apiState.identity = makeIdentity({
      privacy: {
        ...defaultPrivacy(),
        ingestion_consent_granted: true,
      },
    });
    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);

    await screen.findByText("Career Identity");
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "Skills:\nPython\nProjects:\nResume Dashboard" } });
    fireEvent.click(screen.getByRole("button", { name: /Import profile/i }));

    await screen.findByText("Career profile imported.");
    fireEvent.click(screen.getByRole("tab", { name: /Review/i }));
    await screen.findByText(/2 facts need review/i);
    expect(screen.getAllByText("Imported").length).toBeGreaterThan(0);

    const pythonRow = screen.getAllByText("Python")[0].closest("article");
    expect(pythonRow).not.toBeNull();
    fireEvent.click(within(pythonRow as HTMLElement).getByRole("button", { name: "Confirm" }));
    await screen.findByText("Career fact confirmed.");

    const confirmedPythonRow = screen.getByText("Python").closest("article");
    expect(confirmedPythonRow).not.toBeNull();
    fireEvent.click(within(confirmedPythonRow as HTMLElement).getByRole("button", { name: "Edit" }));
    fireEvent.change(await screen.findByLabelText(/Skill/), { target: { value: "TypeScript" } });
    fireEvent.click(screen.getByRole("button", { name: /Save correction/i }));
    await screen.findByText("Career fact corrected.");
    await screen.findByText("TypeScript");

    const projectRow = screen.getAllByText("Resume Dashboard")[0].closest("article");
    expect(projectRow).not.toBeNull();
    fireEvent.click(within(projectRow as HTMLElement).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.queryByText("Resume Dashboard")).not.toBeInTheDocument());
  });

  test("saves privacy controls and refreshes Career Identity recommendations", async () => {
    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);

    await screen.findByText("Career Identity");
    fireEvent.click(screen.getByLabelText("Use Career Identity for recommendations"));
    fireEvent.click(screen.getByRole("button", { name: /Save privacy controls/i }));
    await screen.findByText("Privacy settings saved.");
    expect(updateCareerIdentityPrivacy).toHaveBeenCalledWith(
      expect.objectContaining({ downstream_personalization_consent_granted: true }),
      expect.any(Object),
    );

    fireEvent.click(screen.getByRole("button", { name: /Refresh recommendations/i }));
    await screen.findByText("AI Product Co");
    expect(discoverPersonalizedFromCareerIdentity).toHaveBeenCalledWith(
      expect.objectContaining({ region_ids: ["greater_boston"] }),
      expect.any(Object),
    );
    expect(screen.getByText(/Career Identity applied to this preview/i)).toBeInTheDocument();
  });

  test("keeps validation errors private and handles version conflicts by refetching", async () => {
    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);

    await screen.findByText("Career Identity");
    fireEvent.click(screen.getByRole("tab", { name: /Skills and projects/i }));
    await screen.findByRole("button", { name: /Add skill/i });
    fireEvent.change(screen.getByLabelText("Career fact type"), { target: { value: "project" } });
    fireEvent.change(await screen.findByLabelText(/Project name/), {
      target: { value: "AUDIT_PRIVATE_SENTINEL_35A_X9Q7" },
    });
    apiState.failNextCreate = "validation";
    fireEvent.click(screen.getByRole("button", { name: /Add project/i }));

    await screen.findByText("Invalid Career Identity input.");
    expect(document.body.textContent).not.toContain("AUDIT_PRIVATE_SENTINEL_35A_X9Q7");

    fireEvent.change(screen.getByLabelText(/Project name/), { target: { value: "Portfolio" } });
    apiState.failNextCreate = "conflict";
    fireEvent.click(screen.getByRole("button", { name: /Add project/i }));

    await screen.findByText(/latest version was reloaded/i);
  });

  test("renders legacy evaluation payloads without actionable reason codes", async () => {
    apiState.identity = makeIdentity();
    apiState.identity.completeness = {
      ...completeEvaluation(apiState.identity.current_version),
      actionable_reason_codes: undefined,
    };

    render(<CareerIdentityPage auth={auth} defaultRegionIds={["greater_boston"]} />);

    expect(await screen.findByText("Add a target role or location preference to begin shaping personalized results.")).toBeInTheDocument();
    expect(screen.queryByText("Your core Career Identity sections are ready.")).not.toBeInTheDocument();
  });

  test("shows empty authenticated and unauthenticated states", async () => {
    const unauthenticated = { ...auth, isAuthenticated: false };
    render(<CareerIdentityPage auth={unauthenticated} defaultRegionIds={[]} />);
    expect(await screen.findByText("Sign in to manage Career Identity")).toBeInTheDocument();
  });
});

function makeIdentity(overrides: Partial<CareerIdentity> = {}): CareerIdentity {
  const version = overrides.current_version ?? 1;
  const identity: CareerIdentity = {
    career_identity_id: "ci_test",
    user_id: "user_test",
    current_version: version,
    completeness_state: "minimal",
    sufficiency_state: "insufficient",
    privacy: overrides.privacy ?? defaultPrivacy(),
    completeness: completeEvaluation(version),
    facts: emptyFacts(),
    created_at: "2026-08-28T12:00:00Z",
    updated_at: "2026-08-28T12:00:00Z",
    ...overrides,
  };
  return identity;
}

function makeFact(
  factType: CareerIdentityFactType,
  payload: Record<string, unknown>,
  state: CareerIdentityFact["state"],
): CareerIdentityFact {
  const id = `cif_${apiState.nextId++}`;
  return {
    career_identity_fact_id: id,
    fact_type: factType,
    normalized_key: `${factType}:${id}`,
    state,
    payload,
    provenance: { state, created_by: state === "explicit" ? "user" : "system", history: [] },
    source_import_id: state === "imported" ? "cii_1" : null,
    source_label: state === "imported" ? "Career profile import" : null,
    confirmed_at: null,
    created_at: "2026-08-28T12:00:00Z",
    updated_at: "2026-08-28T12:00:00Z",
  };
}

function emptyFacts(): CareerIdentity["facts"] {
  return {
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
  };
}

function allFacts(identity: CareerIdentity): CareerIdentityFact[] {
  return Object.values(identity.facts).flat();
}

function defaultPrivacy(): CareerIdentityPrivacy {
  return {
    ingestion_consent_granted: false,
    inference_consent_granted: false,
    downstream_personalization_consent_granted: false,
    retain_import_metadata: true,
    privacy_visibility: "private",
  };
}

function completeEvaluation(version: number): CareerIdentityCompleteness {
  return {
    identity_version: version,
    overall_score: version > 1 ? 68 : 18,
    completeness_state: version > 1 ? "partial" : "minimal",
    sufficiency_state: version > 1 ? "sufficient" : "insufficient",
    sufficient: version > 1,
    strong_required_signal_count: version > 1 ? 4 : 0,
    sections: [
      {
        section: "skills",
        score: version > 1 ? 1 : 0,
        status: version > 1 ? "present" : "missing",
        present_signals: [],
        missing_signals: [],
        weak_signals: [],
        reason_codes: [],
      },
    ],
    missing_categories: version > 1 ? [] : ["skills", "goals", "role_preferences"],
    weak_categories: [],
    actionable_reason_codes: version > 1 ? [] : ["missing_skills", "missing_goals"],
  };
}
