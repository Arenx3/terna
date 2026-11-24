import json

from django.core.management import call_command
from django.urls import reverse


def test_schema_documents_health(client):
    response = client.get(reverse("schema"), {"format": "json"})

    assert response.status_code == 200
    schema = json.loads(response.content)
    assert schema["info"]["title"] == "Terna API"
    assert "/api/health/" in schema["paths"]


def test_schema_generates_without_warnings(tmp_path):
    call_command("spectacular", "--fail-on-warn", "--file", str(tmp_path / "schema.yaml"))


def test_docs_page_serves_bundled_swagger_ui(client):
    response = client.get(reverse("docs"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "swagger-ui" in html
    assert "cdn.jsdelivr.net" not in html
