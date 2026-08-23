import asyncio

from services.rag_providers.base import AssistantRef, KnowledgeBaseRef


class FakeProvider:
    def __init__(self):
        self.loop = None
        self.closed = False

    def _ensure_active_loop(self):
        current = asyncio.get_running_loop()
        if self.loop is None:
            self.loop = current
        elif self.loop is not current:
            raise RuntimeError("Event loop is closed")

    async def list_knowledge_bases(self, **kwargs):
        self._ensure_active_loop()
        return [KnowledgeBaseRef(id="kb1",provider="intelliq",connection_id="c1",name="KB")]
    async def list_assistants(self, **kwargs):
        self._ensure_active_loop()
        return [AssistantRef(id="a1",provider="intelliq",connection_id="c1",name="Agent",knowledge_base_selection_mode="selected")]
    async def close(self):
        assert asyncio.get_running_loop() is self.loop
        self.closed = True


def test_resource_endpoints_return_normalized_items(secure_env, monkeypatch):
    import evaluation_db
    from app import create_app
    providers=[]
    def connection_provider(_):
        provider=FakeProvider(); providers.append(provider)
        return {"provider":"intelliq"},provider
    monkeypatch.setattr(evaluation_db,"_connection_provider",connection_provider)
    client=create_app().test_client()
    kb=client.get("/api/v1/evaluation/rag-connections/c1/knowledge-bases").get_json()
    agents=client.get("/api/v1/evaluation/rag-connections/c1/assistants").get_json()
    repeat_kb=client.get("/api/v1/evaluation/rag-connections/c1/knowledge-bases").get_json()
    assert kb["items"][0]["connection_id"] == "c1"
    assert agents["items"][0]["knowledge_base_selection_mode"] == "selected"
    assert repeat_kb["items"][0]["id"] == "kb1"
    assert len(providers)==3 and all(provider.closed for provider in providers)
