global _config_service

"""
RAG 评估系统配置
独立部署的配置文件
"""

import os
from datetime import timedelta


class Config:
    """基础配置类"""

    SECRET_KEY = os.getenv("SECRET_KEY", "rag-evaluation-secret-key-2024")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5002))
    RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_BASE_URL = os.getenv(
        "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
    )
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "siliconflow")
    DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    DEFAULT_EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3")
    EVALUATION_TIMEOUT = int(os.getenv("EVALUATION_TIMEOUT", 300))
    EVALUATION_MAX_WORKERS = int(
        os.getenv("EVALUATION_MAX_WORKERS", os.getenv("MAX_WORKERS", 2))
    )
    EVALUATION_MAX_RETRIES = int(
        os.getenv("EVALUATION_MAX_RETRIES", os.getenv("MAX_RETRIES", 2))
    )
    TEMP_DIR = os.getenv("TEMP_DIR", "tmp")
    DATASETS_DIR = os.path.join(TEMP_DIR, "datasets")
    REPORTS_DIR = os.path.join(TEMP_DIR, "evaluation", "reports")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/evaluation.log")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10485760))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 10))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 104857600))
    ALLOWED_EXTENSIONS = {"json", "xlsx", "tsv", "xls", "csv"}
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///evaluation.db")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/evaluation.db")
    RAG_CREDENTIAL_ENCRYPTION_KEY = os.getenv("RAG_CREDENTIAL_ENCRYPTION_KEY", "")
    SMART_EVAL_ADMIN_TOKEN = os.getenv("SMART_EVAL_ADMIN_TOKEN", "")
    RAG_PROVIDER_ALLOWED_HOSTS = {
        host.strip()
        for host in os.getenv("RAG_PROVIDER_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    INTELLIQ_SESSION_CLEANUP_BATCH_SIZE = int(
        os.getenv("INTELLIQ_SESSION_CLEANUP_BATCH_SIZE", 100)
    )

    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        os.makedirs("logs", exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.DATASETS_DIR, exist_ok=True)
        os.makedirs(Config.REPORTS_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置"""

    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """生产环境配置"""

    DEBUG = False
    LOG_LEVEL = "WARNING"


class TestingConfig(Config):
    """测试环境配置"""

    TESTING = True
    DEBUG = True
    EVALUATION_TIMEOUT = 60


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """获取当前配置"""
    env = os.getenv("FLASK_ENV", "default")
    return config.get(env, DevelopmentConfig)


import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigService:
    """
    统一配置服务 - 单例模式
    提供全局配置获取功能，所有实例都使用同一个配置来源
    优先级：数据库配置 > 环境变量
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigService, cls).__new__(cls)
        return cls._instance

    def get_api_config(self) -> Dict[str, Any]:
        """
        获取 API 配置
        优先级：数据库配置 > 环境变量
        """
        
        try:
            from db import get_config_manager

            config_manager = get_config_manager()
            api_config = config_manager.get_default_api_config()
            if api_config:
                normalized = {
                    "provider": api_config.get("provider"),
                    "apiKey": api_config.get("apiKey")
                    or api_config.get("api_key")
                    or "",
                    "endpoint": api_config.get("endpoint") or "",
                    "model": api_config.get("model"),
                    "embeddingModel": api_config.get("embeddingModel") or "",
                }
                if "temperature" in api_config or "temperature" in normalized:
                    normalized["temperature"] = api_config.get("temperature", 0.7)
                if "max_tokens" in api_config or "maxTokens" in api_config:
                    normalized["maxTokens"] = api_config.get(
                        "maxTokens"
                    ) or api_config.get("max_tokens")
                logger.info(
                    f"✅ 从数据库加载配置: provider={normalized.get('provider')}, model={normalized.get('model')}, embeddingModel={normalized.get('embeddingModel')}"
                )
                return normalized
        except Exception as e:
            logger.warning(f"⚠️  从数据库加载配置失败: {e}. 使用环境变量配置")
        provider = os.getenv("DEFAULT_LLM_PROVIDER", "siliconflow")
        logger.info(f"📝 使用环境变量配置: provider={provider}")
        if provider == "siliconflow":
            return {
                "provider": "siliconflow",
                "apiKey": os.getenv("SILICONFLOW_API_KEY", ""),
                "endpoint": os.getenv(
                    "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
                ),
                "model": os.getenv("DEFAULT_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
                "embeddingModel": os.getenv("DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3"),
            }
        else:
            if provider == "deepseek":
                return {
                    "provider": "deepseek",
                    "apiKey": os.getenv("DEEPSEEK_API_KEY", ""),
                    "endpoint": os.getenv(
                        "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
                    ),
                    "model": os.getenv("DEFAULT_LLM_MODEL", "deepseek-chat"),
                    "embeddingModel": os.getenv(
                        "DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3"
                    ),
                }
            else:
                if provider == "zhipu":
                    return {
                        "provider": "zhipu",
                        "apiKey": os.getenv("ZHIPU_API_KEY", ""),
                        "endpoint": os.getenv(
                            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
                        ),
                        "model": os.getenv("DEFAULT_LLM_MODEL", "glm-4"),
                        "embeddingModel": os.getenv(
                            "DEFAULT_EMBEDDING_MODEL", "BAAI/bge-m3"
                        ),
                    }
                else:
                    return {
                        "provider": "openai",
                        "apiKey": os.getenv("OPENAI_API_KEY", ""),
                        "endpoint": os.getenv(
                            "OPENAI_BASE_URL", "https://api.openai.com/v1"
                        ),
                        "model": os.getenv("DEFAULT_LLM_MODEL", "gpt-4"),
                        "embeddingModel": os.getenv(
                            "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"
                        ),
                    }

    def get_ragflow_url(self) -> str:
        """获取 RAGFlow 服务地址"""
        return os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")

    def get_llm_model(self) -> str:
        """获取 LLM 模型名称"""
        api_config = self.get_api_config()
        return api_config.get(
            "model", os.getenv("DEFAULT_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        )


_config_service = None


def get_config_service() -> ConfigService:
    """获取配置服务单例"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
