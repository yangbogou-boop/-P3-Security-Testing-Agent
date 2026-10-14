"""Trusted offline test seam. Records decisions; performs no HTTP operations."""
from threading import Event, RLock


class Revocation:
    """Owned by the trusted application, never passed to the Planner."""
    def __init__(self):
        self._revoked = Event()
        self._gate = RLock()

    def revoke(self):
        with self._gate:
            self._revoked.set()

    def dispatch_if_active(self, callback):
        # The offline adapter is synchronous/nonblocking. This lock linearizes
        # dispatch acceptance with trusted revocation; it is NOT an HTTP cancel API.
        with self._gate:
            if self.revoked:
                return False
            callback()
            return True

    @property
    def revoked(self):
        return self._revoked.is_set()


class OfflineDispatcher:
    def __init__(self):
        self.calls = []

    def record(self, check, remaining_seconds, revocation):
        self.calls.append((check, remaining_seconds))
        # No response, credentials, HTTP request or security verdict is returned.
