import uuid
from contextvars import Token

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from tenancy import context

COMPANY_CLAIM = "company_id"


def company_from_request(request: Request) -> uuid.UUID | None:
    """The active company, from the `company_id` claim of the access token.

    The server only issues a token for a company after checking the membership,
    and switching companies means a new token, so the claim can be trusted.
    """
    auth = request.auth
    claim = auth.get(COMPANY_CLAIM) if hasattr(auth, "get") else None
    if not claim:
        return None
    try:
        return uuid.UUID(str(claim))
    except ValueError:
        return None


class TenantScopedMixin:
    """For API views over tenant data: runs the whole request as the token's company.

    Relies on ATOMIC_REQUESTS, so the company applies to every query of the
    request and disappears when its transaction ends.
    """

    _tenant_token: Token | None = None

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)  # authentication, permissions, throttling
        company_id = company_from_request(request)
        if company_id is None:
            raise PermissionDenied(_("Choose a company to continue."))
        self._tenant_token = context.activate(company_id)

    def finalize_response(self, request: Request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if self._tenant_token is not None:
            context.deactivate(self._tenant_token)
            self._tenant_token = None
        return response
