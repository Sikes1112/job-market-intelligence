from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, func, select, text

from backend.api.app import create_app
from backend.config.settings import AppEnv, Settings
from backend.public_guest.models import PublicGuestSession
from backend.public_guest.policy import PUBLIC_GUEST_ALLOWED_API_ROUTES
from backend.public_guest.service import (
    PUBLIC_GUEST_COOKIE_NAME,
    PUBLIC_GUEST_PROVIDER,
    VerifiedGuestPrincipal,
)
from backend.shared.db import create_all, make_engine, make_session_factory
from backend.users.models import ExternalAuthIdentity, User, UserProfile
from seeds.mvp_seed import run_seed
from seeds.portfolio_seed import run_portfolio_seed
from seeds.reviewer_scenarios import LOCAL_DEMO_ISSUER, LOCAL_DEMO_SUBJECT

ORIGIN = "https://demo.example"


def test_public_guest_settings_are_strict_and_isolated(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    assert settings.app_env == AppEnv.PUBLIC_GUEST_DEMO
    assert settings.is_public_guest_demo is True
    assert settings.is_public_demo_read_only is False
    assert settings.api_docs_enabled is False
    assert settings.beta_access_required is False
    assert settings.readiness_require_migration_current is True
    assert settings.rate_limit_enabled is True
    assert settings.security_headers_enabled is True
    assert settings.max_request_body_bytes == 65_536
    assert settings.rate_limit_requests == 60

    invalid_values = (
        {"database_url": "postgresql://db.example/jmi"},
        {"public_origin": "http://demo.example"},
        {"public_origin": ""},
        {"auth0_issuer": "https://tenant.auth0.com/"},
        {"stripe_secret_key": "sk_test_not_allowed"},
        {"api_docs_enabled": True},
        {"beta_access_required": True},
        {"rate_limit_enabled": False},
        {"security_headers_enabled": False},
        {"readiness_require_migration_current": False},
        {"guest_session_ttl_seconds": 86_400},
        {"guest_max_active_sessions": 251},
        {"max_request_body_bytes": 65_537},
        {"rate_limit_requests": 61},
        {"rate_limit_window_seconds": 59},
        {"guest_session_issue_window_seconds": 59},
    )
    for values in invalid_values:
        with pytest.raises(ValidationError):
            _settings(tmp_path, **values)

    production = Settings(
        app_env="production",
        database_url="postgresql://user:pass@db.example/jmi",
        cors_allowed_origins="https://app.example",
        auth0_issuer="https://tenant.auth0.com/",
        auth0_audience="https://api.example",
        release_id="release-1",
        api_docs_enabled=False,
        _env_file=None,
    )
    assert production.is_public_guest_demo is False


def test_route_inventory_is_explicit_and_unknown_routes_fail_closed(tmp_path: Path) -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    app = create_app(engine=engine, settings=_settings(tmp_path))
    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.name
        not in {"public-guest-spa-root", "public-guest-spa-fallback"}
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}
    }
    reviewed: dict[tuple[str, str], str] = {}
    inventory_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "public_guest"
        / "route_inventory.txt"
    )
    for line in inventory_path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        decision, method, route_path = line.split("\t")
        reviewed[(method, route_path)] = decision

    assert set(reviewed) == actual
    assert {
        key for key, decision in reviewed.items() if decision == "ALLOW"
    } == PUBLIC_GUEST_ALLOWED_API_ROUTES
    assert all(decision in {"ALLOW", "BLOCK"} for decision in reviewed.values())

    client = TestClient(app, base_url=ORIGIN)
    denied = client.get("/admin/operations/health")
    assert denied.status_code == 403
    assert denied.json()["error"]["type"] == "public_guest_route_denied"
    unknown = client.get("/api/new-unreviewed-route")
    assert unknown.status_code == 403
    assert unknown.headers["content-type"].startswith("application/json")
    # Static blocked routes must not be admitted by an allowed dynamic sibling.
    assert client.get("/current-opportunities/diagnostics").status_code == 403
    assert client.get("/opportunities/submissions").status_code == 403


def test_guest_session_cookie_digest_csrf_and_spoofing_boundaries(tmp_path: Path) -> None:
    app, engine = _app(tmp_path)
    first = TestClient(app, base_url=ORIGIN)
    second = TestClient(app, base_url=ORIGIN)

    local_claim_spoof = second.get(
        "/me",
        headers={
            "X-Verified-OIDC-Claims": (
                '{"iss":"https://local.job-market-intelligence.test/",'
                '"sub":"local|explorer"}'
            )
        },
    )
    assert local_claim_spoof.status_code == 401
    assert local_claim_spoof.json()["error"]["type"] == "guest_session_required"

    cross_origin = first.post("/guest/session", headers={"Origin": "https://evil.example"})
    assert cross_origin.status_code == 403
    assert not first.cookies.get(PUBLIC_GUEST_COOKIE_NAME)

    first_csrf = _bootstrap(first)
    second_csrf = _bootstrap(second)
    first_token = first.cookies.get(PUBLIC_GUEST_COOKIE_NAME)
    second_token = second.cookies.get(PUBLIC_GUEST_COOKIE_NAME)
    assert first_token and second_token and first_token != second_token

    reused = first.post("/guest/session", headers={"Origin": ORIGIN})
    assert reused.status_code == 200
    first_csrf = reused.json()["data"]["csrf_token"]
    set_cookie = reused.headers["set-cookie"]
    assert f"{PUBLIC_GUEST_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Domain=" not in set_cookie

    factory = make_session_factory(engine)
    with factory() as session:
        rows = list(session.scalars(select(PublicGuestSession)))
        identities = list(
            session.scalars(
                select(ExternalAuthIdentity).where(
                    ExternalAuthIdentity.provider == PUBLIC_GUEST_PROVIDER
                )
            )
        )
    assert len(rows) == 2
    assert len({row.user_id for row in rows}) == 2
    assert len(identities) == 2
    assert all(row.token_digest not in {first_token, second_token} for row in rows)
    assert all(len(row.token_digest) == 64 for row in rows)

    missing_csrf = first.post(
        "/me/career-identity", headers={"Origin": ORIGIN}
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["type"] == "guest_csrf_invalid"
    bad_origin = first.post(
        "/me/career-identity",
        headers={"Origin": "https://evil.example", "X-CSRF-Token": first_csrf},
    )
    assert bad_origin.status_code == 403

    initialized = first.post(
        "/me/career-identity", headers=_unsafe_headers(first_csrf)
    )
    assert initialized.status_code == 201
    spoofed = first.get(
        "/me",
        headers={
            "X-Verified-OIDC-Claims": (
                '{"iss":"https://evil.example/","sub":"admin",'
                '"https://jmi.example/admin_role":"admin"}'
            )
        },
    )
    assert spoofed.status_code == 200
    first_user_id = spoofed.json()["data"]["user"]["user_id"]
    with factory() as session:
        row = session.scalar(
            select(PublicGuestSession).where(
                PublicGuestSession.token_digest == rows[0].token_digest
            )
        )
        assert row is not None
    assert first_user_id in {item.user_id for item in rows}

    # The second client's token and CSRF remain independently valid.
    assert second.post(
        "/me/career-identity", headers=_unsafe_headers(second_csrf)
    ).status_code == 201


def test_concurrent_guest_reads_do_not_contend_on_session_touch(tmp_path: Path) -> None:
    database_path = tmp_path / "concurrent-reads.db"
    engine = make_engine(f"sqlite:///{database_path}")
    create_all(engine)
    app = create_app(
        engine=engine,
        settings=_settings(tmp_path, database_url=f"sqlite:///{database_path}"),
    )
    client = TestClient(app, base_url=ORIGIN)
    _bootstrap(client)

    factory = make_session_factory(engine)
    with factory() as session:
        session_before = session.scalar(select(PublicGuestSession)).last_seen_at
        identity_before = session.scalar(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.provider == PUBLIC_GUEST_PROVIDER
            )
        ).last_seen_at

    writes: list[str] = []
    writes_lock = threading.Lock()

    def capture_writes(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        operation = statement.lstrip().split(None, 1)[0].upper()
        if operation in {"INSERT", "UPDATE", "DELETE"}:
            with writes_lock:
                writes.append(statement)

    event.listen(engine, "before_cursor_execute", capture_writes)

    paths = ["/me", "/me/preferences", "/me/recommendation-snapshots"] * 4
    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            responses = list(executor.map(client.get, paths))
    finally:
        event.remove(engine, "before_cursor_execute", capture_writes)

    assert [response.status_code for response in responses] == [200] * len(paths)
    assert writes == []
    with factory() as session:
        assert session.scalar(select(PublicGuestSession)).last_seen_at == session_before
        assert (
            session.scalar(
                select(ExternalAuthIdentity).where(
                    ExternalAuthIdentity.provider == PUBLIC_GUEST_PROVIDER
                )
            ).last_seen_at
            == identity_before
        )


def test_missing_guest_identity_mapping_fails_closed_without_recreation(
    tmp_path: Path,
) -> None:
    app, engine = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    _bootstrap(client)
    factory = make_session_factory(engine)
    with factory() as session:
        identity = session.scalar(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.provider == PUBLIC_GUEST_PROVIDER
            )
        )
        assert identity is not None
        session.delete(identity)
        session.commit()

    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "guest_session_invalid"
    with factory() as session:
        assert session.scalar(select(ExternalAuthIdentity)) is None


