import asyncio
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.domain.paper import Paper
from crawler.repository.semantic_scholar_repository import SemanticScholarRepository


@pytest.fixture
def semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


def test_parse_single_paper(mock_client: httpx.AsyncClient) -> None:
    """単一の論文レスポンスのパーステスト"""
    repo = SemanticScholarRepository(mock_client)

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
    repo = SemanticScholarRepository(mock_client)
    item = {"externalIds": {"DOI": "10.1234/test"}}

    paper = repo._parse_single_paper(item)
    assert paper is not None
    assert paper.doi == "10.1234/test"
    assert paper.abstract is None
    assert paper.pdf_url is None


def test_parse_single_paper_none(mock_client: httpx.AsyncClient) -> None:
    """Noneのパーステスト"""
    repo = SemanticScholarRepository(mock_client)
    paper = repo._parse_single_paper({})  # Empty dict
    assert paper is None


@pytest.mark.asyncio
async def test_enrich_papers_merge_logic(
    mock_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    mocker: MockerFixture,
) -> None:
    """enrich_papersの結合ロジックテスト"""
    repo = SemanticScholarRepository(mock_client)

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
    mocker.patch.object(repo, "fetch_papers_batch", return_value=[fetched_paper])

    # overwrite=False: 元のTitleは保持され、欠損項目は埋まるはず
    await repo.enrich_papers([paper], semaphore=semaphore, overwrite=False)

    assert paper.title == "Original Title"  # 保持
    assert paper.abstract == "New Abstract"  # 更新
    assert paper.pdf_url == "http://new.pdf"  # 更新

    # overwrite=True: 全て更新されるはず
    await repo.enrich_papers([paper], semaphore=semaphore, overwrite=True)
    assert paper.abstract == "New Abstract"  # overwriteされる
    assert paper.pdf_url == "http://new.pdf"  # overwriteされる
    assert paper.title == "Original Title"  # titleはoverwriteされない


async def test_fetch_call_args(
    mock_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    mocker: MockerFixture,
) -> None:
    """fetch_papers_batchが正しく引数を渡しているか確認する"""
    mock_response = httpx.Response(
        200, json={"data": []}, request=httpx.Request("POST", "http://test")
    )

    async def mock_post_with_retry(*args: Any, **kwargs: Any) -> httpx.Response:
        return mock_response

    # Patch crawler.repository.semantic_scholar_repository.post_with_retry
    mock_func = mocker.patch(
        "crawler.repository.semantic_scholar_repository.post_with_retry",
        side_effect=mock_post_with_retry,
    )

    repo = SemanticScholarRepository(mock_client)

    # Create dummy papers to trigger a fetch
    papers = [Paper(title="Test", authors=[], year=2024, venue="", doi="10.1234/test")]

    # fetch_papers_batch expects list[str] (DOIs)
    # The test was passing papers list which is incorrect
    dois = [p.doi for p in papers if p.doi]
    await repo.fetch_papers_batch(dois, semaphore)

    assert mock_func.call_count == 1
    call_args = mock_func.call_args
    # call_args[0] is positional args: (client, url)
    assert call_args[0][0] == mock_client
    # call_args[1] is keyword args: params, json, headers
    # headers is NOT passed
    assert "headers" not in call_args[1]
