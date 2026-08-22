"""Shared response, validation, logging, and file helpers for API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Create a consistent JSON envelope for Flask endpoints."""

    @staticmethod
    def success(
        data: Any = None,
        message: str | None = None,
        status_code: int = 200,
    ):
        payload: dict[str, Any] = {"success": True}
        if data is not None:
            payload["data"] = data
        if message:
            payload["message"] = message
        return jsonify(payload), status_code

    @staticmethod
    def error(
        message: str,
        error: Exception | None = None,
        status_code: int = 500,
    ):
        payload: dict[str, Any] = {"success": False, "error": message}
        if error and logger.isEnabledFor(logging.DEBUG):
            payload["details"] = str(error)
        return jsonify(payload), status_code

    @staticmethod
    def validation_error(message: str):
        return ResponseFormatter.error(message, status_code=400)

    @staticmethod
    def not_found_error(message: str):
        return ResponseFormatter.error(message, status_code=404)


class ConfigValidator:
    """Validate API configuration payloads used by the settings page."""

    REQUIRED_API_FIELDS = ("provider", "model")

    @classmethod
    def validate(cls, data: Mapping[str, Any], config_type: str) -> str | None:
        if not isinstance(data, Mapping):
            return "配置必须是对象"
        if config_type != "api_config":
            return None

        missing = [field for field in cls.REQUIRED_API_FIELDS if not data.get(field)]
        if missing:
            return f"缺少必需字段: {', '.join(missing)}"

        temperature = data.get("temperature")
        if temperature is not None:
            try:
                temperature = float(temperature)
            except (TypeError, ValueError):
                return "temperature必须是数字"
            if not 0 <= temperature <= 2:
                return "temperature必须在0到2之间"

        max_tokens = data.get("maxTokens", data.get("max_tokens"))
        if max_tokens is not None:
            try:
                if int(max_tokens) <= 0:
                    return "maxTokens必须大于0"
            except (TypeError, ValueError):
                return "maxTokens必须是整数"
        return None


class ErrorLogger:
    """Centralize exception logging without leaking secrets to API clients."""

    @staticmethod
    def log_error(error: Exception, context: str = "操作失败") -> None:
        logger.exception("%s: %s", context, error)


class BatchOperationHelper:
    """Run a simple batch operation and summarize successes and failures."""

    @staticmethod
    def execute(
        items: Iterable[Any], operation: Callable[[Any], bool]
    ) -> dict[str, Any]:
        succeeded: list[Any] = []
        failed: list[Any] = []
        for item in items:
            try:
                (succeeded if operation(item) else failed).append(item)
            except Exception:
                logger.exception("Batch operation failed for %r", item)
                failed.append(item)
        return {
            "total_count": len(succeeded) + len(failed),
            "success_count": len(succeeded),
            "failed_count": len(failed),
            "failed_items": failed,
        }


class APIClientValidator:
    """Validate supported OpenAI-compatible API providers."""

    SUPPORTED_PROVIDERS = {"openai", "siliconflow", "deepseek", "zhipu"}

    @classmethod
    def validate_provider(cls, provider: str) -> str | None:
        if not provider:
            return "provider不能为空"
        if provider.lower() not in cls.SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(cls.SUPPORTED_PROVIDERS))
            return f"不支持的provider，支持: {supported}"
        return None


class FileManager:
    """File-name helpers shared by upload endpoints."""

    @staticmethod
    def is_allowed_file(file_name: str, allowed_extensions: Sequence[str]) -> bool:
        suffix = Path(file_name).suffix.lower()
        normalized = {
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            for extension in allowed_extensions
        }
        return bool(file_name) and suffix in normalized


def success_response(
    data: Any = None, message: str | None = None, status_code: int = 200
):
    return ResponseFormatter.success(data, message, status_code)


def handle_error(error: Exception, message: str = "操作失败"):
    ErrorLogger.log_error(error, message)
    status_code = error.code if isinstance(error, HTTPException) else 500
    detail = error.description if isinstance(error, HTTPException) else message
    return ResponseFormatter.error(detail, error, status_code=status_code)
