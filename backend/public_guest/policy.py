from __future__ import annotations

from functools import lru_cache

from starlette.routing import Match, compile_path
from starlette.types import Scope

# Every allowed API surface is identified by method and FastAPI route template.
# Anything not in this set is denied before endpoint execution. A separate
# inventory regression test pins the complete reviewed allow/block decision set.
PUBLIC_GUEST_ALLOWED_API_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("POST", "/guest/session"),
        ("GET", "/regions"),
        ("GET", "/regions/resolve"),
        ("GET", "/regions/search"),
        ("GET", "/regions/{region_id}"),
        ("GET", "/regions/{region_id}/sources"),
        ("GET", "/metadata/coverage"),
        ("GET", "/companies/search"),
        ("GET", "/companies/{company_id}"),
        ("GET", "/companies/{company_id}/regions"),
        ("GET", "/companies/{company_id}/sources"),
        ("GET", "/compare"),
        ("GET", "/markets/imported"),
        ("GET", "/markets/imported/health"),
        ("GET", "/markets/imported/{market_key}/health"),
        ("GET", "/markets/imported/{market_key}/sources"),
        ("GET", "/markets/imported/{market_key}/facts"),
        ("GET", "/markets/imported/{market_key}/gaps"),
        ("GET", "/markets/imported/{market_key}/ranking-diagnostics"),
        ("GET", "/markets/imported/{market_key}/refresh-readiness"),
        ("GET", "/markets/imported/{market_key}/diff-preview"),
        ("GET", "/market-intelligence"),
        ("GET", "/market-intelligence/{market_key}"),
        ("GET", "/market-comparisons"),
        ("GET", "/market-comparisons/{market_a}/{market_b}"),
        ("GET", "/career-goal-comparisons"),
        ("GET", "/career-goal-comparisons/{goal}"),
        ("POST", "/discover/personalized"),
        ("GET", "/recommendations/goal-modes"),
        ("POST", "/recommendations/strategy"),
        ("POST", "/career-agent/answers"),
        ("POST", "/career-agent/action-plans"),
        ("GET", "/data-standards/definitions"),
        ("GET", "/data-standards/partner-schema"),
        ("GET", "/data-standards/partners"),
        ("GET", "/data-standards/partners/{partner_id}"),
        ("GET", "/data-standards/quality-labels"),
        ("GET", "/data-standards/governance-framework"),
        ("POST", "/data-standards/quality-labels/evaluate"),
        ("GET", "/public/benchmarks"),
        ("GET", "/public/benchmarks/{slug}"),
        ("GET", "/public/reports"),
        ("GET", "/public/reports/{slug}"),
        ("GET", "/opportunities"),
        ("GET", "/opportunities/{opportunity_id}"),
        ("POST", "/opportunities/routes"),
        ("GET", "/trust/explanation"),
        ("GET", "/exceptions/subject-status"),
        ("GET", "/user-intelligence/dashboard"),
        ("GET", "/policy/regions/{region_id}/workforce-dashboard"),
        ("GET", "/policy/regions/{region_id}/early-career-access"),
        ("GET", "/policy/regions/{region_id}/employer-concentration"),
        ("GET", "/policy/regions/{region_id}/economic-development"),
        ("GET", "/policy/regions/{region_id}/peer-comparison"),
        ("GET", "/policy/regions/{region_id}/education-alignment"),
        ("GET", "/policy/regions/{region_id}/reports/{report_id}"),
        ("GET", "/platform/history/regions/{region_id}"),
        ("GET", "/platform/history/companies/{company_id}"),
        ("GET", "/platform/signals/regions/{region_id}"),
        ("GET", "/platform/indices"),
        ("GET", "/platform/indices/{index_key}/scores"),
        ("GET", "/platform/reports"),
        ("GET", "/platform/reports/{report_key}"),
        ("GET", "/platform/predictive/reports"),
        ("GET", "/api/v1/platform/docs/openapi.json"),
        ("GET", "/api/v1/platform/docs/postman.json"),
        ("GET", "/api/v1/platform/embeds/{embed_product_slug}"),
        ("GET", "/api/v1/platform/regions/{region_id}/scores"),
        ("GET", "/api/v1/platform/companies/{company_id}/geography"),
        ("GET", "/api/v1/platform/regions/{region_id}/early-career-access"),
        ("GET", "/api/v1/platform/markets/hiring-concentration"),
        ("GET", "/api/v1/platform/markets/compare"),
        ("GET", "/monetization/plans"),
        ("GET", "/monetization/features"),
        ("GET", "/monetization/reports"),
        ("GET", "/monetization/access-preview"),
        ("GET", "/billing/status"),
        ("POST", "/me/discover/personalized"),
        ("POST", "/me/career-agent/answers"),
        ("POST", "/me/career-agent/action-plans"),
        ("GET", "/me/career-memory"),
        ("PUT", "/me/career-memory"),
        ("DELETE", "/me/career-memory"),
        ("GET", "/me/decisions"),
        ("POST", "/me/decisions"),
        ("GET", "/me/decisions/{decision_id}"),
        ("PATCH", "/me/decisions/{decision_id}"),
        ("POST", "/me/decisions/{decision_id}/options"),
        ("POST", "/me/decisions/{decision_id}/compare"),
        ("GET", "/me/decisions/{decision_id}/journal"),
        ("POST", "/me/decisions/{decision_id}/select"),
        ("POST", "/me/decisions/{decision_id}/reopen"),
        ("POST", "/me/decisions/{decision_id}/plan"),
        ("POST", "/me/decisions/{decision_id}/deep-analysis"),
        ("GET", "/me/decisions/{decision_id}/deep-analysis"),
        ("GET", "/me/actions"),
        ("POST", "/me/decisions/{decision_id}/actions"),
        ("PATCH", "/me/actions/{action_id}"),
        ("POST", "/me/applications"),
        ("PATCH", "/me/applications/{application_id}/transition"),
        ("POST", "/me/outcomes"),
        ("GET", "/me/reviews/weekly"),
        ("GET", "/me/strategic-reviews"),
        ("GET", "/me/search-workspace"),
        ("POST", "/me/search-workspace/applications/track"),
        ("GET", "/me/career-identity"),
        ("POST", "/me/career-identity"),
        ("GET", "/me/career-identity/privacy"),
        ("PUT", "/me/career-identity/privacy"),
        ("POST", "/me/career-identity/facts"),
        ("PUT", "/me/career-identity/facts/{fact_id}"),
        ("POST", "/me/career-identity/facts/{fact_id}/confirm"),
        ("DELETE", "/me/career-identity/facts/{fact_id}"),
        ("GET", "/me/career-identity/evaluation"),
        ("POST", "/me/career-identity/ingest"),
        ("GET", "/me/explore/context"),
        ("POST", "/me/explore/markets"),
        ("POST", "/me/explore/markets/{market_ref}"),
        ("POST", "/me/explore/compare"),
        ("POST", "/me/explore/comparisons"),
        ("GET", "/me/explore/comparisons"),
        ("GET", "/me/explore/comparisons/{comparison_id}"),
        ("POST", "/me/explore/prioritize"),
        ("GET", "/current-opportunities"),
        ("GET", "/current-opportunities/matches"),
        ("GET", "/current-opportunities/coverage"),
        ("GET", "/current-opportunities/{opportunity_id}"),
        ("GET", "/me"),
        ("GET", "/me/preferences"),
        ("PUT", "/me/preferences"),
        ("DELETE", "/me/preferences"),
        ("POST", "/me/scoring-preview"),
        ("POST", "/me/explanations/region"),
        ("POST", "/me/explanations/company"),
        ("POST", "/me/explanations/comparison"),
        ("POST", "/me/recommendation-snapshots"),
        ("GET", "/me/recommendation-snapshots"),
        ("GET", "/me/recommendation-snapshots/{recommendation_snapshot_id}"),
        ("GET", "/me/feature-access/{feature_key}"),
        ("GET", "/monetization/me"),
        ("GET", "/monetization/entitlements"),
        ("GET", "/monetization/usage"),
    }
)


