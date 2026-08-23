"""Stateful local IntelliQ-compatible server for manual and lifecycle validation."""
from __future__ import annotations

import itertools
from aiohttp import web

ACTIVE_SESSIONS: set[str] = set()
CREATED_SESSIONS: list[dict] = []
DELETED_BATCHES: list[list[str]] = []
REQUEST_AUDIT: list[dict] = []
_COUNTER = itertools.count(1)


async def knowledge_bases(request):
    return web.json_response({"success": True, "data": [{"id": "kb-demo", "name": "Demo KB", "description": "Mock knowledge base"}]})


async def agents(request):
    return web.json_response({"success": True, "data": [{"id": "agent-demo", "name": "Demo Agent", "description": "Mock agent", "config": {"kb_selection_mode": "selected", "knowledge_bases": ["kb-demo"]}}], "disabled_own_agent_ids": []})


async def create_session(request):
    payload = await request.json()
    session_id = f"mock-session-{next(_COUNTER)}"
    ACTIVE_SESSIONS.add(session_id)
    CREATED_SESSIONS.append({"id": session_id, "payload": payload})
    REQUEST_AUDIT.append({"method": "POST", "path": "/sessions", "session_id": session_id})
    return web.json_response({"success": True, "data": {"id": session_id, **payload}}, status=201)


async def chat(request):
    session_id = request.match_info["session_id"]
    REQUEST_AUDIT.append({"method": "POST", "path": "/agent-chat", "session_id": session_id})
    if session_id not in ACTIVE_SESSIONS:
        return web.json_response({"success": False, "error": {"code": 1003, "message": "Session not found"}}, status=404)
    response = web.StreamResponse(status=200, headers={"Content-Type": "text/event-stream"})
    await response.prepare(request)
    for event in [
        'data: {"response_type":"references","knowledge_references":[{"id":"ref-1","content":"mock context","knowledge_base_id":"kb-demo"}],"done":false}\n\n',
        'data: {"response_type":"answer","content":"mock answer","done":false}\n\n',
        'data: {"response_type":"answer","content":"","done":true}\n\n',
    ]:
        await response.write(event.encode())
    await response.write_eof()
    return response


async def delete_sessions(request):
    payload = await request.json()
    ids = list(dict.fromkeys(payload.get("ids") or []))
    DELETED_BATCHES.append(ids)
    REQUEST_AUDIT.append({"method": "DELETE", "path": "/sessions/batch", "ids": ids})
    for session_id in ids:
        ACTIVE_SESSIONS.discard(session_id)
    return web.json_response({"success": True, "message": "Sessions deleted successfully"})


app = web.Application()
app.router.add_get('/api/v1/knowledge-bases', knowledge_bases)
app.router.add_get('/api/v1/agents', agents)
app.router.add_post('/api/v1/sessions', create_session)
app.router.add_post('/api/v1/agent-chat/{session_id}', chat)
app.router.add_delete('/api/v1/sessions/batch', delete_sessions)

if __name__ == "__main__":
    web.run_app(app, host='127.0.0.1', port=19000)
