import pytest

from services.rag_providers.url_policy import UrlPolicyError, normalize_service_url


@pytest.mark.parametrize("value", ["https://host", "https://host/api/v1", "https://host/api/v1/"])
def test_equivalent_inputs(value):
    result = normalize_service_url(value)
    assert result.service_root == "https://host"
    assert result.api_base == "https://host/api/v1"


@pytest.mark.parametrize("value", [
    "https://host/platform/api-docs",
    "https://host/swagger/index.html",
    "https://user:pass@host",
    "https://host?x=1",
    "https://host#frag",
])
def test_rejects_unsafe_or_document_urls(value):
    with pytest.raises(UrlPolicyError):
        normalize_service_url(value)


def test_collapses_duplicate_version():
    assert normalize_service_url("https://host/api/v1/api/v1").api_base == "https://host/api/v1"
