from __future__ import annotations

import json

import pytest


def make_client(secure_env):
    from app import create_app

    return create_app().test_client()


def seed_dataset(secure_env, sample_count: int = 12) -> str:
    from db import get_dataset_manager

    dataset_id = f"paged-dataset-{sample_count}"
    samples = [
        {
            "question": f"问题 {index}",
            "expected_answer": f"答案 {index}",
        }
        for index in range(1, sample_count + 1)
    ]
    storage_path = secure_env / f"{dataset_id}.json"
    storage_path.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")
    get_dataset_manager().create_dataset(
        {
            "id": dataset_id,
            "name": "分页样本数据集",
            "file_type": ".json",
            "file_size": storage_path.stat().st_size,
            "storage_path": str(storage_path),
            "normalized_storage_path": str(storage_path),
            "normalization_status": "completed",
            "status": "completed",
            "num_samples": sample_count,
        }
    )
    return dataset_id


def test_dataset_samples_endpoint_returns_fixed_pages_and_total(secure_env):
    client = make_client(secure_env)
    dataset_id = seed_dataset(secure_env)

    for offset, expected_questions in (
        (0, ["问题 1", "问题 2", "问题 3", "问题 4", "问题 5"]),
        (5, ["问题 6", "问题 7", "问题 8", "问题 9", "问题 10"]),
        (10, ["问题 11", "问题 12"]),
    ):
        response = client.get(
            f"/api/v1/evaluation/datasets/{dataset_id}/samples",
            query_string={"offset": offset, "limit": 5},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["total"] == 12
        assert payload["limit"] == 5
        assert payload["offset"] == offset
        assert [
            sample["question"] for sample in payload["samples"]
        ] == expected_questions


@pytest.mark.parametrize(
    ("sample_count", "expected_first_page_size"),
    [(0, 0), (3, 3), (5, 5), (6, 5)],
)
def test_dataset_samples_endpoint_handles_small_and_empty_datasets(
    secure_env, sample_count, expected_first_page_size
):
    client = make_client(secure_env)
    dataset_id = seed_dataset(secure_env, sample_count)

    response = client.get(
        f"/api/v1/evaluation/datasets/{dataset_id}/samples",
        query_string={"offset": 0, "limit": 5},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == sample_count
    assert len(payload["samples"]) == expected_first_page_size

    if sample_count == 6:
        final_page = client.get(
            f"/api/v1/evaluation/datasets/{dataset_id}/samples",
            query_string={"offset": 5, "limit": 5},
        )
        assert final_page.status_code == 200
        assert final_page.get_json()["total"] == 6
        assert len(final_page.get_json()["samples"]) == 1


def test_dataset_samples_endpoint_reports_missing_dataset(secure_env):
    client = make_client(secure_env)

    response = client.get(
        "/api/v1/evaluation/datasets/missing-dataset/samples",
        query_string={"offset": 0, "limit": 5},
    )

    assert response.status_code == 404
