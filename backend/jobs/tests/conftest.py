import pytest


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
