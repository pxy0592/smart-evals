from backend.tests.integration.test_report_persistence import seed


def test_report_list_detail_and_missing_conflict(secure_env):
    seed(secure_env)
    from app import create_app
    client=create_app().test_client()
    listing=client.get("/api/v1/evaluation/reports?rag_provider=intelliq&rag_connection_id=c").get_json()
    assert listing["total"] == 1
    assert listing["reports"][0]["warning"]["failed_samples"] == 1
    detail=client.get("/api/v1/evaluation/reports/t").get_json()
    assert detail["scoredSamples"] == 2 and detail["failedSamples"] == 1
    assert client.get("/api/v1/evaluation/reports/missing").status_code == 404
    assert client.get("/api/v1/evaluation/reports?assistant_id=a").get_json()["total"] == 1
    assert client.get("/api/v1/evaluation/reports?rag_provider=ragflow").get_json()["total"] == 0
