import json
import logging
import random
import requests
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AIDatasetGenerator:
    """AI数据集生成器 - 完全基于LLM生成，无模板"""

    def __init__(self):
        self.ragflow_base_url = (
            os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380") + "/api/v1"
        )
        self.ragflow_api_key = os.getenv("RAGFLOW_API_KEY", "")
        if not self.ragflow_api_key:
            try:
                import yaml

                with open("conf/service_conf.yaml", "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    self.ragflow_api_key = config.get("ragflow", {}).get("api_key", "")
            except Exception as e:
                logger.warning(f"Failed to load RAGFlow API key from config: {str(e)}")
        if not self.ragflow_api_key:
            logger.warning("RAGFlow API key not found.")
        else:
            logger.info("RAGFlow API key loaded successfully")

    def get_knowledge_base_chunks(
        self, kb_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取知识库的chunks\n        \n        Args:\n            kb_id: 知识库ID (dataset_id)，直接从 RAGFlow dataset 获取 chunks\n            limit: 最多返回的 chunks 数量\n"""
        try:
            logger.info(f"Getting chunks from knowledge base (dataset_id): {kb_id}")
            chunks = self._get_chunks_from_dataset(kb_id, limit)
            if chunks:
                logger.info(
                    f"Successfully retrieved {len(chunks)} chunks from dataset {kb_id}"
                )
                return chunks
            else:
                logger.warning(f"No chunks found in dataset {kb_id}, using mock data")
                return self._get_mock_chunks()
        except Exception as e:
            logger.error(f"Error getting chunks from knowledge base {kb_id}: {str(e)}")
            return self._get_mock_chunks()

    def _get_chunks_from_dataset(
        self, dataset_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """从指定数据集获取chunks"""
        try:
            chunks = []
            docs_url = f"{self.ragflow_base_url}/datasets/{dataset_id}/documents"
            headers = {"Content-Type": "application/json"}
            if self.ragflow_api_key:
                headers["Authorization"] = f"Bearer {self.ragflow_api_key}"
            params = {"page": 1, "page_size": 50}
            response = requests.get(
                docs_url, headers=headers, params=params, timeout=30
            )
            if response.status_code != 200:
                return []
            else:
                docs_data = response.json()
                if docs_data.get("code") != 0:
                    return []
                else:
                    documents = docs_data.get("data", {}).get("docs", [])
                    if not documents:
                        return []
                    else:
                        chunks_per_doc = max(1, limit // len(documents))
                        for doc in documents[:10]:
                            doc_id = doc.get("id")
                            doc_name = doc.get("name", "未知文档")
                            if not doc_id:
                                continue
                            else:
                                doc_chunks = self._get_chunks_from_document(
                                    dataset_id, doc_id, doc_name, chunks_per_doc
                                )
                                chunks.extend(doc_chunks)
                                if len(chunks) >= limit:
                                    break
                        return chunks[:limit]
        except Exception as e:
            logger.error(f"Error getting chunks from dataset {dataset_id}: {str(e)}")
            return []

    def _get_chunks_from_document(
        self, dataset_id: str, document_id: str, doc_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """从指定文档获取chunks"""
        try:
            chunks_url = f"{self.ragflow_base_url}/datasets/{dataset_id}/documents/{document_id}/chunks"
            headers = {"Content-Type": "application/json"}
            if self.ragflow_api_key:
                headers["Authorization"] = f"Bearer {self.ragflow_api_key}"
            params = {"page": 1, "page_size": limit}
            response = requests.get(
                chunks_url, headers=headers, params=params, timeout=30
            )
            if response.status_code != 200:
                return []
            else:
                chunks_data = response.json()
                if chunks_data.get("code") != 0:
                    return []
                else:
                    raw_chunks = chunks_data.get("data", {}).get("chunks", [])
                    processed_chunks = []
                    for chunk in raw_chunks:
                        processed_chunk = {
                            "id": chunk.get("id", ""),
                            "content": chunk.get("content", ""),
                            "doc_name": doc_name,
                            "doc_id": document_id,
                            "dataset_id": dataset_id,
                            "page_number": chunk.get("page_number", 0),
                            "positions": chunk.get("positions", []),
                            "create_time": chunk.get("create_time", ""),
                            "update_time": chunk.get("update_time", ""),
                        }
                        if processed_chunk["content"].strip():
                            processed_chunks.append(processed_chunk)
                    return processed_chunks
        except Exception as e:
            logger.error(f"Error getting chunks from document {document_id}: {str(e)}")
            return []

    def _get_mock_chunks(self) -> List[Dict[str, Any]]:
        """获取模拟chunks数据用于测试"""
        return [
            {
                "id": "chunk_1",
                "content": "人工智能（Artificial Intelligence, AI）是指通过计算机系统模拟、延伸和扩展人类智能的技术。AI系统能够执行通常需要人类智能才能完成的任务，如视觉感知、语音识别、决策制定和语言翻译等。",
                "doc_name": "AI基础知识.pdf",
                "page_number": 1,
            },
            {
                "id": "chunk_2",
                "content": "机器学习是人工智能的一个重要分支，它使计算机能够在没有明确编程的情况下学习和改进性能。机器学习算法通过分析大量数据来识别模式，并基于这些模式做出预测或决策。",
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

            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "evaluation.db")
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
        self, kb_id: str, sample_count: int, question_types: List[str]
    ) -> List[Dict[str, Any]]:
        """基于知识库生成数据集 - 完全使用LLM生成，无模板"""
        try:
            logger.info(
                f"Starting AI dataset generation for KB {kb_id}, {sample_count} samples"
            )
            chunks = self.get_knowledge_base_chunks(
                kb_id, limit=min(500, sample_count * 50)
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
