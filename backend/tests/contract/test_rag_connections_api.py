from __future__ import annotations


def make_client(secure_env):
    import evaluation_db
    evaluation_db.config_manager = evaluation_db.dataset_manager = evaluation_db.task_manager = evaluation_db.report_manager = evaluation_db.metrics_manager = evaluation_db.evaluation_service = None
    evaluation_db._stale_tasks_recovered = False
    from app import create_app
    return create_app().test_client()


def test_connection_write_requires_admin_and_never_returns_key(secure_env):
    client = make_client(secure_env)
    payload = {"provider":"intelliq","name":"IntelliQ","api_url":"http://localhost:9000/api/v1","api_key":"top-secret","enabled":True}
    assert client.post("/api/v1/evaluation/rag-connections", json=payload).status_code == 401
    response = client.post("/api/v1/evaluation/rag-connections", json=payload, headers={"Authorization":"Bearer test-admin-token"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["api_key_configured"] is True
    assert "top-secret" not in str(body)
    listed = client.get("/api/v1/evaluation/rag-connections").get_json()["connections"]
    assert len([x for x in listed if x["provider"] == "intelliq"]) == 1


def test_connection_update_enable_disable_requires_admin(secure_env):
    client = make_client(secure_env)
    headers={"Authorization":"Bearer test-admin-token"}
    created=client.post("/api/v1/evaluation/rag-connections",json={"provider":"intelliq","name":"I","api_url":"http://localhost:9000","api_key":"secret"},headers=headers).get_json()
    assert client.put(f"/api/v1/evaluation/rag-connections/{created['id']}",json={"enabled":False}).status_code == 401
    updated=client.put(f"/api/v1/evaluation/rag-connections/{created['id']}",json={"enabled":False},headers=headers)
    assert updated.status_code == 200 and updated.get_json()["enabled"] is False
    from models.database import get_db_manager
    db = get_db_manager()
    row = db.get_rag_connection(created["id"])
    assert row["revision"] == 2
    conn = db.get_connection()
    audit = conn.execute(
        "SELECT action, changed_fields, actor FROM rag_connection_audit WHERE connection_id=? ORDER BY id DESC LIMIT 1",
        (created["id"],),
    ).fetchone()
    conn.close()
    assert audit["action"] == "updated"
    assert "enabled" in audit["changed_fields"]
    assert audit["actor"] == "deployment-admin"
