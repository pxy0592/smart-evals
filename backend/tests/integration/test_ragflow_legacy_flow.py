from services.rag_providers.factory import create_provider


def test_legacy_ragflow_connection_maps_to_provider(monkeypatch):
    monkeypatch.setenv("RAGFLOW_API_KEY", "legacy-key")
    provider = create_provider({"id": "ragflow-default", "provider": "ragflow", "base_url": "http://ragflow:9380"}, "legacy-key")
    assert provider.provider_name == "ragflow"
    assert provider.connection_id == "ragflow-default"
    assert provider.api_base == "http://ragflow:9380/api/v1"
