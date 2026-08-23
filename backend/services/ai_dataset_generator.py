"""Generate strictly simplified-Chinese evaluation datasets from knowledge chunks."""

from __future__ import annotations

import json
import logging
import random
import re
import sqlite3
from json import JSONDecodeError
from typing import Any, Dict, List, Optional

from opencc import OpenCC

logger = logging.getLogger(__name__)

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_REFUSAL_TEXTS = {"无法生成", "内容不足", "无法回答", "信息不足"}


class AIDatasetGenerator:
    """LLM dataset generator with strict structured simplified-Chinese output."""

    def __init__(self):
        self._to_simplified = OpenCC("t2s")
        self.last_generation_error: str | None = None
        self.generation_stats: dict[str, int] = {}

    def _record_rejection(
        self, category: str, question_type: str, chunk_id: str, attempt: int
    ) -> None:
        self.generation_stats[category] = self.generation_stats.get(category, 0) + 1
        logger.warning(
            "QA generation rejected category=%s question_type=%s chunk_id=%s attempt=%d",
            category,
            question_type,
            chunk_id,
            attempt,
        )

    def get_knowledge_base_chunks(
        self, provider, kb_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        try:
            logger.info(
                "Getting chunks from KB %s via provider %s",
                kb_id,
                type(provider).__name__,
            )
            chunks = provider.get_chunks(kb_id, limit)
            if chunks:
                logger.info(
                    "Successfully retrieved %d chunks from KB %s", len(chunks), kb_id
                )
            else:
                logger.warning("No chunks found in KB %s", kb_id)
            return chunks
        except Exception as error:
            logger.error("Error getting chunks from KB %s: %s", kb_id, error)
            return []

    def call_llm_for_generation(self, prompt: str) -> Optional[str]:
        """Call the saved default LLM configuration without logging credentials."""
        try:
            from langchain_openai import ChatOpenAI

            db_path = __import__("os").getenv("DATABASE_PATH", "data/evaluation.db")
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT provider, api_key, endpoint, model, temperature, max_tokens "
                "FROM api_configs WHERE is_default = 1 LIMIT 1"
            ).fetchone()
            conn.close()
            if not row:
                logger.error("No default API configuration found")
                return None
            provider, api_key, endpoint, model, temperature, max_tokens = row
            try:
                configured_max_tokens = int(max_tokens)
            except (TypeError, ValueError):
                configured_max_tokens = 2000
            # Preserve a user-configured budget above this threshold.  Below it,
            # reserve enough output for providers that expose a reasoning trace
            # before their final JSON object.
            effective_max_tokens = max(2048, min(configured_max_tokens, 8192))
            logger.info(
                "Using LLM model=%s provider=%s max_tokens=%d for AI dataset generation",
                model,
                provider,
                effective_max_tokens,
            )
            response = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=endpoint,
                temperature=temperature,
                max_tokens=effective_max_tokens,
                timeout=30,
            ).invoke(prompt)
            content = str(response.content or "")
            logger.info("LLM generation successful, response length: %d", len(content))
            return content
        except Exception as error:
            logger.error("LLM generation failed: %s", error)
            return None

    @staticmethod
    def _strip_code_fence(value: str) -> str:
        value = value.strip()
        if value.startswith("```"):
            first_newline = value.find("\n")
            if first_newline >= 0:
                value = value[first_newline + 1 :]
            if value.rstrip().endswith("```"):
                value = value.rstrip()[:-3]
        return value.strip()

    def _extract_json_object(self, response: str) -> Optional[dict[str, Any]]:
        """Extract the final structured QA object from a possibly verbose response.

        Some compatible providers prepend a visible reasoning trace.  That trace can
        quote JSON examples from the prompt, including an error object, so parsing
        the first JSON dictionary is not reliable.  Only a dictionary with all
        required QA fields qualifies, and the final such dictionary wins.
        """
        cleaned = self._strip_code_fence(response)
        decoder = json.JSONDecoder()
        qa_candidates: list[dict[str, Any]] = []
        for index, char in enumerate(cleaned):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
            except JSONDecodeError:
                continue
            if (
                isinstance(value, dict)
                and {"question", "expected_answer", "context"} <= value.keys()
            ):
                qa_candidates.append(value)
        return qa_candidates[-1] if qa_candidates else None

    def _is_structured_refusal(self, response: str) -> bool:
        """Return true only if the complete response is a supported refusal JSON."""
        cleaned = self._strip_code_fence(response)
        try:
            value, end_index = json.JSONDecoder().raw_decode(cleaned)
        except JSONDecodeError:
            return False
        if cleaned[end_index:].strip() or not isinstance(value, dict):
            return False
        error = self._normalize_simplified_chinese(value.get("error"))
        return error in _REFUSAL_TEXTS

    def _normalize_simplified_chinese(self, value: Any) -> str:
        return self._to_simplified.convert(str(value or "").strip())

    def _is_simplified_chinese_content(self, value: str, minimum_cjk: int) -> bool:
        compact = re.sub(r"[\s\d\W_]", "", value, flags=re.UNICODE)
        cjk_count = len(_CHINESE_RE.findall(value))
        if cjk_count < minimum_cjk or not compact:
            return False
        if _ASCII_LETTER_RE.search(value):
            return False
        return cjk_count / len(compact) >= 0.8

    @staticmethod
    def _is_exact_refusal(value: str) -> bool:
        normalized = value.strip().strip("。！？! ")
        return normalized in _REFUSAL_TEXTS

    def _build_prompt(self, content: str, question_type: str) -> str:
        question_type_map = {
            "factual": "事实性问题",
            "analytical": "分析性问题",
            "application": "应用性问题",
            "comparison": "比较性问题",
            "explanation": "解释性问题",
        }
        return f"""你是专业的中文知识库问答数据生成助手。请仅根据以下文档内容生成一个{question_type_map.get(question_type, '事实性问题')}问答对。

文档内容：
{content}

严格要求：
1. 源文档可能是中文、英文或混合语言。无论源文档语言，question、expected_answer、context 三个字段都必须使用简体中文，不能包含英文、繁体中文或其他语言描述。
2. question 长度必须为 5-100 个字符，清晰且可由文档回答。
3. expected_answer 长度必须为 20-500 个字符，只能依据文档内容；源文档为英文时可忠实翻译为简体中文。
4. context 长度必须为 20-800 个字符，是支持答案的简体中文上下文；源文档为英文时可使用忠实的简体中文翻译或摘要。
5. 只输出一个 JSON 对象，不要 Markdown、解释、前缀或后缀。
6. 不要输出思考过程、分析步骤、推理内容或提示词复述。
7. 文档内容不足以生成时，只输出一个 JSON 错误对象，error 字段值为“内容不足”。
8. 成功时，JSON 对象必须且只能包含 question、expected_answer、context 三个字符串字段。"""

    def generate_qa_pair_with_llm(
        self,
        chunk: Dict[str, Any],
        question_type: str,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """Generate one validated simplified-Chinese QA pair from one chunk."""
        content = self._normalize_simplified_chinese(chunk.get("content", ""))
        chunk_id = str(chunk.get("id", ""))
        doc_name = self._normalize_simplified_chinese(chunk.get("doc_name", "未知文档"))
        if len(content.strip()) < 50:
            self._record_rejection("source_chunk_too_short", question_type, chunk_id, 0)
            return None

        prompt = self._build_prompt(content, question_type)
        for attempt in range(1, max_retries + 1):
            response = self.call_llm_for_generation(prompt)
            if not response:
                self._record_rejection(
                    "llm_transport_failure", question_type, chunk_id, attempt
                )
                continue

            normalized_response = self._normalize_simplified_chinese(response)
            if self._is_exact_refusal(
                normalized_response
            ) or self._is_structured_refusal(response):
                self._record_rejection(
                    "content_insufficient", question_type, chunk_id, attempt
                )
                return None

            qa_data = self._extract_json_object(response)
            if qa_data is None:
                self._record_rejection(
                    "json_parse_error", question_type, chunk_id, attempt
                )
                continue

            question = self._normalize_simplified_chinese(qa_data.get("question"))
            expected_answer = self._normalize_simplified_chinese(
                qa_data.get("expected_answer")
            )
            context = self._normalize_simplified_chinese(
                qa_data.get("context") or content
            )
            if not 5 <= len(question) <= 100:
                self._record_rejection(
                    "invalid_question_length", question_type, chunk_id, attempt
                )
                continue
            if not 20 <= len(expected_answer) <= 500:
                self._record_rejection(
                    "invalid_answer_length", question_type, chunk_id, attempt
                )
                continue
            if not 20 <= len(context) <= 800:
                self._record_rejection(
                    "invalid_context_length", question_type, chunk_id, attempt
                )
                continue
            if not (
                self._is_simplified_chinese_content(question, 5)
                and self._is_simplified_chinese_content(expected_answer, 20)
                and self._is_simplified_chinese_content(context, 20)
            ):
                self._record_rejection(
                    "non_simplified_chinese_output", question_type, chunk_id, attempt
                )
                continue

            return {
                "question": question,
                "expected_answer": expected_answer,
                "contexts": [context],
                "source_doc": doc_name,
                "question_type": question_type,
                "chunk_id": chunk_id,
                "generation_method": "llm",
                "attempts_used": attempt,
            }

        self._record_rejection(
            "retries_exhausted", question_type, chunk_id, max_retries
        )
        return None

    def generate_dataset_from_kb(
        self, provider, kb_id: str, sample_count: int, question_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate exactly the requested number of valid simplified-Chinese samples."""
        self.last_generation_error = None
        self.generation_stats = {}
        try:
            logger.info(
                "Starting AI dataset generation for KB %s, %d samples",
                kb_id,
                sample_count,
            )
            chunks = self.get_knowledge_base_chunks(
                provider, kb_id, limit=min(500, sample_count * 50)
            )
            if not chunks:
                self.last_generation_error = "知识库未提供可用内容块"
                return []

            candidates = [
                chunk
                for chunk in chunks
                if len(str(chunk.get("content", "")).strip()) >= 50
            ]
            if not candidates:
                self.last_generation_error = "知识库中没有长度足够的内容块用于生成问答"
                return []

            samples: list[dict[str, Any]] = []
            failed_chunk_ids: set[str] = set()
            used_chunk_ids: set[str] = set()
            for index in range(sample_count):
                logger.info("Generating sample %d/%d...", index + 1, sample_count)
                qa_pair = None
                question_type = random.choice(question_types or ["factual"])
                available = [
                    chunk
                    for chunk in candidates
                    if str(chunk.get("id", "")) not in failed_chunk_ids
                    and str(chunk.get("id", "")) not in used_chunk_ids
                ]
                max_chunk_tries = min(15, len(available))
                for _ in range(max_chunk_tries):
                    if not available:
                        break
                    chunk = random.choice(available)
                    chunk_id = str(chunk.get("id", ""))
                    available = [
                        item
                        for item in available
                        if str(item.get("id", "")) != chunk_id
                    ]
                    logger.info(
                        "Trying chunk %s for sample %d (content length: %d chars)",
                        chunk_id,
                        index + 1,
                        len(str(chunk.get("content", ""))),
                    )
                    qa_pair = self.generate_qa_pair_with_llm(
                        chunk, question_type, max_retries=2
                    )
                    if qa_pair:
                        used_chunk_ids.add(chunk_id)
                        logger.info(
                            "Generated valid simplified-Chinese QA pair using chunk %s",
                            chunk_id,
                        )
                        break
                    failed_chunk_ids.add(chunk_id)

                if not qa_pair:
                    self.last_generation_error = f"只能生成 {len(samples)}/{sample_count} 个符合简体中文要求的有效样本"
                    logger.error(
                        "AI dataset generation stopped: %s", self.last_generation_error
                    )
                    return []
                samples.append(qa_pair)

            logger.info(
                "Generation completed: %d/%d samples; rejection_stats=%s",
                len(samples),
                sample_count,
                self.generation_stats,
            )
            return samples
        except Exception as error:
            logger.exception("Failed to generate dataset from KB %s", kb_id)
            self.last_generation_error = f"AI 数据集生成异常：{str(error)[:300]}"
            return []