def test_inconsistent_guest_identity_mapping_fails_closed(tmp_path: Path) -> None:
    app, engine = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    _bootstrap(client)
    factory = make_session_factory(engine)
    with factory() as session:
        identity = session.scalar(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.provider == PUBLIC_GUEST_PROVIDER
            )
        )
        assert identity is not None
        other_user = User(user_id="user_inconsistent_guest_mapping")
        session.add(other_user)
        session.flush()
        session.add(UserProfile(user_id=other_user.user_id))
        identity.user_id = other_user.user_id
        session.commit()

    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "guest_session_invalid"


def test_authenticated_guest_read_stays_responsive_during_independent_write(
    tmp_path: Path,
) -> None:
    app, engine = _file_app(tmp_path, "read-during-write.db")
    client = TestClient(app, base_url=ORIGIN)
    _bootstrap(client)
    blocker = engine.raw_connection()
    blocker.cursor().execute("BEGIN IMMEDIATE")
    try:
        started = time.perf_counter()
        response = client.get("/me")
        elapsed = time.perf_counter() - started
    finally:
        blocker.rollback()
        blocker.close()

    assert response.status_code == 200
    assert elapsed < 1.0


def test_guest_sqlite_wait_does_not_block_independent_safe_request(
    tmp_path: Path,
) -> None:
    app, engine = _file_app(tmp_path, "threadpool-wait.db")
    bootstrap_client = TestClient(app, base_url=ORIGIN)
    csrf = _bootstrap(bootstrap_client)
    token = bootstrap_client.cookies.get(PUBLIC_GUEST_COOKIE_NAME)
    assert token is not None

    quota_write_attempted = threading.Event()

    def detect_quota_write(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("update public_guest_sessions"):
            quota_write_attempted.set()

    event.listen(engine, "before_cursor_execute", detect_quota_write)
    blocker = engine.raw_connection()
    blocker.cursor().execute("BEGIN IMMEDIATE")

    async def exercise() -> tuple[httpx.Response, httpx.Response, float]:
        transport = httpx.ASGITransport(app=app)
        async with (
            httpx.AsyncClient(
                transport=transport,
                base_url=ORIGIN,
                cookies={PUBLIC_GUEST_COOKIE_NAME: token},
            ) as authenticated,
            httpx.AsyncClient(transport=transport, base_url=ORIGIN) as independent,
        ):
            mutation = asyncio.create_task(
                authenticated.post(
                    "/me/decisions",
                    headers=_unsafe_headers(csrf),
                    json={"decision_type": "career_path", "title": "Threaded quota"},
                )
            )
            assert await asyncio.to_thread(quota_write_attempted.wait, 2.0)
            started = time.perf_counter()
            health = await asyncio.wait_for(independent.get("/health"), timeout=1.0)
            elapsed = time.perf_counter() - started
            blocker.rollback()
            result = await asyncio.wait_for(mutation, timeout=2.0)
            return health, result, elapsed

    try:
        health, mutation, elapsed = asyncio.run(exercise())
    finally:
        blocker.rollback()
        blocker.close()
        event.remove(engine, "before_cursor_execute", detect_quota_write)

    assert health.status_code == 200
    assert elapsed < 1.0
    assert mutation.status_code == 201


def test_concurrent_guest_mutation_quota_is_atomic(tmp_path: Path) -> None:
    app, engine = _file_app(
        tmp_path,
        "atomic-quota.db",
        guest_max_mutations_per_session=1,
    )
    async def exercise() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            bootstrap = await client.post("/guest/session", headers={"Origin": ORIGIN})
            assert bootstrap.status_code == 201
            csrf = bootstrap.json()["data"]["csrf_token"]

            async def mutate(role: str) -> httpx.Response:
                return await client.put(
                    "/me/preferences",
                    headers=_unsafe_headers(csrf),
                    json={"role_interests": [role]},
                )

            return list(await asyncio.gather(mutate("product"), mutate("engineering")))

    responses = asyncio.run(exercise())

    assert sorted(response.status_code for response in responses) == [200, 429]
    factory = make_session_factory(engine)
    with factory() as session:
        guest = session.scalar(select(PublicGuestSession))
        assert guest is not None
        assert guest.mutation_count == 1


def test_verified_guest_state_is_ignored_outside_guest_environment() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    app = create_app(
        engine=engine,
        settings=Settings(app_env="test", database_url="sqlite:///:memory:", _env_file=None),
    )

    @app.middleware("http")
    async def inject_guest_state(request, call_next):  # noqa: ANN001
        request.state.verified_guest_principal = VerifiedGuestPrincipal(
            session_id="guest_session_forged",
            user_id="user_forged",
            provider=PUBLIC_GUEST_PROVIDER,
            issuer="urn:jmi:public-guest",
            subject="guest_forged",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        return await call_next(request)

    response = TestClient(app).get("/me")
    assert response.status_code == 401


def test_two_guest_clients_are_isolated_across_owned_workflows(tmp_path: Path) -> None:
    app, engine = _app(tmp_path, seed_portfolio=True)
    owner = TestClient(app, base_url=ORIGIN)
    other = TestClient(app, base_url=ORIGIN)
    owner_csrf = _bootstrap(owner)
    other_csrf = _bootstrap(other)

    identity = owner.get("/me/career-identity").json()["data"]
    consent = owner.put(
        "/me/career-identity/privacy",
        headers=_unsafe_headers(owner_csrf),
        json={
            "downstream_personalization_consent_granted": True,
            "expected_version": identity["current_version"],
        },
    )
    assert consent.status_code == 200
    fact = owner.post(
        "/me/career-identity/facts",
        headers=_unsafe_headers(owner_csrf),
        json={
            "fact_type": "skill",
            "payload": {"name": "Python"},
            "state": "explicit",
            "expected_version": consent.json()["data"]["current_version"],
        },
    )
    assert fact.status_code == 201
    fact_id = fact.json()["data"]["career_identity_fact_id"]
    assert other.post(
        f"/me/career-identity/facts/{fact_id}/confirm",
        headers=_unsafe_headers(other_csrf),
        json={},
    ).status_code == 404

    preferences = owner.put(
        "/me/preferences",
        headers=_unsafe_headers(owner_csrf),
        json={"role_interests": ["product"], "industry_interests": ["software"]},
    )
    assert preferences.status_code == 200
    assert owner.get("/me/preferences").json()["data"]["persisted"] is True
    assert other.get("/me/preferences").json()["data"]["persisted"] is False

    compared = owner.post(
        "/me/explore/compare",
        headers=_unsafe_headers(owner_csrf),
        json={"market_refs": ["boston", "new-york"], "session_overrides": {}},
    )
    assert compared.status_code == 200
    comparison = compared.json()["data"]
    saved = owner.post(
        "/me/explore/comparisons",
        headers=_unsafe_headers(owner_csrf),
        json={
            "market_refs": ["boston", "new-york"],
            "session_overrides": {},
            "comparison_identity": comparison["comparison_identity"],
        },
    )
    assert saved.status_code == 201
    comparison_id = saved.json()["data"]["comparison"]["comparison_id"]
    assert other.get(f"/me/explore/comparisons/{comparison_id}").status_code == 404

    decision = owner.post(
        "/me/decisions",
        headers=_unsafe_headers(owner_csrf),
        json={"decision_type": "career_path", "title": "Choose a path"},
    )
    assert decision.status_code == 201
    decision_id = decision.json()["data"]["decision"]["decision_id"]
    assert other.get(f"/me/decisions/{decision_id}").status_code == 404

    action = owner.post(
        f"/me/decisions/{decision_id}/actions",
        headers=_unsafe_headers(owner_csrf),
        json={"action_type": "research", "title": "Research the role"},
    )
    assert action.status_code == 201
    action_id = action.json()["data"]["action"]["action_id"]
    assert other.patch(
        f"/me/actions/{action_id}",
        headers=_unsafe_headers(other_csrf),
        json={"status": "completed"},
    ).status_code == 404

    application = owner.post(
        "/me/applications",
        headers=_unsafe_headers(owner_csrf),
        json={
            "decision_id": decision_id,
            "action_id": action_id,
            "status": "applied",
            "role_title": "Product Manager",
        },
    )
    assert application.status_code == 201
    application_id = application.json()["data"]["application"]["application_id"]
    assert other.patch(
        f"/me/applications/{application_id}/transition",
        headers=_unsafe_headers(other_csrf),
        json={"to_status": "interview"},
    ).status_code == 404

    with make_session_factory(engine)() as session:
        guests = list(session.scalars(select(PublicGuestSession)))
    assert len({guest.user_id for guest in guests}) == 2


def test_expired_revoked_reset_and_quota_fail_safely(tmp_path: Path) -> None:
    app, engine = _app(tmp_path, guest_max_decisions=1)
    client = TestClient(app, base_url=ORIGIN)
    csrf = _bootstrap(client)
    old_token = client.cookies.get(PUBLIC_GUEST_COOKIE_NAME)

    first = client.post(
        "/me/decisions",
        headers=_unsafe_headers(csrf),
        json={"decision_type": "career_path", "title": "One"},
    )
    assert first.status_code == 201
    quota = client.post(
        "/me/decisions",
        headers=_unsafe_headers(csrf),
        json={"decision_type": "career_path", "title": "Two"},
    )
    assert quota.status_code == 429
    assert quota.json()["error"]["type"] == "guest_quota_exceeded"

    factory = make_session_factory(engine)
    with factory() as session:
        row = session.scalar(select(PublicGuestSession))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    expired = client.get("/me")
    assert expired.status_code == 401
    assert expired.json()["error"]["type"] == "guest_session_expired"

    refreshed = client.post("/guest/session", headers={"Origin": ORIGIN})
    assert refreshed.status_code == 201
    assert client.cookies.get(PUBLIC_GUEST_COOKIE_NAME) != old_token

    with factory() as session:
        active = session.scalar(select(PublicGuestSession))
        assert active is not None
        active.revoked_at = datetime.now(UTC)
        session.commit()
    revoked = client.get("/me")
    assert revoked.status_code == 401
    assert revoked.json()["error"]["type"] == "guest_session_expired"
    assert client.post("/guest/session", headers={"Origin": ORIGIN}).status_code == 201

    reset_token = client.cookies.get(PUBLIC_GUEST_COOKIE_NAME)
    reset_app, _reset_engine = _app(tmp_path, guest_max_decisions=1)
    reset_client = TestClient(reset_app, base_url=ORIGIN)
    reset_client.cookies.set(
        PUBLIC_GUEST_COOKIE_NAME,
        reset_token,
        domain="demo.example",
        path="/",
    )
    reset = reset_client.post("/guest/session", headers={"Origin": ORIGIN})
    assert reset.status_code == 201
    assert reset.json()["data"]["created"] is True
    assert reset.json()["data"]["replaced"] is True
    assert reset_client.cookies.get(PUBLIC_GUEST_COOKIE_NAME) != reset_token


def test_spa_and_api_cache_boundaries(tmp_path: Path) -> None:
    app, _engine = _app(tmp_path)
    client = TestClient(app, base_url=ORIGIN)

    root = client.get("/", headers={"Accept": "text/html"})
    assert root.status_code == 200
    assert root.headers["cache-control"].startswith("no-cache")
    deep = client.get("/markets/decisions", headers={"Accept": "text/html"})
    assert deep.status_code == 200
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]

    unknown_html = client.get("/not-a-real-page", headers={"Accept": "text/html"})
    assert unknown_html.status_code == 403
    unknown_api = client.get("/api/not-real", headers={"Accept": "application/json"})
    assert unknown_api.status_code == 403
    assert unknown_api.headers["content-type"].startswith("application/json")

    bootstrap = client.post("/guest/session", headers={"Origin": ORIGIN})
    assert bootstrap.headers["cache-control"] == "no-store, private"
    assert "csrf_token" in bootstrap.json()["data"]
    assert PUBLIC_GUEST_COOKIE_NAME not in bootstrap.text
    authenticated_asset = client.get("/assets/app.js")
    assert "immutable" in authenticated_asset.headers["cache-control"]


def test_public_resource_limits_reject_safely(tmp_path: Path) -> None:
    rate_app, _ = _app(tmp_path, guest_session_issue_requests=1)
    first = TestClient(rate_app, base_url=ORIGIN)
    second = TestClient(rate_app, base_url=ORIGIN)
    assert first.post("/guest/session", headers={"Origin": ORIGIN}).status_code == 201
    limited = second.post("/guest/session", headers={"Origin": ORIGIN})
    assert limited.status_code == 429
    assert limited.json()["error"]["type"] == "guest_session_rate_limited"

    capacity_app, _ = _app(tmp_path, guest_max_active_sessions=1)
    capacity_first = TestClient(capacity_app, base_url=ORIGIN)
    capacity_second = TestClient(capacity_app, base_url=ORIGIN)
    assert _bootstrap(capacity_first)
    capacity = capacity_second.post("/guest/session", headers={"Origin": ORIGIN})
    assert capacity.status_code == 503
    assert capacity.json()["error"]["type"] == "guest_capacity_reached"

    body_app, _ = _app(tmp_path, max_request_body_bytes=128)
    body_client = TestClient(body_app, base_url=ORIGIN)
    csrf = _bootstrap(body_client)
    oversized = body_client.post(
        "/me/decisions",
        headers=_unsafe_headers(csrf),
        content=b"x" * 129,
    )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["type"] == "request_too_large"

    full_database_path = tmp_path / "full.db"
    full_engine = make_engine(f"sqlite:///{full_database_path}")
    create_all(full_engine)
    full_app = create_app(
        engine=full_engine,
        settings=_settings(
            tmp_path,
            database_url=f"sqlite:///{full_database_path}",
            guest_max_database_bytes=1,
        ),
    )
    full_client = TestClient(full_app, base_url=ORIGIN)
    full = full_client.post("/guest/session", headers={"Origin": ORIGIN})
    assert full.status_code == 503
    assert full.json()["error"]["type"] == "guest_capacity_reached"


def test_public_guest_startup_migrates_seeds_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "public-guest.db"
    settings = _settings(
        tmp_path,
        database_url=f"sqlite:///{database_path}",
    )

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as first:
        ready = first.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["checks"]["schema"] == "current"
        regions = first.get("/regions")
        assert regions.status_code == 200
        assert len(regions.json()["data"]["regions"]) >= 8
        old_token = first.post(
            "/guest/session", headers={"Origin": ORIGIN}
        ).cookies.get(PUBLIC_GUEST_COOKIE_NAME)

    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    with factory() as session:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        reviewer = session.scalar(
            select(ExternalAuthIdentity).where(
                ExternalAuthIdentity.issuer == LOCAL_DEMO_ISSUER,
                ExternalAuthIdentity.subject == LOCAL_DEMO_SUBJECT,
            )
        )
    engine.dispose()
    assert revision == "0047_public_guest_sessions"
    assert reviewer is None

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as repeated:
        assert repeated.get("/ready").status_code == 200

    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        if candidate.exists():
            candidate.unlink()

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as reset:
        reset.cookies.set(
            PUBLIC_GUEST_COOKIE_NAME,
            old_token,
            domain="demo.example",
            path="/",
        )
        recovered = reset.post("/guest/session", headers={"Origin": ORIGIN})
        assert recovered.status_code == 201
        assert recovered.cookies.get(PUBLIC_GUEST_COOKIE_NAME) != old_token


def test_public_guest_startup_failure_prevents_service_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(
        tmp_path,
        database_url=f"sqlite:///{tmp_path / 'startup-failure.db'}",
    )

    def fail_initialization(_settings: Settings, _engine) -> None:
        raise RuntimeError("seed failed")

    monkeypatch.setattr(
        "backend.api.app.initialize_public_guest_database", fail_initialization
    )
    with pytest.raises(RuntimeError, match="seed failed"):
        with TestClient(create_app(settings=settings), base_url=ORIGIN):
            pass


def test_four_guest_mixed_explore_and_write_workload_is_consistent(
    tmp_path: Path,
) -> None:
    app, engine = _file_app(tmp_path, "mixed-four-guest.db", seed_portfolio=True)
    clients = [TestClient(app, base_url=ORIGIN) for _ in range(4)]
    csrf_tokens = [_bootstrap(client) for client in clients]
    expected_titles: dict[int, set[str]] = {index: set() for index in range(4)}
    observations: list[tuple[int, int, float, float]] = []

    def visitor_round(index: int, round_number: int) -> tuple[int, int, float, float]:
        client = clients[index]
        title = f"Visitor {index} decision {round_number}"
        expected_titles[index].add(title)
        explore_started = time.perf_counter()
        explore = client.post(
            "/me/explore/markets",
            headers=_unsafe_headers(csrf_tokens[index]),
            json={"session_overrides": {}},
        )
        explore_seconds = time.perf_counter() - explore_started
        write_started = time.perf_counter()
        decision = client.post(
            "/me/decisions",
            headers=_unsafe_headers(csrf_tokens[index]),
            json={"decision_type": "career_path", "title": title},
        )
        write_seconds = time.perf_counter() - write_started
        return explore.status_code, decision.status_code, explore_seconds, write_seconds

    for round_number in range(3):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(visitor_round, index, round_number)
                for index in range(4)
            ]
            observations.extend(future.result() for future in futures)

    assert [(explore, write) for explore, write, _er, _wr in observations] == [
        (200, 201)
    ] * 12

    seen_ids: set[str] = set()
    for index, client in enumerate(clients):
        response = client.get("/me/decisions")
        assert response.status_code == 200
        decisions = response.json()["data"]["decisions"]
        assert {decision["title"] for decision in decisions} == expected_titles[index]
        ids = {decision["decision_id"] for decision in decisions}
        assert len(ids) == 3
        assert seen_ids.isdisjoint(ids)
        seen_ids.update(ids)
        client.close()

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM career_decisions"
        ).scalar_one() == 12
    assert engine.pool.checkedout() == 0


