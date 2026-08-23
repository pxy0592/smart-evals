from __future__ import annotations

import os
import sqlite3
import sys
from types import ModuleType, SimpleNamespace

from services.ai_dataset_generator import AIDatasetGenerator

CHINESE_CHUNK = {
    "id": "chunk-1",
    "doc_name": "人工智能基础",
    "content": "人工智能是利用计算机模拟人类学习、推理和决策能力的技术。它可以应用于文本分析、图像识别和知识问答等场景，并通过数据和算法不断改进处理效果。",
}


class Provider:
    def __init__(self, chunks):
        self.chunks = chunks

    def get_chunks(self, _kb_id, _limit):
        return self.chunks


def test_json_is_extracted_before_refusal_text(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator,
        "call_llm_for_generation",
        lambda _prompt: '说明中提到无法生成，但实际结果如下：{"question":"人工智能可以应用在哪些场景？","expected_answer":"人工智能可以应用于文本分析、图像识别和知识问答等场景，并通过数据和算法不断改进处理效果。","context":"人工智能是利用计算机模拟人类学习、推理和决策能力的技术。它可以应用于文本分析、图像识别和知识问答等场景。"}',
    )
    qa = generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual")
    assert qa is not None
    assert qa["question"].startswith("人工智能")
    assert qa["contexts"][0].startswith("人工智能")


def test_exact_refusal_is_rejected(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator, "call_llm_for_generation", lambda _prompt: "无法生成"
    )
    assert generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual") is None
    assert generator.generation_stats["content_insufficient"] == 1


def test_traditional_output_is_normalized_to_simplified(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator,
        "call_llm_for_generation",
        lambda _prompt: '{"question":"人工智慧可以應用在哪些場景？","expected_answer":"人工智慧可以應用於文字分析、圖像識別和知識問答等場景，並透過資料和演算法持續改進處理效果。","context":"人工智慧是利用電腦模擬人類學習、推理和決策能力的技術。它可以應用於文字分析、圖像識別和知識問答等場景。"}',
    )
    qa = generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual")
    assert qa is not None
    assert "應用" not in qa["question"]
    assert "应用" in qa["question"]


def test_non_chinese_output_is_rejected(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator,
        "call_llm_for_generation",
        lambda _prompt: '{"question":"What is artificial intelligence?","expected_answer":"Artificial intelligence simulates human intelligence for data analysis and decisions.","context":"Artificial intelligence is a computer technology."}',
    )
    assert generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual") is None
    assert generator.generation_stats["non_simplified_chinese_output"] == 2


def test_english_source_can_generate_simplified_chinese_output(monkeypatch):
    generator = AIDatasetGenerator()
    english_chunk = {
        "id": "english-1",
        "doc_name": "System Design",
        "content": "A news feed system collects posts from followed users, ranks them by relevance, and presents the most useful content to each reader.",
    }
    monkeypatch.setattr(
        generator,
        "call_llm_for_generation",
        lambda _prompt: '{"question":"新闻推送系统如何向读者展示内容？","expected_answer":"新闻推送系统会收集用户关注对象发布的内容，按照相关性进行排序，并向每位读者展示最有价值的信息。","context":"新闻推送系统会收集关注对象发布的内容，根据相关性排序，再向读者展示最有价值的信息。"}',
    )
    qa = generator.generate_qa_pair_with_llm(english_chunk, "analytical")
    assert qa is not None
    assert qa["question"].startswith("新闻推送")
    assert not any("A" <= char <= "z" for char in qa["contexts"][0])


def test_dataset_requires_exact_requested_sample_count(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator,
        "get_knowledge_base_chunks",
        lambda *_args, **_kwargs: [CHINESE_CHUNK],
    )
    monkeypatch.setattr(
        generator, "generate_qa_pair_with_llm", lambda *_args, **_kwargs: None
    )
    assert (
        generator.generate_dataset_from_kb(
            Provider([CHINESE_CHUNK]), "kb", 10, ["factual"]
        )
        == []
    )
    assert "0/10" in generator.last_generation_error


