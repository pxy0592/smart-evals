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
