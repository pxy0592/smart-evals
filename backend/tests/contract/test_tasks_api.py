import io
import json
import asyncio
import threading

import pytest

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

    async def list_assistants(self, **kwargs):
        self._ensure_active_loop()
        return [
            AssistantRef(id="selected-agent",provider="intelliq",connection_id="c",name="Selected",knowledge_base_selection_mode="selected"),
            AssistantRef(id="all-agent",provider="intelliq",connection_id="c",name="All",knowledge_base_selection_mode="all"),
        ]
    async def list_knowledge_bases(self, **kwargs):
        self._ensure_active_loop()
        return [KnowledgeBaseRef(id="kb1",provider="intelliq",connection_id="c",name="KB1")]
    async def close(self):
        assert asyncio.get_running_loop() is self.loop
        self.closed = True


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

def test_selected_intelliq_task_creation_is_repeatable(secure_env, monkeypatch):
    client, dataset_id = client_with_dataset(secure_env, monkeypatch)
    payload = {
        "dataset_id": dataset_id,
        "metrics": ["answer_relevancy"],
        "rag_target": {
            "provider": "intelliq",
            "connection_id": "c",
            "assistant_id": "selected-agent",
            "knowledge_base_ids": ["kb1"],
        },
    }

    task_ids = []
    for _ in range(10):
        response = client.post("/api/v1/evaluation/tasks", json=payload)
        assert response.status_code == 201
        task_ids.append(response.get_json()["id"])

    from db import get_task_manager

    assert len(set(task_ids)) == 10
    assert get_task_manager().get_tasks(limit=20)["total"] == 10


class FailingProvider(FakeProvider):
    def __init__(self, message):
        super().__init__()
        self.message = message

    async def list_assistants(self, **kwargs):
        self._ensure_active_loop()
        raise RuntimeError(self.message)


@pytest.mark.parametrize(
    ("upstream_message", "expected_status", "expected_category"),
    [
        ("permission:HTTP 403", 403, "permission"),
        ("timeout:socket read timed out", 502, "upstream"),
        ("Event loop is closed", 500, "internal"),
    ],
)
def test_task_creation_returns_safe_error_without_persisting_task(
    secure_env, monkeypatch, upstream_message, expected_status, expected_category
):
    import evaluation_db
    from app import create_app
    from db import get_task_manager

    monkeypatch.setattr(
        evaluation_db.RagConnectionService,
        "get_connection",
        lambda self, *a, **k: {
            "id": "c",
            "provider": "intelliq",
            "name": "I",
            "base_url": "http://localhost:9000",
            "api_key": "secret",
            "enabled": True,
            "revision": 1,
        },
    )
    monkeypatch.setattr(
        evaluation_db,
        "create_provider",
        lambda *a, **k: FailingProvider(upstream_message),
    )
    monkeypatch.setattr(threading, "Thread", NoStartThread)
    client = create_app().test_client()
    upload = client.post(
        "/api/v1/evaluation/datasets",
        data={"file": (io.BytesIO(json.dumps([{"question": "q"}]).encode()), "d.json")},
        content_type="multipart/form-data",
    )
    dataset_id = upload.get_json()["id"]

    response = client.post(
        "/api/v1/evaluation/tasks",
        json={
            "dataset_id": dataset_id,
            "metrics": ["answer_relevancy"],
            "rag_target": {
                "provider": "intelliq",
                "connection_id": "c",
                "assistant_id": "selected-agent",
                "knowledge_base_ids": ["kb1"],
            },
        },
    )

    assert response.status_code == expected_status
    error = response.get_json()["error"]
    assert error["category"] == expected_category
    assert "Event loop" not in error["message"]
    assert "Traceback" not in error["message"]
    assert get_task_manager().get_tasks(limit=20)["total"] == 0