def test_dataset_returns_exact_requested_sample_count(monkeypatch):
    generator = AIDatasetGenerator()
    chunks = [
        {
            "id": f"chunk-{index}",
            "doc_name": "中文资料",
            "content": "人工智能技术通过数据和算法帮助系统完成分析、推理和决策任务，并持续提升服务质量，同时能够在知识问答、文本处理和业务辅助等场景中提供稳定支持。",
        }
        for index in range(10)
    ]
    monkeypatch.setattr(
        generator, "get_knowledge_base_chunks", lambda *_args, **_kwargs: chunks
    )

    def generate(chunk, _question_type, **_kwargs):
        return {
            "question": f"人工智能技术如何发挥作用{chunk['id']}？",
            "expected_answer": "人工智能技术通过数据和算法帮助系统完成分析、推理和决策任务，并持续提升服务质量，同时能够在知识问答、文本处理和业务辅助等场景中提供稳定支持。",
            "contexts": [
                "人工智能技术通过数据和算法帮助系统完成分析、推理和决策任务，并持续提升服务质量，同时能够在知识问答、文本处理和业务辅助等场景中提供稳定支持。"
            ],
        }

    monkeypatch.setattr(generator, "generate_qa_pair_with_llm", generate)
    samples = generator.generate_dataset_from_kb(
        Provider(chunks), "kb", 10, ["factual"]
    )
    assert len(samples) == 10
    assert all(len(sample["contexts"]) == 1 for sample in samples)


def test_reasoning_with_embedded_error_json_then_final_qa_is_accepted(monkeypatch):
    generator = AIDatasetGenerator()
    response = """Here's a thinking process:
The prompt says an insufficient document should return {"error":"内容不足"}.
Final answer: {"question":"新闻推送系统如何为读者筛选内容？","expected_answer":"新闻推送系统会收集用户关注对象发布的内容，根据相关性进行排序，并向每位读者展示最有价值的信息。","context":"新闻推送系统会收集用户关注对象发布的内容，按照相关性排序，再向每位读者展示最有价值的信息。"}"""
    monkeypatch.setattr(generator, "call_llm_for_generation", lambda _prompt: response)

    qa = generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "analytical")

    assert qa is not None
    assert qa["question"] == "新闻推送系统如何为读者筛选内容？"
    assert generator.generation_stats == {}


def test_only_error_json_is_classified_as_content_insufficient(monkeypatch):
    generator = AIDatasetGenerator()
    monkeypatch.setattr(
        generator, "call_llm_for_generation", lambda _prompt: '{"error":"内容不足"}'
    )

    assert generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual") is None
    assert generator.generation_stats["content_insufficient"] == 1
    assert "json_parse_error" not in generator.generation_stats


def test_reasoning_without_final_qa_is_json_parse_error(monkeypatch):
    generator = AIDatasetGenerator()
    response = """Here's a thinking process:\nThe insufficient response example is {\"error\":\"内容不足\"}.\nI will continue reasoning but never emit a final answer."""
    monkeypatch.setattr(generator, "call_llm_for_generation", lambda _prompt: response)

    assert (
        generator.generate_qa_pair_with_llm(CHINESE_CHUNK, "factual", max_retries=1)
        is None
    )
    assert generator.generation_stats["json_parse_error"] == 1
    assert "content_insufficient" not in generator.generation_stats


def test_call_llm_uses_saved_max_tokens_without_forcing_1000(monkeypatch, tmp_path):
    db_path = tmp_path / "evaluation.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE api_configs (
            provider TEXT, api_key TEXT, endpoint TEXT, model TEXT,
            temperature REAL, max_tokens INTEGER, is_default INTEGER
        )""")
    conn.execute(
        "INSERT INTO api_configs VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("custom", "test-key", "http://example.invalid/v1", "test-model", 0.2, 4000, 1),
    )
    conn.commit()
    conn.close()

    calls = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def invoke(self, _prompt):
            return SimpleNamespace(content='{"ok":true}')

    fake_module = ModuleType("langchain_openai")
    fake_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    try:
        assert AIDatasetGenerator().call_llm_for_generation("test") == '{"ok":true}'
    finally:
        os.environ.pop("DATABASE_PATH", None)

    assert calls[0]["max_tokens"] == 4000


def test_call_llm_reserves_minimum_output_budget_for_reasoning_models(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "evaluation.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE api_configs (
            provider TEXT, api_key TEXT, endpoint TEXT, model TEXT,
            temperature REAL, max_tokens INTEGER, is_default INTEGER
        )""")
    conn.execute(
        "INSERT INTO api_configs VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("custom", "test-key", "http://example.invalid/v1", "test-model", 0.2, 809, 1),
    )
    conn.commit()
    conn.close()

    calls = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def invoke(self, _prompt):
            return SimpleNamespace(content='{"ok":true}')

    fake_module = ModuleType("langchain_openai")
    fake_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    try:
        AIDatasetGenerator().call_llm_for_generation("test")
    finally:
        os.environ.pop("DATABASE_PATH", None)

    assert calls[0]["max_tokens"] == 2048
