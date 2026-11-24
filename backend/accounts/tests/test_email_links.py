"""Email verification and password recovery, end to end through the outbox."""

from urllib.parse import parse_qs, urlparse

import pytest

from accounts.models import User
from accounts.tests.conftest import PASSWORD, link_in
from accounts.tokens import make_verification_token

pytestmark = pytest.mark.django_db

SIGNUP = "/api/auth/signup/"
VERIFY = "/api/auth/verify-email/"
RESEND = "/api/auth/verify-email/resend/"
LOGIN = "/api/auth/login/"
RESET = "/api/auth/password-reset/"
RESET_CONFIRM = "/api/auth/password-reset/confirm/"


def query(link: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(link).query).items()}


def sign_up(post, email="ana@acme.test"):
    post(
        SIGNUP,
        {"company_name": "Acme", "full_name": "Ana", "email": email, "password": PASSWORD},
    )


def test_verification_link_verifies_and_allows_login(post, mailoutbox):
    sign_up(post)
    token = query(link_in(mailoutbox[0], "/verify-email"))["token"]

    assert post(LOGIN, {"email": "ana@acme.test", "password": PASSWORD}).status_code == 403
    assert post(VERIFY, {"token": token}).status_code == 200
    assert User.objects.get().is_email_verified
    assert post(LOGIN, {"email": "ana@acme.test", "password": PASSWORD}).status_code == 200


def test_verification_link_can_be_opened_twice(post, mailoutbox):
    sign_up(post)
    token = query(link_in(mailoutbox[0], "/verify-email"))["token"]

    assert post(VERIFY, {"token": token}).status_code == 200
    assert post(VERIFY, {"token": token}).status_code == 200


@pytest.mark.parametrize("token", ["", "garbage", "eyJ1IjoiMSJ9:abc:def"])
def test_tampered_verification_links_are_rejected(post, token):
    response = post(VERIFY, {"token": token})

    assert response.status_code == 400


def test_expired_verification_link_is_rejected(post, mailoutbox, settings):
    sign_up(post)
    token = query(link_in(mailoutbox[0], "/verify-email"))["token"]
    settings.EMAIL_VERIFICATION_MAX_AGE = -1

    response = post(VERIFY, {"token": token})

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_link"


def test_verification_link_is_tied_to_the_address(post, mailoutbox):
    sign_up(post)
    user = User.objects.get()
    token = make_verification_token(user)
    User.objects.filter(id=user.id).update(email="changed@acme.test")

    assert post(VERIFY, {"token": token}).status_code == 400


def test_resend_verification_answers_the_same_for_any_address(post, mailoutbox):
    sign_up(post)
    mailoutbox.clear()

    known = post(RESEND, {"email": "ana@acme.test"})
    unknown = post(RESEND, {"email": "nobody@acme.test"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [m.to for m in mailoutbox] == [["ana@acme.test"]]


def test_password_reset_end_to_end(post, member, mailoutbox):
    member()

    assert post(RESET, {"email": "ana@acme.test"}).status_code == 202
    params = query(link_in(mailoutbox[0], "/reset-password"))
    new_password = "a-brand-new-passphrase-7"

    response = post(RESET_CONFIRM, {**params, "password": new_password})

    assert response.status_code == 200
    assert post(LOGIN, {"email": "ana@acme.test", "password": PASSWORD}).status_code == 401
    assert post(LOGIN, {"email": "ana@acme.test", "password": new_password}).status_code == 200


def test_password_reset_link_works_once(post, member, mailoutbox):
    member()
    post(RESET, {"email": "ana@acme.test"})
    params = query(link_in(mailoutbox[0], "/reset-password"))

    assert post(RESET_CONFIRM, {**params, "password": "first-new-passphrase-1"}).status_code == 200
    second = post(RESET_CONFIRM, {**params, "password": "second-new-passphrase-2"})

    assert second.status_code == 400
    assert second.json()["code"] == "invalid_link"


def test_password_reset_still_checks_strength(post, member, mailoutbox):
    member()
    post(RESET, {"email": "ana@acme.test"})
    params = query(link_in(mailoutbox[0], "/reset-password"))

    response = post(RESET_CONFIRM, {**params, "password": "password"})

    assert response.status_code == 400
    assert "password" in response.json()


def test_password_reset_answers_the_same_for_unknown_addresses(post, member, mailoutbox):
    member()

    known = post(RESET, {"email": "ana@acme.test"})
    unknown = post(RESET, {"email": "nobody@acme.test"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailoutbox) == 1


def test_password_reset_is_rate_limited_per_address(post, member):
    member()

    statuses = [post(RESET, {"email": "ana@acme.test"}).status_code for _ in range(4)]

    assert statuses == [202, 202, 202, 429]
