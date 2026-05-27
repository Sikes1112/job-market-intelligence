"""Billing adapter layer.

Billing providers are external adapters. Product access remains owned by the
internal monetization account, plan assignment, and entitlement modules.
"""

from backend.billing.provider import BillingProvider

__all__ = ["BillingProvider"]
