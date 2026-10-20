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
from sqlalchemy import event, select, text

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
