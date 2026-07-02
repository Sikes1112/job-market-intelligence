"""Partner iframe embed policy and safe payload helpers for Layer 20."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlatformEmbedProductId(StrEnum):
    REGION_COMPARISON = "region_comparison"
    MARKET_SCORE_CARD = "market_score_card"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PlatformEmbedDenialReason(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN_EMBED_PRODUCT = "unknown_embed_product"
    MISSING_DOMAIN = "missing_domain"
    BLOCKED_DOMAIN = "blocked_domain"
    UNAPPROVED_DOMAIN = "unapproved_domain"


class PlatformEmbedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    embed_product_id: PlatformEmbedProductId
    label: str
    allowed_domains: tuple[str, ...]
    blocked_domains: tuple[str, ...] = Field(default_factory=tuple)
    attribution_required: bool = True
    freshness_required: bool = True
    source_summary_required: bool = True

    @model_validator(mode="after")
    def _requirements_hold(self) -> PlatformEmbedPolicy:
        if not (
            self.attribution_required
            and self.freshness_required
            and self.source_summary_required
        ):
            raise ValueError("Platform embeds require attribution, freshness, and source summary.")
        return self


class PlatformEmbedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason: PlatformEmbedDenialReason
    domain: str | None = None
    message: str


class PlatformEmbedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    embed_product_id: PlatformEmbedProductId
    title: str
    attribution: str
    freshness: dict
    confidence: dict
    source_summary: dict
    warnings: tuple[str, ...]
    metrics: tuple[dict, ...]


class PlatformEmbedAccessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: Literal[True] = True
    embed_product_id: PlatformEmbedProductId
    payload: PlatformEmbedPayload


PLATFORM_EMBED_POLICIES: dict[PlatformEmbedProductId, PlatformEmbedPolicy] = {
    PlatformEmbedProductId.REGION_COMPARISON: PlatformEmbedPolicy(
        embed_product_id=PlatformEmbedProductId.REGION_COMPARISON,
        label="Region comparison iframe",
        allowed_domains=("example.edu", "partners.example.org", "localhost", "127.0.0.1"),
        blocked_domains=("blocked.example", "scraper.example"),
    ),
    PlatformEmbedProductId.MARKET_SCORE_CARD: PlatformEmbedPolicy(
        embed_product_id=PlatformEmbedProductId.MARKET_SCORE_CARD,
        label="Market score card iframe",
        allowed_domains=("example.edu", "partners.example.org", "localhost", "127.0.0.1"),
        blocked_domains=("blocked.example", "scraper.example"),
    ),
}

_PLATFORM_EMBED_USAGE_EVENTS: list[dict] = []
_PLATFORM_EMBED_USAGE_EVENT_LIMIT = 500


def decide_platform_embed_domain(
    *,
    embed_product_id: PlatformEmbedProductId | str,
    origin: str | None,
) -> PlatformEmbedDecision:
    try:
        product_id = PlatformEmbedProductId(embed_product_id)
    except ValueError:
        return PlatformEmbedDecision(
            allowed=False,
            reason=PlatformEmbedDenialReason.UNKNOWN_EMBED_PRODUCT,
            domain=None,
            message="Unknown embed product.",
        )
    policy = PLATFORM_EMBED_POLICIES[product_id]
    domain = normalize_embed_origin_domain(origin)
    if domain is None:
        return PlatformEmbedDecision(
            allowed=False,
            reason=PlatformEmbedDenialReason.MISSING_DOMAIN,
            domain=None,
            message="Embed origin domain is required.",
        )
    if _domain_matches(domain, policy.blocked_domains):
        return PlatformEmbedDecision(
            allowed=False,
            reason=PlatformEmbedDenialReason.BLOCKED_DOMAIN,
            domain=domain,
            message="Embed origin domain is blocked.",
        )
    if not _domain_matches(domain, policy.allowed_domains):
        return PlatformEmbedDecision(
            allowed=False,
            reason=PlatformEmbedDenialReason.UNAPPROVED_DOMAIN,
            domain=domain,
            message="Embed origin domain is not approved.",
        )
    return PlatformEmbedDecision(
        allowed=True,
        reason=PlatformEmbedDenialReason.ALLOWED,
        domain=domain,
        message="Embed origin allowed.",
    )


def decide_platform_embed_request(
    *,
    embed_product_id: PlatformEmbedProductId | str,
    origin_header: str | None = None,
    referer_header: str | None = None,
    declared_origin: str | None = None,
) -> PlatformEmbedDecision:
    """Evaluate request-derived and declared origins against backend policy.

    Browser iframe requests do not consistently forward the parent origin to a
    frontend app API call. The backend still owns the decision: headers are
    evaluated when present, and the frontend may provide the parent origin it
    derived from ``ancestorOrigins`` or ``document.referrer``.
    """

    candidates = tuple(
        candidate
        for candidate in (origin_header, referer_header, declared_origin)
        if candidate and candidate.strip()
    )
    if not candidates:
        return decide_platform_embed_domain(
            embed_product_id=embed_product_id,
            origin=None,
        )

    unapproved: PlatformEmbedDecision | None = None
    for candidate in candidates:
        decision = decide_platform_embed_domain(
            embed_product_id=embed_product_id,
            origin=candidate,
        )
        if decision.reason is PlatformEmbedDenialReason.BLOCKED_DOMAIN:
            return decision
        if decision.allowed:
            return decision
        if decision.reason is PlatformEmbedDenialReason.UNAPPROVED_DOMAIN and unapproved is None:
            unapproved = decision
        elif unapproved is None:
            unapproved = decision

    return unapproved or decide_platform_embed_domain(
        embed_product_id=embed_product_id,
        origin=None,
    )


def platform_embed_product_id_from_route(value: str) -> PlatformEmbedProductId:
    return PlatformEmbedProductId(value.replace("-", "_"))


def build_platform_embed_access_payload(
    embed_product_id: PlatformEmbedProductId | str,
) -> PlatformEmbedAccessPayload:
    product_id = PlatformEmbedProductId(embed_product_id)
    return PlatformEmbedAccessPayload(
        embed_product_id=product_id,
        payload=build_platform_embed_payload(product_id),
    )


def build_platform_embed_payload(
    embed_product_id: PlatformEmbedProductId | str,
) -> PlatformEmbedPayload:
    product_id = PlatformEmbedProductId(embed_product_id)
    if product_id is PlatformEmbedProductId.REGION_COMPARISON:
        return PlatformEmbedPayload(
            embed_product_id=product_id,
            title="Regional market comparison",
            attribution=(
                "Powered by Job Market Intelligence. "
                "Verify important decisions independently."
            ),
            freshness=_freshness(),
            confidence={"level": "medium", "label": "Directional public-safe comparison"},
            source_summary={
                "data_basis": "public_safe_summary",
                "source_count": 2,
                "source_categories": ["region score summary", "company-region summaries"],
                "notes": ["No raw scrape records or source ids are exposed."],
            },
            warnings=(
                "Embed output is a summary view, not a raw export.",
                "Coverage and freshness vary by market.",
            ),
            metrics=(
                {"label": "Greater Boston", "opportunity": 0.81, "early_career_access": 0.86},
                {"label": "Greater Atlanta", "opportunity": 0.67, "early_career_access": 0.58},
            ),
        )
    return PlatformEmbedPayload(
        embed_product_id=product_id,
        title="Market score card",
        attribution=(
            "Powered by Job Market Intelligence. "
            "Verify important decisions independently."
        ),
        freshness=_freshness(),
        confidence={"level": "medium", "label": "Directional public-safe score"},
        source_summary={
            "data_basis": "public_safe_summary",
            "source_count": 1,
            "source_categories": ["region score summary"],
            "notes": ["Scoring rules and raw source records are withheld."],
        },
        warnings=("Score card is derived market intelligence, not comprehensive truth.",),
        metrics=(
            {"label": "Opportunity", "value": 0.81},
            {"label": "Early-career access", "value": 0.86},
            {"label": "Live market", "value": 0.68},
        ),
    )


def platform_embed_usage_tracking_hook(
    *,
    embed_product_id: PlatformEmbedProductId | str,
    origin: str | None,
    allowed: bool,
) -> dict:
    return {
        "embed_product_id": PlatformEmbedProductId(embed_product_id).value,
        "origin_domain": normalize_embed_origin_domain(origin),
        "allowed": allowed,
        "tracked_at": datetime.now(UTC).isoformat(),
        "event_type": "platform_embed_view" if allowed else "platform_embed_denied",
    }


def record_platform_embed_usage_event(
    *,
    embed_product_id: PlatformEmbedProductId | str,
    decision: PlatformEmbedDecision,
) -> dict:
    event = platform_embed_usage_tracking_hook(
        embed_product_id=embed_product_id,
        origin=decision.domain,
        allowed=decision.allowed,
    )
    event["denial_reason"] = None if decision.allowed else decision.reason.value
    _PLATFORM_EMBED_USAGE_EVENTS.append(event)
    if len(_PLATFORM_EMBED_USAGE_EVENTS) > _PLATFORM_EMBED_USAGE_EVENT_LIMIT:
        del _PLATFORM_EMBED_USAGE_EVENTS[
            : len(_PLATFORM_EMBED_USAGE_EVENTS) - _PLATFORM_EMBED_USAGE_EVENT_LIMIT
        ]
    return dict(event)


def list_platform_embed_usage_events() -> tuple[dict, ...]:
    return tuple(dict(event) for event in _PLATFORM_EMBED_USAGE_EVENTS)


def clear_platform_embed_usage_events() -> None:
    _PLATFORM_EMBED_USAGE_EVENTS.clear()


def normalize_embed_origin_domain(origin: str | None) -> str | None:
    if origin is None or not origin.strip():
        return None
    raw = origin.strip().lower()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.hostname
    return host.rstrip(".") if host else None


def _domain_matches(domain: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        normalized = pattern.lower().lstrip(".")
        if domain == normalized or domain.endswith(f".{normalized}"):
            return True
    return False


def _freshness() -> dict:
    return {
        "status": "partial",
        "freshness_expires_at": None,
        "last_updated_at": None,
    }
