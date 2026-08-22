import io
import json
import threading

from services.rag_providers.base import AssistantRef, KnowledgeBaseRef


class FakeProvider:
    async def list_assistants(self, **kwargs):
        return [
            AssistantRef(id="selected-agent",provider="intelliq",connection_id="c",name="Selected",knowledge_base_selection_mode="selected"),
            AssistantRef(id="all-agent",provider="intelliq",connection_id="c",name="All",knowledge_base_selection_mode="all"),
        ]
    async def list_knowledge_bases(self, **kwargs):
        return [KnowledgeBaseRef(id="kb1",provider="intelliq",connection_id="c",name="KB1")]
    async def close(self): pass


class NoStartThread:
    def __init__(self,*args,**kwargs): pass
    def start(self): pass


def client_with_dataset(secure_env, monkeypatch):
    import evaluation_db
    import db
    from app import create_app
    monkeypatch.setattr(evaluation_db.RagConnectionService,"get_connection",lambda self,*a,**k:{"id":"c","provider":"intelliq","name":"I","base_url":"http://localhost:9000","api_key":"secret","enabled":True,"revision":1})
    monkeypatch.setattr(evaluation_db,"create_provider",lambda *a,**k:FakeProvider())
    monkeypatch.setattr(threading,"Thread",NoStartThread)
    client=create_app().test_client()
    upload=client.post("/api/v1/evaluation/datasets",data={"name":"D","file":(io.BytesIO(json.dumps([{"question":"q"}]).encode()),"d.json")},content_type="multipart/form-data")
    assert upload.status_code == 201
    return client, upload.get_json()["id"]


def test_selected_all_mode_validation(secure_env, monkeypatch):
    client,dataset_id=client_with_dataset(secure_env,monkeypatch)
    common={"dataset_id":dataset_id,"metrics":["answer_relevancy"]}
    selected={**common,"rag_target":{"provider":"intelliq","connection_id":"c","assistant_id":"selected-agent","knowledge_base_ids":[]}}
    assert client.post("/api/v1/evaluation/tasks",json=selected).status_code == 400
    all_invalid={**common,"rag_target":{"provider":"intelliq","connection_id":"c","assistant_id":"all-agent","knowledge_base_ids":["kb1"]}}
    assert client.post("/api/v1/evaluation/tasks",json=all_invalid).status_code == 400
    selected["rag_target"]["knowledge_base_ids"]=["kb1"]
    assert client.post("/api/v1/evaluation/tasks",json=selected).status_code == 201


def test_legacy_chat_id_still_accepted(secure_env, monkeypatch):
    client,dataset_id=client_with_dataset(secure_env,monkeypatch)
    response=client.post("/api/v1/evaluation/tasks",json={"dataset_id":dataset_id,"metrics":["answer_relevancy"],"chat_id":"legacy"})
    assert response.status_code == 201
    assert response.get_json()["rag_provider"] == "ragflow"
