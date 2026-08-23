import pytest

from services.rag_providers.intelliq import IntelliQProvider


@pytest.mark.asyncio
async def test_intelliq_resource_normalization(monkeypatch):
    provider=IntelliQProvider(base_url="https://example.com/api/v1",api_key="secret",connection_id="c")
    async def fake(path, params=None):
        if path == "/knowledge-bases": return {"data":[{"id":"k","name":"KB","knowledge_count":2}]}
        return {"data":[{"id":"a","name":"Agent","config":{"kb_selection_mode":"selected","knowledge_bases":["k"]}}],"disabled_own_agent_ids":[]}
    monkeypatch.setattr(provider,"_get_json",fake)
    assert (await provider.list_knowledge_bases())[0].id == "k"
    agent=(await provider.list_assistants())[0]
    assert agent.knowledge_base_selection_mode == "selected"
    assert agent.allowed_knowledge_base_ids == ("k",)


@pytest.mark.asyncio
async def test_create_session_accepts_http_201(monkeypatch):
    provider=IntelliQProvider(base_url="https://example.com/api/v1",api_key="secret",connection_id="c")

    class Response:
        status = 201
        async def json(self, content_type=None):
            return {"success": True, "data": {"id": "session-1"}}
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class Client:
        def post(self, *args, **kwargs):
            return Response()

    async def client():
        return Client()

    monkeypatch.setattr(provider,"_client",client)
    result = await provider._create_session()
    assert result.created
    assert result.session_id == "session-1"


@pytest.mark.asyncio
async def test_create_session_requires_business_success(monkeypatch):
    provider = IntelliQProvider(base_url="https://example.com/api/v1", api_key="secret", connection_id="c")

    class Response:
        status = 200
        async def json(self, content_type=None):
            return {"success": False, "error": {"code": 1003, "message": "Session not found"}}
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, traceback): return False

    class Client:
        def post(self, *args, **kwargs):
            assert kwargs["allow_redirects"] is False
            return Response()

    async def client(): return Client()
    monkeypatch.setattr(provider, "_client", client)
    result = await provider._create_session()
    assert not result.created
    assert result.error.http_status == 200
    assert "Session not found" in result.error.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "configured_ids", "expected_ids"),
    [
        ("none", [], []),
        ("selected", ["kb-2"], ["kb-2"]),
        ("all", [], ["kb-1", "kb-2"]),
    ],
)
async def test_assistant_scoped_kbs_filter_tenant_accessible_list(
    monkeypatch, mode, configured_ids, expected_ids
):
    provider = IntelliQProvider(
        base_url="https://example.com/api/v1", api_key="secret", connection_id="c"
    )
    calls = []

    async def fake(path, params=None):
        calls.append((path, params))
        if path == "/agents/agent-1":
            return {
                "success": True,
                "data": {
                    "id": "agent-1",
                    "tenant_id": 10001,
                    "config": {
                        "kb_selection_mode": mode,
                        "knowledge_bases": configured_ids,
                    },
                },
            }
        if path == "/knowledge-bases":
            return {
                "success": True,
                "data": [
                    {"id": "kb-1", "name": "Tenant KB 1"},
                    {"id": "kb-2", "name": "Tenant KB 2"},
                ],
            }
        raise AssertionError(path)

    monkeypatch.setattr(provider, "_get_json", fake)

    resources = await provider.list_knowledge_bases(assistant_id="agent-1", limit=100)

    assert [resource.id for resource in resources] == expected_ids
    assert calls == [("/agents/agent-1", None), ("/knowledge-bases", None)]
