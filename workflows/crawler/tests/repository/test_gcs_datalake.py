# TODO: GCS Datalakeのテストコードを実装する
import re
from unittest.mock import MagicMock, call

import pytest
from google.cloud import storage
from pytest_mock import MockerFixture

from crawler.domain.models.paper import Paper
from crawler.infrastructure.repositories.gcs_datalake import GCSDatalake


@pytest.fixture
def mock_blob(mocker: MockerFixture) -> MagicMock:
    """Mock Blob fixture."""
    blob = mocker.MagicMock(spec=storage.Blob)
    blob.name = "test-blob"
    return blob


@pytest.fixture
def mock_bucket(mocker: MockerFixture, mock_blob: MagicMock) -> MagicMock:
    """Mock Bucket fixture."""
    bucket_m = mocker.MagicMock(spec=storage.Bucket)
    bucket_m.blob.return_value = mock_blob
    return bucket_m


@pytest.fixture
def mock_storage_client(mocker: MockerFixture, mock_bucket: MagicMock) -> MagicMock:
    """Mock Storage Client fixture."""
    client_m = mocker.MagicMock(spec=storage.Client)
    client_m.bucket.return_value = mock_bucket
    return client_m


@pytest.fixture
def papers() -> list[Paper]:
    """テスト用のPaperリストを返すfixture."""
    return [
        Paper(
            title="Test Paper 1",
            authors=["Author A", "Author B"],
            year=2025,
            doi="10.1145/test1",
            abstract="This is a test abstract.",
            pdf_url="https://example.com/test1.pdf",
            venue="RecSys",
        ),
        Paper(
            title="Test Paper 2",
            authors=["Author C"],
            year=2025,
            doi="10.1145/test2",
            abstract="This is another test abstract.",
            pdf_url=None,
            venue="RecSys",
        ),
    ]


async def test_save_papers(
    mock_storage_client: MagicMock,
    mock_bucket: MagicMock,
    mock_blob: MagicMock,
    papers: list[Paper],
) -> None:
    """GCS Datalakeのsave_papersメソッドのテスト."""

    # GCSDatalakeインスタンスを作成
    datalake = GCSDatalake(
        mock_storage_client, bucket_name="test-bucket", batch_size=1, prefix_path="papers"
    )

    # save_papersを呼び出す
    results = await datalake.save_papers(papers, papers_rep_name="test")

    # バケットとblobの呼び出しを検証
    # ファイル名には timestamp と UUID が含まれるため正規表現で検証する
    # 形式: papers/test_{YYYYMMDD}_{HHMMSS}_{microseconds}_{uuid8}.jsonl
    blob_name_pattern = re.compile(r"papers/test_\d{8}_\d{6}_\d{6}_[a-f0-9]{8}\.jsonl")
    actual_blob_calls = [c.args[0] for c in mock_bucket.blob.call_args_list]
    assert len(actual_blob_calls) == 2  # batch_size=1 なので 2バッチ
    for blob_path in actual_blob_calls:
        assert blob_name_pattern.fullmatch(blob_path), f"Unexpected blob path: {blob_path}"

    # upload_from_string の呼び出しを検証（内容は固定値なので完全一致）
    expected_calls = [
        call(
            papers[0].model_dump_json(ensure_ascii=False),
            content_type="application/x-ndjson",
        ),
        call(
            papers[1].model_dump_json(ensure_ascii=False),
            content_type="application/x-ndjson",
        ),
    ]
    mock_blob.upload_from_string.assert_has_calls(expected_calls, any_order=True)

    # 各JSONレコードは1行にシリアライズされること（JSONLの前提）
    for upload_call in mock_blob.upload_from_string.call_args_list:
        payload = upload_call.args[0]
        assert "\n" not in payload

    assert len(results) == 2
