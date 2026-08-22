from flask import Flask

from utils.admin_auth import is_admin_request, require_admin_token


def test_admin_token_required(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setenv("SMART_EVAL_ADMIN_TOKEN", "secret")

    @app.get("/protected")
    @require_admin_token
    def protected():
        return {"ok": True}

    client = app.test_client()
    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_missing_server_token_fails_closed(monkeypatch):
    app = Flask(__name__)
    monkeypatch.delenv("SMART_EVAL_ADMIN_TOKEN", raising=False)
    with app.test_request_context(headers={"Authorization": "Bearer anything"}):
        assert not is_admin_request()