def _settings(tmp_path: Path, **overrides) -> Settings:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'></div>")
    (assets / "app.js").write_text("console.log('guest demo')")
    values = {
        "app_env": "public_guest_demo",
        "database_url": "sqlite:///:memory:",
        "public_origin": ORIGIN,
        "frontend_dist_dir": str(dist),
        "release_id": "test-release",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _app(tmp_path: Path, *, seed_portfolio: bool = False, **setting_overrides):
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    if seed_portfolio:
        factory = make_session_factory(engine)
        with factory() as session:
            now = datetime.now(UTC)
            seed_result = run_seed(session, demo_now=now)
            run_portfolio_seed(
                session,
                seed_result,
                as_of=now.date(),
                demo_now=now,
                include_reviewer=False,
            )
            session.commit()
    return create_app(engine=engine, settings=_settings(tmp_path, **setting_overrides)), engine


def _file_app(
    tmp_path: Path,
    database_name: str,
    *,
    seed_portfolio: bool = False,
    **setting_overrides,
):
    database_path = tmp_path / database_name
    database_url = f"sqlite:///{database_path}"
    engine = make_engine(database_url)
    create_all(engine)
    if seed_portfolio:
        factory = make_session_factory(engine)
        with factory() as session:
            now = datetime.now(UTC)
            seed_result = run_seed(session, demo_now=now)
            run_portfolio_seed(
                session,
                seed_result,
                as_of=now.date(),
                demo_now=now,
                include_reviewer=False,
            )
            session.commit()
    settings = _settings(tmp_path, database_url=database_url, **setting_overrides)
    return create_app(engine=engine, settings=settings), engine


def _bootstrap(client: TestClient) -> str:
    response = client.post("/guest/session", headers={"Origin": ORIGIN})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, private"
    return response.json()["data"]["csrf_token"]


def _unsafe_headers(csrf_token: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}


@pytest.mark.parametrize("first_path", ["direct", "prioritize"])
def test_decision_quota_covers_all_creation_paths_and_preserves_reuse(
    tmp_path: Path,
    first_path: str,
) -> None:
    from backend.career_decisions.models import (
        CareerDecision,
        DecisionContextSnapshot,
        DecisionOption,
        DecisionVersion,
    )
    from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
    from backend.product_measurement.models import ProductAnalyticsEvent

    app, engine = _file_app(tmp_path, "quota-paths.db", seed_portfolio=True, guest_max_decisions=1)
    owner = TestClient(app, base_url=ORIGIN)
    other = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(owner))
    other_headers = _unsafe_headers(_bootstrap(other))
    base = {"market_refs": ["boston", "new-york"], "session_overrides": {}}
    comparison = owner.post("/me/explore/compare", headers=headers, json=base).json()["data"]
    saved = owner.post(
        "/me/explore/comparisons",
        headers=headers,
        json={
            **base,
            "comparison_identity": comparison["comparison_identity"],
        },
    ).json()["data"]["comparison"]["comparison_id"]
    priority = {"comparison_id": saved, "selected_market_ref": "boston"}
    direct = {"decision_type": "career_path", "title": "Quota owner"}
    if first_path == "direct":
        first = owner.post("/me/decisions", headers=headers, json=direct)
        assert first.status_code == 201
        decision_id = first.json()["data"]["decision"]["decision_id"]
    else:
        first = owner.post("/me/explore/prioritize", headers=headers, json=priority)
        assert first.status_code == 200
        decision_id = first.json()["data"]["prioritization"]["decision_id"]
        reused = owner.post("/me/explore/prioritize", headers=headers, json=priority)
        assert reused.status_code == 200
        assert reused.json()["data"]["prioritization"]["created"] is False
        assert reused.json()["data"]["prioritization"]["decision_id"] == decision_id

    factory = make_session_factory(engine)

    def counts():
        with factory() as session:
            return tuple(
                session.scalar(select(func.count()).select_from(model))
                for model in (
                    CareerDecision,
                    ExploreComparisonSnapshot,
                    ExploreDecisionProvenance,
                    DecisionContextSnapshot,
                    DecisionOption,
                    DecisionVersion,
                    ProductAnalyticsEvent,
                )
            )

    before = counts()
    for path, body in (
        ("/me/decisions", direct),
        ("/me/explore/prioritize", {**priority, "selected_market_ref": "new-york"}),
    ):
        rejected = owner.post(path, headers=headers, json=body)
        assert rejected.status_code == 429
        assert rejected.json()["error"]["type"] == "guest_quota_exceeded"
        assert counts() == before
    assert owner.get(f"/me/decisions/{decision_id}").status_code == 200
    assert other.get(f"/me/decisions/{decision_id}").status_code == 404
    assert other.post("/me/decisions", headers=other_headers, json=direct).status_code == 201


