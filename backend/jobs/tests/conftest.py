import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Membership, User
from accounts.sessions import issue_refresh_token
from tenancy.context import tenant_context
from tenancy.services import create_company

Role = Membership.Role


class Team:
    """A company with one person per role, and API clients logged in as each."""

    def __init__(self, name: str) -> None:
        self.company = create_company(name)
        self.people: dict[str, User] = {}
        slug = name.lower()
        for role in Role.values:
            user = User.objects.create_user(
                f"{role}@{slug}.test",
                "correct-horse-battery-42",
                full_name=f"{role.replace('_', ' ').title()} {name}",
                email_verified_at=timezone.now(),
            )
            with tenant_context(self.company.id):
                Membership.objects.create(company=self.company, user=user, role=role)
            self.people[role] = user

    def client(self, role: str) -> APIClient:
        client = APIClient()
        token = issue_refresh_token(self.people[role], self.company.id).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client


@pytest.fixture
def acme(db):
    return Team("Acme")


@pytest.fixture
def globex(db):
    return Team("Globex")


@pytest.fixture
def job_payload():
    def make(**overrides) -> dict:
        payload = {
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "location": "Monterrey, NL",
            "workplace": "hybrid",
            "employment": "full_time",
            "language": "es",
            "description": "Build the services behind checkout.",
            "requirements": [
                {"text": "5+ years building APIs in Python", "kind": "must"},
                {"text": "Kubernetes in production", "kind": "must"},
                {"text": "Advanced English", "kind": "nice"},
            ],
        }
        payload.update(overrides)
        return payload

    return make
