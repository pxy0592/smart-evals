# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: '/app/services/evaluation_service.py'
# Bytecode version: 3.10.b1 (3439)
# Source timestamp: 2025-11-08 13:43:16 UTC (1762609396)

"""
评测服务核心模块
负责执行知识库的评测任务，集成 RAGAS 评估引擎
"""

import asyncio
import logging
import os
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import pandas as pd
import aiohttp

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    logging.warning("LangChain packages not fully installed")
    ChatOpenAI = None
    OpenAIEmbeddings = None
try:
    from ragas import evaluate
    from ragas.metrics import (
        Faithfulness,
        AnswerCorrectness,
        ContextPrecision,
        ContextRecall,
        AnswerRelevancy,
    )
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    from ragas.llms.base import LangchainLLMWrapper
    from ragas.embeddings.base import LangchainEmbeddingsWrapper
    from ragas.run_config import RunConfig
except ImportError:
    logging.warning("RAGAS not installed. Please install with: pip install ragas")
    evaluate = None
    Faithfulness = None
    AnswerCorrectness = None
    ContextPrecision = None
    ContextRecall = None
    AnswerRelevancy = None
    SingleTurnSample = None
    EvaluationDataset = None
    LangchainLLMWrapper = None
    LangchainEmbeddingsWrapper = None
    RunConfig = None
logger = logging.getLogger(__name__)


