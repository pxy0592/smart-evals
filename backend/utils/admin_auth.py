"""Deployment-level authorization for sensitive connection mutations."""
from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import jsonify, request


def _configured_token() -> str:
    return os.getenv("SMART_EVAL_ADMIN_TOKEN", "").strip()


def is_admin_request() -> bool:
    expected = _configured_token()
    if not expected:
        return False
    header = request.headers.get("Authorization", "")
    scheme, _, supplied = header.partition(" ")
    return scheme.lower() == "bearer" and bool(supplied) and hmac.compare_digest(supplied, expected)


def require_admin_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_admin_request():
            return jsonify({"error": {"category": "authentication", "message": "缺少或使用了无效的部署级管理员令牌", "retryable": False}}), 401
        return func(*args, **kwargs)
    return wrapper
