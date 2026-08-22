import json
import logging
import random
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AIDatasetGenerator:
    """AI dataset generator — purely LLM-based, no templates.

    The caller provides a RagProvider instance so chunk retrieval is
    provider-agnostic instead of being hardcoded to RAGFlow.
    """

    def __init__(self):
        pass

    def get_knowledge_base_chunks(
        self, provider, kb_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks from a knowledge base through the given provider.

        Returns empty list when the provider returns no chunks (no mock fallback for real providers).
        """
        try:
            logger.info("Getting chunks from KB %s via provider %s", kb_id, type(provider).__name__)
            chunks = provider.get_chunks(kb_id, limit)
            if chunks:
                logger.info("Successfully retrieved %d chunks from KB %s", len(chunks), kb_id)
            else:
                logger.warning("No chunks found in KB %s", kb_id)
            return chunks
        except Exception as e:
            logger.error("Error getting chunks from KB %s: %s", kb_id, e)
            return []

    def _get_mock_chunks(self) -> List[Dict[str, Any]]:
        """获取模拟chunks数据用于测试"""
        return [
            {
                "id": "chunk_1",
                "content": "人工智能（Artificial Intelligence, AI）是指通过计算机系统模拟、延伸和扩展人类智能的技术。AI系统能够执行通常需要人类智能才能完成的任务，如视觉感知、语音识别、决策制定和语言翻译等。深度学习是当前AI领域最主流的技术路线，通过多层神经网络从海量数据中自动学习特征表示，在图像识别、自然语言处理等领域取得了突破性进展。",
                "doc_name": "AI基础知识.pdf",
                "page_number": 1,
            },
            {
                "id": "chunk_2",
                "content": "机器学习是人工智能的一个重要分支，它使计算机能够在没有明确编程的情况下学习和改进性能。机器学习算法通过分析大量数据来识别模式，并基于这些模式做出预测或决策。常见的机器学习算法包括决策树、支持向量机、随机森林和神经网络等。监督学习、无监督学习和强化学习是机器学习的三大主要范式，各自适用于不同的应用场景。",
                "doc_name": "机器学习指南.pdf",
                "page_number": 2,
            },
        ]

    def call_llm_for_generation(self, prompt: str) -> Optional[str]:
        """调用大模型生成内容"""
        try:
            import sqlite3
            import os
            from langchain_openai import ChatOpenAI

            db_path = os.getenv("DATABASE_PATH", "data/evaluation.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_configs WHERE is_default = 1 LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            if not result:
                logger.error("No default API configuration found")
                return
            else:
                (
                    _,
                    _,
                    provider,
                    api_key,
                    endpoint,
                    model,
                    _,
                    temperature,
                    max_tokens,
                    _,
                    _,
                    _,
                ) = result
                logger.info(f"Using LLM: {model} from {provider}")
                llm = ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    base_url=endpoint,
                    temperature=temperature,
                    max_tokens=min(max_tokens, 1000),
                    timeout=30,
                )
                response = llm.invoke(prompt)
                logger.info(
                    f"LLM generation successful, response length: {len(response.content)}"
                )
                return response.content
        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            return None

    def generate_qa_pair_with_llm(
        self,
        chunk: Dict[str, Any],
        question_type: str,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """使用 LLM 生成并校验一个问答对。"""
        content = chunk.get("content", "").strip()
        doc_name = chunk.get("doc_name", "未知文档")
        question_type_map = {
            "factual": "事实性问题（询问具体信息、定义、事实等）",
            "analytical": "分析性问题（要求分析原理、机制、过程等）",
            "application": "应用性问题（询问如何使用、应用场景等）",
            "comparison": "比较性问题（对比不同概念、方法的异同）",
            "explanation": "解释性问题（询问原因、背景、重要性等）",
        }
        question_desc = question_type_map.get(question_type, question_type)
        prompt = f"""你是专业的问答生成助手。基于以下文档内容生成{question_desc}。

文档内容：
{content}

严格要求：
1. 问题必须清晰明确，长度在5-100字之间。
2. 答案必须来自文档原文，长度在20-500字之间。
3. 问题和答案必须来自同一段文档内容。
4. 如果内容不足，请回复“无法生成”。

请严格返回 JSON：{{"question": "问题", "expected_answer": "摘录的原文"}}"""

        for attempt in range(max_retries):
            response = self.call_llm_for_generation(prompt)
            if not response:
                logger.warning("LLM generation failed, attempt %s", attempt + 1)
                continue
            if "无法生成" in response:
                logger.info("LLM determined insufficient content for %s", question_type)
                return None

            response = response.strip()
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            try:
                qa_data = json.loads(response)
            except json.JSONDecodeError as error:
                logger.warning("JSON parse error (attempt %s): %s", attempt + 1, error)
                continue

            if isinstance(qa_data, list):
                qa_data = (
                    qa_data[0] if qa_data and isinstance(qa_data[0], dict) else None
                )
            if not isinstance(qa_data, dict):
                logger.warning("Invalid response type on attempt %s", attempt + 1)
                continue

            question = str(qa_data.get("question", "")).strip()
            expected_answer = str(qa_data.get("expected_answer", "")).strip()
            if not 5 <= len(question) <= 150:
                logger.warning("Question length invalid on attempt %s", attempt + 1)
                continue
            if not 10 <= len(expected_answer) <= 800:
                logger.warning("Answer length invalid on attempt %s", attempt + 1)
                continue
            if len(expected_answer.replace("#", "").replace("\n", "").strip()) < 20:
                logger.warning("Answer is too simple on attempt %s", attempt + 1)
                continue

            return {
                "question": question,
                "expected_answer": expected_answer,
                "contexts": [content],
                "source_doc": doc_name,
                "question_type": question_type,
                "chunk_id": chunk.get("id", ""),
                "generation_method": "llm",
                "attempts_used": attempt + 1,
            }

        logger.warning(
            "Failed to generate a valid QA pair after %s attempts", max_retries
        )
        return None

    def generate_dataset_from_kb(
        self, provider, kb_id: str, sample_count: int, question_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate a dataset from a knowledge base through the given provider."""
        try:
            logger.info(
                "Starting AI dataset generation for KB %s, %d samples", kb_id, sample_count
            )
            chunks = self.get_knowledge_base_chunks(
                provider, kb_id, limit=min(500, sample_count * 50)
            )
            if not chunks:
                logger.error("No chunks retrieved from knowledge base")
                return []
            else:
                logger.info(f"Retrieved {len(chunks)} chunks from knowledge base")
                samples = []
                failed_chunks = set()
                chunk_attempt_count = {}
                for i in range(sample_count):
                    logger.info(f"Generating sample {i + 1}/{sample_count}...")
                    question_type = random.choice(question_types)
                    qa_pair = None
                    max_chunk_tries = 10
                    for _ in range(max_chunk_tries):
                        available_chunks = [
                            c
                            for c in chunks
                            if not c.get("id") in failed_chunks
                            or chunk_attempt_count.get(c.get("id"), 0) == 0
                        ]
                        if not available_chunks:
                            logger.warning(
                                f"No more available chunks for sample {i + 1}"
                            )
                            break
                        else:
                            chunk = random.choice(available_chunks)
                            chunk_id = chunk.get("id")
                            chunk_content = chunk.get("content", "")
                            chunk_attempt_count[chunk_id] = 1
                            if len(chunk_content) < 128:
                                logger.info(
                                    f"Skipping chunk {chunk_id}: too short ({len(chunk_content)} chars)"
                                )
                                failed_chunks.add(chunk_id)
                                continue
                            else:
                                cleaned_content = (
                                    chunk_content.replace("#", "")
                                    .replace("\n", "")
                                    .replace(" ", "")
                                    .strip()
                                )
                                if len(cleaned_content) < 50:
                                    logger.info(
                                        f"Skipping chunk {chunk_id}: insufficient content after cleaning"
                                    )
                                    failed_chunks.add(chunk_id)
                                    continue
                                else:
                                    logger.info(
                                        f"Trying chunk {chunk_id} for sample {i + 1} (content length: {len(chunk_content)} chars)"
                                    )
                                    qa_pair = self.generate_qa_pair_with_llm(
                                        chunk, question_type, max_retries=1
                                    )
                                    if qa_pair:
                                        logger.info(
                                            f"✅ Successfully generated QA pair using chunk {chunk_id}"
                                        )
                                        break
                                    else:
                                        logger.warning(
                                            f"❌ Failed to generate valid QA pair from chunk {chunk_id}"
                                        )
                                        failed_chunks.add(chunk_id)
                    if qa_pair:
                        samples.append(qa_pair)
                    else:
                        logger.warning(
                            f"Failed to generate sample {i + 1} after trying multiple chunks"
                        )
                logger.info(f"Generation completed: {len(samples)} total samples")
                logger.info(f"  - Failed chunks: {len(failed_chunks)}")
                return samples
        except Exception as e:
            logger.error(f"Failed to generate dataset from KB {kb_id}: {str(e)}")
            import traceback

            logger.error(f"Detailed error: {traceback.format_exc()}")
            return []
