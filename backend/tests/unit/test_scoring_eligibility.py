from services.rag_providers.base import ProviderError, RagQueryResult


def test_incomplete_result_is_not_score_eligible():
    result=RagQueryResult(provider="intelliq",session_id="s",partial_answer="partial",error=ProviderError("timeout","timeout",True))
    assert not result.completed and not result.score_eligible and result.answer == ""

import pytest


@pytest.mark.asyncio
async def test_evaluation_service_generates_unique_sample_sessions(monkeypatch):
    import services.evaluation_service as module
    from services.evaluation_service import EvaluationService
    from services.rag_providers.base import RagQueryResult

    class Sample:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class Dataset:
        def __init__(self, samples): self.samples = samples
    class Config:
        def __init__(self, **kwargs): pass
    class Result:
        scores = [{"metric": .8}, {"metric": .9}]
    class Provider:
        def __init__(self): self.sessions=[]
        async def query_sample(self, **kwargs):
            self.sessions.append(kwargs["session_id"])
            return RagQueryResult(provider="intelliq",session_id=kwargs["session_id"],completed=True,score_eligible=True,answer="a")

    monkeypatch.setattr(module, "SingleTurnSample", Sample)
    monkeypatch.setattr(module, "EvaluationDataset", Dataset)
    monkeypatch.setattr(module, "RunConfig", Config)
    monkeypatch.setattr(module, "evaluate", lambda **kwargs: Result())
    service=EvaluationService(api_config={})
    service.metrics_map={"metric": object()}
    monkeypatch.setattr(service,"_get_llm",lambda:None)
    monkeypatch.setattr(service,"_get_embeddings",lambda:None)
    provider=Provider()
    result=await service.evaluate_with_provider(provider=provider,assistant_id="a",knowledge_base_ids=[],knowledge_base_selection_mode="none",dataset_id="d",selected_metrics=["metric"],dataset_samples=[{"question":"q1"},{"question":"q2"}])
    assert len(provider.sessions) == 2 and len(set(provider.sessions)) == 2
    assert result["evaluation_metadata"]["success_count"] == 2
