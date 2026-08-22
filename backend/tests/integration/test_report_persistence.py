from db import get_dataset_manager, get_report_manager, get_task_manager


def seed(secure_env, scored=2, failed=1):
    datasets=get_dataset_manager(); tasks=get_task_manager(); reports=get_report_manager()
    datasets.create_dataset({"id":"d","name":"D","file_type":"json","file_size":1,"storage_path":str(secure_env/"d.json"),"normalized_storage_path":str(secure_env/"d.json"),"normalization_status":"completed","status":"completed","num_samples":scored+failed})
    tasks.create_task({"id":"t","name":"T","chat_id":"a","assistant_id":"a","dataset_id":"d","metrics":["answer_relevancy"],"rag_provider":"intelliq","rag_connection_id":"c","knowledge_base_ids":[],"knowledge_base_selection_mode_snapshot":"none"})
    reports.save_report({"task_id":"t","chat_id":"a","assistant_id":"a","dataset_id":"d","overall_scores":{"answer_relevancy":{"mean":.8}},"detailed_scores":[],"evaluation_metadata":{},"rag_provider":"intelliq","rag_connection_id":"c","knowledge_base_ids":[],"source_snapshot":{"provider":"intelliq","connection_name":"I","assistant_id":"a","assistant_name":"A","knowledge_base_selection_mode":"none","knowledge_bases":[],"legacy":False},"scored_sample_count":scored,"failed_sample_count":failed,"total_sample_count":scored+failed,"success_rate":scored/(scored+failed),"warning":{"code":"partial_sample_failure","message":"failed","failed_samples":failed} if failed else None})
    return reports


def test_report_counts_and_snapshot(secure_env):
    report=seed(secure_env).get_report("t")
    assert report["scored_sample_count"] == 2
    assert report["failed_sample_count"] == 1
    assert report["source_snapshot"]["knowledge_base_selection_mode"] == "none"
