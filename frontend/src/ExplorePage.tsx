import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  ApiError,
  createSavedMarketArtifact,
  evaluateExploreMarkets,
  getCurrentOpportunities,
  getRegion,
  listSavedMarketArtifacts,
  recordProductEvent,
  resolveGeography,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import { canonicalizeExploreGeography } from "./exploreGeography";
import type {
  CurrentOpportunityPayload,
  ExploreFitResult,
  ExploreMarketsResponse,
  ExploreSessionOverrides,
  RegionDetail,
} from "./types";
import {
  EXPLORE_ROLE_OPTIONS,
  companyGeographyUrl,
  currentOpportunitiesUrl,
  exploreComparisonUrl,
  exploreUrl,
  profileUrl,
  roleExploreValueForQuery,
  type ExploreGeographicIdentity,
  type ExploreUrlState,
} from "./urlState";

type Props = {
  auth: FrontendAuthContextValue;
  state: ExploreUrlState;
  onNavigate: (url: string, options?: { replace?: boolean }) => void;
};

type GeoFeature = {
  properties: { state_code: string; name: string };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};

type Geometry = { features: GeoFeature[] };
type MapViewport = { x: number; y: number; width: number; height: number };

const CURATED_CENTROIDS: Record<string, { latitude: number; longitude: number }> = {
  greater_boston: { latitude: 42.3327, longitude: -71.0726 },
  greater_nyc: { latitude: 40.6635, longitude: -73.9387 },
  greater_seattle: { latitude: 47.6205, longitude: -122.3509 },
  sf_bay_area: { latitude: 37.7272, longitude: -123.0322 },
  washington_dc: { latitude: 38.9041, longitude: -77.0171 },
  atlanta: { latitude: 33.7629, longitude: -84.4227 },
  austin: { latitude: 30.3004, longitude: -97.7522 },
  chicago: { latitude: 41.8376, longitude: -87.6818 },
};

const CURATED_PUBLIC_SLUGS: Record<string, string> = {
  greater_boston: "boston",
  greater_nyc: "new-york",
  greater_seattle: "seattle",
  sf_bay_area: "san-francisco-bay-area",
  washington_dc: "washington-dc",
  atlanta: "atlanta",
  austin: "austin",
  chicago: "chicago",
};

const OPPORTUNITY_OPTIONS = ["internship", "job", "coop"];
const WORK_OPTIONS = ["remote", "hybrid", "onsite", "flexible"];

function message(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : "Explore is unavailable.";
}

function label(value: string | null | undefined): string {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "Not set";
}

function driverLabel(driver: Record<string, unknown> | undefined): string {
  if (!driver) return "Evidence is still developing for this market.";
  for (const key of ["label", "summary", "evidence", "code"]) {
    if (typeof driver[key] === "string" && driver[key]) return label(driver[key] as string);
  }
  return "Evidence is still developing for this market.";
}

function fitLabel(market: ExploreFitResult): string {
  if (market.fit_band) return label(market.fit_band);
  const states: Record<string, string> = {
    general_market_intelligence: "General intelligence",
    insufficient_evidence: "Insufficient evidence",
    hard_constraint_excluded: "Outside your scope",
    unsupported: "Unsupported",
    abstained: "No conclusion",
    tentative: "Tentative Fit",
    confident: "Fit available",
  };
  return states[market.state] ?? label(market.state);
}

function project(longitude: number, latitude: number, stateCode?: string): [number, number] {
  if (stateCode === "AK") return [28 + ((longitude + 180) / 51) * 150, 330 + ((72 - latitude) / 21) * 62];
  if (stateCode === "HI") return [205 + ((longitude + 161) / 7) * 70, 354 + ((23 - latitude) / 5) * 44];
  return [42 + ((longitude + 125) / 59) * 672, 26 + ((50 - latitude) / 26) * 314];
}

function toCanvasPoint(point: [number, number], view: MapViewport): [number, number] {
  return [((point[0] - view.x) / view.width) * 760, ((point[1] - view.y) / view.height) * 420];
}

function marketSlug(market: ExploreFitResult): string {
  return market.region.public_slug || CURATED_PUBLIC_SLUGS[market.region.region_id] || market.region.region_id;
}

function markerCategory(market: ExploreFitResult): "confident" | "tentative" | "limited" | "unsupported" | "excluded" | "general" {
  if (market.state === "hard_constraint_excluded") return "excluded";
  if (market.state === "unsupported") return "unsupported";
  if (["insufficient_evidence", "abstained"].includes(market.state)) return "limited";
  if (market.state === "general_market_intelligence") return "general";
  if (market.state === "tentative") return "tentative";
  return "confident";
}

