def test_unauthorized_connection_create_does_not_persist(secure_env):
    import evaluation_db
    evaluation_db.config_manager = evaluation_db.dataset_manager = evaluation_db.task_manager = evaluation_db.report_manager = evaluation_db.metrics_manager = evaluation_db.evaluation_service = None
    from app import create_app
    client=create_app().test_client()
    response=client.post("/api/v1/evaluation/rag-connections",json={"provider":"intelliq","name":"I","api_url":"http://localhost:9000","api_key":"secret"})
    assert response.status_code == 401
    assert all(item["provider"] != "intelliq" for item in client.get("/api/v1/evaluation/rag-connections").get_json()["connections"])