class EvaluationService:
    """
    RAG 评测服务
    提供知识库的多维度质量评估
    """

    def __init__(
        self,
        llm_model: str = "gpt-4",
        ragflow_url: str = "http://ragflow:9380",
        api_config: Dict = None,
    ):
        """
        初始化评测服务

        Args:
            llm_model: 用于评测的 LLM 模型
            ragflow_url: RAGFlow 服务地址
            api_config: API配置（包含 provider, apiKey, endpoint, embeddingModel 等）
        """

        self.ragflow_url = ragflow_url
        self.llm_model = llm_model
        self.api_config = api_config or {}
        self.llm = None
        self.embeddings = None
        self.metrics_map = self._initialize_metrics()
        logger.info(f"EvaluationService initialized with LLM: {llm_model}")
        logger.info(
            f"API config: provider={self.api_config.get('provider')}, endpoint={self.api_config.get('endpoint')}, embeddingModel={self.api_config.get('embeddingModel')}"
        )

    def _get_llm(self):
        """
        延迟获取 LLM 实例
        从系统配置读取 API Key 和 Endpoint，支持多种 LLM 提供商
        """

        if self.llm is None and ChatOpenAI and LangchainLLMWrapper:
            provider = self.api_config.get("provider", "openai")
            base_url = self.api_config.get("endpoint", None)
            temperature = self.api_config.get("temperature", 0.1)
            api_key = (
                self.api_config.get("apiKey")
                or self.api_config.get("api_key")
                or (
                    os.getenv("SILICONFLOW_API_KEY")
                    if provider == "siliconflow"
                    else None
                )
                or os.getenv("OPENAI_API_KEY", "")
            )
            provider_endpoints = {
                "siliconflow": "https://api.siliconflow.cn/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "zhipu": "https://open.bigmodel.cn/api/paas/v4",
                "openai": None,
            }
            if not base_url and provider in provider_endpoints:
                base_url = provider_endpoints[provider]
            kwargs = {
                "model": self.llm_model,
                "temperature": temperature,
                "api_key": api_key,
            }
            if base_url:
                kwargs["base_url"] = base_url
            masked_key = (
                f"{api_key[:5]}...{api_key[(-5):]}"
                if isinstance(api_key, str) and len(api_key) > 10
                else "***"
            )
            logger.info(
                f"Creating LLM: model={self.llm_model}, provider={provider}, endpoint={base_url}, api_key={masked_key}"
            )
            openai_model = ChatOpenAI(**kwargs)
            self.llm = LangchainLLMWrapper(openai_model)
            logger.info("✅ LLM instance created successfully")
        return self.llm

    def _get_embeddings(self):
        """
        延迟获取 Embeddings 实例
        使用与 LLM 相同的配置源 (self.api_config)
        """

        if self.embeddings is None and OpenAIEmbeddings and LangchainEmbeddingsWrapper:
            provider = self.api_config.get("provider", "openai")
            base_url = self.api_config.get("endpoint", None)
            api_key = (
                self.api_config.get("apiKey")
                or self.api_config.get("api_key")
                or (
                    os.getenv("SILICONFLOW_API_KEY")
                    if provider == "siliconflow"
                    else None
                )
                or os.getenv("OPENAI_API_KEY", "")
            )
            embedding_model = self.api_config.get(
                "embeddingModel"
            ) or self.api_config.get("embedding_model", "")
            if isinstance(embedding_model, list):
                embedding_model = embedding_model[0] if embedding_model else ""
            if not embedding_model:
                logger.warning(
                    "No embedding model configured in system settings. Some metrics (like AnswerCorrectness) may fail."
                )
                return
            else:
                provider_endpoints = {
                    "siliconflow": "https://api.siliconflow.cn/v1",
                    "deepseek": "https://api.deepseek.com/v1",
                    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
                    "openai": None,
                }
                if not base_url and provider in provider_endpoints:
                    base_url = provider_endpoints[provider]
                kwargs = {"model": embedding_model, "api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                openai_embeddings = OpenAIEmbeddings(**kwargs)
                self.embeddings = LangchainEmbeddingsWrapper(openai_embeddings)
                logger.info(
                    f"Embeddings instance created: {embedding_model} (provider: {provider}, endpoint: {base_url})"
                )
        return self.embeddings

    def _initialize_metrics(self) -> Dict:
        """
        初始化可用的评测指标
        注意：某些指标（如 AnswerCorrectness, AnswerRelevancy）需要 embeddings 模型
        这些指标会在执行时动态获取 embeddings 实例
        """

        if not Faithfulness:
            return {}
        else:
            return {
                "faithfulness": Faithfulness(),
                "answer_correctness": AnswerCorrectness(weights=[0.5, 0.5]),
                "context_precision": ContextPrecision(),
                "context_recall": ContextRecall(),
                "answer_relevancy": AnswerRelevancy(),
            }

    async def evaluate_knowledge_base(
        self,
        chat_id: str,
        dataset_id: str,
        selected_metrics: List[str],
        dataset_samples: List[Dict],
        batch_size: int = 10,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        评测对话助手

        Args:
            chat_id: 对话助手 ID (Chat Assistant ID)
            dataset_id: 数据集 ID
            selected_metrics: 选择的评测指标
            dataset_samples: 数据集样本
            batch_size: 批处理大小
            progress_callback: 进度回调函数，接收绝对进度值 (0-99)

        Returns:
            评测结果
        """

        if not evaluate:
            raise ImportError(
                "RAGAS not installed. Please install with: pip install ragas"
            )
        else:
            logger.info(
                f"Starting evaluation for Chat: {chat_id}, Dataset: {dataset_id}"
            )
            logger.info(f"Selected metrics: {selected_metrics}")
            logger.info(
                f"Dataset samples: {len(dataset_samples)}, Batch size: {batch_size}"
            )
            try:
                logger.info("Step 1: Preparing evaluation samples...")

                def sample_progress_callback(processed: int, total: int):
                    if progress_callback:
                        progress = int(processed / total * 50)
                        progress_callback(progress)

                evaluation_samples, rag_responses = (
                    await self._prepare_samples_with_responses(
                        chat_id, dataset_samples, sample_progress_callback
                    )
                )
                logger.info("Step 2: Creating RAGAS dataset...")
                if progress_callback:
                    progress_callback(50)
                eval_dataset = EvaluationDataset(samples=evaluation_samples)
                logger.info("Step 3: Selecting metrics...")
                if progress_callback:
                    progress_callback(55)
                metrics = []
                for metric_name in selected_metrics:
                    if metric_name in self.metrics_map:
                        metrics.append(self.metrics_map[metric_name])
                        logger.info(f"  - Added metric: {metric_name}")
                    else:
                        logger.warning(f"  - Unknown metric: {metric_name}")
                if progress_callback:
                    progress_callback(60)
                run_config = RunConfig(max_workers=2, max_retries=2, timeout=300)
                logger.info(
                    f"Step 4: Running evaluation with {len(metrics)} metrics..."
                )
                logger.info(f"  - Max workers: {run_config.max_workers}")
                logger.info(f"  - Timeout: {run_config.timeout}s")
                logger.info(f"  - Max retries: {run_config.max_retries}")
                embeddings = self._get_embeddings()
                if embeddings:
                    logger.info("  - Using embeddings model")
                else:
                    logger.info("  - No embeddings model configured")
                loop = asyncio.get_event_loop()
                logger.info("Starting RAGAS evaluation...")
                if progress_callback:
                    progress_callback(65)
                results = await loop.run_in_executor(
                    None,
                    lambda: evaluate(
                        dataset=eval_dataset,
                        metrics=metrics,
                        llm=self._get_llm(),
                        embeddings=embeddings,
                        run_config=run_config,
                    ),
                )
                logger.info("RAGAS evaluation completed")
                if progress_callback:
                    progress_callback(95)
                logger.info("Step 5: Processing results...")
                evaluation_result = self._process_results(
                    results, chat_id, dataset_id, rag_responses
                )
                if progress_callback:
                    progress_callback(99)
                success_rate = evaluation_result["evaluation_metadata"].get(
                    "success_rate", "0 / 0"
                )
                logger.info(
                    f"Evaluation completed for Chat: {chat_id}, Success rate: {success_rate}"
                )
                return evaluation_result
            except Exception as e:
                logger.error(f"Evaluation failed: {str(e)}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                raise

    async def _prepare_samples(
        self, chat_id: str, dataset_samples: List[Dict], progress_callback=None
    ) -> List[SingleTurnSample]:
        """
        准备评测样本，查询 RAGFlow 获取响应

        Args:
            chat_id: 对话助手 ID
            dataset_samples: 原始数据集样本
            progress_callback: 进度回调函数，接收 (processed_count, total_count)

        Returns:
            RAGAS 格式的评测样本
        """

        samples = []
        total_samples = len(dataset_samples)
        for idx, item in enumerate(dataset_samples, 1):
            logger.info(
                f"Preparing sample {idx}/{total_samples}: {item.get('question', '')[:50]}..."
            )
            try:
                rag_response = await self._query_ragflow(chat_id, item["question"])
                logger.info(
                    f"Sample {idx}/{total_samples}: Got response with {len(rag_response.get('contexts', []))} contexts"
                )
            except Exception as e:
                logger.error(
                    f"Sample {idx}/{total_samples}: Failed to query RAGFlow: {str(e)}"
                )
                rag_response = {"answer": "", "contexts": []}
            sample = SingleTurnSample(
                user_input=item["question"],
                retrieved_contexts=rag_response.get("contexts", []),
                response=rag_response.get("answer", ""),
                reference=item.get("expected_answer"),
                reference_contexts=item.get("reference_contexts", []),
            )
            samples.append(sample)
            if progress_callback:
                progress_callback(idx, total_samples)
        logger.info(f"Prepared {len(samples)} samples for evaluation")
        return samples

    async def _prepare_samples_with_responses(
        self, chat_id: str, dataset_samples: List[Dict], progress_callback=None
    ) -> tuple[List[SingleTurnSample], List[Dict]]:
        """
        准备评测样本，查询 RAGFlow 获取响应，并保留原始数据

        Args:
            chat_id: 对话助手 ID
            dataset_samples: 原始数据集样本
            progress_callback: 进度回调函数，接收 (processed_count, total_count)

        Returns:
            tuple: (RAGAS格式的评测样本, RAGFlow响应列表)
        """

        samples = []
        rag_responses = []
        total_samples = len(dataset_samples)
        for idx, item in enumerate(dataset_samples, 1):
            logger.info(
                f"Preparing sample {idx}/{total_samples}: {item.get('question', '')[:50]}..."
            )
            try:
                rag_response = await self._query_ragflow(chat_id, item["question"])
                logger.info(
                    f"Sample {idx}/{total_samples}: Got response with {len(rag_response.get('contexts', []))} contexts"
                )
            except Exception as e:
                logger.error(
                    f"Sample {idx}/{total_samples}: Failed to query RAGFlow: {str(e)}"
                )
                rag_response = {"answer": "", "contexts": []}
            rag_response["original_question"] = item["question"]
            rag_response["expected_answer"] = item.get("expected_answer", "")
            rag_responses.append(rag_response)
            sample = SingleTurnSample(
                user_input=item["question"],
                retrieved_contexts=rag_response.get("contexts", []),
                response=rag_response.get("answer", ""),
                reference=item.get("expected_answer"),
                reference_contexts=item.get("reference_contexts", []),
            )
            samples.append(sample)
            if progress_callback:
                progress_callback(idx, total_samples)
        logger.info(f"Prepared {len(samples)} samples for evaluation")
        return (samples, rag_responses)

    async def _query_ragflow(self, chat_id: str, question: str) -> Dict:
        """查询 RAGFlow 对话助手并返回答案及检索上下文。"""
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=50)
        base_url = self.ragflow_url.rstrip("/")
        completion_url = f"{base_url}/api/v1/chats/{chat_id}/completions"
        session_url = f"{base_url}/api/v1/chats/{chat_id}/sessions"
        api_key = os.getenv("RAGFLOW_API_KEY", "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                session_id = getattr(self, "_cached_session_id", None)
                if not session_id:
                    async with session.post(
                        session_url, json={}, headers=headers
                    ) as response:
                        if response.status == 200:
                            session_data = await response.json()
                            if session_data.get("code") == 0 and session_data.get(
                                "data"
                            ):
                                session_id = session_data["data"]["id"]
                                self._cached_session_id = session_id
                            else:
                                logger.warning(
                                    "Failed to create RAGFlow session: %s", session_data
                                )
                        else:
                            logger.warning(
                                "Failed to create session, status: %s", response.status
                            )

                payload = {
                    "question": question,
                    "stream": False,
                    "session_id": session_id,
                }
                logger.debug(
                    "RAGFlow query: chat=%s, question=%s", chat_id, question[:50]
                )
                async with session.post(
                    completion_url, json=payload, headers=headers
                ) as response:
                    if response.status != 200:
                        logger.error(
                            "RAGFlow query failed with HTTP %s: %s",
                            response.status,
                            await response.text(),
                        )
                        return {"answer": "", "contexts": []}

                    result = await response.json()
                    if result.get("code") != 0 or not result.get("data"):
                        logger.error("RAGFlow returned an error: %s", result)
                        return {"answer": "", "contexts": []}

                    data = result["data"]
                    reference = data.get("reference") or {}
                    contexts = [
                        chunk.get("content", "")
                        for chunk in reference.get("chunks", [])
                        if chunk.get("content")
                    ]
                    raw_answer = data.get("answer", "")
                    cleaned_answer = re.sub(r"\[ID:\d+\]\s*", "", raw_answer)
                    cleaned_answer = re.sub(r"\s+", " ", cleaned_answer).strip()
                    return {
                        "answer": cleaned_answer,
                        "contexts": contexts,
                        "session_id": data.get("session_id", session_id),
                    }
        except asyncio.TimeoutError:
            logger.error("RAGFlow query timed out for question: %s", question[:50])
        except aiohttp.ClientError as error:
            logger.error("Network error querying RAGFlow: %s", error)
        except Exception:
            logger.exception("Failed to query RAGFlow")
        return {"answer": "", "contexts": []}

    def _process_results(
        self,
        results: Any,
        chat_id: str,
        dataset_id: str,
        rag_responses: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        处理评测结果

        Args:
            results: RAGAS 评测结果
            chat_id: 对话助手 ID
            dataset_id: 数据集 ID
            rag_responses: RAGFlow 响应列表（包含原始问题、答案等）

        Returns:
            格式化的评测结果
        """

        import pandas as pd
        import numpy as np

        scores_list = results.scores
        if scores_list:
            scores_df = pd.DataFrame(scores_list)
        else:
            scores_df = pd.DataFrame()
        overall_scores = {}
        for metric in scores_df.columns:
            if metric != "user_input" and (not scores_df[metric].isna().all()):
                valid_scores = scores_df[metric].dropna()
                if len(valid_scores) > 0:
                    mean_value = float(valid_scores.mean())
                    std_value = (
                        float(valid_scores.std()) if len(valid_scores) > 1 else 0.0
                    )
                    if np.isnan(std_value):
                        std_value = 0.0
                    overall_scores[metric] = {
                        "mean": mean_value,
                        "std": std_value,
                        "min": float(valid_scores.min()),
                        "max": float(valid_scores.max()),
                        "valid_count": len(valid_scores),
                        "total_count": len(scores_df[metric]),
                    }
        processed_scores = []
        if rag_responses and scores_list:
            for idx, (score_dict, rag_response) in enumerate(
                zip(scores_list, rag_responses)
            ):
                processed_dict = {}
                processed_dict["user_input"] = rag_response.get("original_question", "")
                processed_dict["actual_answer"] = rag_response.get("answer", "")
                processed_dict["expected_answer"] = rag_response.get(
                    "expected_answer", ""
                )
                processed_dict["contexts"] = rag_response.get("contexts", [])
                for key, value in score_dict.items():
                    if key != "user_input":
                        if pd.isna(value) or (
                            isinstance(value, float) and np.isnan(value)
                        ):
                            processed_dict[key] = None
                        else:
                            processed_dict[key] = value
                processed_scores.append(processed_dict)
        success_count = (
            len(
                [
                    s
                    for s in processed_scores
                    if any((v is not None for k, v in s.items()))
                ]
            )
            if processed_scores
            else 0
        )
        evaluation_result = {
            "chat_id": chat_id,
            "dataset_id": dataset_id,
            "timestamp": datetime.now().isoformat(),
            "overall_scores": overall_scores,
            "detailed_scores": processed_scores,
            "evaluation_metadata": {
                "llm_model": self.llm_model,
                "num_samples": len(scores_list),
                "metrics_used": list(overall_scores.keys()),
                "success_rate": (
                    f"{success_count} / {len(scores_list)}" if scores_list else "0 / 0"
                ),
                "success_count": success_count,
                "total_count": len(scores_list),
            },
        }
        return evaluation_result

    async def quick_evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        metric_name: str = "faithfulness",
    ) -> float:
        """
        快速评测单个问答对

        Args:
            question: 问题
            answer: 答案
            contexts: 上下文
            metric_name: 评测指标名称

        Returns:
            评分
        """

        if metric_name not in self.metrics_map:
            raise ValueError(f"Unknown metric: {metric_name}")
        else:
            metric = self.metrics_map[metric_name]
            sample = SingleTurnSample(
                user_input=question, response=answer, retrieved_contexts=contexts
            )
            score = await metric.single_turn_ascore(sample, llm=self._get_llm())
            return score

    def get_available_metrics(self) -> List[Dict[str, str]]:
        """
        获取可用的评测指标列表

        Returns:
            指标列表
        """

        metrics_info = [
            {
                "name": "faithfulness",
                "display_name": "忠实度",
                "description": "评估回答是否基于检索到的上下文",
                "type": "llm_based",
            },
            {
                "name": "answer_correctness",
                "display_name": "答案正确性",
                "description": "评估回答与参考答案的匹配程度",
                "type": "llm_based",
            },
            {
                "name": "context_precision",
                "display_name": "上下文精准度",
                "description": "评估检索到的上下文的相关性",
                "type": "llm_based",
            },
            {
                "name": "context_recall",
                "display_name": "上下文召回率",
                "description": "评估是否检索到所有相关信息",
                "type": "llm_based",
            },
            {
                "name": "answer_relevancy",
                "display_name": "答案相关性",
                "description": "评估回答与问题的相关程度",
                "type": "llm_based",
            },
        ]
        available_metrics = [m for m in metrics_info if m["name"] in self.metrics_map]
        return available_metrics


from config import get_config_service

config_service = get_config_service()
api_config = config_service.get_api_config()
evaluation_service = EvaluationService(
    llm_model=config_service.get_llm_model(),
    ragflow_url=config_service.get_ragflow_url(),
    api_config=api_config,
)
