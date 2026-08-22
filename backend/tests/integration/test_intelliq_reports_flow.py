from db import get_dataset_manager, get_task_manager


def test_failed_task_has_no_final_report(secure_env):
    datasets=get_dataset_manager(); tasks=get_task_manager()
    datasets.create_dataset({"id":"d2","name":"D","file_type":"json","file_size":1,"storage_path":"x","normalized_storage_path":"x","normalization_status":"completed","status":"completed"})
    tasks.create_task({"id":"failed","chat_id":"a","dataset_id":"d2","metrics":["answer_relevancy"],"rag_provider":"intelliq"})
    tasks.update_task_status("failed","failed",outcome="failed")
    from app import create_app
    assert create_app().test_client().get("/api/v1/evaluation/reports/failed").status_code == 409


def test_report_snapshot_does_not_require_live_connection(secure_env):
    from backend.tests.integration.test_report_persistence import seed
    report = seed(secure_env).get_report("t")
    assert report["source_snapshot"]["connection_name"] == "I"
    assert report["source_snapshot"]["assistant_name"] == "A"
