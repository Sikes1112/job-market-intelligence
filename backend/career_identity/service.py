from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.career_identity.completeness import evaluate_career_identity
from backend.career_identity.exceptions import (
    CareerIdentityFactNotFound,
    CareerIdentityNotFound,
    CareerIdentityStateTransitionError,
    CareerIdentityValidationError,
    CareerIdentityVersionConflict,
)
from backend.career_identity.ingestion import (
    content_hash_for_ingestion,
    fact_inputs_from_ingestion,
)
from backend.career_identity.models import (
    CareerIdentity,
    CareerIdentityFact,
    CareerIdentityImport,
)
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityFactUpdateInput,
    CareerIdentityFactView,
    CareerIdentityIngestionRequest,
    CareerIdentityIngestionResult,
    CareerIdentityPrivacyInput,
    CareerIdentityView,
    canonical_payload,
    normalized_key_for_payload,
    provenance_payload,
)
from backend.shared.versioning import next_version
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.repository import UserRepository

STATE_PRECEDENCE: dict[str, int] = {
    CareerFactState.INFERRED.value: 1,
    CareerFactState.IMPORTED.value: 2,
    CareerFactState.EXPLICIT.value: 3,
    CareerFactState.CONFIRMED.value: 4,
}

LEGAL_STATE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("inferred", "imported"),
        ("inferred", "explicit"),
        ("inferred", "confirmed"),
        ("imported", "explicit"),
        ("imported", "confirmed"),
        ("explicit", "confirmed"),
    }
)


@dataclass(frozen=True, slots=True)
class FactUpsertResult:
    fact: CareerIdentityFact
    outcome: str
    version_changed: bool


@dataclass(frozen=True, slots=True)
class PreparedFactInput:
    request: CareerIdentityFactInput
    payload: dict[str, Any]
    normalized_key: str
    source_label: str | None
    provenance: dict[str, Any]


