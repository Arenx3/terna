import hashlib

from rest_framework.throttling import ScopedRateThrottle

from accounts.models import normalize_email


class IPRateThrottle(ScopedRateThrottle):
    """Per client IP, with the rate named by the view's `throttle_scope`."""


class EmailRateThrottle(ScopedRateThrottle):
    """Per target address, named by the view's `email_throttle_scope`.

    Stops slow, distributed guessing against one account, which a per-IP
    limit alone would let through. The address is hashed in the cache key.
    """

    scope_attr = "email_throttle_scope"

    def get_cache_key(self, request, view) -> str | None:
        email = normalize_email(request.data.get("email") if hasattr(request.data, "get") else "")
        if not email:
            return None
        ident = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}
