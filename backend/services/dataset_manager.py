"""
评测数据集管理器
负责管理评测数据集的上传、解析、存储和检索
"""

import os
import json
import logging
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
from pathlib import Path
import aiofiles
import chardet

logger = logging.getLogger(__name__)


class DatasetManager:
    """
    评测数据集管理器
    支持多种格式的数据集上传和管理
    """

    def __init__(self, storage_path: str = "/data/evaluation/datasets"):
        """
        初始化数据集管理器

        Args:
            storage_path: 数据集存储路径
        """

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"DatasetManager initialized with storage path: {storage_path}")

    async def upload_dataset(
        self,
        file_content: bytes,
        file_name: str,
        dataset_name: str,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        上传评测数据集

        Args:
            file_content: 文件内容
            file_name: 文件名
            dataset_name: 数据集名称
            description: 数据集描述
            user_id: 用户 ID

        Returns:
            数据集信息
        """

        try:
            dataset_id = str(uuid.uuid4())
            file_extension = Path(file_name).suffix.lower()
            dataset_dir = self.storage_path / dataset_id
            dataset_dir.mkdir(exist_ok=True)
            original_file_path = dataset_dir / f"original{file_extension}"
            async with aiofiles.open(original_file_path, "wb") as f:
                await f.write(file_content)
            samples = await self._parse_dataset(file_content, file_extension)
            processed_file_path = dataset_dir / "processed.json"
            async with aiofiles.open(processed_file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(samples, ensure_ascii=False, indent=2))
            metadata = {
                "id": dataset_id,
                "name": dataset_name,
                "description": description,
                "file_name": file_name,
                "file_type": file_extension,
                "num_samples": len(samples),
                "has_reference": any(
                    ("expected_answer" in s or "reference" in s for s in samples)
                ),
                "has_contexts": any(
                    ("contexts" in s or "reference_contexts" in s for s in samples)
                ),
                "created_at": datetime.now().isoformat(),
                "created_by": str(dataset_dir) if samples else [],
                "storage_path": str(dataset_dir) if dataset_dir else [],
                "sample_fields": str(dataset_dir) if dataset_dir else [],
            }
            metadata_file = dataset_dir / "metadata.json"
            async with aiofiles.open(metadata_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
            logger.info(
                f"Dataset {dataset_id} uploaded successfully with {len(samples)} samples"
            )
            return metadata
        except Exception as e:
            logger.error(f"Failed to upload dataset: {str(e)}")
            raise

    async def _parse_dataset(
        self, file_content: bytes, file_extension: str
    ) -> List[Dict]:
        """
        解析不同格式的数据集文件

        Args:
            file_content: 文件内容
            file_extension: 文件扩展名

        Returns:
            解析后的样本列表
        """

        samples = []
        if file_extension in [".csv"]:
            samples = self._parse_csv(file_content)
        else:
            if file_extension in [".json", ".jsonl"]:
                samples = self._parse_json(file_content)
            else:
                if file_extension in [".xlsx", ".xls"]:
                    samples = self._parse_excel(file_content)
                else:
                    if file_extension in [".txt"]:
                        samples = self._parse_text(file_content)
                    else:
                        raise ValueError(f"Unsupported file type: {file_extension}")
        samples = self._standardize_samples(samples)
        return samples

    def _parse_csv(self, file_content: bytes) -> List[Dict]:
        """解析 CSV 文件"""
        encoding = chardet.detect(file_content)["encoding"] or "utf-8"
        import io

        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
        samples = df.to_dict("records")
        return samples

    def _parse_json(self, file_content: bytes) -> List[Dict]:
        """解析 JSON/JSONL 文件"""
        content = file_content.decode("utf-8")
        samples = []
        try:
            samples = json.loads(content)
            if not isinstance(samples, list):
                samples = [samples]
        except json.JSONDecodeError:
            for line in content.strip().split("\n"):
                if line.strip():
                    samples.append(json.loads(line))
        return samples

    def _parse_excel(self, file_content: bytes) -> List[Dict]:
        """解析 Excel 文件"""
        import io

        df = pd.read_excel(io.BytesIO(file_content))
        samples = df.to_dict("records")
        return samples

    def _parse_text(self, file_content: bytes) -> List[Dict]:
        """解析纯文本文件（每行一个问题）"""
        content = file_content.decode("utf-8")
        samples = []
        for line in content.strip().split("\n"):
            if line.strip():
                samples.append({"question": line.strip()})
        return samples

    def _standardize_samples(self, samples: List[Dict]) -> List[Dict]:
        """
        标准化样本字段名

        Args:
            samples: 原始样本列表

        Returns:
            标准化后的样本列表
        """

        field_mappings = {
            "query": "question",
            "prompt": "question",
            "input": "question",
            "answer": "expected_answer",
            "reference": "expected_answer",
            "ground_truth": "expected_answer",
            "context": "contexts",
            "documents": "contexts",
            "reference_context": "reference_contexts",
            "golden_contexts": "reference_contexts",
        }
        standardized = []
        for sample in samples:
            new_sample = {}
            for key, value in sample.items():
                standardized_key = field_mappings.get(key.lower(), key)
                new_sample[standardized_key] = value
            if "question" not in new_sample:
                logger.warning(f"Sample missing 'question' field: {new_sample}")
                continue
            else:
                if "contexts" in new_sample and isinstance(new_sample["contexts"], str):
                    new_sample["contexts"] = [new_sample["contexts"]]
                if "reference_contexts" in new_sample and isinstance(
                    new_sample["reference_contexts"], str
                ):
                    new_sample["reference_contexts"] = [
                        new_sample["reference_contexts"]
                    ]
                standardized.append(new_sample)
        return standardized

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        获取数据集信息

        Args:
            dataset_id: 数据集 ID

        Returns:
            数据集信息
        """

        dataset_dir = self.storage_path / dataset_id
        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset {dataset_id} not found")
        else:
            metadata_file = dataset_dir / "metadata.json"
            async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.loads(await f.read())
            return metadata
            return metadata

    async def get_dataset_samples(
        self, dataset_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Dict]:
        """
        获取数据集样本

        Args:
            dataset_id: 数据集 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            样本列表
        """

        dataset_dir = self.storage_path / dataset_id
        processed_file = dataset_dir / "processed.json"
        if not processed_file.exists():
            raise FileNotFoundError(f"Dataset samples not found for {dataset_id}")
        else:
            async with aiofiles.open(processed_file, "r", encoding="utf-8") as f:
                samples = json.loads(await f.read())
        if limit:
            samples = samples[offset : offset + limit]
            return samples
        else:
            samples = samples[offset:]
            return samples

    async def list_datasets(
        self, user_id: Optional[str] = None, offset: int = 0, limit: int = 20
    ) -> Dict[str, Any]:
        """
        列出数据集

        Args:
            user_id: 用户 ID（可选，用于过滤）
            offset: 偏移量
            limit: 限制数量

        Returns:
            数据集列表
        """

        datasets = []
        for dataset_dir in self.storage_path.iterdir():
            if dataset_dir.is_dir():
                metadata_file = dataset_dir / "metadata.json"
                if metadata_file.exists():
                    async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.loads(await f.read())
                    if user_id and metadata.get("created_by") != user_id:
                        continue
                    datasets.append(metadata)
        datasets.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        total = len(datasets)
        datasets = datasets[offset : offset + limit]
        return {"datasets": datasets, "total": total, "offset": offset, "limit": limit}

    async def delete_dataset(self, dataset_id: str) -> bool:
        """
        删除数据集

        Args:
            dataset_id: 数据集 ID

        Returns:
            是否删除成功
        """

        dataset_dir = self.storage_path / dataset_id
        if not dataset_dir.exists():
            return False
        else:
            import shutil

            shutil.rmtree(dataset_dir)
            logger.info(f"Dataset {dataset_id} deleted")
            return True

    async def generate_sample_dataset(
        self, dataset_type: str = "basic"
    ) -> Dict[str, Any]:
        """Generate and persist a small sample dataset."""
        basic_questions = [
            "What is RAGFlow?",
            "How does RAG work?",
            "What are the benefits of using RAG?",
            "How to install RAGFlow?",
            "What databases does RAGFlow support?",
        ]
        answers = [
            "RAGFlow is an open-source RAG engine for deep document understanding.",
            "RAG retrieves relevant documents and then generates an answer from that context.",
            "RAG improves grounding, reduces hallucinations, and reuses existing knowledge.",
            "RAGFlow can be installed with Docker or from a configured Python source environment.",
            "RAGFlow supports Elasticsearch and integrations with vector databases such as Milvus.",
        ]
        contexts = [
            ["RAGFlow is an open-source retrieval-augmented generation engine."],
            ["RAG first retrieves documents and then generates a grounded answer."],
            ["Grounded retrieval improves accuracy and reduces hallucinations."],
            ["RAGFlow supports Docker deployment and source-based installation."],
            ["RAGFlow uses search and vector database components for retrieval."],
        ]

        if dataset_type == "basic":
            samples = [{"question": question} for question in basic_questions]
        elif dataset_type == "with_reference":
            samples = [
                {"question": question, "expected_answer": answer}
                for question, answer in zip(basic_questions, answers)
            ]
        elif dataset_type == "with_contexts":
            samples = [
                {
                    "question": question,
                    "expected_answer": answer,
                    "contexts": sample_contexts,
                    "reference_contexts": sample_contexts,
                }
                for question, answer, sample_contexts in zip(
                    basic_questions, answers, contexts
                )
            ]
        else:
            raise ValueError(f"Unsupported sample dataset type: {dataset_type}")

        content = json.dumps(samples, ensure_ascii=False).encode("utf-8")
        return await self.upload_dataset(
            file_content=content,
            file_name="sample.json",
            dataset_name=f"Sample Dataset - {dataset_type}",
            description=f"Auto-generated sample dataset of type: {dataset_type}",
            user_id="system",
        )

# Provider-integration upload contract (synchronous helper used by active routes)
MAX_DATASET_BYTES = 10 * 1024 * 1024
SUPPORTED_DATASET_EXTENSIONS = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}