@pytest.mark.parametrize("separate_app", [False, True])
def test_concurrent_cross_path_decision_quota_is_serialized(
    tmp_path: Path, separate_app: bool,
) -> None:
    from backend.career_decisions.models import CareerDecision

    app, engine = _file_app(
        tmp_path, "concurrent-decisions.db", seed_portfolio=True, guest_max_decisions=1
    )
    owner = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(owner))
    base = {"market_refs": ["boston", "new-york"], "session_overrides": {}}
    comparison = owner.post("/me/explore/compare", headers=headers, json=base).json()["data"]
    saved = owner.post(
        "/me/explore/comparisons",
        headers=headers,
        json={
            **base,
            "comparison_identity": comparison["comparison_identity"],
        },
    ).json()["data"]["comparison"]["comparison_id"]

    async def race():
        import httpx

        transport = httpx.ASGITransport(app=app)
        peer_app = create_app(engine=engine, settings=app.state.settings) if separate_app else app
        async with httpx.AsyncClient(
            transport=transport, base_url=ORIGIN, cookies=owner.cookies
        ) as client, httpx.AsyncClient(
            transport=httpx.ASGITransport(app=peer_app), base_url=ORIGIN, cookies=owner.cookies
        ) as peer:
            import asyncio

            # Both requests are scheduled on the same app event loop, as in Uvicorn.
            return await asyncio.gather(
                client.post(
                    "/me/decisions",
                    headers=headers,
                    json={"decision_type": "career_path", "title": "Racer"},
                ),
                peer.post(
                    "/me/explore/prioritize",
                    headers=headers,
                    json={
                        "comparison_id": saved,
                        "selected_market_ref": "boston",
                    },
                ),
            )

    import asyncio

    responses = asyncio.run(race())
    assert sorted(response.status_code for response in responses) in ([200, 429], [201, 429])
    with make_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(CareerDecision)) == 1


