"""Internal app-user identity and user-owned personalization persistence.

Users are app identities mapped from managed-auth provider subjects. Saved
preferences, saved market artifacts, personalized recommendation snapshots, and
privacy controls are user-owned behavior only; this package must not contain
canonical market-truth behavior.
"""
