import json

from services.credential_cipher import redact_secret
from services.rag_providers.base import ProviderError, RagQueryResult
from utils.shared_utils import redact_mapping


def test_secret_fields_and_values_are_redacted():
    payload = redact_mapping(
        {
            "api_key": "secret-key",
            "Authorization": "Bearer admin-token",
            "nested": {"X-API-Key": "secret-key"},
        }
    )
    serialized = json.dumps(payload)
    assert "secret-key" not in serialized
    assert "admin-token" not in serialized


def test_provider_result_never_contains_headers_or_secret():
    result = RagQueryResult(
        provider="intelliq",
        session_id="s",
        error=ProviderError("authentication", "invalid credential"),
    ).to_dict()
    serialized = redact_secret(json.dumps(result), ["top-secret"])
    assert "top-secret" not in serialized
