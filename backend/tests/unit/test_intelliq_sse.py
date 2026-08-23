import pytest

from services.rag_providers.sse import aggregate_intelliq_sse


async def chunks(*values):
    for value in values:
        yield value


@pytest.mark.asyncio
async def test_aggregates_answer_and_references_only():
    stream = chunks(
        b'data: {"response_type":"agent_query","content":"","done":true}\n\n',
        b'data: {"response_type":"references","knowledge_references":[{"id":"r1","content":"ctx"}],"done":false}\n\n',
        b'data: {"response_type":"answer","content":"hello ","done":false}\n\n',
        b'data: {"response_type":"thinking","content":"secret thought","done":false}\n\n',
        b'data: {"response_type":"answer","content":"world","done":false}\n\n',
        b'data: {"response_type":"answer","content":"","done":true}\n\n',
    )
    result = await aggregate_intelliq_sse(stream, "s1")
    assert result.completed and result.score_eligible
    assert result.answer == "hello world"
    assert result.contexts == ["ctx"]
    assert "secret thought" not in result.answer


@pytest.mark.asyncio
async def test_split_utf8_and_missing_done_fail():
    raw = 'data: {"response_type":"answer","content":"你好","done":false}\n\n'.encode()
    result = await aggregate_intelliq_sse(chunks(raw[:30], raw[30:]), "s2")
    assert not result.completed
    assert not result.score_eligible
    assert result.answer == ""
    assert result.partial_answer == "你好"
    assert result.error.category == "protocol"


@pytest.mark.asyncio
async def test_error_event_fails():
    result = await aggregate_intelliq_sse(chunks(b'data: {"response_type":"error","content":"bad","done":false}\n\n'), "s3")
    assert result.error.category == "upstream"


@pytest.mark.asyncio
async def test_recoverable_tool_errors_continue_to_final_answer():
    stream = chunks(
        b'data: {"response_type":"error","content":"bad arguments","done":false,"data":{"tool_call_id":"call-1","tool_name":"list_knowledge_chunks"}}\n\n',
        b'data: {"response_type":"error","content":"bad arguments","done":false,"data":{"tool_call_id":"call-1","tool_name":"list_knowledge_chunks"}}\n\n',
        b'data: {"response_type":"error","content":"knowledge not found","done":false,"data":{"tool_call_id":"call-2","tool_name":"list_knowledge_chunks"}}\n\n',
        'data: {"response_type":"answer","content":"最终答案","done":false}\n\n'.encode(),
        b'data: {"response_type":"complete","content":"","done":true}\n\n',
    )

    result = await aggregate_intelliq_sse(stream, "s4")

    assert result.completed and result.score_eligible
    assert result.answer == "最终答案"
    assert result.error is None
    assert len(result.tool_errors) == 2
    assert all(item["recovered"] for item in result.tool_errors)
    assert result.tool_errors[0]["event_count"] == 2
    assert "arguments" not in result.tool_errors[0]


@pytest.mark.asyncio
async def test_terminal_tool_error_and_empty_complete_still_fail():
    terminal = await aggregate_intelliq_sse(
        chunks(
            b'data: {"response_type":"error","content":"terminal","done":true,"data":{"tool_call_id":"call-1","tool_name":"tool"}}\n\n'
        ),
        "s5",
    )
    empty = await aggregate_intelliq_sse(
        chunks(
            b'data: {"response_type":"error","content":"recoverable","done":false,"data":{"tool_call_id":"call-1","tool_name":"tool"}}\n\n',
            b'data: {"response_type":"complete","content":"","done":true}\n\n',
        ),
        "s6",
    )

    assert not terminal.completed and terminal.error.category == "upstream"
    assert not empty.completed and empty.error.category == "protocol"
    assert empty.tool_errors[0]["recovered"] is False
