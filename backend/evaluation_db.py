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
        default_api = None
        if api_configs:
            default_api = next(
                (config for config in api_configs if config.get("is_default")),
                api_configs[0],
            )

        def to_camel_case(config):
            if not config:
                return
            else:
                return {
                    "id": config.get("id"),
                    "name": config.get("name"),
                    "provider": config.get("provider"),
                    "apiKey": config.get("api_key"),
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
        data = request.get_json()
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
    """上传评测数据集，并在后台解析样本元数据。"""
    try:
        init_services()
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        dataset_name = request.form.get("name", file.filename)
        description = request.form.get("description", "")
        file_content = file.read()
        file_size = len(file_content)
        dataset_id = str(uuid.uuid4())
        file_type = Path(file.filename).suffix.lower()
        if file_type not in {".json", ".jsonl", ".csv", ".xlsx", ".xls"}:
            return jsonify({"error": f"Unsupported file format: {file_type}"}), 400

        storage_path = Path("tmp/datasets")
        storage_path.mkdir(parents=True, exist_ok=True)
        file_path = storage_path / f"{dataset_id}{file_type}"
        file_path.write_bytes(file_content)

        dataset_data = {
            "id": dataset_id,
            "name": dataset_name,
            "description": description,
            "file_name": secure_filename(file.filename),
            "file_type": file_type,
            "file_size": file_size,
            "storage_path": str(file_path),
            "num_samples": 0,
            "has_reference": False,
            "has_contexts": False,
            "sample_fields": [],
            "status": "processing",
            "progress": 0,
            "created_by": request.headers.get("X-User-Id", "anonymous"),
        }
        dataset_manager.create_dataset(dataset_data)

        def process_async():
            try:
                if file_type in {".json", ".jsonl"}:
                    decoded = file_content.decode("utf-8")
                    try:
                        samples = json.loads(decoded)
                        if isinstance(samples, dict):
                            samples = [samples]
                    except json.JSONDecodeError:
                        samples = [
                            json.loads(line)
                            for line in decoded.splitlines()
                            if line.strip()
                        ]
                elif file_type == ".csv":
                    from io import BytesIO

                    samples = pd.read_csv(BytesIO(file_content)).to_dict("records")
                else:
                    from io import BytesIO

                    samples = pd.read_excel(BytesIO(file_content)).to_dict("records")

                if not isinstance(samples, list):
                    raise ValueError(
                        "Dataset root must be a JSON array or tabular records"
                    )

                num_samples = len(samples)
                has_reference = any(
                    "expected_answer" in sample or "reference" in sample
                    for sample in samples
                    if isinstance(sample, dict)
                )
                has_contexts = any(
                    "contexts" in sample or "reference_contexts" in sample
                    for sample in samples
                    if isinstance(sample, dict)
                )
                dataset_manager.update_dataset_status(
                    dataset_id,
                    "completed",
                    progress=100,
                    num_samples=num_samples,
                    has_reference=has_reference,
                    has_contexts=has_contexts,
                )
            except Exception as error:
                logger.exception("Failed to process dataset %s", dataset_id)
                dataset_manager.update_dataset_status(
                    dataset_id, "failed", error_message=str(error)
                )

        import threading

        thread = threading.Thread(target=process_async, daemon=True)
        thread.start()
        return (
            jsonify(
                {
                    "id": dataset_id,
                    "name": dataset_name,
                    "description": description,
                    "file_name": secure_filename(file.filename),
                    "file_type": file_type,
                    "num_samples": 0,
                    "status": "processing",
                    "progress": 0,
                    "created_at": datetime.now().isoformat(),
                }
            ),
            202,
        )
    except Exception as error:
        logger.exception("Failed to upload dataset")
        return jsonify({"error": f"Failed to upload dataset: {error}"}), 500


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
        if not kb_id:
            return (jsonify({"error": "Knowledge base ID is required"}), 400)
        else:
            if sample_count < 1 or sample_count > 100:
                return (
                    jsonify({"error": "Sample count must be between 1 and 100"}),
                    400,
                )
            else:
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
                        else:
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
    """创建评测任务"""
    logger.info("🚀 收到创建评测任务请求")
    try:
        init_services()
        data = request.get_json()
        logger.info(f"📝 任务创建参数: {json.dumps(data, ensure_ascii=False)}")
        required_fields = ["chat_id", "dataset_id", "metrics"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"⚠️  缺少必填字段: {field}")
                return (jsonify({"error": f"Missing required field: {field}"}), 400)
        logger.info("✅ 参数验证通过")
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "name": data.get(
                "name", f"Evaluation Task {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ),
            "chat_id": data["chat_id"],
            "dataset_id": data["dataset_id"],
            "metrics": data["metrics"],
            "batch_size": data.get("batch_size", 10),
            "llm_model": data.get("llm_model"),
            "embedding_model": data.get("embedding_model"),
            "created_by": request.headers.get("X-User-Id", "anonymous"),
        }
        task_manager.create_task(task_data)
        if evaluation_service:
            import threading

            thread = threading.Thread(target=run_evaluation_task, args=(task_id,))
            thread.daemon = True
            thread.start()
        else:
            task_manager.update_task_status(
                task_id, "failed", error_message="Evaluation service not available"
            )
        return (
            jsonify(
                {
                    "id": task_id,
                    "name": task_data["name"],
                    "chat_id": data["chat_id"],
                    "dataset_id": data["dataset_id"],
                    "metrics": data["metrics"],
                    "batch_size": data["batch_size"],
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                }
            ),
            201,
        )
    except Exception as e:
        logger.error(f"Failed to create evaluation task: {str(e)}")
        return (jsonify({"error": "Failed to create evaluation task"}), 500)


def run_evaluation_task(task_id: str):
    """Execute an evaluation task in a worker thread."""
    task = task_manager.get_task(task_id)
    if not task:
        logger.error("Task %s not found", task_id)
        return

    samples = dataset_manager.get_dataset_samples(task["dataset_id"])
    if not samples:
        task_manager.update_task_status(
            task_id, "failed", error_message="No samples found in dataset"
        )
        return

    task_manager.update_task_status(
        task_id,
        "running",
        total_samples=len(samples),
        processed_samples=0,
        progress=0,
    )

    def progress_callback(progress: int):
        progress = max(0, min(99, int(progress)))
        processed_samples = int(progress / 100 * len(samples))
        task_manager.update_task_status(
            task_id,
            "running",
            processed_samples=processed_samples,
            progress=progress,
        )

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        evaluation_result = loop.run_until_complete(
            _run_rag_evaluation(task_id, task, samples, progress_callback)
        )
        metadata = evaluation_result.get("evaluation_metadata", {})
        report_data = {
            "task_id": task_id,
            "chat_id": task["chat_id"],
            "dataset_id": task["dataset_id"],
            "overall_scores": evaluation_result.get("overall_scores", {}),
            "detailed_scores": evaluation_result.get("detailed_scores", []),
            "evaluation_metadata": {
                **metadata,
                "metrics": task["metrics"],
                "total_samples": len(samples),
            },
        }
        report_id = report_manager.save_report(report_data)
        logger.info("Evaluation report saved: %s", report_id)
        task_manager.update_task_status(
            task_id,
            "completed",
            progress=100,
            processed_samples=len(samples),
        )
    except Exception as error:
        logger.exception("Evaluation task failed: %s", task_id)
        task_manager.update_task_status(task_id, "failed", error_message=str(error))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _run_rag_evaluation(
    task_id: str, task: dict, samples: list, progress_callback=None
) -> dict:
    """运行 RAGAS 评测"""
    try:
        from services.evaluation_service import evaluation_service

        if not evaluation_service:
            raise Exception("Evaluation service not available")
        else:
            result = await evaluation_service.evaluate_knowledge_base(
                chat_id=task["chat_id"],
                dataset_id=task["dataset_id"],
                selected_metrics=task["metrics"],
                dataset_samples=samples,
                batch_size=task.get("batch_size", 10),
                progress_callback=progress_callback,
            )
            logger.info("✅ RAGAS 评测成功完成")
            return result
    except Exception as e:
        logger.error(f"❌ RAGAS 评测失败: {str(e)}")
        import traceback

        logger.error(f"🔍 详细错误信息: {traceback.format_exc()}")
        raise


@evaluation_bp.route("/tasks", methods=["GET"])
@cross_origin()
def list_tasks():
    """获取任务列表"""
    logger.info("📋 收到获取任务列表请求")
    try:
        init_services()
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        status = request.args.get("status")
        logger.info(f"🔍 查询任务参数: limit={limit}, offset={offset}, status={status}")
        result = task_manager.get_tasks(limit, offset, status)
        task_count = len(result.get("tasks", []))
        logger.info(
            f"✅ 成功获取任务列表: 共 {task_count} 个任务 (总数: {result.get('total', 0)})"
        )
        if task_count > 0:
            for task in result["tasks"][:3]:
                logger.info(
                    f"  - 任务 {task['id'][:8]}: {task['name']} | 状态: {task['status']} | 进度: {task.get('progress', 0)}%"
                )
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {str(e)}")
        import traceback

        logger.error(f"📋 详细错误信息: {traceback.format_exc()}")
        return (jsonify({"error": "Failed to list tasks"}), 500)


@evaluation_bp.route("/tasks/<task_id>", methods=["GET"])
@cross_origin()
def get_task_status(task_id: str):
    """获取任务状态"""
    try:
        init_services()
        task = task_manager.get_task(task_id)
        if not task:
            return (jsonify({"error": "Task not found"}), 404)
        else:
            return jsonify(task)
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        return (jsonify({"error": "Failed to get task status"}), 500)


@evaluation_bp.route("/reports/<task_id>", methods=["GET"])
@cross_origin()
def get_evaluation_report(task_id: str):
    """获取并扩展单个评测报告。"""
    try:
        init_services()
        report = report_manager.get_report(task_id)
        if not report:
            return jsonify({"error": "Report not found"}), 404

        task = task_manager.get_task(task_id)
        dataset = dataset_manager.get_dataset(task["dataset_id"]) if task else None
        detailed_scores = report.get("detailed_scores", [])
        metric_scores = report.get("overall_scores", {})
        means = [
            score["mean"]
            for score in metric_scores.values()
            if isinstance(score, dict) and isinstance(score.get("mean"), (int, float))
        ]
        overall_score = sum(means) / len(means) if means else 0
        metadata = report.get("evaluation_metadata", {})
        total_count = metadata.get(
            "total_samples", metadata.get("num_samples", len(detailed_scores))
        )
        success_count = metadata.get("success_count", 0)
        success_rate = success_count / total_count * 100 if total_count else 0

        display_names = {
            "faithfulness": "忠实度",
            "answer_correctness": "答案正确性",
            "context_precision": "上下文精确度",
            "context_recall": "上下文召回率",
            "answer_relevancy": "答案相关性",
        }
        recommendations = [
            f"{display_names.get(name, name)}较低 ({score['mean']:.2f})，建议优化相关策略"
            for name, score in metric_scores.items()
            if isinstance(score, dict)
            and isinstance(score.get("mean"), (int, float))
            and score["mean"] < 0.6
        ] or ["整体表现良好，继续保持"]

        low_score_samples = []
        for sample in detailed_scores:
            numeric_scores = {
                key: value
                for key, value in sample.items()
                if key
                not in {"user_input", "actual_answer", "expected_answer", "contexts"}
                and isinstance(value, (int, float))
            }
            if numeric_scores:
                average = sum(numeric_scores.values()) / len(numeric_scores)
                if average < 0.6:
                    lowest_name = min(numeric_scores, key=numeric_scores.get)
                    low_score_samples.append(
                        {
                            "question": sample.get("user_input", "Unknown")[:100],
                            "score": round(average, 2),
                            "issue": f"{display_names.get(lowest_name, lowest_name)} 得分低",
                        }
                    )

        return jsonify(
            {
                "task_id": task_id,
                "kb_name": task.get("name", "Unknown") if task else "Unknown",
                "dataset_name": (
                    dataset.get("name", "Unknown") if dataset else "Unknown"
                ),
                "overall_score": round(overall_score, 4),
                "metric_scores": metric_scores,
                "summary": f"评测完成，共 {total_count} 个样本，成功率 {success_rate:.1f}%",
                "recommendations": recommendations,
                "lowScoreSamples": low_score_samples[:5],
                "created_at": report.get("created_at", ""),
                "createdAt": report.get("created_at", ""),
                "detailed_scores": detailed_scores,
                "evaluation_metadata": metadata,
                "totalSamples": total_count,
            }
        )
    except Exception as error:
        logger.exception("Failed to get evaluation report")
        return jsonify({"error": f"Failed to get evaluation report: {error}"}), 500


@evaluation_bp.route("/reports", methods=["GET"])
@cross_origin()
def list_reports():
    """获取报告列表"""
    try:
        init_services()
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        result = report_manager.get_reports(limit, offset)
        enriched_reports = []
        for report in result.get("reports", []):
            task_id = report.get("task_id")
            task = task_manager.get_task(task_id)
            dataset = dataset_manager.get_dataset(task["dataset_id"]) if task else None
            overall_scores = report.get("overall_scores", {})
            valid_scores = []
            for _, scores in overall_scores.items():
                if isinstance(scores, dict) and "mean" in scores:
                    valid_scores.append(scores["mean"])
            overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
            metadata = report.get("evaluation_metadata", {})
            success_count = metadata.get("success_count", 0)
            total_count = metadata.get("num_samples", metadata.get("total_count", 1))
            success_rate = success_count / total_count * 100 if total_count > 0 else 0
            enriched_reports.append(
                {
                    "task_id": task_id,
                    "kb_name": task.get("name", "Unknown") if task else "Unknown",
                    "dataset_name": (
                        dataset.get("name", "Unknown") if dataset else "Unknown"
                    ),
                    "overall_score": round(overall_score, 4),
                    "totalSamples": total_count,
                    "successRate": round(success_rate, 1),
                    "createdAt": report.get("created_at", ""),
                    "metric_scores": overall_scores,
                }
            )
        return jsonify(enriched_reports)
    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return (jsonify({"error": "Failed to list reports"}), 500)


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
    """健康检查"""
    try:
        init_services()
        db_status = "healthy"
        try:
            config_manager.get_setting("test_key")
        except Exception:
            db_status = "unhealthy"
        evaluation_status = "available" if evaluation_service else "unavailable"
        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "database": db_status,
                    "evaluation_service": evaluation_status,
                    "metrics_manager": (
                        "available" if metrics_manager else "unavailable"
                    ),
                },
                "version": "1.0.0",
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )


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
        if not api_key:
            return jsonify({"success": False, "message": "API Key 不能为空"}), 400

        if "*" in api_key:
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
                },
            }
        )
    except Exception as error:
        logger.exception("API connection test failed")
        return jsonify({"success": False, "message": f"测试失败: {error}"}), 500
