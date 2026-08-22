"""Incremental Server-Sent Events parser for IntelliQ responses."""
from __future__ import annotations

import codecs
import json
from typing import Any, AsyncIterable

from .base import ProviderError, RagQueryResult


class SSEProtocolError(ValueError):
    pass


async def iter_sse_events(chunks: AsyncIterable[bytes]):
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    event_name = "message"
    data_lines: list[str] = []

    async def emit():
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return None
        payload = "\n".join(data_lines)
        current = (event_name, payload)
        event_name = "message"
        data_lines = []
        return current

    async for chunk in chunks:
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if not line:
                current = await emit()
                if current:
                    yield current
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event_name = value or "message"
            elif field == "data":
                data_lines.append(value)
    buffer += decoder.decode(b"", final=True)
    if buffer:
        line = buffer.rstrip("\r")
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    current = await emit()
    if current:
        yield current


async def aggregate_intelliq_sse(chunks: AsyncIterable[bytes], session_id: str) -> RagQueryResult:
    answer_parts: list[str] = []
    references: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    event_counts: dict[str, int] = {}
    completed = False

    try:
        async for _, raw in iter_sse_events(chunks):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SSEProtocolError("IntelliQ SSE 包含无效 JSON") from exc
            response_type = str(payload.get("response_type") or "unknown")
            event_counts[response_type] = event_counts.get(response_type, 0) + 1
            if response_type == "answer" and payload.get("content"):
                answer_parts.append(str(payload["content"]))
            elif response_type == "references":
                for ref in payload.get("knowledge_references") or payload.get("references") or []:
                    key = str(ref.get("id") or ref.get("knowledge_id") or ref.get("content") or len(references))
                    if key not in seen_refs:
                        seen_refs.add(key)
                        references.append(ref)
            elif response_type == "error":
                message = str(payload.get("content") or payload.get("message") or "IntelliQ 返回错误")
                return RagQueryResult(
                    provider="intelliq",
                    session_id=session_id,
                    partial_answer="".join(answer_parts),
                    references=references,
                    contexts=[str(r.get("content", "")) for r in references if r.get("content")],
                    intermediate_event_summary=event_counts,
                    error=ProviderError("upstream", message, False),
                )
            if payload.get("done") is True:
                completed = True
                break
    except Exception as exc:
        if isinstance(exc, SSEProtocolError):
            category = "protocol"
        else:
            category = "upstream"
        return RagQueryResult(
            provider="intelliq",
            session_id=session_id,
            partial_answer="".join(answer_parts),
            references=references,
            contexts=[str(r.get("content", "")) for r in references if r.get("content")],
            intermediate_event_summary=event_counts,
            error=ProviderError(category, str(exc), False),
        )

    answer = "".join(answer_parts)
    contexts = [str(r.get("content", "")) for r in references if r.get("content")]
    if completed and answer:
        return RagQueryResult(
            provider="intelliq",
            session_id=session_id,
            completed=True,
            score_eligible=True,
            answer=answer,
            contexts=contexts,
            references=references,
            intermediate_event_summary=event_counts,
        )
    return RagQueryResult(
        provider="intelliq",
        session_id=session_id,
        partial_answer=answer,
        contexts=contexts,
        references=references,
        intermediate_event_summary=event_counts,
        error=ProviderError("protocol", "流在明确完成前结束或最终答案为空", False),
    )
