from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.api.app import create_app  # noqa: E402
from backend.config.settings import Settings  # noqa: E402
from backend.imports.bulk import (  # noqa: E402
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.shared.db import create_all, make_engine, make_session_factory  # noqa: E402
from seeds import mvp_seed  # noqa: E402

AS_OF = date(2026, 7, 9)


def main() -> int:
    paths = json.loads(os.environ.get("PUBLIC_DEMO_SMOKE_API_PATHS", "[]"))
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError("PUBLIC_DEMO_SMOKE_API_PATHS must be a JSON string list")

    db_path = Path(tempfile.gettempdir()) / f"jmi_public_demo_smoke_{os.getpid()}.db"
    db_path.unlink(missing_ok=True)
    database_url = f"sqlite:///{db_path}"
    engine = make_engine(database_url)

    try:
        create_all(engine)
        session_factory = make_session_factory(engine)
        session = session_factory()
        try:
            mvp_seed.run_seed(session)
            import_result = import_all_curated_market_datasets(session, as_of=AS_OF)
            if not import_result.ok:
                raise RuntimeError(f"curated market import failed: {import_result}")
            post_import_result = run_all_curated_market_post_imports(
                session,
                as_of=AS_OF,
            )
            if not post_import_result.ok:
                raise RuntimeError(
                    f"curated market post-import failed: {post_import_result}"
                )
            session.commit()
        finally:
            session.close()

        app = create_app(
            engine=engine,
            settings=Settings(
                app_env="public_demo",
                database_url=database_url,
                cors_allowed_origins="http://127.0.0.1:5173",
            ),
        )
        with TestClient(app) as client:
            results = [
                {"path": path, "status": client.get(path).status_code}
                for path in paths
            ]
        print(json.dumps(results, sort_keys=True))
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)

    return 0 if all(200 <= item["status"] < 300 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
