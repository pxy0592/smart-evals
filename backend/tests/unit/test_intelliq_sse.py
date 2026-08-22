import pytest

from services.rag_providers.sse import aggregate_intelliq_sse


async def chunks(*values):
    for value in values:
        yield value


@pytest.mark.asyncio
async def test_aggregates_answer_and_references_only():
    stream = chunks(
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
