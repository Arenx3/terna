"""Single-purpose links sent by email: verify an address, reset a password."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import User

VERIFY_EMAIL_SALT = "accounts.verify-email"


class InvalidLinkError(ValueError):
    """The link is malformed, expired, already used or for another address."""


def make_verification_token(user: User) -> str:
    # Bound to the address: changing the email invalidates links sent to the old one.
    return signing.dumps({"u": str(user.id), "e": user.email}, salt=VERIFY_EMAIL_SALT)


def verify_email(token: str) -> User:
    try:
        payload = signing.loads(
            token, salt=VERIFY_EMAIL_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE
        )
        user = User.objects.get(id=payload["u"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, User.DoesNotExist) as exc:
        raise InvalidLinkError from exc
    if user.email != payload.get("e") or not user.is_active:
        raise InvalidLinkError
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def make_password_reset_params(user: User) -> dict[str, str]:
    # Django's generator hashes the password and last login into the token,
    # so a link stops working once it is used or the user logs in.
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }


def user_for_password_reset(uid: str, token: str) -> User:
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as exc:
        raise InvalidLinkError from exc
    if not user.is_active or not default_token_generator.check_token(user, token):
        raise InvalidLinkError
    return user
