"""The active company's team: members, roles and invitations. Changes are admin-only."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts import invitations, team
from accounts.models import Invitation, Membership, User
from accounts.permissions import CompanyView, IsCompanyAdmin, IsCompanyMember
from accounts.serializers import (
    AcceptInvitationSerializer,
    InvitationPreviewSerializer,
    InvitationSerializer,
    InviteSerializer,
    MemberSerializer,
    RoleSerializer,
    SessionSerializer,
)
from accounts.throttles import IPRateThrottle
from accounts.views import session_response


class LastAdmin(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A company needs at least one admin."
    default_code = "last_admin"


class AlreadyMember(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This person is already a member of the company."
    default_code = "already_member"


class InvitationProblem(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This invitation can't be used."
    default_code = "invitation_invalid"


class MembersView(CompanyView):
    @extend_schema(responses={200: MemberSerializer(many=True)}, tags=["team"])
    def get(self, request: Request) -> Response:
        members = Membership.objects.select_related("user").order_by("created_at")
        return Response(MemberSerializer(members, many=True).data)


class MemberDetailView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, IsCompanyAdmin)

    @extend_schema(request=RoleSerializer, responses={200: MemberSerializer}, tags=["team"])
    def patch(self, request: Request, pk: int) -> Response:
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = team.change_role(pk, serializer.validated_data["role"])
        except Membership.DoesNotExist as exc:
            raise exceptions.NotFound from exc
        except team.LastAdminError as exc:
            raise LastAdmin from exc
        return Response(MemberSerializer(membership).data)

    @extend_schema(responses={204: None}, tags=["team"])
    def delete(self, request: Request, pk: int) -> Response:
        try:
            team.remove_member(pk)
        except Membership.DoesNotExist as exc:
            raise exceptions.NotFound from exc
        except team.LastAdminError as exc:
            raise LastAdmin from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationsView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, IsCompanyAdmin)
    throttle_classes = (IPRateThrottle,)
    throttle_scope = "invite"

    def get_throttles(self):
        # Only sending invitations is limited; listing them is not.
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(responses={200: InvitationSerializer(many=True)}, tags=["team"])
    def get(self, request: Request) -> Response:
        pending = (
            Invitation.objects.select_related("invited_by")
            .filter(accepted_at__isnull=True, revoked_at__isnull=True)
            .order_by("-created_at")
        )
        return Response(InvitationSerializer(pending, many=True).data)

    @extend_schema(request=InviteSerializer, responses={201: InvitationSerializer}, tags=["team"])
    def post(self, request: Request) -> Response:
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = invitations.invite(
                **serializer.validated_data,
                invited_by=request.user,
                language=request.LANGUAGE_CODE,
            )
        except invitations.AlreadyMemberError as exc:
            raise AlreadyMember from exc
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationDetailView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, IsCompanyAdmin)

    @extend_schema(responses={204: None}, tags=["team"])
    def delete(self, request: Request, pk: int) -> Response:
        if not invitations.revoke(pk):
            raise exceptions.NotFound
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicInvitationView(APIView):
    """Opened from the emailed link. Signing in is optional: it decides how to accept."""

    authentication_classes = (JWTAuthentication,)
    permission_classes = (AllowAny,)
    throttle_classes = (IPRateThrottle,)
    throttle_scope = "invitation"

    def _lookup(self, token: str) -> invitations.InvitationLookup:
        lookup = invitations.find(token)
        if lookup is None:
            raise InvitationProblem
        return lookup


class InvitationPreviewView(PublicInvitationView):
    @extend_schema(responses={200: InvitationPreviewSerializer}, tags=["team"])
    def get(self, request: Request, token: str) -> Response:
        lookup = self._lookup(token)
        data = {
            "company_name": lookup.company_name,
            "email": lookup.email,
            "role": lookup.role,
            "status": lookup.status,
            "account_exists": User.objects.filter(email=lookup.email).exists(),
        }
        return Response(InvitationPreviewSerializer(data).data)


class AcceptInvitationView(PublicInvitationView):
    @extend_schema(
        request=AcceptInvitationSerializer, responses={200: SessionSerializer}, tags=["team"]
    )
    def post(self, request: Request, token: str) -> Response:
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user and request.user.is_authenticated else None
        try:
            user, membership = invitations.accept(token, user=user, **serializer.validated_data)
        except invitations.InvitationError as exc:
            raise InvitationProblem(code=exc.code) from exc
        except DjangoValidationError as exc:
            raise exceptions.ValidationError({"password": list(exc.messages)}) from exc
        # Signed in, and switched to the company they just joined.
        return session_response(user, membership)
