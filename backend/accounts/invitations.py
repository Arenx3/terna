"""Invitations: an admin invites an address with a role; the link joins the company once."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.auth.password_validation import validate_password
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import Invitation, Membership, User, normalize_email
from accounts.sessions import CompanyMembership, membership_in
from accounts.tasks import send_invitation_email
from events.models import EventType
from events.outbox import emit
from tenancy.context import tenant_context

LIFETIME = timedelta(days=7)
INVITATION_LOOKUP_FUNCTION = "app_invitation_by_token"


class InvitationError(Exception):
    """Why an invitation link cannot be used. `code` is stable for clients."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AlreadyMemberError(Exception):
    """The address already belongs to the company."""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class InvitationLookup:
    id: int
    company_id: uuid.UUID
    company_name: str
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        if self.accepted_at is not None:
            return "used"
        if self.expires_at <= timezone.now():
            return "expired"
        return "valid"


def find(token: str) -> InvitationLookup | None:
    """Look an invitation up by its link, across companies.

    Whoever opens the link has no active company yet, so this goes through a
    SECURITY DEFINER function that only matches the exact token hash.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM {INVITATION_LOOKUP_FUNCTION}(%s)",  # noqa: S608 (constant name)
            [hash_token(token)],
        )
        row = cursor.fetchone()
    return InvitationLookup(*row) if row else None


def invite(*, email: str, role: str, invited_by: User, language: str) -> Invitation:
    """Invite an address to the active company. A pending invitation is replaced."""
    email = normalize_email(email)
    if Membership.objects.filter(user__email=email).exists():
        raise AlreadyMemberError
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        Invitation.objects.filter(
            email=email, accepted_at__isnull=True, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
        invitation = Invitation.objects.create(
            email=email,
            role=role,
            language=language,
            token_hash=hash_token(token),
            invited_by=invited_by,
            expires_at=timezone.now() + LIFETIME,
        )
        emit(
            EventType.INVITATION_SENT,
            entity_type="invitation",
            entity_id=invitation.id,
            label=email,
            payload={"role": role},
        )
    company_id, invitation_id = str(invitation.company_id), invitation.id
    transaction.on_commit(lambda: send_invitation_email.delay(company_id, invitation_id, token))
    return invitation


def revoke(invitation_id: int) -> bool:
    with transaction.atomic():
        invitation = (
            Invitation.objects.select_for_update()
            .filter(id=invitation_id, accepted_at__isnull=True, revoked_at__isnull=True)
            .first()
        )
        if invitation is None:
            return False
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at"])
        emit(
            EventType.INVITATION_REVOKED,
            entity_type="invitation",
            entity_id=invitation.id,
            label=invitation.email,
            payload={"role": invitation.role},
        )
        return True


def accept(
    token: str,
    *,
    user: User | None,
    full_name: str | None = None,
    password: str | None = None,
) -> tuple[User, CompanyMembership]:
    """Join the company. Without a signed-in user, creates the account first.

    Following the emailed link proves the address, so a new account starts
    verified. An existing account must sign in first, as that same address.
    """
    lookup = find(token)
    if lookup is None:
        raise InvitationError("invitation_invalid")
    if lookup.status != "valid":
        raise InvitationError(f"invitation_{lookup.status}")

    with tenant_context(lookup.company_id):
        invitation = Invitation.objects.select_for_update().get(id=lookup.id)
        if not invitation.is_pending or invitation.expires_at <= timezone.now():
            raise InvitationError("invitation_used")  # lost a race with another click

        if user is None:
            if User.objects.filter(email=invitation.email).exists():
                raise InvitationError("login_required")
            if not full_name or not password:
                raise InvitationError("account_details_required")
            # Raises Django's ValidationError with the reasons, in the request's language.
            validate_password(password, user=User(email=invitation.email, full_name=full_name))
            user = User.objects.create_user(
                invitation.email,
                password,
                full_name=full_name,
                language=invitation.language,
                email_verified_at=timezone.now(),
            )
        elif user.email != invitation.email:
            raise InvitationError("invitation_email_mismatch")

        membership, joined = Membership.objects.get_or_create(
            user=user, defaults={"role": invitation.role}
        )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
        if joined:
            emit(
                EventType.MEMBER_JOINED,
                entity_type="member",
                entity_id=user.id,
                label=user.full_name,
                payload={"role": membership.role},
                actor=user,
            )

    membership = membership_in(user.id, lookup.company_id)
    if membership is None:  # created above in this same transaction
        raise RuntimeError("Membership missing right after accepting an invitation.")
    return user, membership
