from services.rag_providers.base import AssistantRef, RagQueryResult


def test_assistant_mode_and_result_serialization():
    assistant = AssistantRef(id="a", provider="intelliq", connection_id="c", name="Agent", knowledge_base_selection_mode="none")
    assert assistant.to_dict()["knowledge_base_selection_mode"] == "none"
    result = RagQueryResult(provider="intelliq", session_id="s", completed=True, score_eligible=True, answer="ok")
    assert result.to_dict()["error"] is None
