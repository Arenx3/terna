import pytest

from accounts.models import Membership, User
from accounts.tests.conftest import PASSWORD, link_in
from tenancy.context import all_company_ids, tenant_context
from tenancy.models import Company

pytestmark = pytest.mark.django_db

URL = "/api/auth/signup/"


def signup_data(**overrides) -> dict:
    return {
        "company_name": "Acme",
        "full_name": "Ana Pérez",
        "email": "Ana@Acme.test ",
        "password": PASSWORD,
        "language": "en",
        **overrides,
    }


def test_creates_company_admin_and_membership(post, mailoutbox):
    response = post(URL, signup_data())

    assert response.status_code == 202
    user = User.objects.get()
    assert user.email == "ana@acme.test"
    assert user.full_name == "Ana Pérez"
    assert user.is_email_verified is False
    [company_id] = all_company_ids()
    with tenant_context(company_id):
        assert Company.objects.get().name == "Acme"
        membership = Membership.objects.get()
        assert (membership.user_id, membership.role) == (user.id, Membership.Role.ADMIN)

    [message] = mailoutbox
    assert message.to == ["ana@acme.test"]
    assert "/verify-email?token=" in link_in(message, "/verify-email")


def test_sends_the_email_in_the_users_language(post, mailoutbox):
    post(URL, signup_data(language="es"))

    [message] = mailoutbox
    assert message.subject == "Confirma tu correo para Terna"
    assert "Hola, Ana Pérez" in message.body


def test_is_all_or_nothing(post, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(Membership.objects, "create", fail)

    with pytest.raises(RuntimeError):
        post(URL, signup_data())

    assert not User.objects.exists()
    assert all_company_ids() == []


def test_existing_address_gets_the_same_answer_and_a_heads_up(post, member, mailoutbox):
    member("ana@acme.test")

    response = post(URL, signup_data(company_name="Other"))

    assert response.status_code == 202
    assert response.json() == post(URL, signup_data(email="new@acme.test")).json()
    assert User.objects.filter(email="ana@acme.test").count() == 1
    assert mailoutbox[0].subject == "You already have a Terna account"
    assert "/forgot-password" in mailoutbox[0].body


def test_rejects_weak_passwords_in_the_requested_language(post):
    response = post(URL, signup_data(password="12345678"), HTTP_ACCEPT_LANGUAGE="es")

    assert response.status_code == 400
    messages = " ".join(response.json()["password"])
    assert "demasiado corta" in messages
    assert not User.objects.exists()


def test_rejects_passwords_too_similar_to_the_email(post):
    response = post(URL, signup_data(password="ana@acme.test"))

    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.parametrize("field", ["company_name", "full_name", "email", "password"])
def test_requires_every_field(post, field):
    data = signup_data()
    del data[field]

    response = post(URL, data)

    assert response.status_code == 400
    assert field in response.json()


def test_is_rate_limited_per_ip(post):
    statuses = [post(URL, signup_data(email=f"u{i}@acme.test")).status_code for i in range(6)]

    assert statuses[:5] == [202] * 5
    assert statuses[5] == 429
