class UserIdentityError(RuntimeError):
    """Base error for internal user identity mapping failures."""


class ExternalIdentityNotFound(UserIdentityError):
    """Raised when a read-only identity lookup has no existing mapping."""

    def __init__(self, provider: str, issuer: str, subject: str) -> None:
        super().__init__(
            "external auth identity not found for "
            f"provider={provider!r}, issuer={issuer!r}, subject={subject!r}"
        )
        self.provider = provider
        self.issuer = issuer
        self.subject = subject


class MissingUserForExternalIdentity(UserIdentityError):
    """Raised when an auth identity points at a missing internal user."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"external auth identity references missing user {user_id!r}")
        self.user_id = user_id


class MissingProfileForExternalIdentity(UserIdentityError):
    """Raised when an existing identity has no required internal profile."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"external auth identity references missing profile {user_id!r}")
        self.user_id = user_id


class UserNotFound(UserIdentityError):
    """Raised when a user-scoped operation references a missing app user."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"user not found: {user_id!r}")
        self.user_id = user_id


class DeactivatedUserAuthenticationBlocked(UserIdentityError):
    """Raised when a deactivated app account attempts to authenticate again."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"deactivated user cannot authenticate: {user_id!r}")
        self.user_id = user_id


class CrossUserAccessBlocked(UserIdentityError):
    """Raised when a caller attempts to access another user's owned data."""

    def __init__(self, current_user_id: str, owner_user_id: str) -> None:
        super().__init__(
            f"user {current_user_id!r} cannot access user-owned data for {owner_user_id!r}"
        )
        self.current_user_id = current_user_id
        self.owner_user_id = owner_user_id


class SavedMarketArtifactNotFound(UserIdentityError):
    """Raised when a saved artifact does not exist."""

    def __init__(self, saved_artifact_id: str) -> None:
        super().__init__(f"saved market artifact not found: {saved_artifact_id!r}")
        self.saved_artifact_id = saved_artifact_id


class RecommendationSnapshotNotFound(UserIdentityError):
    """Raised when a personalized recommendation snapshot does not exist."""

    def __init__(self, recommendation_snapshot_id: str) -> None:
        super().__init__(
            f"personalized recommendation snapshot not found: "
            f"{recommendation_snapshot_id!r}"
        )
        self.recommendation_snapshot_id = recommendation_snapshot_id


class PreferenceProfileNotFound(UserIdentityError):
    """Raised when a snapshot references a missing saved preference profile."""

    def __init__(self, preference_profile_id: str) -> None:
        super().__init__(f"user preference profile not found: {preference_profile_id!r}")
        self.preference_profile_id = preference_profile_id


class InvalidSavedMarketArtifactType(UserIdentityError):
    """Raised when a saved artifact type is outside the allowed Batch B set."""

    def __init__(self, artifact_type: str) -> None:
        super().__init__(f"invalid saved market artifact_type: {artifact_type!r}")
        self.artifact_type = artifact_type
