import json
from pathlib import Path

from db import get_dataset_manager, get_report_manager, get_task_manager
from services.rag_providers.base import RagQueryResult


class FakeProvider:
    async def close(self): pass


def seed_task(secure_env):
    normalized=secure_env/"dataset.json"; normalized.write_text(json.dumps([{"question":"q1"},{"question":"q2"}]))
    get_dataset_manager().create_dataset({"id":"d","name":"D","file_type":"json","file_size":10,"storage_path":str(normalized),"normalized_storage_path":str(normalized),"normalization_status":"completed","status":"completed","num_samples":2})
    get_task_manager().create_task({"id":"t","name":"T","chat_id":"a","assistant_id":"a","dataset_id":"d","metrics":["answer_relevancy"],"rag_provider":"intelliq","rag_connection_id":"c","rag_connection_revision":1,"knowledge_base_ids":[],"knowledge_base_selection_mode_snapshot":"none","connection_name_snapshot":"I","connection_base_url_snapshot":"http://localhost:9000"})


def test_partial_success_task_generates_warning_report(secure_env, monkeypatch):
    seed_task(secure_env)
    import evaluation_db
    import services.evaluation_service as scoring
    monkeypatch.setattr(evaluation_db.RagConnectionService,"get_connection",lambda self,*a,**k:{"id":"c","provider":"intelliq","name":"I","base_url":"http://localhost:9000","api_key":"secret","enabled":True,"revision":1})
    monkeypatch.setattr(evaluation_db,"create_provider",lambda *a,**k:FakeProvider())
    async def fake_evaluate(**kwargs):
        kwargs["sample_started"](0,"s1",{"question":"q1"}); kwargs["sample_started"](1,"s2",{"question":"q2"})
        return {"overall_scores":{"answer_relevancy":{"mean":.8}},"detailed_scores":[{"sample_index":0,"user_input":"q1","actual_answer":"a","contexts":[],"references":[],"completion_status":"completed","score_eligible":True}],"evaluation_metadata":{"success_count":1,"failed_count":1,"total_count":2}}
    monkeypatch.setattr(scoring.evaluation_service,"evaluate_with_provider",fake_evaluate)
    evaluation_db.init_services()
    evaluation_db.run_evaluation_task("t")
    task=get_task_manager().get_task("t")
    assert task["status"] == "completed" and task["outcome"] == "partially_succeeded" and task["has_warnings"]
    report=get_report_manager().get_report("t")
    assert report["scored_sample_count"] == 1 and report["failed_sample_count"] == 1


def test_all_failed_task_has_no_report(secure_env, monkeypatch):
    seed_task(secure_env)
    import evaluation_db
    import services.evaluation_service as scoring
    monkeypatch.setattr(evaluation_db.RagConnectionService,"get_connection",lambda self,*a,**k:{"id":"c","provider":"intelliq","name":"I","base_url":"http://localhost:9000","api_key":"secret","enabled":True,"revision":1})
    monkeypatch.setattr(evaluation_db,"create_provider",lambda *a,**k:FakeProvider())
    async def fail(**kwargs): raise RuntimeError("没有任何样本获得完整可评分回答")
    monkeypatch.setattr(scoring.evaluation_service,"evaluate_with_provider",fail)
    evaluation_db.init_services(); evaluation_db.run_evaluation_task("t")
    assert get_task_manager().get_task("t")["status"] == "failed"
    assert get_report_manager().get_report("t") is None