class CareerIdentityService:
    def __init__(
        self,
        repository: CareerIdentityRepository,
        user_repository: UserRepository,
    ) -> None:
        self._repo = repository
        self._user_repo = user_repository

    def get_or_create_identity(self, current_user_id: str) -> CareerIdentity:
        self._ensure_user(current_user_id)
        identity = self._repo.get_identity_for_user(current_user_id)
        if identity is not None:
            return identity
        identity = CareerIdentity(
            career_identity_id=_new_identity_id(),
            user_id=current_user_id,
            current_version=1,
            completeness_state="empty",
            sufficiency_state="insufficient",
            privacy_visibility="private",
        )
        self._repo.add_identity(identity)
        self._repo.flush()
        self._refresh_evaluation(identity, advance_version=False)
        return identity

    def get_identity(self, current_user_id: str) -> CareerIdentity:
        self._ensure_user(current_user_id)
        identity = self._repo.get_identity_for_user(current_user_id)
        if identity is None:
            raise CareerIdentityNotFound(current_user_id)
        return identity

    def view_identity(self, current_user_id: str) -> CareerIdentityView:
        identity = self.get_or_create_identity(current_user_id)
        self._refresh_evaluation(identity, advance_version=False)
        return self._identity_view(identity)

    def update_privacy(
        self,
        current_user_id: str,
        request: CareerIdentityPrivacyInput,
    ) -> CareerIdentityView:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, request.expected_version)
        before = _privacy_payload(identity)
        for field in (
            "ingestion_consent_granted",
            "inference_consent_granted",
            "downstream_personalization_consent_granted",
            "retain_import_metadata",
        ):
            value = getattr(request, field)
            if value is not None:
                setattr(identity, field, value)
        after = _privacy_payload(identity)
        if after != before:
            self._advance_version(identity)
            self._refresh_evaluation(identity, advance_version=False)
            self._repo.flush()
        return self._identity_view(identity)

    def upsert_fact(
        self,
        current_user_id: str,
        request: CareerIdentityFactInput,
        *,
        source_import_id: str | None = None,
    ) -> FactUpsertResult:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, request.expected_version)
        self._ensure_state_consent(identity, request.state)
        prepared = self._prepare_fact_input(request, source_import_id=source_import_id)
        return self._upsert_prepared_fact(
            current_user_id,
            identity,
            prepared,
            source_import_id=source_import_id,
        )

    def _upsert_prepared_fact(
        self,
        current_user_id: str,
        identity: CareerIdentity,
        prepared: PreparedFactInput,
        *,
        source_import_id: str | None = None,
    ) -> FactUpsertResult:
        request = prepared.request
        payload = prepared.payload
        normalized_key = prepared.normalized_key
        source_label = prepared.source_label
        provenance = prepared.provenance
        existing = self._repo.get_fact_by_key(
            career_identity_id=identity.career_identity_id,
            fact_type=request.fact_type.value,
            normalized_key=normalized_key,
        )
        if existing is None:
            fact = CareerIdentityFact(
                career_identity_fact_id=_new_fact_id(),
                career_identity_id=identity.career_identity_id,
                user_id=current_user_id,
                fact_type=request.fact_type.value,
                normalized_key=normalized_key,
                state=request.state.value,
                payload=payload,
                provenance=provenance,
                source_import_id=source_import_id,
                source_label=source_label,
                confirmed_at=(
                    datetime.now(UTC)
                    if request.state is CareerFactState.CONFIRMED
                    else None
                ),
            )
            self._repo.add_fact(fact)
            self._advance_and_refresh(identity)
            self._repo.flush()
            return FactUpsertResult(fact=fact, outcome="created", version_changed=True)

        outcome = self._merge_existing_fact(
            existing,
            payload=payload,
            incoming_state=request.state,
            provenance=provenance,
            source_import_id=source_import_id,
            source_label=source_label,
        )
        if outcome in {"updated", "confirmed"}:
            self._advance_and_refresh(identity)
            self._repo.flush()
            return FactUpsertResult(fact=existing, outcome=outcome, version_changed=True)
        self._repo.flush()
        return FactUpsertResult(fact=existing, outcome=outcome, version_changed=False)

    def _prepare_fact_input(
        self,
        request: CareerIdentityFactInput,
        *,
        source_import_id: str | None = None,
    ) -> PreparedFactInput:
        try:
            payload = canonical_payload(request.fact_type, request.payload)
            normalized_key = normalized_key_for_payload(
                request.fact_type,
                payload,
                request.normalized_key,
            )
        except ValidationError as exc:
            raise _career_validation_error(exc, request.fact_type) from exc
        source_label = (
            request.provenance.source_label
            if request.provenance is not None
            else None
        )
        provenance = provenance_payload(
            request.state,
            request.provenance,
            source_import_id=source_import_id,
        )
        return PreparedFactInput(
            request=request,
            payload=payload,
            normalized_key=normalized_key,
            source_label=source_label,
            provenance=provenance,
        )

    def update_fact(
        self,
        current_user_id: str,
        fact_id: str,
        request: CareerIdentityFactUpdateInput,
    ) -> CareerIdentityFact:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, request.expected_version)
        fact = self._get_owned_fact(current_user_id, fact_id)
        incoming_state = request.state or CareerFactState(fact.state)
        self._ensure_state_consent(identity, incoming_state)
        if incoming_state.value != fact.state and not _can_transition(
            fact.state,
            incoming_state.value,
        ):
            raise CareerIdentityStateTransitionError(fact.state, incoming_state.value)
        payload = fact.payload
        if request.payload is not None:
            try:
                payload = canonical_payload(CareerFactType(fact.fact_type), request.payload)
            except ValidationError as exc:
                raise _career_validation_error(
                    exc,
                    CareerFactType(fact.fact_type),
                ) from exc
        normalized_key = (
            normalized_key_for_payload(
                CareerFactType(fact.fact_type),
                payload,
                request.normalized_key,
            )
            if request.payload is not None or request.normalized_key is not None
            else fact.normalized_key
        )
        before = _fact_comparison_tuple(fact)
        fact.payload = payload
        fact.normalized_key = normalized_key
        fact.state = incoming_state.value
        if request.provenance is not None:
            fact.provenance = provenance_payload(incoming_state, request.provenance)
            fact.source_label = request.provenance.source_label
        if incoming_state is CareerFactState.CONFIRMED and fact.confirmed_at is None:
            fact.confirmed_at = datetime.now(UTC)
        if _fact_comparison_tuple(fact) != before:
            self._advance_and_refresh(identity)
            self._repo.flush()
        return fact

    def confirm_fact(
        self,
        current_user_id: str,
        fact_id: str,
        *,
        expected_version: int | None = None,
    ) -> CareerIdentityFact:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, expected_version)
        fact = self._get_owned_fact(current_user_id, fact_id)
        if fact.state == CareerFactState.CONFIRMED.value:
            return fact
        if not _can_transition(fact.state, CareerFactState.CONFIRMED.value):
            raise CareerIdentityStateTransitionError(
                fact.state,
                CareerFactState.CONFIRMED.value,
            )
        history = list(fact.provenance.get("history", []))
        history.append(
            {
                "from_state": fact.state,
                "to_state": CareerFactState.CONFIRMED.value,
                "changed_at": datetime.now(UTC).isoformat(),
                "changed_by": "user",
            }
        )
        fact.state = CareerFactState.CONFIRMED.value
        fact.confirmed_at = datetime.now(UTC)
        fact.provenance = {**fact.provenance, "state": fact.state, "history": history}
        self._advance_and_refresh(identity)
        self._repo.flush()
        return fact

    def delete_fact(
        self,
        current_user_id: str,
        fact_id: str,
        *,
        expected_version: int | None = None,
    ) -> None:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, expected_version)
        fact = self._get_owned_fact(current_user_id, fact_id)
        self._repo.delete_fact(fact)
        self._advance_and_refresh(identity)
        self._repo.flush()

    def evaluate(self, current_user_id: str) -> dict[str, Any]:
        identity = self.get_or_create_identity(current_user_id)
        return self._refresh_evaluation(identity, advance_version=False)

    def ingest_profile(
        self,
        current_user_id: str,
        request: CareerIdentityIngestionRequest,
    ) -> CareerIdentityIngestionResult:
        identity = self.get_or_create_identity(current_user_id)
        self._check_version(identity, request.expected_version)
        if not request.consent_granted or not identity.ingestion_consent_granted:
            raise CareerIdentityValidationError(
                "career identity ingestion requires explicit ingestion consent",
                code="ingestion_consent_required",
            )
        content_hash = content_hash_for_ingestion(request)
        existing_import = self._repo.get_import_by_hash(
            career_identity_id=identity.career_identity_id,
            content_hash=content_hash,
        )
        if existing_import is not None:
            completeness = self._refresh_evaluation(identity, advance_version=False)
            return CareerIdentityIngestionResult(
                career_identity_import_id=existing_import.career_identity_import_id,
                identity_version=identity.current_version,
                status="duplicate",
                imported_fact_count=existing_import.imported_fact_count,
                created_fact_count=0,
                updated_fact_count=0,
                protected_fact_count=0,
                duplicate_fact_count=existing_import.imported_fact_count,
                diagnostics=tuple(existing_import.diagnostics or []),
                completeness=completeness,
            )

        import_id = _new_import_id()
        facts, diagnostics = fact_inputs_from_ingestion(request, source_import_id=import_id)
        if not facts:
            raise CareerIdentityValidationError(
                "submitted profile did not contain supported career identity facts",
                code="no_supported_import_facts",
            )
        prepared_facts = [
            self._prepare_fact_input(fact, source_import_id=import_id)
            for fact in facts
        ]
        row = CareerIdentityImport(
            career_identity_import_id=import_id,
            career_identity_id=identity.career_identity_id,
            user_id=current_user_id,
            source_type=request.source_type,
            source_label=request.source_label,
            content_hash=content_hash,
            artifact_metadata={
                "input_type": request.source_type,
                "text_length": len(request.text or ""),
                "structured_keys": sorted((request.structured_profile or {}).keys()),
                "raw_content_retained": False,
            },
            import_status="completed",
            diagnostics=diagnostics,
            imported_fact_count=0,
        )
        self._repo.add_import(row)
        self._repo.flush()

        created = updated = protected = duplicate = 0
        for prepared in prepared_facts:
            result = self._upsert_prepared_fact(
                current_user_id,
                identity,
                prepared,
                source_import_id=import_id,
            )
            if result.outcome == "created":
                created += 1
            elif result.outcome in {"updated", "confirmed"}:
                updated += 1
            elif result.outcome == "protected":
                protected += 1
            else:
                duplicate += 1
        row.imported_fact_count = len(facts)
        row.diagnostics = [
            *diagnostics,
            {
                "code": "ingestion_result",
                "created": created,
                "updated": updated,
                "protected": protected,
                "duplicate": duplicate,
            },
        ]
        completeness = self._refresh_evaluation(identity, advance_version=False)
        self._repo.flush()
        return CareerIdentityIngestionResult(
            career_identity_import_id=import_id,
            identity_version=identity.current_version,
            status="completed",
            imported_fact_count=len(facts),
            created_fact_count=created,
            updated_fact_count=updated,
            protected_fact_count=protected,
            duplicate_fact_count=duplicate,
            diagnostics=tuple(row.diagnostics),
            completeness=completeness,
        )

    def export_user_data(self, current_user_id: str) -> dict[str, Any] | None:
        identity = self._repo.get_identity_for_user(current_user_id)
        if identity is None:
            return None
        facts = [
            self._fact_view(fact).model_dump(mode="json")
            for fact in self._repo.list_facts(identity.career_identity_id)
        ]
        imports = [
            {
                "career_identity_import_id": row.career_identity_import_id,
                "source_type": row.source_type,
                "source_label": row.source_label,
                "content_hash": row.content_hash,
                "artifact_metadata": deepcopy(row.artifact_metadata),
                "import_status": row.import_status,
                "diagnostics": deepcopy(row.diagnostics),
                "imported_fact_count": row.imported_fact_count,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in self._repo.list_imports(identity.career_identity_id)
        ]
        return {
            "career_identity_id": identity.career_identity_id,
            "user_id": identity.user_id,
            "current_version": identity.current_version,
            "completeness_state": identity.completeness_state,
            "sufficiency_state": identity.sufficiency_state,
            "privacy": _privacy_payload(identity),
            "completeness": deepcopy(identity.completeness_snapshot),
            "facts": facts,
            "imports": imports,
            "raw_import_content_retained": False,
            "created_at": identity.created_at.isoformat(),
            "updated_at": identity.updated_at.isoformat(),
        }

    def delete_user_data(self, current_user_id: str) -> tuple[int, int, int]:
        deleted = self._repo.delete_identity_for_user(current_user_id)
        self._repo.flush()
        return deleted

    def _merge_existing_fact(
        self,
        existing: CareerIdentityFact,
        *,
        payload: dict[str, Any],
        incoming_state: CareerFactState,
        provenance: dict[str, Any],
        source_import_id: str | None,
        source_label: str | None,
    ) -> str:
        current_rank = STATE_PRECEDENCE[existing.state]
        incoming_rank = STATE_PRECEDENCE[incoming_state.value]
        if current_rank > incoming_rank:
            existing.provenance = _append_history(
                existing.provenance,
                {
                    "outcome": "protected",
                    "incoming_state": incoming_state.value,
                    "source_import_id": source_import_id,
                    "observed_at": datetime.now(UTC).isoformat(),
                },
            )
            return "protected"
        before = _fact_comparison_tuple(existing)
        if current_rank == incoming_rank and _semantically_same_payload(existing, payload):
            existing.provenance = _append_history(
                existing.provenance,
                {
                    "outcome": "duplicate",
                    "incoming_state": incoming_state.value,
                    "source_import_id": source_import_id,
                    "observed_at": datetime.now(UTC).isoformat(),
                },
            )
            return "duplicate"
        if current_rank < incoming_rank and not _can_transition(
            existing.state,
            incoming_state.value,
        ):
            raise CareerIdentityStateTransitionError(existing.state, incoming_state.value)
        history = list(existing.provenance.get("history", []))
        history.append(
            {
                "outcome": "merged",
                "from_state": existing.state,
                "to_state": incoming_state.value,
                "source_import_id": source_import_id,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        existing.payload = payload
        existing.state = incoming_state.value
        existing.provenance = {**provenance, "history": history}
        existing.source_import_id = source_import_id or existing.source_import_id
        existing.source_label = source_label or existing.source_label
        if incoming_state is CareerFactState.CONFIRMED and existing.confirmed_at is None:
            existing.confirmed_at = datetime.now(UTC)
        return "updated" if _fact_comparison_tuple(existing) != before else "duplicate"

    def _get_owned_fact(self, current_user_id: str, fact_id: str) -> CareerIdentityFact:
        fact = self._repo.get_fact(fact_id)
        if fact is None:
            raise CareerIdentityFactNotFound(fact_id)
        if fact.user_id != current_user_id:
            raise CrossUserAccessBlocked(current_user_id, fact.user_id)
        return fact

    def _identity_view(self, identity: CareerIdentity) -> CareerIdentityView:
        facts = self._repo.list_facts(identity.career_identity_id)
        grouped: dict[str, list[dict[str, Any]]] = {
            fact_type.value: [] for fact_type in CareerFactType
        }
        for fact in facts:
            grouped[fact.fact_type].append(
                self._fact_view(fact).model_dump(mode="json")
            )
        return CareerIdentityView(
            career_identity_id=identity.career_identity_id,
            user_id=identity.user_id,
            current_version=identity.current_version,
            completeness_state=identity.completeness_state,
            sufficiency_state=identity.sufficiency_state,
            privacy=_privacy_payload(identity),
            completeness=deepcopy(identity.completeness_snapshot),
            facts=grouped,
            created_at=identity.created_at,
            updated_at=identity.updated_at,
        )

    def _fact_view(self, fact: CareerIdentityFact) -> CareerIdentityFactView:
        return CareerIdentityFactView(
            career_identity_fact_id=fact.career_identity_fact_id,
            fact_type=CareerFactType(fact.fact_type),
            normalized_key=fact.normalized_key,
            state=CareerFactState(fact.state),
            payload=deepcopy(fact.payload),
            provenance=deepcopy(fact.provenance),
            source_import_id=fact.source_import_id,
            source_label=fact.source_label,
            confirmed_at=fact.confirmed_at,
            created_at=fact.created_at,
            updated_at=fact.updated_at,
        )

    def _refresh_evaluation(
        self,
        identity: CareerIdentity,
        *,
        advance_version: bool,
    ) -> dict[str, Any]:
        snapshot = evaluate_career_identity(
            identity,
            self._repo.list_facts(identity.career_identity_id),
        )
        before = (
            identity.completeness_state,
            identity.sufficiency_state,
            identity.completeness_snapshot,
        )
        identity.completeness_state = snapshot["completeness_state"]
        identity.sufficiency_state = snapshot["sufficiency_state"]
        identity.completeness_snapshot = snapshot
        if advance_version and before != (
            identity.completeness_state,
            identity.sufficiency_state,
            identity.completeness_snapshot,
        ):
            self._advance_version(identity)
        self._repo.flush()
        return snapshot

    def _advance_and_refresh(self, identity: CareerIdentity) -> None:
        self._advance_version(identity)
        self._refresh_evaluation(identity, advance_version=False)

    def _advance_version(self, identity: CareerIdentity) -> None:
        identity.current_version = next_version(identity.current_version)

    def _check_version(
        self,
        identity: CareerIdentity,
        expected_version: int | None,
    ) -> None:
        if expected_version is not None and expected_version != identity.current_version:
            raise CareerIdentityVersionConflict(expected_version, identity.current_version)

    def _ensure_state_consent(
        self,
        identity: CareerIdentity,
        state: CareerFactState,
    ) -> None:
        if state is CareerFactState.IMPORTED and not identity.ingestion_consent_granted:
            raise CareerIdentityValidationError(
                "imported career facts require ingestion consent",
                code="ingestion_consent_required",
            )
        if state is CareerFactState.INFERRED and not identity.inference_consent_granted:
            raise CareerIdentityValidationError(
                "inferred career facts require inference consent",
                code="inference_consent_required",
            )

    def _ensure_user(self, user_id: str) -> None:
        if self._user_repo.get_user(user_id) is None:
            raise UserNotFound(user_id)


def _privacy_payload(identity: CareerIdentity) -> dict[str, Any]:
    return {
        "privacy_visibility": identity.privacy_visibility,
        "ingestion_consent_granted": identity.ingestion_consent_granted,
        "inference_consent_granted": identity.inference_consent_granted,
        "downstream_personalization_consent_granted": (
            identity.downstream_personalization_consent_granted
        ),
        "retain_import_metadata": identity.retain_import_metadata,
        "raw_import_content_exposed": False,
    }


def _career_validation_error(
    exc: ValidationError,
    fact_type: CareerFactType,
) -> CareerIdentityValidationError:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "__root__")
    msg = _safe_validation_message(first)
    target = f"{fact_type.value} payload"
    if loc:
        target = f"{target} at {loc}"
    return CareerIdentityValidationError(
        f"Invalid {target}: {msg}",
        code="invalid_fact_payload",
    )


def _safe_validation_message(error: dict[str, Any]) -> str:
    msg = str(error.get("msg") or "invalid value")
    msg = msg.split("\n", 1)[0]
    return msg or "invalid value"


def _fact_comparison_tuple(fact: CareerIdentityFact) -> tuple[Any, ...]:
    return (
        fact.fact_type,
        fact.normalized_key,
        fact.state,
        fact.payload,
        fact.provenance,
        fact.source_import_id,
        fact.source_label,
        fact.confirmed_at,
    )


def _semantically_same_payload(
    existing: CareerIdentityFact,
    incoming_payload: dict[str, Any],
) -> bool:
    if existing.payload == incoming_payload:
        return True
    if existing.fact_type == CareerFactType.SKILL.value:
        existing_name = (
            existing.payload.get("normalized_name") or existing.payload.get("name") or ""
        )
        incoming_name = (
            incoming_payload.get("normalized_name") or incoming_payload.get("name") or ""
        )
        return str(existing_name).casefold() == str(incoming_name).casefold()
    return False


def _can_transition(current_state: str, target_state: str) -> bool:
    if current_state == target_state:
        return True
    return (current_state, target_state) in LEGAL_STATE_TRANSITIONS


def _append_history(provenance: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(provenance)
    history = list(updated.get("history", []))
    history.append(event)
    updated["history"] = history
    return updated


def _new_identity_id() -> str:
    return f"career_identity_{uuid4().hex[:48]}"


def _new_fact_id() -> str:
    return f"career_fact_{uuid4().hex[:52]}"


def _new_import_id() -> str:
    return f"career_import_{uuid4().hex[:50]}"