function markerSymbol(category: ReturnType<typeof markerCategory>): string {
  return category === "confident" ? "●" : category === "tentative" ? "◆" : category === "limited" ? "△" : category === "unsupported" ? "?" : category === "excluded" ? "×" : "○";
}

function ExploreMap({ geometry, markets, focused, onFocus }: {
  geometry: Geometry | null;
  markets: ExploreFitResult[];
  focused?: string;
  onFocus: (market: ExploreFitResult) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 760, height: 420, dpr: 1 });
  const focusedMarket = markets.find((market) => marketSlug(market) === focused);
  const focusedCentroid = focusedMarket
    ? focusedMarket.region.centroid ?? CURATED_CENTROIDS[focusedMarket.region.region_id]
    : null;
  const focusPoint = focusedCentroid
    ? project(focusedCentroid.longitude, focusedCentroid.latitude, focusedMarket?.region.state_codes[0])
    : null;
  const view = focusPoint
    ? { x: Math.max(0, focusPoint[0] - 190), y: Math.max(0, focusPoint[1] - 120), width: 380, height: 240 }
    : { x: 0, y: 0, width: 760, height: 420 };
  const { x: viewX, y: viewY, width: viewWidth, height: viewHeight } = view;
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const dpr = Math.max(1, window.devicePixelRatio || 1);
      if (rect.width > 0 && rect.height > 0) setCanvasSize({ width: rect.width, height: rect.height, dpr });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(wrap);
    resize();
    window.addEventListener("resize", resize);
    return () => { observer.disconnect(); window.removeEventListener("resize", resize); };
  }, []);

  useEffect(() => {
    if (!geometry) return;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    canvas.width = Math.round(canvasSize.width * canvasSize.dpr);
    canvas.height = Math.round(canvasSize.height * canvasSize.dpr);
    context.setTransform(
      (canvasSize.width / 760) * canvasSize.dpr,
      0,
      0,
      (canvasSize.height / 420) * canvasSize.dpr,
      0,
      0,
    );
    context.clearRect(0, 0, 760, 420);
    context.fillStyle = "#fbfcf8";
    context.strokeStyle = "#98aa9d";
    context.lineWidth = focusedMarket ? 1.7 : 1.15;
    for (const feature of geometry.features) {
      const polygons = feature.geometry.type === "Polygon"
        ? [feature.geometry.coordinates as number[][][]]
        : feature.geometry.coordinates as number[][][][];
      context.beginPath();
      for (const polygon of polygons) {
        for (const ring of polygon) {
          ring.forEach(([longitude, latitude], index) => {
            const [x, y] = toCanvasPoint(project(longitude, latitude, feature.properties.state_code), { x: viewX, y: viewY, width: viewWidth, height: viewHeight });
            if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
          });
          context.closePath();
        }
      }
      context.fill("evenodd");
      context.stroke();
    }
  }, [canvasSize, focusedMarket, geometry, viewHeight, viewWidth, viewX, viewY]);

  if (!geometry) return <div className="explore-map-state" role="status">Loading U.S. map data…</div>;

  return (
    <div aria-label="U.S. Explore markets. The ranked list provides the complete equivalent." className="explore-map-canvas-wrap" ref={wrapRef} role="region">
      <canvas aria-hidden="true" className="explore-map-canvas" height="420" ref={canvasRef} width="760" />
      {markets.flatMap((market) => {
        const centroid = market.region.centroid ?? CURATED_CENTROIDS[market.region.region_id];
        if (!centroid) return [];
        const [x, y] = toCanvasPoint(project(centroid.longitude, centroid.latitude, market.region.state_codes[0]), view);
        if (x < 0 || x > 760 || y < 0 || y > 420) return [];
        const active = marketSlug(market) === focused;
        const category = markerCategory(market);
        return [<button aria-label={`${market.region.display_name}: ${fitLabel(market)}, ${label(market.confidence)} confidence`} className={`market-map-marker market-map-marker-${category} ${active ? "market-map-marker-active" : ""}`} data-result-state={category} key={market.region.region_id} onClick={() => onFocus(market)} style={{ left: `${(x / 760) * 100}%`, top: `${(y / 420) * 100}%` }} type="button"><i aria-hidden="true">{markerSymbol(category)}</i><span>{market.region.primary_city ?? market.region.display_name}</span></button>];
      })}
    </div>
  );
}

