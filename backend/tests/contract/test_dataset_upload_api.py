import io
import json


def make_client(secure_env):
    from app import create_app
    return create_app().test_client()


def test_json_csv_and_invalid_uploads(secure_env):
    client=make_client(secure_env)
    json_response=client.post("/api/v1/evaluation/datasets",data={"file":(io.BytesIO(json.dumps([{"question":"q"}]).encode()),"d.json")},content_type="multipart/form-data")
    assert json_response.status_code == 201
    assert json_response.get_json()["status"] == "completed"
    csv_response=client.post("/api/v1/evaluation/datasets",data={"file":(io.BytesIO(b"question,expected_answer\nq,a\n"),"d.csv")},content_type="multipart/form-data")
    assert csv_response.status_code == 201
    txt_response=client.post("/api/v1/evaluation/datasets",data={"file":(io.BytesIO(b"q"),"d.txt")},content_type="multipart/form-data")
    assert txt_response.status_code == 415
    assert not list((secure_env / "datasets").glob("*.txt"))
