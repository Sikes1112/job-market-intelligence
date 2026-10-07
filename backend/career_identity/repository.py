from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_identity.models import (
    CareerIdentity,
    CareerIdentityFact,
    CareerIdentityImport,
)


class CareerIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_identity_for_user(self, user_id: str) -> CareerIdentity | None:
        return self._session.execute(
            select(CareerIdentity).where(CareerIdentity.user_id == user_id)
        ).scalar_one_or_none()

    def add_identity(self, identity: CareerIdentity) -> None:
        self._session.add(identity)

    def get_fact(self, fact_id: str) -> CareerIdentityFact | None:
        return self._session.get(CareerIdentityFact, fact_id)

    def get_fact_by_key(
        self,
        *,
        career_identity_id: str,
        fact_type: str,
        normalized_key: str,
    ) -> CareerIdentityFact | None:
        return self._session.execute(
            select(CareerIdentityFact).where(
                CareerIdentityFact.career_identity_id == career_identity_id,
                CareerIdentityFact.fact_type == fact_type,
                CareerIdentityFact.normalized_key == normalized_key,
            )
        ).scalar_one_or_none()

    def list_facts(self, career_identity_id: str) -> list[CareerIdentityFact]:
        return list(
            self._session.execute(
                select(CareerIdentityFact)
                .where(CareerIdentityFact.career_identity_id == career_identity_id)
                .order_by(
                    CareerIdentityFact.fact_type,
                    CareerIdentityFact.created_at,
                    CareerIdentityFact.career_identity_fact_id,
                )
            ).scalars()
        )

    def add_fact(self, fact: CareerIdentityFact) -> None:
        self._session.add(fact)

    def delete_fact(self, fact: CareerIdentityFact) -> None:
        self._session.delete(fact)

    def get_import_by_hash(
        self,
        *,
        career_identity_id: str,
        content_hash: str,
    ) -> CareerIdentityImport | None:
        return self._session.execute(
            select(CareerIdentityImport).where(
                CareerIdentityImport.career_identity_id == career_identity_id,
                CareerIdentityImport.content_hash == content_hash,
            )
        ).scalar_one_or_none()

    def add_import(self, row: CareerIdentityImport) -> None:
        self._session.add(row)

    def list_imports(self, career_identity_id: str) -> list[CareerIdentityImport]:
        return list(
            self._session.execute(
                select(CareerIdentityImport)
                .where(CareerIdentityImport.career_identity_id == career_identity_id)
                .order_by(
                    CareerIdentityImport.created_at.desc(),
                    CareerIdentityImport.career_identity_import_id,
                )
            ).scalars()
        )

    def delete_identity_for_user(self, user_id: str) -> tuple[int, int, int]:
        identity = self.get_identity_for_user(user_id)
        if identity is None:
            return (0, 0, 0)
        facts = self.list_facts(identity.career_identity_id)
        imports = self.list_imports(identity.career_identity_id)
        for fact in facts:
            self._session.delete(fact)
        self._session.flush()
        for row in imports:
            self._session.delete(row)
        self._session.flush()
        self._session.delete(identity)
        return (1, len(facts), len(imports))

    def flush(self) -> None:
        self._session.flush()
