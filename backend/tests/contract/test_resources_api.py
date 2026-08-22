from services.rag_providers.base import AssistantRef, KnowledgeBaseRef


class FakeProvider:
    async def list_knowledge_bases(self, **kwargs):
        return [KnowledgeBaseRef(id="kb1",provider="intelliq",connection_id="c1",name="KB")]
    async def list_assistants(self, **kwargs):
        return [AssistantRef(id="a1",provider="intelliq",connection_id="c1",name="Agent",knowledge_base_selection_mode="selected")]
    async def close(self): pass


def test_resource_endpoints_return_normalized_items(secure_env, monkeypatch):
    import evaluation_db
    from app import create_app
    monkeypatch.setattr(evaluation_db,"_connection_provider",lambda _: ({"provider":"intelliq"},FakeProvider()))
    client=create_app().test_client()
    kb=client.get("/api/v1/evaluation/rag-connections/c1/knowledge-bases").get_json()
    agents=client.get("/api/v1/evaluation/rag-connections/c1/assistants").get_json()
    assert kb["items"][0]["connection_id"] == "c1"
    assert agents["items"][0]["knowledge_base_selection_mode"] == "selected"
