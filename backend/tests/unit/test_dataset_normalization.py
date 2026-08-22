import json
from io import BytesIO

import pandas as pd
import pytest

from services.dataset_manager import MAX_DATASET_BYTES, normalize_dataset_bytes


def test_json_and_jsonl_normalize():
    rows, meta = normalize_dataset_bytes(json.dumps([{"question":"q"}]).encode(), "a.json")
    assert rows[0]["question"] == "q" and meta["num_samples"] == 1
    rows, _ = normalize_dataset_bytes(b'{"question":"q1"}\n{"question":"q2"}\n', "a.jsonl")
    assert len(rows) == 2


def test_csv_normalizes():
    rows, _ = normalize_dataset_bytes(b"question,expected_answer\nq,a\n", "a.csv")
    assert rows[0]["expected_answer"] == "a"


@pytest.mark.parametrize("file_name", ["a.xlsx", "a.xls"])
def test_excel_formats_normalize(file_name):
    output = BytesIO()
    pd.DataFrame([{"question": "q", "expected_answer": "a"}]).to_excel(
        output, index=False
    )
    rows, _ = normalize_dataset_bytes(output.getvalue(), file_name)
    assert rows[0]["question"] == "q"


def test_rejects_unsupported_oversized_and_missing_question():
    with pytest.raises(TypeError): normalize_dataset_bytes(b"x", "a.txt")
    with pytest.raises(OverflowError): normalize_dataset_bytes(b"x" * (MAX_DATASET_BYTES + 1), "a.json")
    with pytest.raises(ValueError): normalize_dataset_bytes(b'[{}]', "a.json")


def test_exact_size_limit_is_not_classified_as_oversized():
    with pytest.raises((ValueError, UnicodeError)) as error:
        normalize_dataset_bytes(b" " * MAX_DATASET_BYTES, "a.json")
    assert not isinstance(error.value, OverflowError)
