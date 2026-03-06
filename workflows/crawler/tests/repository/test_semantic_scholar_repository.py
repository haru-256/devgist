import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.domain.models.paper import Paper
from crawler.infrastructure.http.http_retry_client import HttpRetryClient
from crawler.infrastructure.repositories.semantic_scholar_repository import (
    SemanticScholarRepository,
)


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


def test_parse_single_paper(mock_client: httpx.AsyncClient) -> None:
    """単一の論文レスポンスのパーステスト"""
    repo = SemanticScholarRepository.from_client(mock_client)

    item = {
        "externalIds": {"DOI": "10.1234/test"},
        "abstract": "Test Abstract",
        "openAccessPdf": {"url": "http://example.com/pdf"},
        "title": "Test Title",
        "year": 2024,
        "venue": "Test Venue",
        "authors": [
            {"authorId": "1", "name": "Author One"},
            {"authorId": "2", "name": "Author Two"},
        ],
        "url": "https://www.semanticscholar.org/paper/test",
    }

    paper = repo._parse_single_paper(item)
    assert paper is not None
    assert paper.doi == "10.1234/test"
    assert paper.abstract == "Test Abstract"
    assert paper.pdf_url == "http://example.com/pdf"
    assert paper.title == "Test Title"
    assert paper.year == 2024
    assert paper.venue == "Test Venue"
    assert paper.authors == ["Author One", "Author Two"]


def test_parse_single_paper_minimal(mock_client: httpx.AsyncClient) -> None:
    """最小限のフィールドでのパーステスト"""
    repo = SemanticScholarRepository.from_client(mock_client)
    item = {"externalIds": {"DOI": "10.1234/test"}}

    paper = repo._parse_single_paper(item)
    assert paper is not None
    assert paper.doi == "10.1234/test"
    assert paper.abstract is None
    assert paper.pdf_url is None


def test_parse_single_paper_none(mock_client: httpx.AsyncClient) -> None:
    """Noneのパーステスト"""
    repo = SemanticScholarRepository.from_client(mock_client)
    paper = repo._parse_single_paper({})  # Empty dict
    assert paper is None


@pytest.mark.asyncio
async def test_enrich_papers_merge_logic(
    mock_client: httpx.AsyncClient,
    mocker: MockerFixture,
) -> None:
    """enrich_papersの結合ロジックテスト"""
    repo = SemanticScholarRepository.from_client(mock_client)

    # 既存の論文（一部情報不足）
    paper = Paper(
        title="Original Title",
        authors=[],
        year=0,
        venue="",
        doi="10.1234/test",
    )

    # APIから取得される論文（情報あり）
    fetched_paper = Paper(
        title="New Title",
        authors=["Author A"],
        year=2024,
        venue="New Venue",
        doi="10.1234/test",
        abstract="New Abstract",
        pdf_url="http://new.pdf",
    )

    # fetch_papers_batchをモック
    mocker.patch.object(repo, "fetch_papers_batch", return_value=[fetched_paper], autospec=True)

    # overwrite=False: 元のTitleは保持され、欠損項目は埋まるはず
    await repo.enrich_papers([paper], overwrite=False)

    assert paper.title == "Original Title"  # 保持
    assert paper.abstract == "New Abstract"  # 更新
    assert paper.pdf_url == "http://new.pdf"  # 更新

    # overwrite=True: 全て更新されるはず
    await repo.enrich_papers([paper], overwrite=True)
    assert paper.abstract == "New Abstract"  # overwriteされる
    assert paper.pdf_url == "http://new.pdf"  # overwriteされる
    assert paper.title == "Original Title"  # titleはoverwriteされない


async def test_fetch_call_args(
    mock_client: httpx.AsyncClient,
    mocker: MockerFixture,
) -> None:
    """fetch_papers_batchが正しく引数を渡しているか確認する"""
    mock_response = httpx.Response(200, json=[], request=httpx.Request("POST", "http://test"))

    repo = SemanticScholarRepository.from_client(mock_client)
    assert isinstance(repo.http, HttpRetryClient)

    mock_post = mocker.patch.object(repo.http, "post", return_value=mock_response)

    dois = ["10.1234/test"]
    await repo.fetch_papers_batch(dois)

    assert mock_post.call_count == 1
    call_args = mock_post.call_args
    # url は第1位置引数
    assert SemanticScholarRepository.PAPER_BATCH_SEARCH_PATH in call_args[0][0]
    # headers は渡さない
    assert "headers" not in call_args[1]