@pytest.mark.parametrize("limit", [1, 2])
def test_configured_decision_limit_rejects_only_new_insertions(tmp_path: Path, limit: int) -> None:
    app, _engine = _app(tmp_path, guest_max_decisions=limit)
    client = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(client))
    for index in range(limit):
        assert (
            client.post(
                "/me/decisions",
                headers=headers,
                json={
                    "decision_type": "career_path",
                    "title": f"Decision {index}",
                },
            ).status_code
            == 201
        )
    rejected = client.post(
        "/me/decisions",
        headers=headers,
        json={
            "decision_type": "career_path",
            "title": "Beyond quota",
        },
    )
    assert rejected.status_code == 429
    assert rejected.json()["error"]["type"] == "guest_quota_exceeded"

def _business_digest(engine):
    """Assert rollback across the complete business graph, excluding session accounting."""
    from sqlalchemy import MetaData

    metadata = MetaData()
    metadata.reflect(engine)
    with engine.connect() as connection:
        return {
            name: sorted(repr(tuple(row)) for row in connection.execute(select(table)))
            for name, table in metadata.tables.items()
            if name != "public_guest_sessions"
        }


@pytest.mark.parametrize("resource", ["options", "actions"])
@pytest.mark.parametrize("aggregate_first", [False, True])
def test_nested_resource_quota_cross_paths_and_rollback(tmp_path, resource, aggregate_first):
    settings = {"guest_max_decision_options" if resource == "options" else "guest_max_actions": 1}
    app, engine = _file_app(tmp_path, "nested.db", seed_portfolio=True, **settings)
    client, other = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    headers, peer_headers = _unsafe_headers(_bootstrap(client)), _unsafe_headers(_bootstrap(other))

    def new_decision(c=client, h=headers, **extra):
        return c.post(
            "/me/decisions",
            headers=h,
            json={
                "title": "Nested quota",
                "decision_type": "career_path",
                **extra,
            },
        )

    first = new_decision().json()["data"]["decision"]["decision_id"]
    second = new_decision().json()["data"]["decision"]["decision_id"]
    direct_path = f"/me/decisions/{first}/{resource}"
    payload = (
        {"title": "First"}
        if resource == "options"
        else {"title": "First", "action_type": "research"}
    )
    aggregate_path = "/me/decisions" if resource == "options" else f"/me/decisions/{second}/plan"
    aggregate = (
        {"title": "Embedded", "decision_type": "career_path", "options": [payload]}
        if resource == "options"
        else {"actions": [payload]}
    )
    paths = [(direct_path, payload), (aggregate_path, aggregate)]
    if aggregate_first:
        paths.reverse()
    assert client.post(paths[0][0], headers=headers, json=paths[0][1]).status_code == 201
    before = _business_digest(engine)
    rejected = client.post(paths[1][0], headers=headers, json=paths[1][1])
    assert rejected.status_code == 429
    assert rejected.json()["error"]["type"] == "guest_quota_exceeded"
    assert _business_digest(engine) == before
    assert client.get("/me/decisions/" + first).status_code == 200
    assert other.get("/me/decisions/" + first).status_code == 404
    # Distinct owner retains full quota capacity.
    peer = new_decision(other, peer_headers).json()["data"]["decision"]["decision_id"]
    assert (
        other.post(
            f"/me/decisions/{peer}/{resource}", headers=peer_headers, json=payload
        ).status_code
        == 201
    )
    if resource == "actions":
        plan_decision = second if aggregate_first else first
        before = _business_digest(engine)
        reused = client.post(f"/me/decisions/{plan_decision}/plan", headers=headers, json={})
        assert reused.status_code == 201
        assert _business_digest(engine) == before


