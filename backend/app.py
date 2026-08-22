"""
RAG 评估系统主应用
独立部署的 RAG 评估服务，可与多种 RAG 系统集成
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging(app):
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]",
        handlers=[logging.StreamHandler()],
    )
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "evaluation.log"), maxBytes=10240000, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    app.logger.setLevel(logging.INFO)
    app.logger.info("RAG Evaluation System startup")
    print("✓ 日志系统已初始化 - 输出到控制台和 logs/evaluation.log")


def create_app():
    """应用工厂函数"""
    app = Flask(__name__)
    from config import get_config

    config_class = get_config()
    app.config.from_object(config_class)
    config_class.init_app(app)
    project_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(project_env):
        load_dotenv(project_env, override=False)
        print(f"Loaded project .env from: {project_env}")
    backend_env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)
        print(f"Loaded backend .env from: {backend_env}")
    knowflow_env = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowflow", ".env"
    )
    if os.path.exists(knowflow_env):
        load_dotenv(knowflow_env, override=False)
        print(f"Loaded Smart .env from: {knowflow_env}")
    setup_logging(app)
    CORS(
        app,
        resources={
            "/api/*": {
                "origins": app.config["CORS_ORIGINS"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )
    try:
        from evaluation_db import init_services, evaluation_bp

        init_services()
        app.register_blueprint(evaluation_bp)
        app.logger.info("✅ Evaluation blueprint registered successfully")
    except ImportError as e:
        app.logger.error(f"❌ Failed to import evaluation_db module: {e}")
        print(f"Error: {e}")
        print("Make sure the evaluation_db.py file is in the same directory as app.py")
        raise e

    @app.route("/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "rag-evaluation",
            "version": "1.0.0",
            "config": {
                "debug": app.config.get("DEBUG", False),
                "ragflow_url": app.config.get("RAGFLOW_BASE_URL"),
                "default_llm": app.config.get("DEFAULT_LLM_MODEL"),
            },
        }

    @app.route(
        "/api/ragflow/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    def ragflow_proxy(path):
        """代理 RAGFlow API 请求"""
        import requests

        ragflow_base_url = app.config.get("RAGFLOW_BASE_URL", "http://localhost:9380")
        ragflow_api_key = app.config.get("RAGFLOW_API_KEY", "")
        target_url = f"{ragflow_base_url}/{path}"
        headers = dict(request.headers)
        headers.pop("Host", None)
        if ragflow_api_key:
            headers["Authorization"] = f"Bearer {ragflow_api_key}"
        try:
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.args,
                json=request.get_json(silent=True),
                data=(
                    request.get_data()
                    if request.get_json(silent=True) is None
                    else None
                ),
                timeout=30,
            )
            return (resp.content, resp.status_code, dict(resp.headers))
        except Exception as e:
            app.logger.error(f"RAGFlow proxy error: {str(e)}")
            return ({"error": f"Failed to connect to RAGFlow: {str(e)}"}, 502)

    @app.route("/")
    def index():
        return {
            "service": "RAG Evaluation System",
            "version": "1.0.0",
            "description": "独立部署的 RAG 系统评测工具",
            "endpoints": {
                "evaluation": "/api/v1/evaluation",
                "health": "/health",
                "docs": "/api/v1/evaluation/docs",
            },
            "features": [
                "支持多种 RAG 系统评测",
                "基于 RAGAS 框架",
                "多种评测指标",
                "可视化报告",
                "批量评测支持",
            ],
        }

    return app


if __name__ == "__main__":
    app = create_app()
    port = app.config.get("PORT", 5002)
    host = app.config.get("HOST", "0.0.0.0")
    print(f"\n{'============================================================'}")
    print("RAG Evaluation System")
    print(f"{'============================================================'}")
    print(f"Starting on {host}:{port}")
    print(f"Debug Mode: {app.config.get('DEBUG', False)}")
    print(f"RAGFlow URL: {app.config.get('RAGFLOW_BASE_URL')}")
    print(f"Default LLM: {app.config.get('DEFAULT_LLM_MODEL')}")
    print(f"{'============================================================'}")
    print(f"API Documentation: http://{host}:{port}/api/v1/evaluation/docs")
    print(f"Health Check: http://{host}:{port}/health")
    print(f"{'============================================================'}\n")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
