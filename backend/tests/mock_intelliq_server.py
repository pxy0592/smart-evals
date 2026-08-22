"""Local IntelliQ-compatible server for manual/Playwright validation."""
from aiohttp import web

async def knowledge_bases(request):
    return web.json_response({"success": True, "data": [{"id": "kb-demo", "name": "Demo KB", "description": "Mock knowledge base"}]})

async def agents(request):
    return web.json_response({"success": True, "data": [{"id": "agent-demo", "name": "Demo Agent", "description": "Mock agent", "config": {"kb_selection_mode": "selected", "knowledge_bases": ["kb-demo"]}}], "disabled_own_agent_ids": []})

async def chat(request):
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

app = web.Application()
app.router.add_get('/api/v1/knowledge-bases', knowledge_bases)
app.router.add_get('/api/v1/agents', agents)
app.router.add_post('/api/v1/agent-chat/{session_id}', chat)
web.run_app(app, host='127.0.0.1', port=19000)
