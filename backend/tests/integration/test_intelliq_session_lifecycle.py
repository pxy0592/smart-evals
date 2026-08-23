import json

import pytest

from services.rag_providers.intelliq import IntelliQProvider


class MockContent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class MockResponse:
    def __init__(self, status, payload=None, headers=None, chunks=None, text=""):
        self.status = status
        self._payload = payload
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = MockContent(chunks or [])
        self._text = text

    async def json(self, content_type=None):
        if self._payload is None:
            raise ValueError("non-json")
        return self._payload

    async def text(self):
        return self._text or json.dumps(self._payload or {})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class StatefulClient:
    def __init__(self):
        self.sessions = set()
        self.created = []
        self.chat_ids = []
        self.deleted_batches = []
        self.fail_cleanup = False
        self.fail_create = False

    def post(self, url, json=None, headers=None, allow_redirects=False):
        if url.endswith("/sessions"):
            if self.fail_create:
                return MockResponse(401, {"success": False, "error": {"code": 4010, "message": "bad key"}})
            session_id = f"session-{len(self.created) + 1}"
            self.sessions.add(session_id)
            self.created.append({"url": url, "json": json, "headers": headers, "id": session_id, "allow_redirects": allow_redirects})
            return MockResponse(201, {"success": True, "data": {"id": session_id}})
        session_id = url.rsplit("/", 1)[-1]
        self.chat_ids.append(session_id)
        if session_id not in self.sessions:
            return MockResponse(404, {"success": False, "error": {"code": 1003, "message": "Session not found"}})
        return MockResponse(
            200,
            headers={"Content-Type": "text/event-stream"},
            chunks=[
                b'data: {"response_type":"answer","content":"ok","done":false}\n\n',
                b'data: {"response_type":"answer","content":"","done":true}\n\n',
            ],
        )

    def delete(self, url, json=None, headers=None, allow_redirects=False):
        self.deleted_batches.append({"url": url, "ids": list(json["ids"]), "headers": headers, "allow_redirects": allow_redirects})
        if self.fail_cleanup:
            return MockResponse(200, {"success": False, "message": "cleanup rejected"})
        for session_id in json["ids"]:
            self.sessions.discard(session_id)
        return MockResponse(200, {"success": True, "message": "deleted"})


async def wire_client(provider, client):
    async def get_client():
        return client
    provider._client = get_client


@pytest.mark.asyncio
async def test_query_creates_real_session_then_chats_and_cleans_up():
    provider = IntelliQProvider(base_url="https://example.com/api/v1", api_key="secret", connection_id="c")
    client = StatefulClient()
    await wire_client(provider, client)
    created = []
    result = await provider.query_sample(
        question="q", assistant_id="agent", knowledge_base_ids=[], knowledge_base_selection_mode="none",
        on_session_created=created.append,
    )
    assert result.score_eligible
    assert result.session_id == "session-1"
    assert created == ["session-1"]
    assert client.chat_ids == ["session-1"]
    assert client.created[0]["headers"]["X-API-Key"] == "secret"
    assert client.created[0]["allow_redirects"] is False
    cleanup = await provider.cleanup_sessions()
    assert cleanup.succeeded
    assert cleanup.cleaned_ids == ["session-1"]
    assert client.deleted_batches[0]["ids"] == ["session-1"]


@pytest.mark.asyncio
async def test_creation_failure_does_not_chat():
    provider = IntelliQProvider(base_url="https://example.com/api/v1", api_key="secret", connection_id="c")
    client = StatefulClient(); client.fail_create = True
    await wire_client(provider, client)
    result = await provider.query_sample(question="q", assistant_id="agent", knowledge_base_ids=[], knowledge_base_selection_mode="none")
    assert not result.score_eligible
    assert result.session_creation_status == "failed"
    assert result.error.http_status == 401
    assert "bad key" in result.error.message
    assert client.chat_ids == []


@pytest.mark.asyncio
async def test_cleanup_business_failure_retains_session_for_compensation():
    provider = IntelliQProvider(base_url="https://example.com/api/v1", api_key="secret", connection_id="c")
    client = StatefulClient(); client.fail_cleanup = True
    await wire_client(provider, client)
    await provider.query_sample(question="q", assistant_id="agent", knowledge_base_ids=[], knowledge_base_selection_mode="none")
    cleanup = await provider.cleanup_sessions()
    assert cleanup.failed_ids == ["session-1"]
    assert provider._session_ids == ["session-1"]