@pytest.mark.parametrize("resource", ["options", "actions"])
def test_nested_batch_quota_rolls_back_parent_and_all_children(tmp_path, resource):
    settings = {"guest_max_decision_options" if resource == "options" else "guest_max_actions": 1}
    app, engine = _file_app(tmp_path, "batch.db", **settings)
    client = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(client))
    payload = {"title": "Batch", "decision_type": "career_path"}
    if resource == "options":
        path = "/me/decisions"
        payload["options"] = [{"title": "One"}, {"title": "Two"}]
    else:
        decision = client.post("/me/decisions", headers=headers, json=payload).json()["data"][
            "decision"
        ]["decision_id"]
        path = f"/me/decisions/{decision}/plan"
        payload = {}  # default generated plan contains multiple actions
    before = _business_digest(engine)
    assert client.post(path, headers=headers, json=payload).status_code == 429
    assert _business_digest(engine) == before


@pytest.mark.parametrize("resource", ["options", "actions"])
def test_concurrent_direct_and_aggregate_resource_quota(tmp_path, resource):
    from backend.career_decisions.models import CareerAction, DecisionOption

    settings = {"guest_max_decision_options" if resource == "options" else "guest_max_actions": 1}
    app, engine = _file_app(tmp_path, "race.db", **settings)
    owner = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(owner))
    ids = [
        owner.post(
            "/me/decisions", headers=headers, json={"title": "Race", "decision_type": "career_path"}
        ).json()["data"]["decision"]["decision_id"]
        for _ in range(2)
    ]
    peer_engine = make_engine(str(engine.url))
    peer_app = create_app(engine=peer_engine, settings=app.state.settings)
    barrier = threading.Barrier(2)
    arrivals = []

    def at_transaction(conn, cursor, statement, parameters, context, executemany):
        if statement == "BEGIN IMMEDIATE":
            arrivals.append(statement)
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", at_transaction)
    event.listen(peer_engine, "before_cursor_execute", at_transaction)

    def deliver(aggregate):
        target = peer_app if aggregate else app
        with TestClient(target, base_url=ORIGIN, cookies=owner.cookies) as c:
            item = {
                "title": "Racer",
                **({"action_type": "research"} if resource == "actions" else {}),
            }
            path = (
                (f"/me/decisions/{ids[1]}/plan" if resource == "actions" else "/me/decisions")
                if aggregate
                else f"/me/decisions/{ids[0]}/{resource}"
            )
            payload = (
                (
                    {"actions": [item]}
                    if resource == "actions"
                    else {
                        "title": "Embedded racer",
                        "decision_type": "career_path",
                        "options": [item],
                    }
                )
                if aggregate
                else item
            )
            return c.post(path, headers=headers, json=payload)

    try:
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(deliver, [False, True]))
    finally:
        event.remove(engine, "before_cursor_execute", at_transaction)
        event.remove(peer_engine, "before_cursor_execute", at_transaction)
        peer_engine.dispose()
    assert len(arrivals) == 2
    assert sorted(r.status_code for r in responses) == [201, 429]
    with make_session_factory(engine)() as session:
        model = DecisionOption if resource == "options" else CareerAction
        assert session.scalar(select(func.count()).select_from(model)) == 1


def test_comparison_option_batch_rejection_rolls_back_implicit_snapshot(tmp_path):
    app, engine = _file_app(
        tmp_path, "comparison-options.db", seed_portfolio=True, guest_max_decision_options=1
    )
    client = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(client))
    identity = client.post(
        "/me/explore/compare",
        headers=headers,
        json={
            "market_refs": ["boston", "new-york"],
            "session_overrides": {},
        },
    ).json()["data"]["comparison_identity"]
    before = _business_digest(engine)
    response = client.post(
        "/me/explore/prioritize",
        headers=headers,
        json={
            "market_refs": ["boston", "new-york"],
            "session_overrides": {},
            "selected_market_ref": "boston",
            "comparison_identity": identity,
        },
    )
    assert response.status_code == 429
    assert _business_digest(engine) == before


def test_non_guest_nested_resources_are_not_subject_to_guest_caps(tmp_path):
    import json

    from backend.career_decisions.models import CareerAction, DecisionOption

    url = "sqlite:///" + str(tmp_path / "non-guest.db")
    engine = make_engine(url)
    create_all(engine)
    settings = Settings(
        app_env="test",
        database_url=url,
        guest_max_decision_options=1,
        guest_max_actions=1,
        guest_max_career_identity_facts=1,
        guest_max_applications=1,
        guest_max_recommendation_snapshots=1,
        _env_file=None,
    )
    client = TestClient(create_app(engine=engine, settings=settings))
    headers = {
        "X-Verified-OIDC-Claims": json.dumps(
            {
                "iss": "https://jmi.us.auth0.com/",
                "sub": "auth0|quota-nonguest",
                "email": "quota@example.invalid",
                "email_verified": True,
            }
        )
    }
    for _ in range(2):
        response = client.post(
            "/me/decisions",
            headers=headers,
            json={
                "decision_type": "career_path",
                "title": "Independent non-guest",
                "options": [{"title": "Option"}],
            },
        )
        assert response.status_code == 201
        did = response.json()["data"]["decision"]["decision_id"]
        assert (
            client.post(
                f"/me/decisions/{did}/plan",
                headers=headers,
                json={
                    "actions": [{"title": "Research", "action_type": "research"}],
                },
            ).status_code
            == 201
        )
        assert client.post('/me/applications', headers=headers, json={
            'decision_id':did, 'role_title':'Non guest', 'status':'preparing'}).status_code == 201
        assert client.post('/me/career-identity/facts', headers=headers, json={
            'fact_type':'skill','state':'explicit','payload':{'name':did}}).status_code == 201
        assert client.post('/me/recommendation-snapshots', headers=headers, json={
            'personalized_output':{},'recommendation_version':'r6','source_version_bundle':{},
            'recommendation_inputs_hash':did,
            'generated_at':'2026-11-04T00:00:00Z'}).status_code == 201
    with make_session_factory(engine)() as session:
        for model in (DecisionOption, CareerAction):
            assert session.scalar(select(func.count()).select_from(model)) == 2


