from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User, normalize_email


def check_password_strength(password: str, user: User) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc


class SignupSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=200, trim_whitespace=True)
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    language = serializers.ChoiceField(choices=settings.LANGUAGES, default="en")

    def validate(self, attrs: dict) -> dict:
        attrs["email"] = normalize_email(attrs["email"])
        candidate = User(email=attrs["email"], full_name=attrs["full_name"])
        try:
            check_password_strength(attrs["password"], candidate)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"password": exc.detail}) from exc
        return attrs


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "language"]


class CompanySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="company_id")
    name = serializers.CharField(source="company_name")
    role = serializers.CharField()


class SessionSerializer(serializers.Serializer):
    """What the app needs after login or refresh: who, and in which company."""

    access = serializers.CharField()
    user = UserSerializer()
    company = CompanySerializer()
    companies = CompanySerializer(many=True)


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)
