from __future__ import annotations

import asyncio
import io
import json
import threading

from services.rag_providers.base import AssistantRef, KnowledgeBaseRef


class LoopScopedProvider:
    def __init__(self):
        self.loop = None
        self.closed = False

    def _claim_loop(self):
        current = asyncio.get_running_loop()
        if self.loop is None:
            self.loop = current
        elif self.loop is not current:
            raise RuntimeError("Event loop is closed")

    async def list_assistants(self, **_kwargs):
        self._claim_loop()
        return [
            AssistantRef(
                id="agent",
                provider="intelliq",
                connection_id="connection",
                name="Agent",
                knowledge_base_selection_mode="selected",
            )
        ]

    async def list_knowledge_bases(self, **_kwargs):
        self._claim_loop()
        return [
            KnowledgeBaseRef(
                id="kb",
                provider="intelliq",
                connection_id="connection",
                name="Knowledge Base",
            )
        ]

    async def close(self):
        assert asyncio.get_running_loop() is self.loop
        self.closed = True


class NoStartThread:
    def __init__(self, *_args, **_kwargs):
        pass

    def start(self):
        pass


def test_ten_sequential_intelliq_task_creations_use_fresh_provider_scopes(
    secure_env, monkeypatch
):
    import evaluation_db
    from app import create_app
    from db import get_task_manager

    monkeypatch.setattr(
        evaluation_db.RagConnectionService,
        "get_connection",
        lambda self, *_args, **_kwargs: {
            "id": "connection",
            "provider": "intelliq",
            "name": "IntelliQ",
            "base_url": "http://localhost:9000",
            "api_key": "secret",
            "enabled": True,
            "revision": 1,
        },
    )
    monkeypatch.setattr(
        evaluation_db, "create_provider", lambda *_args, **_kwargs: LoopScopedProvider()
    )
    monkeypatch.setattr(threading, "Thread", NoStartThread)

    client = create_app().test_client()
    upload = client.post(
        "/api/v1/evaluation/datasets",
        data={
            "file": (
                io.BytesIO(json.dumps([{"question": "q"}]).encode()),
                "dataset.json",
            )
        },
        content_type="multipart/form-data",
    )
    dataset_id = upload.get_json()["id"]
    payload = {
        "dataset_id": dataset_id,
        "metrics": ["answer_relevancy"],
        "rag_target": {
            "provider": "intelliq",
            "connection_id": "connection",
            "assistant_id": "agent",
            "knowledge_base_ids": ["kb"],
        },
    }

    responses = [
        client.post("/api/v1/evaluation/tasks", json=payload) for _ in range(10)
    ]

    assert all(response.status_code == 201 for response in responses)
    assert get_task_manager().get_tasks(limit=20)["total"] == 10