@pytest.mark.parametrize("resource", ["options", "actions"])
def test_resource_batch_exact_limit_and_rejection(tmp_path, resource):
    limit = {"guest_max_decision_options" if resource == "options" else "guest_max_actions": 2}
    app, engine = _file_app(tmp_path, "exact-batch.db", **limit)
    client = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(client))
    body = {"title": "Batch boundary", "decision_type": "career_path"}
    if resource == "options":
        path = "/me/decisions"
        body["options"] = [{"title": "One"}, {"title": "Two"}]
    else:
        did = client.post("/me/decisions", headers=headers, json=body).json()["data"]["decision"][
            "decision_id"
        ]
        path = f"/me/decisions/{did}/plan"
        body = {
            "actions": [{"title": title, "action_type": "research"} for title in ("One", "Two")]
        }
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 201
    did = (
        response.json()["data"]["decision"]["decision_id"]
        if resource == "options"
        else response.json()["data"]["action_plan"]["decision_id"]
    )
    before = _business_digest(engine)
    response = client.post(
        f"/me/decisions/{did}/{resource}",
        headers=headers,
        json={"title": "Over", **({"action_type": "research"} if resource == "actions" else {})},
    )
    assert response.status_code == 429
    assert _business_digest(engine) == before


def test_existing_comparison_options_reused_at_capacity(tmp_path):
    app, engine = _file_app(
        tmp_path, "reuse-options.db", seed_portfolio=True, guest_max_decision_options=2
    )
    client = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(client))
    base = {"market_refs": ["boston", "new-york"], "session_overrides": {}}
    compared = client.post("/me/explore/compare", headers=headers, json=base).json()["data"]
    saved = client.post(
        "/me/explore/comparisons",
        headers=headers,
        json={**base, "comparison_identity": compared["comparison_identity"]},
    )
    payload = {
        "comparison_id": saved.json()["data"]["comparison"]["comparison_id"],
        "selected_market_ref": "boston",
    }
    first = client.post("/me/explore/prioritize", headers=headers, json=payload)
    assert first.status_code == 200
    before = _business_digest(engine)
    second = client.post("/me/explore/prioritize", headers=headers, json=payload)
    assert second.status_code == 200
    assert second.json()["data"]["prioritization"]["created"] is False
    assert (
        second.json()["data"]["prioritization"]["decision_id"]
        == first.json()["data"]["prioritization"]["decision_id"]
    )
    assert _business_digest(engine) == before
@pytest.mark.parametrize("ingest_first", [False, True])
def test_fact_quota_ingestion_cross_paths_reuse_and_rollback(tmp_path, ingest_first):
    app, engine = _file_app(tmp_path, "facts.db", guest_max_career_identity_facts=1)
    owner = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(owner))
    identity = owner.get("/me/career-identity").json()["data"]
    assert (
        owner.put(
            "/me/career-identity/privacy",
            headers=headers,
            json={
                "ingestion_consent_granted": True,
                "expected_version": identity["current_version"],
            },
        ).status_code
        == 200
    )

    def ingest(name):
        return owner.post(
            "/me/career-identity/ingest",
            headers=headers,
            json={
                "source_type": "structured_profile",
                "consent_granted": True,
                "structured_profile": {"skills": [{"name": name}]},
            },
        )

    def direct(name):
        return owner.post(
            "/me/career-identity/facts",
            headers=headers,
            json={"fact_type": "skill", "state": "explicit", "payload": {"name": name}},
        )

    assert (ingest("First") if ingest_first else direct("First")).status_code in (200, 201)
    # An identical normalized fact is an update/reuse, not another slot.
    assert direct("First").status_code == 201
    before = _business_state(engine)
    assert (direct("Excess") if ingest_first else ingest("Excess")).status_code == 429
    assert _business_state(engine) == before
    other = TestClient(app, base_url=ORIGIN)
    assert (
        other.post(
            "/me/career-identity/facts",
            headers=_unsafe_headers(_bootstrap(other)),
            json={"fact_type": "skill", "state": "explicit", "payload": {"name": "Independent"}},
        ).status_code
        == 201
    )


def test_ingestion_batch_failure_is_atomic(tmp_path):
    app, engine = _file_app(tmp_path, "batch-facts.db", guest_max_career_identity_facts=1)
    c = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(c))
    identity = c.get("/me/career-identity").json()["data"]
    assert (
        c.put(
            "/me/career-identity/privacy",
            headers=headers,
            json={
                "ingestion_consent_granted": True,
                "expected_version": identity["current_version"],
            },
        ).status_code
        == 200
    )
    before = _business_state(engine)
    r = c.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "structured_profile",
            "consent_granted": True,
            "structured_profile": {"skills": [{"name": "One"}, {"name": "Two"}]},
        },
    )
    assert r.status_code == 429
    assert _business_state(engine) == before


@pytest.mark.parametrize(
    "resource", ["applications", "recommendation_snapshots", "career_identity_facts"]
)
def test_remaining_resource_quota_across_independent_apps(tmp_path, resource):
    app, engine = _file_app(tmp_path, "race-extra.db", **{"guest_max_" + resource: 1})
    owner = TestClient(app, base_url=ORIGIN)
    headers = _unsafe_headers(_bootstrap(owner))
    did = owner.post(
        "/me/decisions",
        headers=headers,
        json={"title": "Race owner", "decision_type": "career_path"},
    ).json()["data"]["decision"]["decision_id"]
    peer_engine = make_engine(str(engine.url))
    peer = create_app(engine=peer_engine, settings=app.state.settings)
    barrier = threading.Barrier(2)
    arrivals = []

    def at_transaction(conn, cursor, statement, parameters, context, executemany):
        if statement == "BEGIN IMMEDIATE":
            arrivals.append(True)
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", at_transaction)
    event.listen(peer_engine, "before_cursor_execute", at_transaction)
    path = {
        "applications": "/me/applications",
        "recommendation_snapshots": "/me/recommendation-snapshots",
        "career_identity_facts": "/me/career-identity/facts",
    }[resource]

    def deliver(index):
        payload = {
            "applications": {
                "decision_id": did,
                "role_title": f"Role {index}",
                "status": "preparing",
            },
            "recommendation_snapshots": {
                "personalized_output": {},
                "recommendation_version": "r6",
                "source_version_bundle": {},
                "recommendation_inputs_hash": f"r6-{index}",
                "generated_at": "2026-11-04T00:00:00Z",
            },
            "career_identity_facts": {
                "fact_type": "skill",
                "state": "explicit",
                "payload": {"name": f"Skill {index}"},
            },
        }[resource]
        with TestClient(peer if index else app, base_url=ORIGIN, cookies=owner.cookies) as c:
            return c.post(path, headers=headers, json=payload)

    try:
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(deliver, [0, 1]))
    finally:
        event.remove(engine, "before_cursor_execute", at_transaction)
        event.remove(peer_engine, "before_cursor_execute", at_transaction)
        peer_engine.dispose()
    assert len(arrivals) == 2
    assert sorted(r.status_code for r in responses) == [201, 429]
    table = {
        "applications": "career_applications",
        "recommendation_snapshots": "personalized_recommendation_snapshots",
        "career_identity_facts": "career_identity_facts",
    }[resource]
    with engine.connect() as c:
        assert c.exec_driver_sql("select count(*) from " + table).scalar_one() == 1


