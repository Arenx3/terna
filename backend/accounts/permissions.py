"""Role checks for company-scoped API views.

The role comes from the caller's membership in the active company, read from
the database on every request rather than trusted from the token: removing
someone or changing their role takes effect immediately.
"""

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.models import Membership
from tenancy.api import TenantScopedMixin

_UNSET = object()


def current_membership(request: Request) -> Membership | None:
    """The caller's membership in the active company, cached for the request."""
    cached = getattr(request, "_membership", _UNSET)
    if cached is _UNSET:
        user = request.user
        cached = (
            Membership.objects.filter(user_id=user.id).first()
            if user is not None and user.is_authenticated
            else None
        )
        request._membership = cached
    return cached


class IsCompanyMember(BasePermission):
    message = "You are not a member of this company."
    code = "not_member"

    def has_permission(self, request: Request, view: APIView) -> bool:
        return current_membership(request) is not None


class IsCompanyAdmin(BasePermission):
    message = "Only company admins can do this."
    code = "admin_required"

    def has_permission(self, request: Request, view: APIView) -> bool:
        membership = current_membership(request)
        return membership is not None and membership.role == Membership.Role.ADMIN


class CompanyView(TenantScopedMixin, APIView):
    """Base for views over the active company's data: members only."""

    permission_classes = (IsAuthenticated, IsCompanyMember)
