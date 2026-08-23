from __future__ import annotations


def make_client(secure_env):
    import evaluation_db

    evaluation_db.config_manager = None
    evaluation_db.dataset_manager = None
    evaluation_db.task_manager = None
    evaluation_db.report_manager = None
    evaluation_db.metrics_manager = None
    evaluation_db.evaluation_service = None
    evaluation_db._stale_tasks_recovered = False
    evaluation_db._session_cleanup_recovered = False

    from app import create_app

    return create_app().test_client()


def test_config_accepts_single_tag_values_and_stores_scalars(secure_env):
    client = make_client(secure_env)
    response = client.put(
        "/api/v1/evaluation/config",
        json={
            "api_config": {
                "provider": "custom",
                "apiKey": "test-key",
                "endpoint": "http://example.test/v1",
                "model": ["gpt-test"],
                "embeddingModel": ["BAAI/bge-m3"],
                "temperature": 0.2,
                "maxTokens": 1024,
            }
        },
    )
    assert response.status_code == 200

    from db import get_config_manager

    config = get_config_manager().get_default_api_config()
    assert config["model"] == "gpt-test"
    assert config["embeddingModel"] == "BAAI/bge-m3"


def test_config_rejects_multiple_tag_values_before_sqlite(secure_env):
    client = make_client(secure_env)
    response = client.put(
        "/api/v1/evaluation/config",
        json={
            "api_config": {
                "provider": "custom",
                "model": ["one", "two"],
                "embeddingModel": ["BAAI/bge-m3"],
            }
        },
    )
    assert response.status_code == 400
    assert "at most one value" in response.get_json()["error"]


def test_config_masks_stored_api_key_but_reports_it_is_configured(secure_env):
    client = make_client(secure_env)
    client.put(
        "/api/v1/evaluation/config",
        json={
            "api_config": {
                "provider": "custom",
                "apiKey": "persisted-secret",
                "model": "gpt-test",
                "embeddingModel": "BAAI/bge-m3",
                "maxTokens": 4096,
            }
        },
    )

    response = client.get("/api/v1/evaluation/config")
    assert response.status_code == 200
    api = response.get_json()["api"]
    assert api["apiKey"]
    assert "*" in api["apiKey"]
    assert "persisted-secret" not in api["apiKey"]
    assert api["apiKeyConfigured"] is True
    assert api["embeddingModel"] == "BAAI/bge-m3"
    assert api["maxTokens"] == 4096


def test_connection_test_uses_stored_key_when_request_key_is_omitted(
    secure_env, monkeypatch
):
    client = make_client(secure_env)
    client.put(
        "/api/v1/evaluation/config",
        json={
            "api_config": {
                "provider": "custom",
                "apiKey": "persisted-secret",
                "model": "gpt-test",
            }
        },
    )

    import langchain_openai

    calls = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def invoke(self, _prompt):
            class Response:
                content = "ok"

            return Response()

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
    response = client.post(
        "/api/v1/evaluation/test-connection",
        json={
            "provider": "untrusted-provider",
            "apiKey": "untrusted-key",
            "endpoint": "http://untrusted.test/v1",
            "model": "untrusted-model",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["details"]["usingStoredApiKey"] is True
    assert response.get_json()["details"]["usingStoredConfig"] is True
    assert calls[0]["api_key"] == "persisted-secret"
    assert calls[0]["model"] == "gpt-test"
