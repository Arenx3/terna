"""Authentication API.

Every endpoint is rate limited, and none reveals whether an address has an account.
"""

import uuid
from contextlib import suppress

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts import services, sessions
from accounts.models import User
from accounts.serializers import (
    DetailSerializer,
    EmailSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    SessionSerializer,
    SignupSerializer,
    SwitchCompanySerializer,
    TokenSerializer,
    UserSerializer,
    check_password_strength,
)
from accounts.throttles import EmailRateThrottle, IPRateThrottle
from accounts.tokens import InvalidLinkError, user_for_password_reset, verify_email
from tenancy.api import COMPANY_CLAIM, company_from_request

ACCEPTED = {"detail": "If the address can receive email, a message is on its way."}


class InvalidCredentials(exceptions.AuthenticationFailed):
    default_detail = "Email or password is incorrect."
    default_code = "invalid_credentials"


class EmailNotVerified(exceptions.PermissionDenied):
    default_detail = "Verify your email address before logging in."
    default_code = "email_not_verified"


class NoCompany(exceptions.PermissionDenied):
    default_detail = "This account does not belong to any company."
    default_code = "no_company"


class InvalidLink(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This link is invalid or has expired."
    default_code = "invalid_link"


class SessionExpired(exceptions.NotAuthenticated):
    default_detail = "Your session has expired. Log in again."
    default_code = "session_expired"


class PublicAuthView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (IPRateThrottle,)

    def get_authenticate_header(self, request: Request) -> str:
        # Without authenticators DRF would turn 401 into 403; failed logins are 401.
        return 'Bearer realm="api"'


def session_response(user: User, membership: sessions.CompanyMembership) -> Response:
    """Access token in the body, refresh token in the httpOnly cookie."""
    refresh = sessions.issue_refresh_token(user, membership.company_id)
    data = {
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
        "company": membership,
        "companies": sessions.user_memberships(user.id),
    }
    response = Response(SessionSerializer(data).data)
    sessions.set_refresh_cookie(response, refresh)
    return response


class SignupView(PublicAuthView):
    throttle_scope = "signup"

    @extend_schema(request=SignupSerializer, responses={202: DetailSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.register_company(**serializer.validated_data)
        return Response(ACCEPTED, status=status.HTTP_202_ACCEPTED)


class VerifyEmailView(PublicAuthView):
    throttle_scope = "verify_email"

    @extend_schema(request=TokenSerializer, responses={200: DetailSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            verify_email(serializer.validated_data["token"])
        except InvalidLinkError as exc:
            raise InvalidLink from exc
        return Response({"detail": "Email verified."})


class ResendVerificationView(PublicAuthView):
    throttle_classes = (IPRateThrottle, EmailRateThrottle)
    throttle_scope = "resend_verification"
    email_throttle_scope = "resend_verification_email"

    @extend_schema(request=EmailSerializer, responses={202: DetailSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_verification_email(serializer.validated_data["email"])
        return Response(ACCEPTED, status=status.HTTP_202_ACCEPTED)


class LoginView(PublicAuthView):
    throttle_classes = (IPRateThrottle, EmailRateThrottle)
    throttle_scope = "login"
    email_throttle_scope = "login_email"

    @extend_schema(request=LoginSerializer, responses={200: SessionSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Django's backend hashes even for unknown addresses, so timing reveals nothing.
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise InvalidCredentials
        if not user.is_email_verified:
            raise EmailNotVerified
        memberships = sessions.user_memberships(user.id)
        if not memberships:
            raise NoCompany
        update_last_login(None, user)
        return session_response(user, memberships[0])


class RefreshView(PublicAuthView):
    """Rotates the refresh cookie and returns a fresh access token.

    The membership is checked again, so removing someone from a company takes
    effect within one access-token lifetime.
    """

    throttle_scope = "refresh"

    @extend_schema(request=None, responses={200: SessionSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        try:
            refresh = RefreshToken(raw)  # checks signature, expiry and blacklist
        except TokenError as exc:
            raise SessionExpired from exc
        user = User.objects.filter(id=refresh.get("user_id"), is_active=True).first()
        membership = (
            sessions.membership_in(user.id, _uuid(refresh.get(COMPANY_CLAIM))) if user else None
        )
        if membership is None:
            refresh.blacklist()
            raise SessionExpired
        refresh.blacklist()  # single use: a stolen copy stops working after the next refresh
        return session_response(user, membership)


class LogoutView(PublicAuthView):
    throttle_scope = "refresh"

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if raw:
            # Already expired or revoked: nothing left to end.
            with suppress(TokenError):
                RefreshToken(raw).blacklist()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        sessions.clear_refresh_cookie(response)
        return response


class PasswordResetView(PublicAuthView):
    throttle_classes = (IPRateThrottle, EmailRateThrottle)
    throttle_scope = "password_reset"
    email_throttle_scope = "password_reset_email"

    @extend_schema(request=EmailSerializer, responses={202: DetailSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response(ACCEPTED, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(PublicAuthView):
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        request=PasswordResetConfirmSerializer, responses={200: DetailSerializer}, tags=["auth"]
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = user_for_password_reset(data["uid"], data["token"])
        except InvalidLinkError as exc:
            raise InvalidLink from exc
        try:
            check_password_strength(data["password"], user)
        except exceptions.ValidationError as exc:
            raise exceptions.ValidationError({"password": exc.detail}) from exc
        user.set_password(data["password"])
        # Following the link proves the address too.
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
        user.save(update_fields=["password", "email_verified_at"])
        return Response({"detail": "Password updated. Log in with your new password."})


class NotMember(exceptions.PermissionDenied):
    default_detail = "You are not a member of this company."
    default_code = "not_member"


class SwitchCompanyView(APIView):
    """New tokens for another company the person belongs to.

    The current refresh cookie is revoked, so the previous company's session
    cannot be resumed by replaying it.
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (IPRateThrottle,)
    throttle_scope = "refresh"

    @extend_schema(
        request=SwitchCompanySerializer, responses={200: SessionSerializer}, tags=["auth"]
    )
    def post(self, request: Request) -> Response:
        serializer = SwitchCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = sessions.membership_in(
            request.user.id, serializer.validated_data["company_id"]
        )
        if membership is None:
            raise NotMember
        raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if raw:
            with suppress(TokenError):
                RefreshToken(raw).blacklist()
        return session_response(request.user, membership)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: SessionSerializer}, tags=["auth"])
    def get(self, request: Request) -> Response:
        membership = sessions.membership_in(request.user.id, company_from_request(request))
        if membership is None:
            raise SessionExpired
        data = {
            "access": str(request.auth),
            "user": UserSerializer(request.user).data,
            "company": membership,
            "companies": sessions.user_memberships(request.user.id),
        }
        return Response(SessionSerializer(data).data)


def _uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