@lru_cache(maxsize=1)
def _compiled_allowed_routes() -> tuple[tuple[str, object], ...]:
    return tuple(
        (method, compile_path(template)[0])
        for method, template in sorted(PUBLIC_GUEST_ALLOWED_API_ROUTES)
    )


def public_guest_api_route_allowed(method: str, path: str) -> bool:
    normalized_method = method.upper()
    normalized_path = path if path == "/" else path.rstrip("/")
    return any(
        route_method == normalized_method and pattern.fullmatch(normalized_path)
        for route_method, pattern in _compiled_allowed_routes()
    )


def public_guest_scope_allowed(scope: Scope) -> bool:
    """Classify the exact FastAPI route selected by Starlette's route order.

    This prevents an allowed dynamic template such as
    ``/current-opportunities/{opportunity_id}`` from accidentally admitting a
    blocked static route such as ``/current-opportunities/diagnostics``.
    """

    app = scope.get("app")
    routes = getattr(app, "routes", ())
    method = str(scope.get("method", "")).upper()
    for route in routes:
        match, _child_scope = route.matches(scope)
        if match is Match.FULL:
            template = getattr(route, "path", None)
            return isinstance(template, str) and (
                method,
                template,
            ) in PUBLIC_GUEST_ALLOWED_API_ROUTES
    return False


_PUBLIC_TOP_LEVEL_EXACT = frozenset(
    {
        "/",
        "/benchmarks",
        "/data-standards",
        "/data-licensing",
        "/developers",
        "/career-market-guides",
        "/forecasts",
        "/reports",
        "/glossary",
        "/methodology",
        "/data-limitations",
        "/privacy",
        "/terms",
        "/sources",
    }
)
_PUBLIC_PREFIXES = (
    "/benchmarks/",
    "/reports/",
    "/developers/docs",
    "/embed/region-comparison",
    "/embed/market-score-card",
    "/best-cities/",
    "/compare/",
    "/career-markets/",
    "/roles/",
)
_MARKET_SECTIONS = frozenset(
    {
        "region",
        "company",
        "compare",
        "comparisons",
        "my-search",
        "dashboard",
        "intelligence",
        "discovery",
        "career-identity",
        "profile",
        "decisions",
        "decision-workspace",
        "recommendations",
        "career-agent",
        "agent",
        "opportunity-routes",
        "routes",
        "current-opportunities",
        "opportunities",
        "policy",
        "plans",
        "pricing",
        "account",
    }
)


def public_guest_frontend_path_allowed(path: str) -> bool:
    normalized = path if path == "/" else path.rstrip("/")
    if normalized in _PUBLIC_TOP_LEVEL_EXACT:
        return True
    if any(normalized.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return True
    parts = normalized.strip("/").split("/")
    if parts == ["markets"]:
        return True
    return len(parts) >= 2 and parts[0] == "markets" and parts[1] in _MARKET_SECTIONS
