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


def _tool_error_diagnostic(payload: dict[str, Any], message: str) -> dict[str, Any] | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    tool_call_id = str(data.get("tool_call_id") or "").strip()
    tool_name = str(data.get("tool_name") or "").strip()
    if payload.get("done") is True or not (tool_call_id or tool_name):
        return None
    return {
        "tool_call_id": tool_call_id or None,
        "tool_name": tool_name or None,
        "message": message[:500],
        "recovered": False,
        "event_count": 1,
    }


def _tool_error_key(diagnostic: dict[str, Any]) -> tuple[str, str]:
    return (
        str(diagnostic.get("tool_call_id") or diagnostic.get("tool_name") or ""),
        str(diagnostic.get("message") or ""),
    )


async def aggregate_intelliq_sse(chunks: AsyncIterable[bytes], session_id: str) -> RagQueryResult:
    answer_parts: list[str] = []
    references: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    event_counts: dict[str, int] = {}
    tool_errors: list[dict[str, Any]] = []
    tool_error_indexes: dict[tuple[str, str], int] = {}
    completed = False

    def contexts() -> list[str]:
        return [str(ref.get("content", "")) for ref in references if ref.get("content")]

    def result_error(category: str, message: str) -> RagQueryResult:
        return RagQueryResult(
            provider="intelliq",
            session_id=session_id,
            partial_answer="".join(answer_parts),
            references=references,
            contexts=contexts(),
            intermediate_event_summary=event_counts,
            tool_errors=tool_errors,
            error=ProviderError(category, message, False),
        )

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
                diagnostic = _tool_error_diagnostic(payload, message)
                if diagnostic is not None:
                    key = _tool_error_key(diagnostic)
                    existing_index = tool_error_indexes.get(key)
                    if existing_index is None:
                        tool_error_indexes[key] = len(tool_errors)
                        tool_errors.append(diagnostic)
                    else:
                        tool_errors[existing_index]["event_count"] += 1
                    continue
                return result_error("upstream", message)
            if (response_type == "answer" and payload.get("done") is True) or (
                response_type == "complete" and payload.get("done") is True
            ):
                completed = True
                break
    except Exception as exc:
        category = "protocol" if isinstance(exc, SSEProtocolError) else "upstream"
        return result_error(category, str(exc))

    answer = "".join(answer_parts)
    if completed and answer:
        for diagnostic in tool_errors:
            diagnostic["recovered"] = True
        return RagQueryResult(
            provider="intelliq",
            session_id=session_id,
            completed=True,
            score_eligible=True,
            answer=answer,
            contexts=contexts(),
            references=references,
            intermediate_event_summary=event_counts,
            tool_errors=tool_errors,
        )
    return result_error("protocol", "流在明确完成前结束或最终答案为空")
