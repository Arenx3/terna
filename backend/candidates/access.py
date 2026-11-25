"""Who may see which applications. One rule, used by every endpoint about candidates."""

from django.db.models import QuerySet
from rest_framework.request import Request

from accounts.models import Membership, User
from accounts.permissions import current_membership
from candidates.models import Application

Role = Membership.Role
MANAGERS = frozenset({Role.ADMIN, Role.RECRUITER})


def visible_applications(request: Request) -> QuerySet[Application]:
    """Admins and recruiters see every candidate; hiring managers, those of the jobs
    they own; interviewers, only the candidates they are assigned to."""
    membership = current_membership(request)
    applications = Application.objects.all()
    if membership is None:
        return applications.none()
    if membership.role in MANAGERS:
        return applications
    if membership.role == Role.HIRING_MANAGER:
        return applications.filter(job__hiring_manager_id=request.user.id)
    if membership.role == Role.INTERVIEWER:
        return applications.filter(assignments__user_id=request.user.id)
    return applications.none()


def can_manage(request: Request) -> bool:
    membership = current_membership(request)
    return membership is not None and membership.role in MANAGERS


def people_who_can_see(application: Application) -> list[User]:
    """Everyone a comment on this application can mention: they can all open it."""
    memberships = Membership.objects.select_related("user")
    allowed = []
    assigned = set(application.assignments.values_list("user_id", flat=True))
    for membership in memberships:
        role, user = membership.role, membership.user
        if (
            role in MANAGERS
            or (role == Role.HIRING_MANAGER and application.job.hiring_manager_id == user.id)
            or (role == Role.INTERVIEWER and user.id in assigned)
        ):
            allowed.append(user)
    return sorted(allowed, key=lambda person: person.full_name)
