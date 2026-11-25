"""Role changes and removals, keeping at least one admin per company.

Every change locks the company's admin memberships first, so two admins
demoting each other at the same moment are serialized: one of them wins and
the other gets LastAdminError instead of leaving the company without an admin.
"""

from django.db import transaction

from accounts.models import Membership
from events.models import EventType
from events.outbox import emit

ADMIN = Membership.Role.ADMIN


class LastAdminError(Exception):
    """The change would leave the company without an admin."""


def _locked(membership_id: int) -> tuple[Membership, list[int]]:
    admin_ids = list(
        Membership.objects.select_for_update().filter(role=ADMIN).values_list("id", flat=True)
    )
    membership = (
        Membership.objects.select_for_update(of=("self",))
        .select_related("user")
        .get(id=membership_id)
    )
    return membership, admin_ids


def change_role(membership_id: int, role: str) -> Membership:
    with transaction.atomic():
        membership, admin_ids = _locked(membership_id)
        if membership.role == ADMIN and role != ADMIN and admin_ids == [membership.id]:
            raise LastAdminError
        previous = membership.role
        membership.role = role
        membership.save(update_fields=["role"])
        if previous != role:
            _emit(EventType.MEMBER_ROLE_CHANGED, membership, {"from": previous, "to": role})
        return membership


def remove_member(membership_id: int) -> None:
    with transaction.atomic():
        membership, admin_ids = _locked(membership_id)
        if membership.role == ADMIN and admin_ids == [membership.id]:
            raise LastAdminError
        _emit(EventType.MEMBER_REMOVED, membership, {"role": membership.role})
        membership.delete()


def _emit(type: EventType, membership: Membership, payload: dict) -> None:
    # The person is the subject: events about them survive their leaving.
    user = membership.user
    emit(type, entity_type="member", entity_id=user.id, label=user.full_name, payload=payload)
