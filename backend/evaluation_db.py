global evaluation_service
global report_manager
global metrics_manager
global dataset_manager
global task_manager
global config_manager

"""
使用数据库的评测系统 API 路由
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import uuid
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from services.dataset_manager import MAX_DATASET_BYTES, normalize_dataset_bytes
from services.rag_connection_service import RagConnectionService
from services.rag_providers.factory import create_provider
from utils.admin_auth import require_admin_token
from db import (
    get_config_manager,
    get_dataset_manager,
    get_task_manager,
    get_report_manager,
)

try:
    from services.evaluation_service import EvaluationService
    from services.metrics_manager import MetricsManager
except ImportError as e:
    print(f"Import error: {e}")
    EvaluationService = None
    MetricsManager = None
logger = logging.getLogger(__name__)
evaluation_bp = Blueprint("evaluation_db", __name__, url_prefix="/api/v1/evaluation")
evaluation_service = None
config_manager = None
dataset_manager = None
task_manager = None
report_manager = None
metrics_manager = None
_stale_tasks_recovered = False
_session_cleanup_recovered = False


class NaNSafeJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 NaN 和 Infinity 值"""

    def encode(self, o):
        if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
            return "null"
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        """重写 iterencode 以处理嵌套的 NaN 值"""
        for chunk in super().iterencode(o, _one_shot):
            chunk = chunk.replace("NaN", "null")
            chunk = chunk.replace("Infinity", "null")
            chunk = chunk.replace("-Infinity", "null")
            yield chunk


def init_services():
    """初始化所有服务"""
    global evaluation_service
    global report_manager
    global metrics_manager
    global dataset_manager
    global task_manager
    global config_manager
    global _stale_tasks_recovered
    global _session_cleanup_recovered
    if not config_manager:
        config_manager = get_config_manager()
        logger.info("ConfigManager initialized")
    if not dataset_manager:
        dataset_manager = get_dataset_manager()
        logger.info("DatasetManager initialized")
    if not task_manager:
        task_manager = get_task_manager()
        logger.info("TaskManager initialized")
    if not report_manager:
        report_manager = get_report_manager()
        logger.info("ReportManager initialized")
    if not metrics_manager and MetricsManager:
        metrics_manager = MetricsManager()
        logger.info("MetricsManager initialized")
    if not evaluation_service:
        try:
            init_evaluation_service()
            logger.info("EvaluationService initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize EvaluationService: {e}")
            evaluation_service = None
    if task_manager and not _stale_tasks_recovered:
        for stale in task_manager.get_tasks(limit=10000, status="running").get(
            "tasks", []
        ):
            task_manager.update_task_status(
                stale["id"],
                "failed",
                error_message="Task interrupted by application restart",
                outcome="failed",
                interrupted_at=datetime.now().isoformat(),
            )
        _stale_tasks_recovered = True
    if task_manager and not _session_cleanup_recovered:
        _recover_pending_session_cleanups()
        _session_cleanup_recovered = True


def init_evaluation_service(force_reload=False):
    """初始化评测服务"""
    global evaluation_service
    if not evaluation_service or force_reload:
        try:
            from config import get_config_service

            config_service = get_config_service()
            api_config = config_service.get_api_config()
            ragflow_url = config_service.get_ragflow_url()
            llm_model = config_service.get_llm_model()
            evaluation_service = EvaluationService(
                llm_model=llm_model, ragflow_url=ragflow_url, api_config=api_config
            )
            logger.info("EvaluationService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EvaluationService: {str(e)}")
            evaluation_service = None