def normalize_dataset_bytes(file_content: bytes, file_name: str) -> tuple[list[dict], dict]:
    """Parse supported dataset formats into the canonical list-of-records shape."""
    from io import BytesIO
    import pandas as pd

    if len(file_content) > MAX_DATASET_BYTES:
        raise OverflowError("数据集文件不能超过 10 MB")
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_DATASET_EXTENSIONS:
        raise TypeError(f"不支持的数据集格式: {suffix or 'unknown'}")
    if suffix in {".json", ".jsonl"}:
        decoded = file_content.decode("utf-8-sig")
        if suffix == ".json":
            samples = json.loads(decoded)
            if isinstance(samples, dict):
                samples = [samples]
        else:
            samples = [json.loads(line) for line in decoded.splitlines() if line.strip()]
    elif suffix == ".csv":
        samples = pd.read_csv(BytesIO(file_content)).where(pd.notna, None).to_dict("records")
    else:
        samples = pd.read_excel(BytesIO(file_content)).where(pd.notna, None).to_dict("records")
    if not isinstance(samples, list) or not samples:
        raise ValueError("数据集必须至少包含一个样本")
    normalized = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"第 {index + 1} 个样本不是对象")
        question = sample.get("question", sample.get("user_input"))
        if question is None or not str(question).strip():
            raise ValueError(f"第 {index + 1} 个样本缺少 question")
        item = dict(sample)
        item["question"] = str(question).strip()
        if "contexts" in item and item["contexts"] is not None and not isinstance(item["contexts"], list):
            item["contexts"] = [str(item["contexts"])]
        normalized.append(item)
    fields = sorted({key for sample in normalized for key in sample})
    metadata = {
        "num_samples": len(normalized),
        "has_reference": any(bool(s.get("expected_answer") or s.get("reference")) for s in normalized),
        "has_contexts": any(bool(s.get("contexts") or s.get("reference_contexts")) for s in normalized),
        "sample_fields": fields,
        "file_type": suffix.lstrip("."),
    }
    return normalized, metadata
