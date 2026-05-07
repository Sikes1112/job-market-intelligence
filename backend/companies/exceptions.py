"""Company service domain exceptions."""

from __future__ import annotations


class CompanyError(Exception):
    """Base for all company service errors."""


class CompanyNotFound(CompanyError):
    """Raised when a company_id is referenced but does not exist."""


class DuplicateCompany(CompanyError):
    """Raised when creating a company whose company_id already exists."""


class InvalidClassification(CompanyError):
    """Raised when a classification result is structurally contradictory.

    Example: ``is_mag7=True`` paired with ``eligibility_status=ineligible`` and
    no override.
    """


class InvalidOverride(CompanyError):
    """Raised when an override declaration is malformed (e.g. blank reason)."""