function MarketRow({ market, active, compared, onOpen, onCompare }: {
  market: ExploreFitResult;
  active: boolean;
  compared: boolean;
  onOpen: () => void;
  onCompare: () => void;
}) {
  const limitation = market.contradiction_blocking
    ? market.contradiction_summary ?? market.abstention_reason
    : market.material_limitations[0] ?? market.abstention_reason;
  const reason = market.contradiction_blocking
    ? market.abstention_reason ?? market.contradiction_summary ?? "Evidence conflicts, so no confident result is shown."
    : driverLabel(market.primary_drivers[0]);
  return (
    <li className={`market-result ${active ? "market-result-active" : ""}`} aria-current={active ? "true" : undefined}>
      <button className="market-result-main" id={`market-row-${market.region.region_id}`} type="button" onClick={onOpen}>
        <span className="market-rank">{market.rank ? `#${market.rank}` : "—"}</span>
        <span>
          <strong>{market.region.display_name}</strong>
          <small>{reason}</small>
          {limitation ? <small className="market-limitation">{limitation}</small> : null}
        </span>
        <span className={`fit-state fit-state-${market.state}`}>
          <strong>{fitLabel(market)}</strong>
          <small>{label(market.confidence)} confidence</small>
        </span>
      </button>
      <button aria-label={`${compared ? "Remove" : "Add"} ${market.region.display_name} ${compared ? "from" : "to"} comparison`} className="compare-toggle" onClick={onCompare} type="button">
        {compared ? "Selected ✓" : "+ Compare"}
      </button>
    </li>
  );
}