@evaluation_bp.route("/config", methods=["GET"])
@cross_origin()
def get_config():
    """获取系统配置"""
    try:
        init_services()
        settings = config_manager.get_settings()
        config_by_category = {}
        for setting in settings:
            category = setting["category"]
            if category not in config_by_category:
                config_by_category[category] = []
            config_by_category[category].append(
                {
                    "key": setting["key"],
                    "value": setting["value"],
                    "description": setting["description"],
                }
            )
        api_configs = config_manager.get_api_configs()
        default_api = config_manager.get_default_api_config()

        def to_camel_case(config):
            if not config:
                return
            else:
                stored_api_key = config.get("api_key") or config.get("apiKey")
                return {
                    "id": config.get("id"),
                    "name": config.get("name"),
                    "provider": config.get("provider"),
                    "apiKey": "",
                    "apiKeyConfigured": bool(stored_api_key),
                    "endpoint": config.get("endpoint"),
                    "model": config.get("model"),
                    "embeddingModel": config.get("embedding_model"),
                    "temperature": config.get("temperature"),
                    "maxTokens": config.get("max_tokens"),
                    "isDefault": config.get("is_default"),
                    "createdAt": config.get("created_at"),
                    "updatedAt": config.get("updated_at"),
                }

        api_configs_camel = [to_camel_case(c) for c in api_configs]
        default_api_camel = to_camel_case(default_api)
        return jsonify(
            {
                "config": config_by_category,
                "api_configs": api_configs_camel,
                "api": default_api_camel,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get config: {str(e)}")
        return (jsonify({"error": "Failed to get configuration"}), 500)


@evaluation_bp.route("/config", methods=["PUT"])
@cross_origin()
def update_config():
    """更新系统配置"""
    try:
        init_services()
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Configuration payload must be an object"}), 400
        if "settings" in data:
            config_manager.update_settings_batch(data["settings"])
        if "api_config" in data:
            api_config = data["api_config"]
            field_mapping = {
                "apiKey": "api_key",
                "embeddingModel": "embedding_model",
                "maxTokens": "max_tokens",
            }
            normalized_config = {}
            for key, value in api_config.items():
                db_key = field_mapping.get(key, key)
                if db_key in {"model", "embedding_model"} and isinstance(
                    value, list
                ):
                    if len(value) > 1:
                        return (
                            jsonify(
                                {
                                    "error": f"{key} must contain at most one value"
                                }
                            ),
                            400,
                        )
                    value = value[0] if value else None
                if isinstance(value, (dict, list)):
                    return (
                        jsonify(
                            {"error": f"{key} must be a scalar configuration value"}
                        ),
                        400,
                    )
                normalized_config[db_key] = value
            default_config = config_manager.get_default_api_config()
            if default_config:
                config_manager.update_api_config(
                    default_config["id"], normalized_config
                )
            else:
                config_manager.create_api_config(normalized_config)
        if "notification" in data:
            config_manager.update_setting(
                "notification_enabled", data["notification"].get("enabled", False)
            )
            if "webhook_url" in data["notification"]:
                config_manager.update_setting(
                    "notification_webhook_url", data["notification"]["webhook_url"]
                )
        return jsonify({"message": "Configuration updated successfully"})
    except Exception as e:
        logger.error(f"Failed to update config: {str(e)}")
        return (jsonify({"error": str(e)}), 500)


@evaluation_bp.route("/api-configs", methods=["GET"])
@cross_origin()
def get_api_configs():
    """获取 API 配置列表"""
    try:
        init_services()
        configs = config_manager.get_api_configs()
        return jsonify({"configs": configs})
    except Exception as e:
        logger.error(f"Failed to get API configs: {str(e)}")
        return (jsonify({"error": "Failed to get API configurations"}), 500)


@evaluation_bp.route("/api-configs", methods=["POST"])
@cross_origin()
def create_api_config():
    """创建 API 配置"""
    try:
        init_services()
        data = request.get_json()
        required_fields = ["name", "provider", "api_key"]
        for field in required_fields:
            if field not in data:
                return (jsonify({"error": f"Missing required field: {field}"}), 400)
        if data.get("is_default", False):
            pass
        config_id = config_manager.create_api_config(data)
        return (
            jsonify(
                {
                    "message": "API configuration created successfully",
                    "config_id": config_id,
                }
            ),
            201,
        )
    except Exception as e:
        logger.error(f"Failed to create API config: {str(e)}")
        return (jsonify({"error": "Failed to create API configuration"}), 500)


@evaluation_bp.route("/api-configs/<int:config_id>", methods=["PUT"])
@cross_origin()
def update_api_config(config_id):
    """更新 API 配置"""
    try:
        init_services()
        data = request.get_json()
        required_fields = ["name", "provider", "api_key"]
        for field in required_fields:
            if field not in data:
                return (jsonify({"error": f"Missing required field: {field}"}), 400)
        success = config_manager.update_api_config(config_id, data)
        if success:
            return jsonify({"message": "API configuration updated successfully"})
        else:
            return (jsonify({"error": "API configuration not found"}), 404)
    except Exception as e:
        logger.error(f"Failed to update API config: {str(e)}")
        return (jsonify({"error": "Failed to update API configuration"}), 500)


@evaluation_bp.route("/api-configs/<int:config_id>", methods=["DELETE"])
@cross_origin()
def delete_api_config(config_id):
    """删除 API 配置"""
    try:
        init_services()
        success = config_manager.delete_api_config(config_id)
        if success:
            return jsonify({"message": "API configuration deleted successfully"})
        else:
            return (jsonify({"error": "API configuration not found"}), 404)
    except Exception as e:
        logger.error(f"Failed to delete API config: {str(e)}")
        return (jsonify({"error": "Failed to delete API configuration"}), 500)


@evaluation_bp.route("/datasets", methods=["GET"])
@cross_origin()
def list_datasets():
    """获取数据集列表"""
    try:
        init_services()
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        result = dataset_manager.get_datasets(limit, offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to list datasets: {str(e)}")
        return (jsonify({"error": "Failed to list datasets"}), 500)


@evaluation_bp.route("/datasets", methods=["POST"])
@cross_origin()
def upload_dataset():
    """Upload and normalize one evaluation dataset before making it usable."""
    init_services()
    if "file" not in request.files:
        return jsonify({"error": {"category": "validation", "message": "No file provided", "retryable": False}}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": {"category": "validation", "message": "No file selected", "retryable": False}}), 400
    content = file.read(MAX_DATASET_BYTES + 1)
    if len(content) > MAX_DATASET_BYTES:
        return jsonify({"error": {"category": "validation", "message": "数据集文件不能超过 10 MB", "retryable": False}}), 413
    dataset_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix.lower()
    storage_dir = Path(os.getenv("DATASETS_DIR", "tmp/datasets"))
    storage_dir.mkdir(parents=True, exist_ok=True)
    original_path = storage_dir / f"{dataset_id}{suffix}"
    normalized_path = storage_dir / f"{dataset_id}.json"
    try:
        samples, metadata = normalize_dataset_bytes(content, file.filename)
        original_path.write_bytes(content)
        normalized_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
        data = {
            "id": dataset_id,
            "name": request.form.get("name") or file.filename,
            "description": request.form.get("description", ""),
            "file_name": secure_filename(file.filename),
            "file_type": metadata["file_type"],
            "file_size": len(content),
            "storage_path": str(original_path),
            "normalized_storage_path": str(normalized_path),
            "normalization_status": "completed",
            "num_samples": metadata["num_samples"],
            "has_reference": metadata["has_reference"],
            "has_contexts": metadata["has_contexts"],
            "sample_fields": metadata["sample_fields"],
            "status": "completed",
            "progress": 100,
            "created_by": request.headers.get("X-User-Id", "anonymous"),
        }
        dataset_manager.create_dataset(data)
        return jsonify(data), 201
    except TypeError as exc:
        return jsonify({"error": {"category": "validation", "message": str(exc), "retryable": False}}), 415
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return jsonify({"error": {"category": "validation", "message": str(exc), "retryable": False}}), 422
    except Exception as exc:
        logger.exception("Failed to upload dataset")
        return jsonify({"error": {"category": "upstream", "message": "数据集处理失败", "retryable": False}}), 500
    finally:
        if not normalized_path.exists():
            for candidate in (original_path, normalized_path):
                candidate.unlink(missing_ok=True)

@evaluation_bp.route("/datasets/<dataset_id>", methods=["GET"])
@cross_origin()
def get_dataset(dataset_id: str):
    """获取数据集详情"""
    try:
        init_services()
        dataset = dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return (jsonify({"error": "Dataset not found"}), 404)
        else:
            return jsonify(dataset)
    except Exception as e:
        logger.error(f"Failed to get dataset: {str(e)}")
        return (jsonify({"error": "Failed to get dataset"}), 500)


@evaluation_bp.route("/datasets/<dataset_id>/samples", methods=["GET"])
@cross_origin()
def get_dataset_samples(dataset_id: str):
    """获取数据集样本"""
    try:
        init_services()
        dataset = dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return (jsonify({"error": "Dataset not found"}), 404)
        else:
            limit = int(request.args.get("limit", 10))
            offset = int(request.args.get("offset", 0))
            samples = dataset_manager.get_dataset_samples(dataset_id, offset, limit)
            all_samples = dataset_manager.get_dataset_samples(dataset_id, 0, None)
            total = len(all_samples)
            return jsonify(
                {"samples": samples, "total": total, "limit": limit, "offset": offset}
            )
    except FileNotFoundError as e:
        logger.error(f"Dataset samples not found: {str(e)}")
        return (jsonify({"error": "Dataset file not found"}), 404)
    except Exception as e:
        logger.error(f"Failed to get dataset samples: {str(e)}")
        return (jsonify({"error": "Failed to get dataset samples"}), 500)


@evaluation_bp.route("/datasets/generate/<dataset_type>", methods=["POST"])
@cross_origin()
def generate_sample_dataset(dataset_type: str):
    """生成示例数据集"""
    
    try:
        init_services()
        if dataset_type == "basic":
            samples = [
                {
                    "question": "什么是人工智能？",
                    "expected_answer": "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
                },
                {
                    "question": "什么是机器学习？",
                    "expected_answer": "机器学习是人工智能的一个子集，使计算机能够在没有明确编程的情况下学习和改进。",
                },
                {
                    "question": "什么是深度学习？",
                    "expected_answer": "深度学习是机器学习的一个子集，使用具有多个隐藏层的神经网络来学习数据的复杂模式。",
                },
            ]
        else:
            if dataset_type == "with_contexts":
                samples = [
                    {
                        "question": "什么是人工智能？",
                        "expected_answer": "人工智能是计算机科学的一个分支。",
                        "contexts": [
                            "人工智能是指由机器模拟人类智能行为的技术。",
                            "AI系统可以学习、推理和解决问题。",
                        ],
                        "reference_contexts": [
                            "人工智能的定义包括感知、学习、推理等功能。"
                        ],
                    },
                    {
                        "question": "机器学习有哪些类型？",
                        "expected_answer": "机器学习包括监督学习、无监督学习和强化学习。",
                        "contexts": [
                            "监督学习使用标记数据训练。",
                            "无监督学习从未标记数据中发现模式。",
                            "强化学习通过奖励和惩罚来学习。",
                        ],
                    },
                ]
            else:
                return (jsonify({"error": "Unknown dataset type"}), 400)
        dataset_id = str(uuid.uuid4())
        dataset_name = f"Sample Dataset - {dataset_type}"
        storage_path = Path("tmp/datasets")
        storage_path.mkdir(parents=True, exist_ok=True)
        file_path = storage_path / f"{dataset_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)
        dataset_data = {
            "id": dataset_id,
            "name": dataset_name,
            "description": f"Auto-generated sample dataset of type: {dataset_type}",
            "file_name": "sample.json",
            "file_type": ".json",
            "file_size": os.path.getsize(file_path),
            "storage_path": str(file_path),
            "num_samples": len(samples),
            "has_reference": any(("contexts" in sample for sample in samples)),
            "has_contexts": list(samples[0].keys()) if samples else [],
            "sample_fields": "system",
            "created_by": "system",
        }
        dataset_manager.create_dataset(dataset_data)
        return (
            jsonify(
                {
                    "id": dataset_id,
                    "name": dataset_name,
                    "description": dataset_data["description"],
                    "file_name": "sample.json",
                    "file_type": ".json",
                    "num_samples": len(samples),
                    "has_reference": dataset_data["has_reference"],
                    "has_contexts": dataset_data["has_contexts"],
                    "sample_fields": dataset_data["sample_fields"],
                    "created_at": datetime.now().isoformat(),
                }
            ),
            201,
        )
    except Exception as e:
        logger.error(f"Failed to generate sample dataset: {str(e)}")
        return (jsonify({"error": "Failed to generate sample dataset"}), 500)


@evaluation_bp.route("/datasets/generate/ai", methods=["POST"])
@cross_origin()
def generate_ai_dataset():
    """基于知识库AI生成数据集（异步）"""
    try:
        init_services()
        data = request.get_json()
        kb_id = data.get("kb_id")
        sample_count = data.get("sample_count", 10)
        question_types = data.get("question_types", ["factual", "analytical"])
        connection_id = data.get("connection_id", "ragflow-default")
        if not kb_id:
            return (jsonify({"error": "Knowledge base ID is required"}), 400)
        if sample_count < 1 or sample_count > 100:
            return (jsonify({"error": "Sample count must be between 1 and 100"}), 400)
        # Resolve connection and verify capabilities
        connection = RagConnectionService().get_connection(connection_id, include_secret=True)
        if not connection or not connection.get("enabled"):
            return (jsonify({"error": "RAG connection not found or disabled"}), 400)
        provider = create_provider(connection, connection.get("api_key"))
        if not provider.capabilities.generate_dataset_from_knowledge_base:
            return (jsonify({"error": "This connection type does not support AI dataset generation"}), 400)
        dataset_id = str(uuid.uuid4())
        dataset_name = (
            f"AI Generated Dataset - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        dataset_data = {
            "id": dataset_id,
            "name": dataset_name,
            "description": f"AI generated dataset from knowledge base {kb_id} with {sample_count} samples",
            "file_name": "ai_generated.json",
            "file_type": ".json",
            "file_size": 0,
            "storage_path": f"tmp/datasets/{dataset_id}.json",
            "num_samples": 0,
            "has_reference": False,
            "has_contexts": False,
            "sample_fields": [],
            "status": "processing",
            "progress": 0,
            "created_by": "ai-generator",
        }
        dataset_manager.create_dataset(dataset_data)
        import threading

        def generate_async():
            try:
                from services.ai_dataset_generator import AIDatasetGenerator

                generator = AIDatasetGenerator()
                samples = generator.generate_dataset_from_kb(
                    provider=provider,
                    kb_id=kb_id,
                    sample_count=sample_count,
                    question_types=question_types,
                )
                if not samples:
                    dataset_manager.update_dataset_status(
                        dataset_id,
                        "failed",
                        error_message="Failed to generate samples from knowledge base",
                    )
                    return
                storage_path = Path("tmp/datasets")
                storage_path.mkdir(parents=True, exist_ok=True)
                file_path = storage_path / f"{dataset_id}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(samples, f, ensure_ascii=False, indent=2)
                dataset_manager.update_dataset_status(
                    dataset_id,
                    "completed",
                    progress=100,
                    num_samples=len(samples),
                    has_reference=any(
                        ("expected_answer" in sample for sample in samples)
                    ),
                    has_contexts=any(
                        ("contexts" in sample for sample in samples)
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to generate AI dataset: {str(e)}")
                dataset_manager.update_dataset_status(
                    dataset_id, "failed", error_message=str(e)
                )

        thread = threading.Thread(target=generate_async)
        thread.daemon = True
        thread.start()
        return (
            jsonify(
                {
                    "id": dataset_id,
                    "name": dataset_name,
                    "description": dataset_data["description"],
                    "file_name": "ai_generated.json",
                    "file_type": ".json",
                    "num_samples": 0,
                    "status": "processing",
                    "progress": 0,
                    "created_at": datetime.now().isoformat(),
                }
            ),
            202,
        )
    except Exception as e:
        logger.error(f"Failed to create AI dataset task: {str(e)}")
        return (jsonify({"error": "Failed to create AI dataset task"}), 500)


@evaluation_bp.route("/datasets/<dataset_id>", methods=["DELETE"])
@cross_origin()
def delete_dataset(dataset_id: str):
    """删除单个数据集"""
    try:
        init_services()
        success = dataset_manager.delete_dataset(dataset_id)
        if success:
            return jsonify({"message": "Dataset deleted successfully"})
        else:
            return (jsonify({"error": "Dataset not found"}), 404)
    except Exception as e:
        logger.error(f"Failed to delete dataset: {str(e)}")
        return (jsonify({"error": "Failed to delete dataset"}), 500)


@evaluation_bp.route("/datasets/batch", methods=["DELETE"])
@cross_origin()
def delete_datasets_batch():
    """批量删除数据集"""
    try:
        init_services()
        data = request.get_json()
        dataset_ids = data.get("dataset_ids", [])
        if not dataset_ids:
            return (jsonify({"error": "No dataset IDs provided"}), 400)
        else:
            logger.info(f"🗑️  开始批量删除数据集: {len(dataset_ids)} 个")
            deleted_count = 0
            failed_ids = []
            for dataset_id in dataset_ids:
                try:
                    success = dataset_manager.delete_dataset(dataset_id)
                    if success:
                        deleted_count += 1
                        logger.info(f"✅ 数据集删除成功: {dataset_id}")
                    else:
                        failed_ids.append(dataset_id)
                        logger.warning(f"⚠️  数据集删除失败: {dataset_id}")
                except Exception as e:
                    failed_ids.append(dataset_id)
                    logger.error(f"❌ 数据集删除异常: {dataset_id}, 错误: {str(e)}")
            response_data = {
                "message": f"Successfully deleted {deleted_count} out of {len(dataset_ids)} datasets",
                "deleted_count": deleted_count,
                "total_count": len(dataset_ids),
                "failed_count": len(failed_ids),
            }
            if failed_ids:
                response_data["failed_ids"] = failed_ids
            logger.info(f"🎉 批量删除完成: 成功 {deleted_count}/{len(dataset_ids)}")
            return jsonify(response_data)
    except Exception as e:
        logger.error(f"Failed to batch delete datasets: {str(e)}")
        return (jsonify({"error": "Failed to batch delete datasets"}), 500)


@evaluation_bp.route("/tasks", methods=["POST"])
@cross_origin()
def create_evaluation_task():
    """Create a legacy RAGFlow or provider-aware evaluation task."""
    init_services()
    data = request.get_json(silent=True) or {}
    if not data.get("dataset_id") or not data.get("metrics"):
        return jsonify({"error": {"category": "validation", "message": "dataset_id 和 metrics 为必填项", "retryable": False}}), 400
    if bool(data.get("rag_target")) == bool(data.get("chat_id")):
        return jsonify({"error": {"category": "validation", "message": "rag_target 与 legacy chat_id 必须且只能提供一个", "retryable": False}}), 400
    dataset = dataset_manager.get_dataset(data["dataset_id"])
    if not dataset or dataset.get("status") != "completed" or dataset.get("normalization_status") not in {None, "completed"}:
        return jsonify({"error": {"category": "validation", "message": "数据集不存在或尚未完成归一化", "retryable": False}}), 400

    if data.get("rag_target"):
        target = data["rag_target"]
        connection_id = target.get("connection_id")
        connection = RagConnectionService().get_connection(connection_id, include_secret=True)
        if not connection or not connection.get("enabled"):
            return jsonify({"error": {"category": "validation", "message": "RAG connection 不存在或未启用", "retryable": False}}), 400
        provider = create_provider(connection, connection.get("api_key"))
        try:
            assistants = _run_async(provider.list_assistants(limit=100))
            assistant = next((item for item in assistants if item.id == target.get("assistant_id")), None)
            if not assistant or not assistant.selectable or not assistant.knowledge_base_selection_mode:
                return jsonify({"error": {"category": "validation", "message": "Agent 不可用或知识库模式未知，请刷新资源", "retryable": False}}), 400
            mode = assistant.knowledge_base_selection_mode
            kb_ids = [str(x) for x in target.get("knowledge_base_ids") or []]
            if mode == "selected" and not kb_ids:
                return jsonify({"error": {"category": "validation", "message": "selected 模式至少需要一个知识库", "retryable": False}}), 400
            if mode in {"all", "none"} and kb_ids:
                return jsonify({"error": {"category": "validation", "message": f"{mode} 模式不能手动提交知识库", "retryable": False}}), 400
            kb_names = []
            if kb_ids:
                resources = _run_async(provider.list_knowledge_bases(assistant_id=assistant.id, limit=100))
                mapping = {item.id: item for item in resources if item.selectable}
                if any(kb_id not in mapping for kb_id in kb_ids):
                    return jsonify({"error": {"category": "validation", "message": "知识库不属于当前连接或 Agent 无权访问", "retryable": False}}), 400
                kb_names = [mapping[kb_id].name for kb_id in kb_ids]
        finally:
            _run_async(provider.close())
        provider_name = connection["provider"]
        assistant_id = assistant.id
        task_source = {
            "rag_provider": provider_name,
            "rag_connection_id": connection_id,
            "rag_connection_revision": connection.get("revision"),
            "assistant_id": assistant_id,
            "assistant_name_snapshot": assistant.name,
            "knowledge_base_ids": kb_ids,
            "knowledge_base_names_snapshot": kb_names,
            "knowledge_base_selection_mode_snapshot": mode,
            "connection_name_snapshot": connection.get("name"),
            "connection_base_url_snapshot": connection.get("base_url") or connection.get("api_url"),
            "source_legacy": False,
        }
    else:
        assistant_id = str(data["chat_id"])
        task_source = {
            "rag_provider": "ragflow",
            "rag_connection_id": "ragflow-default",
            "rag_connection_revision": 1,
            "assistant_id": assistant_id,
            "assistant_name_snapshot": assistant_id,
            "knowledge_base_ids": [],
            "knowledge_base_names_snapshot": [],
            "knowledge_base_selection_mode_snapshot": "selected",
            "connection_name_snapshot": "RAGFlow",
            "connection_base_url_snapshot": os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380"),
            "source_legacy": True,
        }

    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "name": data.get("name") or f"Evaluation Task {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "chat_id": assistant_id,
        "dataset_id": data["dataset_id"],
        "metrics": data["metrics"],
        "batch_size": int(data.get("batch_size", 10)),
        "llm_model": data.get("llm_model"),
        "embedding_model": data.get("embedding_model"),
        "created_by": request.headers.get("X-User-Id", "anonymous"),
        **task_source,
    }
    task_manager.create_task(task_data)
    import threading
    worker = threading.Thread(target=run_evaluation_task, args=(task_id,), daemon=True)
    worker.start()
    return jsonify({**task_data, "status": "pending", "progress": 0, "created_at": datetime.now().isoformat()}), 201


def run_evaluation_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return
    try:
        samples = dataset_manager.get_dataset_samples(task["dataset_id"])
    except Exception as exc:
        task_manager.update_task_status(task_id, "failed", error_message=str(exc), outcome="failed")
        return
    task_manager.update_task_status(task_id, "running", total_samples=len(samples), processed_samples=0, progress=0)
    connection = RagConnectionService().get_connection(task.get("rag_connection_id") or "ragflow-default", include_secret=True)
    if not connection:
        task_manager.update_task_status(task_id, "failed", error_message="RAG connection not found", outcome="failed")
        return
    if task.get("rag_connection_revision") and connection.get("revision") != task.get("rag_connection_revision"):
        task_manager.update_task_status(task_id, "failed", error_message="RAG connection revision changed before execution", outcome="failed")
        return
    provider = create_provider(connection, connection.get("api_key"))

    def progress(value):
        current = task_manager.get_task(task_id)
        if current and current.get("status") == "cancelled":
            return
        task_manager.update_task_status(task_id, "running", progress=max(0, min(99, int(value))), processed_samples=int(max(0, min(99, int(value))) / 100 * len(samples)))

    def cancelled():
        current = task_manager.get_task(task_id)
        return not current or current.get("status") == "cancelled"

    def sample_started(index, session_id, sample):
        attempts = [row for row in task_manager.db.get_final_sample_runs(task_id) if row["sample_index"] == index]
        return task_manager.db.create_sample_run({"task_id": task_id, "sample_index": index, "attempt": len(attempts) + 1, "session_id": session_id, "question": str(sample.get("question") or sample.get("user_input") or "")})

    def sample_session_created(run_id, provider_session_id):
        if run_id is not None:
            task_manager.db.mark_sample_session_created(run_id, provider_session_id)

    def sample_completed(run_id, result):
        if run_id is not None:
            task_manager.db.complete_sample_run(run_id, result)

    cleanup_warning = {}

    def session_cleanup_completed(result, session_run_ids):
        task_manager.db.mark_session_cleanup_result(
            list(session_run_ids.keys()),
            result.cleaned_ids,
            result.failed_ids,
            result.error.to_dict() if result.error else None,
        )
        if result.failed_ids:
            cleanup_warning["value"] = {
                "code": "intelliq_session_cleanup_failed",
                "message": result.error.message if result.error else "IntelliQ Session cleanup failed",
                "failed_sessions": len(result.failed_ids),
            }

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        from services.evaluation_service import evaluation_service as scoring_service
        evaluation_result = loop.run_until_complete(scoring_service.evaluate_with_provider(
            provider=provider,
            assistant_id=task.get("assistant_id") or task["chat_id"],
            knowledge_base_ids=task.get("knowledge_base_ids") or [],
            knowledge_base_selection_mode=task.get("knowledge_base_selection_mode_snapshot") or "selected",
            dataset_id=task["dataset_id"],
            selected_metrics=task["metrics"],
            dataset_samples=samples,
            progress_callback=progress,
            sample_started=sample_started,
            sample_session_created=sample_session_created,
            sample_completed=sample_completed,
            session_cleanup_completed=session_cleanup_completed,
            cancellation_check=cancelled,
        ))
        metadata = evaluation_result.get("evaluation_metadata", {})
        scored = int(metadata.get("success_count", 0))
        failed = int(metadata.get("failed_count", len(samples) - scored))
        if scored <= 0:
            raise RuntimeError("没有任何样本获得完整可评分回答")
        warning = {"code": "partial_sample_failure", "message": f"{failed} 个样本执行失败", "failed_samples": failed} if failed else None
        if cleanup_warning.get("value"):
            if warning:
                warning["session_cleanup_warning"] = cleanup_warning["value"]
            else:
                warning = cleanup_warning["value"]
        source_snapshot = {
            "provider": task.get("rag_provider", "ragflow"),
            "connection_id": task.get("rag_connection_id"),
            "connection_revision": task.get("rag_connection_revision"),
            "connection_name": task.get("connection_name_snapshot") or "RAGFlow",
            "connection_base_url": task.get("connection_base_url_snapshot"),
            "assistant_id": task.get("assistant_id") or task["chat_id"],
            "assistant_name": task.get("assistant_name_snapshot") or task["chat_id"],
            "knowledge_base_selection_mode": task.get("knowledge_base_selection_mode_snapshot"),
            "knowledge_bases": [{"id": kid, "name": name} for kid, name in zip(task.get("knowledge_base_ids") or [], task.get("knowledge_base_names_snapshot") or [])],
            "legacy": bool(task.get("source_legacy")),
        }
        report_manager.save_report({
            "task_id": task_id,
            "chat_id": task["chat_id"],
            "assistant_id": task.get("assistant_id"),
            "dataset_id": task["dataset_id"],
            "overall_scores": evaluation_result.get("overall_scores", {}),
            "detailed_scores": evaluation_result.get("detailed_scores", []),
            "evaluation_metadata": {**metadata, "metrics": task["metrics"]},
            "rag_provider": task.get("rag_provider", "ragflow"),
            "rag_connection_id": task.get("rag_connection_id"),
            "knowledge_base_ids": task.get("knowledge_base_ids") or [],
            "source_snapshot": source_snapshot,
            "scored_sample_count": scored,
            "failed_sample_count": failed,
            "total_sample_count": len(samples),
            "success_rate": scored / len(samples),
            "warning": warning,
        })
        task_manager.update_task_status(task_id, "completed", progress=100, processed_samples=len(samples), scored_sample_count=scored, failed_sample_count=failed, has_warnings=bool(failed or cleanup_warning.get("value")), outcome="partially_succeeded" if failed else "succeeded")
    except asyncio.CancelledError:
        task_manager.update_task_status(task_id, "cancelled", outcome="cancelled")
    except Exception as exc:
        logger.exception("Evaluation task failed: %s", task_id)
        task_manager.update_task_status(task_id, "failed", error_message=str(exc), outcome="failed")
    finally:
        loop.run_until_complete(provider.close())
        loop.close()
        asyncio.set_event_loop(None)


@evaluation_bp.route("/tasks", methods=["GET"])
@cross_origin()
def list_tasks():
    init_services()
    result = task_manager.get_tasks(
        limit=min(int(request.args.get("limit", 20)), 100),
        offset=max(int(request.args.get("offset", 0)), 0),
        status=request.args.get("status"),
        rag_provider=request.args.get("rag_provider"),
        rag_connection_id=request.args.get("rag_connection_id"),
    )
    for task in result["tasks"]:
        dataset = dataset_manager.get_dataset(task["dataset_id"])
        task["dataset_name"] = dataset.get("name") if dataset else None
        task["source_snapshot"] = {
            "provider": task.get("rag_provider", "ragflow"),
            "connection_id": task.get("rag_connection_id"),
            "connection_revision": task.get("rag_connection_revision"),
            "connection_name": task.get("connection_name_snapshot") or "RAGFlow",
            "connection_base_url": task.get("connection_base_url_snapshot"),
            "assistant_id": task.get("assistant_id") or task.get("chat_id"),
            "assistant_name": task.get("assistant_name_snapshot") or task.get("chat_id"),
            "knowledge_base_selection_mode": task.get("knowledge_base_selection_mode_snapshot"),
            "knowledge_bases": [{"id": kid, "name": name} for kid, name in zip(task.get("knowledge_base_ids") or [], task.get("knowledge_base_names_snapshot") or [])],
            "legacy": bool(task.get("source_legacy")),
        }
    return jsonify(result)


@evaluation_bp.route("/tasks/<task_id>", methods=["GET"])
@cross_origin()
def get_task_status(task_id: str):
    init_services()
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"error": {"category": "not_found", "message": "Task not found", "retryable": False}}), 404
    dataset = dataset_manager.get_dataset(task["dataset_id"])
    task["dataset_name"] = dataset.get("name") if dataset else None
    task["sample_runs"] = task_manager.db.get_final_sample_runs(task_id)
    return jsonify(task)


@evaluation_bp.route("/reports/<task_id>", methods=["GET"])
@cross_origin()
def get_evaluation_report(task_id: str):
    init_services()
    report = report_manager.get_report(task_id)
    if not report:
        task = task_manager.get_task(task_id)
        status = 409 if task and task.get("status") in {"pending", "running", "failed", "cancelled"} else 404
        return jsonify({"error": {"category": "conflict" if status == 409 else "not_found", "message": "该任务没有最终评测报告", "retryable": False}}), status
    dataset = dataset_manager.get_dataset(report["dataset_id"])
    scores = report.get("overall_scores") or {}
    means = [value.get("mean") for value in scores.values() if isinstance(value, dict) and isinstance(value.get("mean"), (int, float))]
    source = report.get("source_snapshot") or {}
    return jsonify({
        "task_id": task_id,
        "rag_provider": report.get("rag_provider", "ragflow"),
        "rag_connection_id": report.get("rag_connection_id"),
        "assistant_id": report.get("assistant_id"),
        "knowledge_base_ids": report.get("knowledge_base_ids") or [],
        "source_snapshot": source,
        "kb_name": ((source.get("knowledge_bases") or [{}])[0].get("name") if source.get("knowledge_bases") else source.get("assistant_name", "Unknown")),
        "dataset_id": report["dataset_id"],
        "dataset_name": dataset.get("name", "Unknown") if dataset else "Unknown",
        "overall_score": round(sum(means) / len(means), 4) if means else 0,
        "metric_scores": scores,
        "summary": f"评测完成，共 {report.get('total_sample_count', 0)} 个样本，成功率 {report.get('success_rate', 0) * 100:.1f}%",
        "recommendations": [],
        "created_at": report.get("created_at", ""),
        "createdAt": report.get("created_at", ""),
        "detailed_scores": report.get("detailed_scores") or [],
        "evaluation_metadata": report.get("evaluation_metadata") or {},
        "totalSamples": report.get("total_sample_count", 0),
        "scoredSamples": report.get("scored_sample_count", 0),
        "failedSamples": report.get("failed_sample_count", 0),
        "successRate": round(report.get("success_rate", 0) * 100, 1),
        "warning": report.get("warning"),
    })


@evaluation_bp.route("/reports", methods=["GET"])
@cross_origin()
def list_reports():
    init_services()
    result = report_manager.get_reports(
        limit=min(int(request.args.get("limit", 20)), 100),
        offset=max(int(request.args.get("offset", 0)), 0),
        rag_provider=request.args.get("rag_provider"),
        rag_connection_id=request.args.get("rag_connection_id"),
        assistant_id=request.args.get("assistant_id"),
        knowledge_base_id=request.args.get("knowledge_base_id"),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
    )
    summaries = []
    for report in result["reports"]:
        dataset = dataset_manager.get_dataset(report["dataset_id"])
        scores = report.get("overall_scores") or {}
        means = [value.get("mean") for value in scores.values() if isinstance(value, dict) and isinstance(value.get("mean"), (int, float))]
        source = report.get("source_snapshot") or {}
        summaries.append({
            "task_id": report["task_id"],
            "rag_provider": report.get("rag_provider", "ragflow"),
            "rag_connection_id": report.get("rag_connection_id"),
            "assistant_id": report.get("assistant_id"),
            "knowledge_base_ids": report.get("knowledge_base_ids") or [],
            "source_snapshot": source,
            "kb_name": ((source.get("knowledge_bases") or [{}])[0].get("name") if source.get("knowledge_bases") else source.get("assistant_name", "Unknown")),
            "dataset_id": report["dataset_id"],
            "dataset_name": dataset.get("name", "Unknown") if dataset else "Unknown",
            "overall_score": round(sum(means) / len(means), 4) if means else 0,
            "metric_scores": scores,
            "totalSamples": report.get("total_sample_count", 0),
            "scoredSamples": report.get("scored_sample_count", 0),
            "failedSamples": report.get("failed_sample_count", 0),
            "successRate": round(report.get("success_rate", 0) * 100, 1),
            "warning": report.get("warning"),
            "createdAt": report.get("created_at", ""),
        })
    return jsonify({"reports": summaries, "total": result["total"], "offset": result["offset"], "limit": result["limit"]})


@evaluation_bp.route("/reports/<task_id>", methods=["DELETE"])
@cross_origin()
def delete_report(task_id: str):
    """删除单个评测报告"""
    try:
        init_services()
        success = report_manager.delete_report(task_id)
        if success:
            return jsonify({"message": "Report deleted successfully"})
        else:
            return (jsonify({"error": "Report not found"}), 404)
    except Exception as e:
        logger.error(f"Failed to delete report: {str(e)}")
        return (jsonify({"error": "Failed to delete report"}), 500)


@evaluation_bp.route("/reports/batch", methods=["DELETE"])
@cross_origin()
def delete_reports_batch():
    """批量删除评测报告"""
    try:
        init_services()
        data = request.get_json()
        task_ids = data.get("task_ids", [])
        if not task_ids:
            return (jsonify({"error": "No task IDs provided"}), 400)
        else:
            logger.info(f"🗑️  开始批量删除评测报告: {len(task_ids)} 个")
            deleted_count = report_manager.delete_reports_batch(task_ids)
            response_data = {
                "message": f"Successfully deleted {deleted_count} out of {len(task_ids)} reports",
                "deleted_count": deleted_count,
                "total_count": len(task_ids),
                "failed_count": len(task_ids) - deleted_count,
            }
            logger.info(f"🎉 批量删除完成: 成功 {deleted_count}/{len(task_ids)}")
            return jsonify(response_data)
    except Exception as e:
        logger.error(f"Failed to batch delete reports: {str(e)}")
        return (jsonify({"error": "Failed to batch delete reports"}), 500)


def _recover_pending_session_cleanups():
    """Best-effort startup compensation for persisted IntelliQ Session cleanup work."""
    for group in task_manager.db.get_pending_session_cleanup_groups():
        connection = RagConnectionService().get_connection(
            group["rag_connection_id"], include_secret=True
        )
        if not connection:
            logger.warning("Skipping pending Session cleanup: connection %s unavailable", group["rag_connection_id"])
            continue
        provider = create_provider(connection, connection.get("api_key"))
        try:
            result = _run_async(provider.cleanup_session_ids(group["session_ids"]))
            task_manager.db.mark_session_cleanup_result(
                group["session_ids"], result.cleaned_ids, result.failed_ids,
                result.error.to_dict() if result.error else None,
            )
        except Exception as exc:
            logger.warning("Pending IntelliQ Session cleanup failed: %s", str(exc)[:300])
        finally:
            _run_async(provider.close())


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _connection_provider(connection_id: str):
    service = RagConnectionService()
    connection = service.get_connection(connection_id, include_secret=True)
    if not connection:
        raise KeyError("RAG connection not found")
    return connection, create_provider(connection, connection.get("api_key"))


@evaluation_bp.route("/rag-connections", methods=["GET"])
@cross_origin()
def list_rag_connections():
    return jsonify({"connections": RagConnectionService().list_connections()})


@evaluation_bp.route("/rag-connections", methods=["POST"])
@cross_origin()
@require_admin_token
def create_rag_connection():
    try:
        return jsonify(RagConnectionService().create(request.get_json(silent=True) or {})), 201
    except ValueError as exc:
        status = 409 if "仅支持一个" in str(exc) else 400
        return jsonify({"error": {"category": "conflict" if status == 409 else "validation", "message": str(exc), "retryable": False}}), status
    except Exception as exc:
        logger.exception("Failed to create RAG connection")
        return jsonify({"error": {"category": "validation", "message": str(exc), "retryable": False}}), 400


@evaluation_bp.route("/rag-connections/<connection_id>", methods=["GET"])
@cross_origin()
def get_rag_connection(connection_id):
    connection = RagConnectionService().get_connection(connection_id)
    if not connection:
        return jsonify({"error": {"category": "not_found", "message": "RAG connection not found", "retryable": False}}), 404
    return jsonify(connection)


@evaluation_bp.route("/rag-connections/<connection_id>", methods=["PUT"])
@cross_origin()
@require_admin_token
def update_rag_connection(connection_id):
    if connection_id == "ragflow-default":
        return jsonify({"error": {"category": "validation", "message": "RAGFlow default connection is environment-managed", "retryable": False}}), 400
    try:
        connection = RagConnectionService().update(connection_id, request.get_json(silent=True) or {})
        if not connection:
            return jsonify({"error": {"category": "not_found", "message": "RAG connection not found", "retryable": False}}), 404
        return jsonify(connection)
    except Exception as exc:
        return jsonify({"error": {"category": "validation", "message": str(exc), "retryable": False}}), 400


@evaluation_bp.route("/rag-connections/<connection_id>/test", methods=["POST"])
@cross_origin()
@require_admin_token
def test_rag_connection(connection_id):
    try:
        result = _run_async(RagConnectionService().validate(connection_id))
        if result is None:
            return jsonify({"error": {"category": "not_found", "message": "RAG connection not found", "retryable": False}}), 404
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": {"category": "upstream", "message": str(exc), "retryable": False}}), 502


@evaluation_bp.route("/rag-connections/<connection_id>/knowledge-bases", methods=["GET"])
@cross_origin()
def list_connection_knowledge_bases(connection_id):
    try:
        connection, provider = _connection_provider(connection_id)
        try:
            items = _run_async(provider.list_knowledge_bases(search=request.args.get("search"), assistant_id=request.args.get("assistant_id"), offset=int(request.args.get("offset", 0)), limit=min(int(request.args.get("limit", 100)), 100)))
        finally:
            _run_async(provider.close())
        return jsonify({"provider": connection["provider"], "connection_id": connection_id, "items": [item.to_dict() for item in items], "total": len(items), "offset": int(request.args.get("offset", 0)), "limit": min(int(request.args.get("limit", 100)), 100)})
    except KeyError:
        return jsonify({"error": {"category": "not_found", "message": "RAG connection not found", "retryable": False}}), 404
    except Exception as exc:
        return jsonify({"error": {"category": "upstream", "message": str(exc), "retryable": False}}), 502


@evaluation_bp.route("/rag-connections/<connection_id>/assistants", methods=["GET"])
@cross_origin()
def list_connection_assistants(connection_id):
    try:
        connection, provider = _connection_provider(connection_id)
        try:
            items = _run_async(provider.list_assistants(search=request.args.get("search"), offset=int(request.args.get("offset", 0)), limit=min(int(request.args.get("limit", 100)), 100)))
        finally:
            _run_async(provider.close())
        return jsonify({"provider": connection["provider"], "connection_id": connection_id, "items": [item.to_dict() for item in items], "total": len(items), "offset": int(request.args.get("offset", 0)), "limit": min(int(request.args.get("limit", 100)), 100)})
    except KeyError:
        return jsonify({"error": {"category": "not_found", "message": "RAG connection not found", "retryable": False}}), 404
    except Exception as exc:
        return jsonify({"error": {"category": "upstream", "message": str(exc), "retryable": False}}), 502


@evaluation_bp.route("/knowledgebases", methods=["GET"])
@cross_origin()
def list_knowledge_bases():
    """获取知识库列表 (返回 RAGFlow 的数据集列表)"""
    try:
        init_services()
        import requests

        ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
        ragflow_base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
        if not ragflow_api_key:
            return (
                jsonify({"code": 1, "message": "RAGFlow API key not configured"}),
                500,
            )
        else:
            headers = {
                "Authorization": f"Bearer {ragflow_api_key}",
                "Content-Type": "application/json",
            }
            response = requests.get(
                f"{ragflow_base_url}/api/v1/datasets", headers=headers, timeout=10
            )
            if response.status_code == 200:
                ragflow_data = response.json()
                if ragflow_data.get("code") == 0 and ragflow_data.get("data"):
                    knowledge_bases = []
                    datasets = ragflow_data.get("data", [])
                    if isinstance(datasets, list):
                        for dataset in datasets:
                            knowledge_bases.append(
                                {
                                    "id": dataset["id"],
                                    "name": dataset["name"],
                                    "description": dataset.get("description") or "",
                                    "doc_num": dataset.get("document_count", 0),
                                    "chunk_num": dataset.get("chunk_count", 0),
                                    "created_at": dataset.get("create_time"),
                                    "updated_at": dataset.get("update_time"),
                                    "status": "1",
                                }
                            )
                    return jsonify(
                        {
                            "knowledgebases": knowledge_bases,
                            "total": len(knowledge_bases),
                        }
                    )
                else:
                    return (
                        jsonify(
                            {
                                "code": ragflow_data.get("code", (-1)),
                                "message": ragflow_data.get(
                                    "message", "Failed to fetch RAGFlow data"
                                ),
                            }
                        ),
                        400,
                    )
            else:
                return (
                    jsonify(
                        {
                            "code": response.status_code,
                            "message": f"RAGFlow API request failed: {response.status_code}",
                        }
                    ),
                    response.status_code,
                )
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch RAGFlow chats: {str(e)}")
        return (jsonify({"code": 500, "message": "Failed to connect to RAGFlow"}), 500)
    except Exception as e:
        logger.error(f"Failed to list knowledge bases: {str(e)}")
        return (
            jsonify({"code": 500, "message": "Failed to list knowledge bases"}),
            500,
        )


@evaluation_bp.route("/knowledgebases/<kb_id>", methods=["GET"])
@cross_origin()
def get_knowledge_base(kb_id: str):
    """获取知识库详情 (返回 RAGFlow 数据集详情)"""
    try:
        init_services()
        import requests

        ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
        ragflow_base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
        if not ragflow_api_key:
            return (
                jsonify({"code": 1, "message": "RAGFlow API key not configured"}),
                500,
            )
        else:
            headers = {
                "Authorization": f"Bearer {ragflow_api_key}",
                "Content-Type": "application/json",
            }
            response = requests.get(
                f"{ragflow_base_url}/api/v1/datasets?id={kb_id}",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                dataset_data = response.json()
                if dataset_data.get("code") == 0 and dataset_data.get("data"):
                    datasets = dataset_data["data"].get("datasets", [])
                    if datasets:
                        dataset = datasets[0]
                        knowledge_base = {
                            "id": dataset["id"],
                            "name": dataset["name"],
                            "description": dataset.get("description", "RAGFlow 数据集"),
                            "doc_num": dataset.get("document_count", 0),
                            "chunk_count": dataset.get("chunk_count", 0),
                            "embedding_model": dataset.get("embedding_model", ""),
                            "chunk_method": dataset.get("chunk_method", ""),
                            "parser_config": dataset.get("parser_config", {}),
                            "created_at": dataset.get("created_at"),
                            "updated_at": dataset.get("updated_at"),
                            "status": dataset.get("status", "1"),
                        }
                        return jsonify({"code": 0, "data": knowledge_base})
                    else:
                        return (
                            jsonify({"code": (-1), "message": "Dataset not found"}),
                            404,
                        )
                else:
                    return (
                        jsonify(
                            {
                                "code": dataset_data.get("code", (-1)),
                                "message": dataset_data.get(
                                    "message", "Dataset not found"
                                ),
                            }
                        ),
                        404,
                    )
            else:
                return (
                    jsonify(
                        {
                            "code": response.status_code,
                            "message": f"RAGFlow API request failed: {response.status_code}",
                        }
                    ),
                    response.status_code,
                )
    except Exception as e:
        logger.error(f"Failed to get knowledge base: {str(e)}")
        return (jsonify({"code": 500, "message": "Failed to get knowledge base"}), 500)


@evaluation_bp.route(
    "/ragflow/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
@cross_origin()
def ragflow_proxy(path):
    """RAGFlow API 通用代理 - 统一从后端转发到 RAGFlow"""
    try:
        import requests

        ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
        ragflow_base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
        if not ragflow_api_key:
            return (
                jsonify({"code": 1, "message": "RAGFlow API key not configured"}),
                500,
            )
        else:
            target_url = f"{ragflow_base_url}/{path}"
            headers = {
                "Authorization": f"Bearer {ragflow_api_key}",
                "Content-Type": "application/json",
            }
            params = request.args.to_dict()
            data = None
            if request.method in ["POST", "PUT", "PATCH"]:
                data = request.get_json()
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=params,
                json=data,
                timeout=30,
            )
            return (jsonify(response.json()), response.status_code)
    except requests.exceptions.RequestException as e:
        logger.error(f"RAGFlow proxy error: {str(e)}")
        return (
            jsonify(
                {"code": 500, "message": f"Failed to connect to RAGFlow: {str(e)}"}
            ),
            500,
        )
    except Exception as e:
        logger.error(f"RAGFlow proxy error: {str(e)}")
        return (
            jsonify({"code": 500, "message": f"RAGFlow proxy error: {str(e)}"}),
            500,
        )


@evaluation_bp.route("/metrics", methods=["GET"])
@cross_origin()
def list_metrics():
    """获取可用评测指标。"""
    metrics = [
        {
            "name": "faithfulness",
            "display_name": "忠实度",
            "description": "评估回答是否忠实于检索上下文",
            "type": "llm_based",
            "requires_contexts": True,
            "requires_reference": False,
            "default_enabled": True,
        },
        {
            "name": "answer_correctness",
            "display_name": "答案正确性",
            "description": "评估回答与参考答案的匹配程度",
            "type": "llm_based",
            "requires_contexts": False,
            "requires_reference": True,
            "default_enabled": True,
        },
        {
            "name": "context_precision",
            "display_name": "上下文精确度",
            "description": "评估检索上下文与问题的相关性",
            "type": "llm_based",
            "requires_contexts": True,
            "requires_reference": False,
            "default_enabled": True,
        },
        {
            "name": "context_recall",
            "display_name": "上下文召回率",
            "description": "评估检索结果是否覆盖回答所需信息",
            "type": "llm_based",
            "requires_contexts": True,
            "requires_reference": True,
            "default_enabled": True,
        },
        {
            "name": "answer_relevancy",
            "display_name": "答案相关性",
            "description": "评估回答与问题的相关程度",
            "type": "llm_based",
            "requires_contexts": False,
            "requires_reference": False,
            "default_enabled": True,
        },
    ]
    return jsonify({"metrics": metrics})


@evaluation_bp.route("/statistics", methods=["GET"])
@cross_origin()
def get_statistics():
    """获取统计数据"""
    
    try:
        init_services()
        logger.info("📊 开始获取统计数据")
        task_stats = task_manager.get_task_statistics()
        logger.info(f"📊 任务统计: {task_stats}")
        dataset_stats = dataset_manager.get_dataset_statistics()
        logger.info(f"📊 数据集统计: {dataset_stats}")
        report_stats = report_manager.get_report_statistics()
        logger.info(f"📊 报告统计: {report_stats}")
        health_score = calculate_health_score(report_stats.get("recent_scores", []))
        logger.info(f"📊 健康度分数: {health_score}")
        avg_processing_time = task_stats.get("avg_processing_time", 0)
        response_data = {
            "health_score": health_score,
            "total_evaluations": task_stats.get("total_completed", 0),
            "active_datasets": dataset_stats.get("total_count", 0),
            "avg_processing_time": avg_processing_time,
            "task_status_counts": task_stats.get("status_counts", {}),
            "recent_scores": report_stats.get("recent_scores", []),
            "metric_scores": report_stats.get("metric_averages", []),
            "total_tasks": task_stats.get("running_count", 0),
            "running_tasks": task_stats.get("total_completed", 0),
            "completed_tasks": task_stats.get("failed_count", 0),
        }
        logger.info(f"📊 返回统计数据: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        import traceback

        logger.error(f"Failed to get statistics: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return (jsonify({"error": "Failed to get statistics"}), 500)


def calculate_health_score(scores):
    """计算健康度分数 - 基于实际评测数据"""
    if not scores:
        return 0
    else:
        avg_score = sum(scores) / len(scores)
        return round(min(100, max(0, avg_score * 100)))


@evaluation_bp.route("/health", methods=["GET"])
@cross_origin()
def health_check():
    """Readiness check for SQLite and mounted writable directories."""
    try:
        init_services()
        task_manager.db.get_connection().close()
        for directory in (
            Path(os.getenv("DATASETS_DIR", "tmp/datasets")),
            Path(os.getenv("REPORTS_DIR", "tmp/evaluation/reports")),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            if not os.access(directory, os.W_OK):
                raise OSError(f"Directory is not writable: {directory}")
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {"database": "healthy", "evaluation_service": "available" if evaluation_service else "unavailable"},
            "database_path": task_manager.db.db_path,
            "version": "1.0.0",
        })
    except Exception as exc:
        logger.exception("Health check failed")
        return jsonify({"status": "unready", "message": str(exc)}), 503


@evaluation_bp.route("/tasks/<task_id>/start", methods=["POST"])
@cross_origin()
def start_task(task_id):
    """开始任务"""
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            return (jsonify({"error": "Task not found"}), 404)
        else:
            if task["status"] not in ["pending", "failed"]:
                return (
                    jsonify({"error": "Task cannot be started in current state"}),
                    400,
                )
            else:
                task_manager.update_task_status(task_id, "pending")
                if evaluation_service:
                    import threading

                    thread = threading.Thread(
                        target=run_evaluation_task, args=(task_id,)
                    )
                    thread.daemon = True
                    thread.start()
                    logger.info(f"Task {task_id} started successfully")
                    return jsonify({"message": "Task started"})
                else:
                    return (jsonify({"error": "Evaluation service not available"}), 503)
    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {str(e)}")
        return (jsonify({"error": "Failed to start task"}), 500)


@evaluation_bp.route("/tasks/<task_id>/pause", methods=["POST"])
@cross_origin()
def pause_task(task_id):
    """暂停任务"""
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            return (jsonify({"error": "Task not found"}), 404)
        else:
            if task["status"] != "running":
                return (jsonify({"error": "Task is not running"}), 400)
            else:
                task_manager.update_task_status(task_id, "paused")
                logger.info(f"Task {task_id} paused")
                return jsonify({"message": "Task paused"})
    except Exception as e:
        logger.error(f"Failed to pause task {task_id}: {str(e)}")
        return (jsonify({"error": "Failed to pause task"}), 500)


@evaluation_bp.route("/tasks/<task_id>/cancel", methods=["POST"])
@cross_origin()
def cancel_task(task_id):
    """取消任务"""
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            return (jsonify({"error": "Task not found"}), 404)
        else:
            if task["status"] in ["completed"]:
                return (jsonify({"error": "Cannot cancel completed task"}), 400)
            else:
                task_manager.update_task_status(task_id, "cancelled")
                logger.info(f"Task {task_id} cancelled")
                return jsonify({"message": "Task cancelled"})
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {str(e)}")
        return (jsonify({"error": "Failed to cancel task"}), 500)


@evaluation_bp.route("/tasks/<task_id>/retry", methods=["POST"])
@cross_origin()
def retry_task(task_id):
    """重试任务"""
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            return (jsonify({"error": "Task not found"}), 404)
        else:
            if task["status"] not in ["failed", "cancelled"]:
                return (
                    jsonify(
                        {
                            "error": "Task can only be retried from failed or cancelled state"
                        }
                    ),
                    400,
                )
            else:
                task_manager.update_task_status(task_id, "pending", error_message=None)
                if evaluation_service:
                    import threading

                    thread = threading.Thread(
                        target=run_evaluation_task, args=(task_id,)
                    )
                    thread.daemon = True
                    thread.start()
                    logger.info(f"Task {task_id} retry started")
                    return jsonify({"message": "Task retry started"})
                else:
                    return (jsonify({"error": "Evaluation service not available"}), 503)
    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {str(e)}")
        return (jsonify({"error": "Failed to retry task"}), 500)


@evaluation_bp.route("/tasks/<task_id>", methods=["DELETE"])
@cross_origin()
def delete_task(task_id):
    """删除任务"""
    logger.info(f"🗑️  收到删除任务请求: {task_id}")
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            logger.warning(f"⚠️  删除任务失败: 任务不存在 {task_id}")
            return (jsonify({"error": "Task not found"}), 404)
        else:
            logger.info(f"📋 找到任务: {task['name']} | 状态: {task['status']}")
            if task["status"] == "running":
                logger.warning(f"⚠️  无法删除运行中的任务: {task_id}")
                return (jsonify({"error": "Cannot delete running task"}), 400)
            else:
                logger.info(f"🗑️  开始删除任务: {task_id}")
                task_manager.delete_task(task_id)
                logger.info(f"✅ 任务删除成功: {task_id} - {task['name']}")
                return jsonify({"message": "Task deleted"})
    except Exception as e:
        logger.error(f"❌ 删除任务失败 {task_id}: {str(e)}")
        import traceback

        logger.error(f"🗑️  详细错误信息: {traceback.format_exc()}")
        return (jsonify({"error": "Failed to delete task"}), 500)


@evaluation_bp.route("/tasks/batch", methods=["DELETE"])
@cross_origin()
def delete_tasks_batch():
    """批量删除非运行中的评测任务。"""
    try:
        init_services()
        data = request.get_json(silent=True) or {}
        task_ids = data.get("task_ids", [])
        if not isinstance(task_ids, list) or not task_ids:
            return jsonify({"error": "No task IDs provided"}), 400

        deleted_count = 0
        failed_ids = []
        running_tasks = []
        for task_id in task_ids:
            try:
                task = task_manager.get_task(task_id)
                if not task:
                    failed_ids.append(task_id)
                elif task.get("status") == "running":
                    running_tasks.append(task_id)
                elif task_manager.delete_task(task_id):
                    deleted_count += 1
                else:
                    failed_ids.append(task_id)
            except Exception:
                logger.exception("Failed to delete task %s", task_id)
                failed_ids.append(task_id)

        return jsonify(
            {
                "message": f"Successfully deleted {deleted_count} out of {len(task_ids)} tasks",
                "deleted_count": deleted_count,
                "total_count": len(task_ids),
                "failed_count": len(failed_ids),
                "running_count": len(running_tasks),
                "failed_ids": failed_ids,
                "running_tasks": running_tasks,
            }
        )
    except Exception as error:
        logger.exception("Failed to batch delete tasks")
        return jsonify({"error": f"Failed to batch delete tasks: {error}"}), 500


@evaluation_bp.route("/test-connection", methods=["POST"])
@cross_origin()
def test_api_connection():
    """测试 OpenAI 兼容 API 的连通性。"""
    try:
        init_services()
        data = request.get_json(silent=True) or {}
        provider = data.get("provider", "openai")
        api_key = data.get("apiKey") or data.get("api_key")
        endpoint = data.get("endpoint")
        model = data.get("model", "gpt-4")
        using_stored_api_key = False
        if not api_key or "*" in api_key:
            default_config = config_manager.get_default_api_config()
            stored_key = default_config.get("apiKey") if default_config else None
            if not stored_key:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "无法获取完整的 API Key，请重新输入",
                        }
                    ),
                    400,
                )
            api_key = stored_key
            using_stored_api_key = True

        provider_endpoints = {
            "siliconflow": "https://api.siliconflow.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "openai": None,
        }
        endpoint = endpoint or provider_endpoints.get(provider)

        from langchain_openai import ChatOpenAI

        llm_config = {"model": model, "api_key": api_key, "timeout": 10}
        if endpoint:
            llm_config["base_url"] = endpoint
        response = ChatOpenAI(**llm_config).invoke("Hello")
        return jsonify(
            {
                "success": True,
                "message": "连接测试成功",
                "details": {
                    "provider": provider,
                    "model": model,
                    "response": str(response.content)[:200],
                    "usingStoredApiKey": using_stored_api_key,
                },
            }
        )
    except Exception as error:
        logger.exception("API connection test failed")
        return jsonify({"success": False, "message": f"测试失败: {error}"}), 500