def _business_state(engine):
    from sqlalchemy import inspect

    with engine.connect() as connection:
        return {
            table: connection.exec_driver_sql(f'SELECT * FROM "{table}"').fetchall()
            for table in inspect(engine).get_table_names()
            if table != "public_guest_sessions"
        }


@pytest.mark.parametrize("resource", ["applications", "recommendation_snapshots"])
def test_other_resource_limits_rollback_and_independent_owners(tmp_path, resource):
    app, engine = _file_app(tmp_path, "other-limits.db", **{"guest_max_" + resource: 1})
    for _index in range(2):
        c = TestClient(app, base_url=ORIGIN)
        headers = _unsafe_headers(_bootstrap(c))
        did = c.post(
            "/me/decisions",
            headers=headers,
            json={"title": "Owner", "decision_type": "career_path"},
        ).json()["data"]["decision"]["decision_id"]
        path = "/me/applications" if resource == "applications" else "/me/recommendation-snapshots"
        payload = (
            {"decision_id": did, "role_title": "Independent", "status": "preparing"}
            if resource == "applications"
            else {
                "personalized_output": {},
                "recommendation_version": "r6",
                "source_version_bundle": {},
                "recommendation_inputs_hash": "r6",
                "generated_at": "2026-11-04T00:00:00Z",
            }
        )
        assert c.post(path, headers=headers, json=payload).status_code == 201
        before = _business_state(engine)
        r = c.post(path, headers=headers, json=payload)
        assert r.status_code == 429
        assert r.json()["error"]["type"] == "guest_quota_exceeded"
        assert _business_state(engine) == before


def _comparison_payload(client, headers, markets):
    # Decision creation initializes Identity; keep preview context stable.
    assert client.get("/me/career-identity").status_code == 200
    base = {"market_refs": markets, "session_overrides": {}}
    r = client.post("/me/explore/compare", headers=headers, json=base)
    assert r.status_code == 200
    return {**base, "comparison_identity": r.json()["data"]["comparison_identity"]}


@pytest.mark.parametrize("internal_first", [False, True])
def test_saved_comparison_mixed_creation_promotion_and_reuse(tmp_path, internal_first):
    app, engine = _file_app(
        tmp_path, "mixed.db", seed_portfolio=True, guest_max_saved_comparisons=1
    )
    c = TestClient(app, base_url=ORIGIN)
    h = _unsafe_headers(_bootstrap(c))
    first = _comparison_payload(c, h, ["boston", "new-york"])
    second = _comparison_payload(c, h, ["atlanta", "austin"])
    priority = {**second, "selected_market_ref": "atlanta"}
    if internal_first:
        assert c.post("/me/explore/prioritize", headers=h, json=priority).status_code == 200
    assert c.post("/me/explore/comparisons", headers=h, json=first).status_code == 201
    assert c.post("/me/explore/prioritize", headers=h, json=priority).status_code == 200
    assert c.post("/me/explore/comparisons", headers=h, json=first).status_code == 201
    assert (
        c.post(
            "/me/explore/compare",
            headers=h,
            json={k: v for k, v in first.items() if k != "comparison_identity"},
        ).status_code
        == 200
    )
    before = _business_state(engine)
    assert c.post("/me/explore/comparisons", headers=h, json=second).status_code == 429
    assert _business_state(engine) == before
    with engine.connect() as db:
        assert (
            db.exec_driver_sql("select count(*) from explore_comparison_snapshots").scalar_one()
            == 2
        )
        assert (
            db.exec_driver_sql(
                "select count(*) from explore_comparison_snapshots where saved_at is not null"
            ).scalar_one()
            == 1
        )
    peer = TestClient(app, base_url=ORIGIN)
    peer_headers = _unsafe_headers(_bootstrap(peer))
    assert peer.get("/me/career-identity").status_code == 200
    assert peer.post("/me/explore/comparisons", headers=peer_headers, json=first).status_code == 201


def test_internal_promotion_and_decision_quota_rollback(tmp_path):
    app, engine = _file_app(
        tmp_path,
        "promote.db",
        seed_portfolio=True,
        guest_max_saved_comparisons=1,
        guest_max_decisions=1,
    )
    c = TestClient(app, base_url=ORIGIN)
    h = _unsafe_headers(_bootstrap(c))
    first = _comparison_payload(c, h, ["boston", "new-york"])
    assert (
        c.post(
            "/me/explore/prioritize", headers=h, json={**first, "selected_market_ref": "boston"}
        ).status_code
        == 200
    )
    assert c.post("/me/explore/comparisons", headers=h, json=first).status_code == 201
    assert c.post("/me/explore/comparisons", headers=h, json=first).status_code == 201
    second = _comparison_payload(c, h, ["atlanta", "austin"])
    before = _business_state(engine)
    assert (
        c.post(
            "/me/explore/prioritize", headers=h, json={**second, "selected_market_ref": "atlanta"}
        ).status_code
        == 429
    )
    assert _business_state(engine) == before
    with engine.connect() as db:
        assert (
            db.exec_driver_sql("select count(*) from explore_comparison_snapshots").scalar_one()
            == 1
        )
        assert (
            db.exec_driver_sql(
                "select count(*) from explore_comparison_snapshots where saved_at is not null"
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("promote", [False, True])
def test_saved_comparison_concurrent_independent_apps(tmp_path, promote):
    app, engine = _file_app(
        tmp_path, "saved-race.db", seed_portfolio=True, guest_max_saved_comparisons=1
    )
    c = TestClient(app, base_url=ORIGIN)
    h = _unsafe_headers(_bootstrap(c))
    payloads = []
    for markets in [["boston", "new-york"], ["atlanta", "austin"]]:
        payload = _comparison_payload(c, h, markets)
        payloads.append(payload)
        if promote:
            assert (
                c.post(
                    "/me/explore/prioritize",
                    headers=h,
                    json={**payload, "selected_market_ref": markets[0]},
                ).status_code
                == 200
            )
    peer_engine = make_engine(str(engine.url))
    peer = create_app(engine=peer_engine, settings=app.state.settings)
    barrier = threading.Barrier(2)
    arrivals = []

    def sync(conn, cursor, statement, parameters, context, executemany):
        if statement == "BEGIN IMMEDIATE":
            arrivals.append(True)
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", sync)
    event.listen(peer_engine, "before_cursor_execute", sync)

    def deliver(i):
        with TestClient(peer if i else app, base_url=ORIGIN, cookies=c.cookies) as client:
            return client.post("/me/explore/comparisons", headers=h, json=payloads[i])

    try:
        with ThreadPoolExecutor(2) as pool:
            rs = list(pool.map(deliver, [0, 1]))
    finally:
        event.remove(engine, "before_cursor_execute", sync)
        event.remove(peer_engine, "before_cursor_execute", sync)
        peer_engine.dispose()
    assert len(arrivals) == 2
    assert sorted(r.status_code for r in rs) == [201, 429]
    with engine.connect() as db:
        assert (
            db.exec_driver_sql(
                "select count(*) from explore_comparison_snapshots where saved_at is not null"
            ).scalar_one()
            == 1
        )
        assert db.exec_driver_sql(
            "select count(*) from explore_comparison_snapshots"
        ).scalar_one() == (2 if promote else 1)