export default function ExplorePage({ auth, state, onNavigate }: Props) {
  const [results, setResults] = useState<ExploreMarketsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [mapError, setMapError] = useState(false);
  const [resolvedGeographicScope, setResolvedGeographicScope] = useState<string[] | null>(state.geographicScope.length ? null : []);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [query, setQuery] = useState(state.query ?? "");
  const [announcement, setAnnouncement] = useState("");
  const [regionDetail, setRegionDetail] = useState<RegionDetail | null>(null);
  const [opportunities, setOpportunities] = useState<CurrentOpportunityPayload[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const emittedEvents = useRef(new Set<string>());
  const protectedOptions = useMemo<ProtectedRequestOptions>(() => ({ getAccessToken: auth.getAccessTokenSilently }), [auth.getAccessTokenSilently]);
  const overrideKey = JSON.stringify([state.goal, state.opportunityTypes, state.workArrangements, resolvedGeographicScope, state.industries]);
  const overrides = useMemo<ExploreSessionOverrides>(() => ({
    goal: state.goal,
    industries: state.industries.length ? state.industries : undefined,
    opportunity_types: state.opportunityTypes.length ? state.opportunityTypes : undefined,
    work_arrangements: state.workArrangements.length ? state.workArrangements : undefined,
    geographic_scope: resolvedGeographicScope?.length ? { region_refs: resolvedGeographicScope } : undefined,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [overrideKey]);

  useEffect(() => {
    fetch("/data/us_states_simplified.geojson")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("map data unavailable")))
      .then((data: Geometry) => setGeometry(data))
      .catch(() => setMapError(true));
  }, []);

  useEffect(() => {
    let active = true;
    if (!state.geographicScope.length) {
      setResolvedGeographicScope([]);
      return () => { active = false; };
    }
    setResolvedGeographicScope(null);
    canonicalizeExploreGeography({
      ...state,
      focus: undefined,
      selected: [],
    }).then((canonicalState) => {
      if (!active) return;
      const canonical = canonicalState.geographicScope;
      setResolvedGeographicScope(canonical);
      if (canonical.join(",") !== state.geographicScope.join(",")) update({ geographicScope: canonical }, true);
    });
    return () => { active = false; };
  // URL normalization intentionally precedes Explore evaluation.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.geographicScope.join(",")]);

  useEffect(() => {
    if (auth.isLoading) return;
    if (resolvedGeographicScope === null) return;
    if (!auth.isAuthenticated) {
      setLoading(false);
      setError("Sign in to open personalized Explore.");
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    evaluateExploreMarkets(overrides, protectedOptions)
      .then((envelope) => {
        if (!active) return;
        if (!envelope.data) throw new Error(envelope.error?.message ?? "Explore returned no results.");
        setResults(envelope.data);
        setAnnouncement(`Explore results updated. ${envelope.data.markets.length} markets available.`);
      })
      .catch((reason) => active && setError(message(reason)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [auth.isAuthenticated, auth.isLoading, overrideKey, protectedOptions, overrides, reloadNonce, resolvedGeographicScope]);

  const markets = useMemo(() => results?.markets ?? [], [results?.markets]);
  const focusedMarket = markets.find((market) => marketSlug(market) === state.focus);
  const selectedRegionIds = useMemo(() => new Set(state.selected.flatMap((slug) => {
    const market = markets.find((candidate) => marketSlug(candidate) === slug);
    return market ? [market.region.region_id] : [];
  })), [markets, state.selected]);
  const matchingMarkets = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return markets;
    return markets.filter((market) => [market.region.display_name, market.region.primary_city, market.region.public_slug, market.region.region_id]
      .some((value) => value?.toLowerCase().includes(normalized)));
  }, [markets, query]);

  useEffect(() => setQuery(state.query ?? ""), [state.query]);

  useEffect(() => {
    if (!markets.length) return;
    let active = true;
    const directIdentities: ExploreGeographicIdentity[] = markets.map((market) => ({
      region_id: market.region.region_id,
      public_slug: marketSlug(market),
      aliases: [market.region.display_name, market.region.primary_city ?? ""],
    }));
    canonicalizeExploreGeography(state, directIdentities).then((canonical) => {
      if (!active) return;
      const geographicStateChanged = canonical.focus !== state.focus
        || canonical.selected.join(",") !== state.selected.join(",")
        || canonical.geographicScope.join(",") !== state.geographicScope.join(",");
      if (geographicStateChanged) onNavigate(exploreUrl(canonical), { replace: true });
    });
    return () => { active = false; };
  }, [markets, onNavigate, state]);

  useEffect(() => {
    setSaved(false);
    setRegionDetail(null);
    setOpportunities([]);
    if (!focusedMarket) return;
    let active = true;
    setDetailLoading(true);
    const hasCoverage = !["unsupported", "unavailable", "unknown"].includes(focusedMarket.opportunity_coverage.status);
    const inspectedEventKey = `inspected:${results?.context.context_fingerprint}:${focusedMarket.region.region_id}`;
    if (!emittedEvents.current.has(inspectedEventKey)) {
      emittedEvents.current.add(inspectedEventKey);
      void recordProductEvent({
        event_type: "market_inspected",
        event_source: "frontend",
        product_surface: "explore_market_detail",
        confidence_bucket: focusedMarket.confidence,
        coverage_status: focusedMarket.opportunity_coverage.status,
        payload: { region_id: focusedMarket.region.region_id },
      }, protectedOptions).catch(() => undefined);
    }
    const opportunityType = results?.context.effective_context.opportunity_types[0];
    const workArrangement = results?.context.effective_context.work_arrangements[0];
    Promise.allSettled([
      getRegion(focusedMarket.region.region_id),
      listSavedMarketArtifacts(protectedOptions, "region"),
      ...(hasCoverage ? [getCurrentOpportunities({ market: focusedMarket.region.region_id, role_family: results?.context.supported_goal, opportunity_type: opportunityType, work_arrangement: workArrangement, limit: 3 }, protectedOptions)] : []),
    ]).then((settled) => {
      if (!active) return;
      if (settled[0]?.status === "fulfilled") setRegionDetail(settled[0].value.data);
      if (settled[1]?.status === "fulfilled") setSaved(Boolean(settled[1].value.data?.saved_market_artifacts.some((item) => item.artifact_type === "region" && item.artifact_ref === focusedMarket.region.region_id)));
      if (settled[2]?.status === "fulfilled") setOpportunities(settled[2].value.data?.opportunities ?? []);
      setDetailLoading(false);
    });
    const coverageEventKey = `coverage:${results?.context.context_fingerprint}:${focusedMarket.region.region_id}:${focusedMarket.opportunity_coverage.status}`;
    if (!hasCoverage && !emittedEvents.current.has(coverageEventKey)) {
      emittedEvents.current.add(coverageEventKey);
      void recordProductEvent({
        event_type: "coverage_limitation_viewed", event_source: "frontend", product_surface: "explore_market_detail",
        confidence_bucket: focusedMarket.confidence,
        coverage_status: focusedMarket.opportunity_coverage.status,
        payload: { region_id: focusedMarket.region.region_id, coverage_status: focusedMarket.opportunity_coverage.status },
      }, protectedOptions).catch(() => undefined);
    }
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => { active = false; };
  }, [focusedMarket, protectedOptions, results?.context.context_fingerprint, results?.context.effective_context.opportunity_types, results?.context.effective_context.work_arrangements, results?.context.supported_goal]);

  function update(next: Partial<ExploreUrlState>, replace = false) {
    onNavigate(exploreUrl({ ...state, ...next }), { replace });
  }

  function focusMarket(market: ExploreFitResult) {
    update({ focus: marketSlug(market) });
    setAnnouncement(`${market.region.display_name} selected. Market details opened.`);
  }

  function toggleCompare(market: ExploreFitResult) {
    const slug = marketSlug(market);
    const exists = selectedRegionIds.has(market.region.region_id);
    if (!exists && selectedRegionIds.size >= 4) {
      setAnnouncement("Comparison selection is limited to four markets.");
      return;
    }
    const selected = exists ? state.selected.filter((item) => item !== slug) : [...state.selected, slug];
    update({ selected });
    if (!exists && selected.length >= 2) {
      const eventKey = `selection-ready:${results?.context.context_fingerprint}:${[...selected].sort().join(",")}`;
      if (!emittedEvents.current.has(eventKey)) {
        emittedEvents.current.add(eventKey);
        void recordProductEvent({
          event_type: "comparison_selection_ready",
          event_source: "frontend",
          product_surface: "explore",
          payload: { selected_market_count: selected.length },
        }, protectedOptions).catch(() => undefined);
      }
    }
    setAnnouncement(`${market.region.display_name} ${exists ? "removed from" : "added to"} comparison.`);
  }

  function closeDetail() {
    if (!focusedMarket) return;
    const returnTarget = focusedMarket.region.region_id;
    update({ focus: undefined });
    window.setTimeout(() => document.getElementById(`market-row-${returnTarget}`)?.focus(), 0);
  }

  function handleSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const market = matchingMarkets[0];
    if (market) {
      setQuery("");
      return focusMarket(market);
    }
    const role = roleExploreValueForQuery(query);
    if (role) {
      setQuery("");
      return update({ query: undefined, goal: role });
    }
    void resolveGeography(query).then((envelope) => {
      const resolved = envelope.data;
      const resolvedMarket = markets.find((candidate) => candidate.region.region_id === resolved?.region_id);
      if (resolvedMarket) {
        setQuery("");
        focusMarket(resolvedMarket);
      }
    }).catch(() => {
      const unsupportedRole = query.trim() || undefined;
      setQuery("");
      update({ query: undefined, goal: unsupportedRole });
    });
  }

  async function saveMarket() {
    if (!focusedMarket || saved) return;
    try {
      await createSavedMarketArtifact({
        artifact_type: "region", artifact_ref: focusedMarket.region.region_id, label: focusedMarket.region.display_name,
      }, protectedOptions);
      setSaved(true);
      setAnnouncement(`${focusedMarket.region.display_name} saved to My Search.`);
    } catch (reason) {
      setAnnouncement(`Could not save market: ${message(reason)}`);
    }
  }

  const context = results?.context;
  const unappliedFields = new Set(context?.unapplied_context.map((item) => item.field) ?? []);
  const appliedFields = new Set(context?.applied_context ?? []);
  const fitContextParts = context ? [
    ...(appliedFields.has("goal") && context.supported_goal ? [label(context.supported_goal)] : []),
    ...(appliedFields.has("role_families") ? context.effective_context.role_families.map(label) : []),
    ...(appliedFields.has("included_region_ids") && context.effective_context.included_region_ids.length ? [`${context.effective_context.included_region_ids.length} included market${context.effective_context.included_region_ids.length === 1 ? "" : "s"}`] : []),
    ...(appliedFields.has("excluded_region_ids") && context.effective_context.excluded_region_ids.length ? [`${context.effective_context.excluded_region_ids.length} excluded market${context.effective_context.excluded_region_ids.length === 1 ? "" : "s"}`] : []),
  ] : [];
  const contextualParts = context ? [
    ...(unappliedFields.has("industries") ? context.effective_context.industries.map(label) : []),
    ...(unappliedFields.has("opportunity_types") ? context.effective_context.opportunity_types.map((value) => `${label(value)} opportunities`) : []),
    ...(unappliedFields.has("work_arrangements") ? context.effective_context.work_arrangements.map((value) => `${label(value)} work`) : []),
    ...(unappliedFields.has("career_stage") && context.effective_context.career_stage ? [label(context.effective_context.career_stage)] : []),
    ...(unappliedFields.has("timing") ? context.effective_context.timing.map(label) : []),
    ...(unappliedFields.has("preferred_region_ids") && context.effective_context.preferred_region_ids.length ? [`${context.effective_context.preferred_region_ids.length} preferred market${context.effective_context.preferred_region_ids.length === 1 ? "" : "s"}`] : []),
  ] : [];
  const unsupportedParts = context ? Array.from(new Set(context.unsupported_context.map((item) => label(item.field)))) : [];
  const hasTemporaryOverrides = Boolean(state.goal || state.opportunityTypes.length || state.workArrangements.length || state.geographicScope.length || state.industries.length);
  const mapModeLabel = context?.personalization_state === "personalized" ? "Market Fit for your search" : "General market intelligence";
  const hiringCompanies = regionDetail?.top_companies_hiring ?? [];
  const companyEvidence = hiringCompanies.length ? hiringCompanies : regionDetail?.top_companies_present ?? [];
  const companyEvidenceKind = hiringCompanies.length ? "Current hiring evidence" : "Company presence (not active hiring evidence)";
  const opportunityUrl = focusedMarket ? currentOpportunitiesUrl({
    market: focusedMarket.region.region_id,
    roleFamily: context?.supported_goal ?? undefined,
    opportunityType: context?.effective_context.opportunity_types[0],
    workArrangement: context?.effective_context.work_arrangements[0],
    returnTo: exploreUrl(state),
  }) : currentOpportunitiesUrl();
  const strongest = markets.filter((market) => market.rank).slice(0, 3).map((market) => market.region.primary_city ?? market.region.display_name);

  return (
    <div className="explore-page">
      <div aria-atomic="true" aria-live="polite" className="sr-only">{announcement}</div>
      <section className="explore-intro" aria-labelledby="explore-title">
        <div>
          <p className="eyebrow">Career market exploration</p>
          <h1 id="explore-title">Find where your career can move.</h1>
          <p>{strongest.length ? `${strongest.join(", ")} currently look strongest for this search.` : "Explore supported U.S. career markets and inspect the evidence behind each result."}</p>
        </div>
        <label className="explore-search">
          <span>Search markets or roles</span>
          <input aria-label="Search markets or roles" aria-describedby="search-help" onChange={(event) => setQuery(event.target.value)} onKeyDown={handleSearchKey} placeholder="Try Boston or AI / machine learning" type="search" value={query} />
          <small id="search-help">Choose a market below, or press Enter for the first match.</small>
        </label>
      </section>

      <section className="personalization-strip" aria-label="Active Explore context">
        <div className="context-summary">
          <div><span>{context?.personalization_state === "personalized" ? "Fit based on" : "Showing"}</span><strong>{fitContextParts.length ? fitContextParts.join(" · ") : "General market intelligence"}</strong></div>
          {contextualParts.length ? <div><span>Also filtering/context</span><strong>{contextualParts.join(" · ")}</strong><small>Not currently used in market Fit</small></div> : null}
          {unsupportedParts.length ? <div><span>Unsupported</span><strong>{unsupportedParts.join(" · ")}</strong><small>Not interpreted by the current Explore contract</small></div> : null}
        </div>
        <div className="context-actions">
          {hasTemporaryOverrides ? <span className="temporary-flag">Temporary Explore override</span> : <span className="profile-default-flag">Profile defaults</span>}
          <button className="text-button" onClick={() => setFiltersOpen((open) => !open)} type="button">{filtersOpen ? "Close filters" : "Edit"}</button>
        </div>
      </section>

      {filtersOpen ? (
        <section className="explore-filters" aria-label="Temporary Explore filters">
          <label>Target role <span className="applied-label">Used in Fit when supported</span><select onChange={(event) => update({ goal: event.target.value || undefined })} value={state.goal ?? ""}><option value="">From Profile</option>{EXPLORE_ROLE_OPTIONS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
          <label>Opportunity type <span className="unapplied-label">Jobs/context only</span><select onChange={(event) => update({ opportunityTypes: event.target.value ? [event.target.value] : [] })} value={state.opportunityTypes[0] ?? ""}><option value="">From Profile</option>{OPPORTUNITY_OPTIONS.map((value) => <option key={value}>{label(value)}</option>)}</select></label>
          <label>Work arrangement <span className="unapplied-label">Jobs/context only</span><select onChange={(event) => update({ workArrangements: event.target.value ? [event.target.value] : [] })} value={state.workArrangements[0] ?? ""}><option value="">From Profile</option>{WORK_OPTIONS.map((value) => <option key={value}>{label(value)}</option>)}</select></label>
          <label>Geography<select onChange={(event) => update({ geographicScope: event.target.value ? [event.target.value] : [] })} value={state.geographicScope[0] ?? ""}><option value="">Nationwide</option>{markets.map((market) => <option key={market.region.region_id} value={marketSlug(market)}>{market.region.display_name}</option>)}</select></label>
          <label>Industry <span className="unapplied-label">Context only — not used in Fit</span><input onChange={(event) => update({ industries: event.target.value ? [event.target.value] : [] })} placeholder="e.g. healthcare" value={state.industries[0] ?? ""} /></label>
          <button className="secondary-button" onClick={() => onNavigate(exploreUrl())} type="button">Clear temporary filters</button>
        </section>
      ) : null}

      {context?.personalization_state === "general_market_intelligence" ? <div className="explore-notice"><strong>General market intelligence</strong><span>{!context.career_identity_id ? "Tell us what kind of role you're looking for." : !context.personalization_consent ? "Personalization is off. Showing general market intelligence." : "Add a supported target role for personalized Fit."}</span><a href={profileUrl()}>{context.career_identity_id ? "Open Profile" : "Create Profile"}</a></div> : null}
      {context?.personalization_state === "needs_input" ? <div className="explore-notice"><strong>{context.career_identity_id ? "A supported target role is needed" : "Profile essentials are missing"}</strong><span>{context.career_identity_id ? "Your Profile is saved, but its target role is not supported for personalized Fit yet." : "Tell us what kind of role you're looking for."}</span><a href={profileUrl()}>{context.career_identity_id ? "Open Profile" : "Complete Profile"}</a></div> : null}
      {context?.personalization_state === "unsupported" ? <div className="explore-notice explore-notice-warning"><strong>Personalized Fit is not supported for this role yet</strong><span>General market evidence remains available. Choose a supported temporary role to personalize Fit.</span></div> : null}
      {results?.contradiction_blocking ? <div className="explore-notice explore-notice-warning"><strong>Evidence conflicts</strong><span>{results.contradiction_summary ?? "We cannot name a confident result for this search."}</span></div> : null}
      {context?.limitations.length ? <details className="context-limitations"><summary>Search context limitations</summary><ul>{context.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details> : null}
      {loading ? <div className="explore-status" role="status">Evaluating your search across supported markets…</div> : null}
      {error ? <div className="explore-status explore-error" role="alert"><strong>Explore could not load</strong><span>{error}</span>{auth.isAuthenticated ? <button onClick={() => setReloadNonce((value) => value + 1)} type="button">Try again</button> : <button onClick={() => void auth.login()} type="button">Sign in</button>}</div> : null}

      {!loading && !error && results ? (
        <section className="explore-workspace" aria-label="Explore market results">
          <div className="mobile-view-toggle" role="group" aria-label="Explore view"><button aria-pressed={state.view === "list"} onClick={() => update({ view: "list" })} type="button">List</button><button aria-pressed={state.view === "map"} onClick={() => update({ view: "map" })} type="button">Map</button></div>
          <div className={`explore-map-pane ${state.view === "map" ? "mobile-pane-active" : ""}`}>
            {mapError ? <div className="explore-map-state"><strong>Map unavailable</strong><span>The ranked list contains the complete result set.</span></div> : <ExploreMap focused={state.focus} geometry={geometry} markets={markets} onFocus={focusMarket} />}
            <div className="map-legend" aria-label="Map result legend"><strong>{mapModeLabel}</strong><span><i className="legend-fit">●</i> Confident Fit</span><span><i className="legend-tentative">◆</i> Tentative Fit</span><span><i className="legend-limited">△</i> Limited or conflicting</span><span><i className="legend-unsupported">?</i> Unsupported</span><span><i className="legend-excluded">×</i> Outside constraints</span></div>
            <p className="map-caption">Markers represent {context?.personalization_state === "personalized" ? "market Fit for this search" : "general market evidence"}—not job volume. Markets without coordinates remain in the list.</p>
          </div>
          <div className={`market-list-pane ${state.view === "list" ? "mobile-pane-active" : ""}`}>
            <header><div><p className="eyebrow">Explore Fit</p><h2>Ranked markets</h2></div><span>{results.ranking_universe.label}</span></header>
            <ol className="market-results">{matchingMarkets.map((market) => <MarketRow active={marketSlug(market) === state.focus} compared={selectedRegionIds.has(market.region.region_id)} key={market.region.region_id} market={market} onCompare={() => toggleCompare(market)} onOpen={() => focusMarket(market)} />)}</ol>
            {!matchingMarkets.length ? <p className="empty-inline">No markets match “{query}”. Clear search to restore the full Fit universe.</p> : null}
          </div>
        </section>
      ) : null}

      {focusedMarket ? (
        <aside aria-label={`${focusedMarket.region.display_name} details`} className="market-detail-panel" role="dialog">
          <header><div><p className="eyebrow">Location detail</p><h2>{focusedMarket.region.display_name}</h2></div><button aria-label="Close market details" className="icon-button" onClick={closeDetail} ref={closeButtonRef} type="button">×</button></header>
          <div className="fit-conclusion"><span>{fitLabel(focusedMarket)}</span>{focusedMarket.rank ? <strong>#{focusedMarket.rank} of {results?.ranking_universe.market_count}</strong> : <strong>No supported rank</strong>}<small>{label(focusedMarket.confidence)} confidence</small></div>
          {focusedMarket.contradiction_blocking ? <p className="material-limitation"><strong>Evidence conflicts:</strong> {focusedMarket.contradiction_summary ?? focusedMarket.abstention_reason ?? "We cannot name a confident result."}</p> : focusedMarket.material_limitations[0] ? <p className="material-limitation"><strong>Important:</strong> {focusedMarket.material_limitations[0]}</p> : null}
          {focusedMarket.state === "insufficient_evidence" ? <p className="material-limitation">We don't have enough evidence to rank this market confidently.</p> : null}
          {focusedMarket.state === "hard_constraint_excluded" ? <p className="material-limitation">Outside your current search constraints.</p> : null}
          <section><h3>Why this market</h3>{focusedMarket.contradiction_blocking || focusedMarket.state === "abstained" ? <><p>{focusedMarket.abstention_reason ?? focusedMarket.contradiction_summary ?? "Evidence conflicts, so we're not naming a confident result."}</p>{focusedMarket.contradiction_findings.length ? <details><summary>Review conflicting evidence</summary><ul>{focusedMarket.contradiction_findings.map((finding, index) => <li key={index}>{driverLabel(finding)}</li>)}</ul></details> : null}</> : <><ul>{focusedMarket.primary_drivers.slice(0, 3).map((driver, index) => <li key={index}>{driverLabel(driver)}</li>)}</ul>{!focusedMarket.primary_drivers.length ? <p>{focusedMarket.abstention_reason ?? focusedMarket.market_coverage.summary}</p> : null}</>}</section>
          <section><h3>Tradeoffs</h3>{focusedMarket.tradeoffs.length ? <ul>{focusedMarket.tradeoffs.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul> : <p>No material tradeoff was returned for this result.</p>}</section>
          <section><h3>Employers that explain this market</h3>{!detailLoading && companyEvidence.length ? <p className="evidence-kind">{companyEvidenceKind}</p> : null}{detailLoading ? <p>Loading company evidence…</p> : companyEvidence.slice(0, 4).map((company) => <a className="evidence-link" href={companyGeographyUrl(company.company_id)} key={company.company_id}>{company.company_name}<span>View company →</span></a>)}{!detailLoading && !companyEvidence.length ? <p>Company evidence is not available for this market.</p> : null}</section>
          <section><h3>Current opportunities</h3>{["unsupported", "unavailable", "unknown"].includes(focusedMarket.opportunity_coverage.status) ? <p className="coverage-unavailable">Current job coverage is unsupported for this search; no zero-job claim is being made.</p> : <><p>{focusedMarket.opportunity_coverage.active_opportunity_count} observed active · {focusedMarket.opportunity_coverage.ranking_eligible_opportunity_count} matching and ranking-eligible</p><p>Coverage: {label(focusedMarket.opportunity_coverage.status)} · {focusedMarket.opportunity_coverage.fresh_opportunity_count} fresh</p>{opportunities.map((opportunity) => <a className="evidence-link" href={`${currentOpportunitiesUrl()}/${opportunity.opportunity_id}`} key={opportunity.opportunity_id}>{opportunity.normalized_title || opportunity.original_title}<span>{opportunity.company_name}</span></a>)}<a className="text-link" href={opportunityUrl}>View all observed opportunities</a></>}</section>
          <details onToggle={(event) => { const key = `trust:${results?.context.context_fingerprint}:${focusedMarket.region.region_id}`; if (event.currentTarget.open && !emittedEvents.current.has(key)) { emittedEvents.current.add(key); void recordProductEvent({ event_type: "trust_explanation_viewed", event_source: "frontend", product_surface: "explore_market_detail", confidence_bucket: focusedMarket.confidence, payload: { region_id: focusedMarket.region.region_id } }, protectedOptions).catch(() => undefined); } }}><summary>Why and evidence</summary><p>{focusedMarket.market_coverage.summary}</p><p>Freshness: {label(focusedMarket.freshness)}. Evidence sufficiency: {label(focusedMarket.evidence_sufficiency)}.</p><p>Current opportunity counts do not change market Fit.</p></details>
          <div className="detail-actions"><button disabled={saved} onClick={() => void saveMarket()} type="button">{saved ? "Saved ✓" : "Save market"}</button><button className="secondary-button" onClick={() => toggleCompare(focusedMarket)} type="button">{selectedRegionIds.has(focusedMarket.region.region_id) ? "Remove from compare" : "Add to compare"}</button></div>
        </aside>
      ) : null}

      <aside className="comparison-tray" aria-label="Comparison selection">
        <div><strong>{selectedRegionIds.size ? `${selectedRegionIds.size} market${selectedRegionIds.size === 1 ? "" : "s"} selected` : "Select up to 4 markets"}</strong><span>Select 2–4 markets to compare governed Fit, evidence, and tradeoffs.</span></div>
        <div className="comparison-chips">{state.selected.flatMap((slug) => { const market = markets.find((candidate) => marketSlug(candidate) === slug); return market ? [<button aria-label={`Remove ${market.region.display_name} from comparison`} key={slug} onClick={() => toggleCompare(market)} type="button">{market.region.display_name} ×</button>] : []; })}</div>
        <button disabled={selectedRegionIds.size < 2} onClick={() => onNavigate(exploreComparisonUrl(state))} type="button">Compare {selectedRegionIds.size || ""}</button>
      </aside>
    </div>
  );
}
