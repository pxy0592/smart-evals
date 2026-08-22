from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture
def secure_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "evaluation.db"))
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path / "datasets"))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("RAG_CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SMART_EVAL_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("RAG_PROVIDER_ALLOWED_HOSTS", "localhost,127.0.0.1")
    import models.database as database
    import db
    database.db_manager = None
    db.config_manager = db.dataset_manager = db.task_manager = db.report_manager = None
    if "evaluation_db" in sys.modules:
        module = sys.modules["evaluation_db"]
        module.config_manager = module.dataset_manager = module.task_manager = None
        module.report_manager = module.metrics_manager = module.evaluation_service = None
        module._stale_tasks_recovered = False
    yield tmp_path
    database.db_manager = None
    db.config_manager = db.dataset_manager = db.task_manager = db.report_manager = None
    if "evaluation_db" in sys.modules:
        module = sys.modules["evaluation_db"]
        module.config_manager = module.dataset_manager = module.task_manager = None
        module.report_manager = module.metrics_manager = module.evaluation_service = None
        module._stale_tasks_recovered = False
