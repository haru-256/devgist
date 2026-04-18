import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.domain.models.paper import FetchedPaperEnrichment, Paper, PaperEnrichment
from crawler.infrastructure.http.http_retry_client import HttpRetryClient
from crawler.infrastructure.repositories.semantic_scholar_repository import (
    SemanticScholarRepository,
)


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


def test_parse_single_paper(mock_client: httpx.AsyncClient) -> None:
    """単一の論文レスポンスから補完情報をパースできることをテスト"""
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
    assert paper.enrichment.abstract == "Test Abstract"
    assert paper.enrichment.pdf_url == "http://example.com/pdf"
    assert isinstance(paper, FetchedPaperEnrichment)


def test_parse_single_paper_minimal(mock_client: httpx.AsyncClient) -> None:
    """最小限のフィールドで補完情報をパースできることをテスト"""
    repo = SemanticScholarRepository.from_client(mock_client)
    item = {"externalIds": {"DOI": "10.1234/test"}}

    paper = repo._parse_single_paper(item)
    assert paper is not None
    assert paper.doi == "10.1234/test"
    assert paper.enrichment.abstract is None
    assert paper.enrichment.pdf_url is None


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
    fetched_paper = FetchedPaperEnrichment(
        doi="10.1234/test",
        enrichment=PaperEnrichment(
            abstract="New Abstract",
            pdf_url="http://new.pdf",
        ),
    )

    mocker.patch.object(repo, "fetch_papers_batch", return_value=[fetched_paper], autospec=True)

    results = await repo.fetch_enrichments([paper])

    assert results == [fetched_paper]
    paper.apply_enrichment(fetched_paper.enrichment, overwrite=False)

    assert paper.title == "Original Title"  # 保持
    assert paper.abstract == "New Abstract"  # 更新
    assert paper.pdf_url == "http://new.pdf"  # 更新

    paper.apply_enrichment(fetched_paper.enrichment, overwrite=True)
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


@pytest.mark.asyncio
async def test_check_url_exists_uses_http_retry_client_head(
    mock_client: httpx.AsyncClient,
    mocker: MockerFixture,
) -> None:
    """URL 存在確認が生の AsyncClient ではなく HttpRetryClient を経由すること。"""
    repo = SemanticScholarRepository.from_client(mock_client)
    mock_head = mocker.patch.object(
        repo.http,
        "head",
        return_value=httpx.Response(200, request=httpx.Request("HEAD", "http://test")),
    )
    mock_client.head.side_effect = AssertionError("raw client head should not be called")

    result = await repo.check_url_exists("http://test")

    assert result is True
    mock_head.assert_awaited_once_with("http://test")
