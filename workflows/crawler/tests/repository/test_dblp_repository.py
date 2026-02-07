import asyncio
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.repository.dblp_repository import DBLPRepository


@pytest.fixture
def semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_dblp_response_data() -> dict[str, Any]:
    return {
        "result": {
            "hits": {
                "@total": "2",
                "hit": [
                    {
                        "info": {
                            "title": "Test Paper 1",
                            "authors": {
                                "author": [
                                    {"text": "Author A"},
                                    {"text": "Author B"},
                                ]
                            },
                            "year": "2025",
                            "venue": "RecSys",
                            "doi": "10.1145/test1",
                            "type": "Conference and Workshop Papers",
                            "ee": "https://doi.org/10.1145/test1",
                            "url": "https://dblp.org/rec/conf/recsys/test1",
                        }
                    },
                    {
                        "info": {
                            "title": "Test Paper 2",
                            "authors": {"author": {"text": "Author C"}},
                            "year": "2025",
                            "venue": "RecSys",
                            "doi": None,
                            "type": None,
                            "ee": None,
                            "url": None,
                        }
                    },
                ],
            }
        }
    }


def test_parse_papers_valid(
    mock_client: httpx.AsyncClient, mock_dblp_response_data: dict[str, Any]
) -> None:
    """正常系: パース処理のテスト"""
    repo = DBLPRepository(mock_client)
    papers = repo._parse_papers(mock_dblp_response_data)

    assert len(papers) == 2
    assert papers[0].title == "Test Paper 1"
    assert papers[0].authors == ["Author A", "Author B"]
    assert papers[0].year == 2025
    assert papers[0].venue == "RecSys"
    assert papers[0].doi == "10.1145/test1"

    assert papers[1].title == "Test Paper 2"
    assert papers[1].authors == ["Author C"]
    assert papers[1].doi is None


def test_parse_papers_no_hits(mock_client: httpx.AsyncClient) -> None:
    """ヒットなしの場合のパーステスト"""
    repo = DBLPRepository(mock_client)
    data = {"result": {"hits": {"@total": "0"}}}
    papers = repo._parse_papers(data)
    assert papers == []


def test_parse_papers_invalid_data(mock_client: httpx.AsyncClient) -> None:
    """不正なデータのパーステスト"""
    repo = DBLPRepository(mock_client)
    data = {"invalid": "data"}
    papers = repo._parse_papers(data)
    assert papers == []


def test_parse_authors(mock_client: httpx.AsyncClient) -> None:
    """著者情報のパーステスト"""
    repo = DBLPRepository(mock_client)

    # リスト形式
    data_list = {"author": [{"text": "A"}, {"text": "B"}]}
    assert repo._parse_authors(data_list) == ["A", "B"]

    # 単一辞書形式
    data_dict = {"author": {"text": "C"}}
    assert repo._parse_authors(data_dict) == ["C"]

    # None
    assert repo._parse_authors(None) == []

    # 空辞書
    assert repo._parse_authors({}) == []


async def test_fetch_papers_integration_mock(
    mock_client: httpx.AsyncClient,
    mock_dblp_response_data: dict[str, Any],
    semaphore: asyncio.Semaphore,
    mocker: MockerFixture,
) -> None:
    """fetch_papersメソッドの統合的テスト（get_with_retryモック）"""
    mock_api_response = httpx.Response(
        200, json=mock_dblp_response_data, request=httpx.Request("GET", "http://test")
    )

    async def mock_get_with_retry(*args: Any, **kwargs: Any) -> httpx.Response:
        return mock_api_response

    # Initialize needs to be mocked or handled
    # DBLPRepository.initialize calls robot_guard.load()
    # We can mock robot_guard.load to do nothing
    from crawler.utils import RobotGuard

    mocker.patch.object(RobotGuard, "load", return_value=None)
    mocker.patch.object(RobotGuard, "can_fetch", return_value=True)

    mocker.patch(
        "crawler.repository.dblp_repository.get_with_retry", side_effect=mock_get_with_retry
    )

    repo = DBLPRepository(mock_client)
    papers = await repo.fetch_papers(conf="recsys", year=2025, semaphore=semaphore)

    assert len(papers) == 2
    assert papers[0].title == "Test Paper 1"


async def test_fetch_call_args(
    mock_client: httpx.AsyncClient,
    mock_dblp_response_data: dict[str, Any],
    semaphore: asyncio.Semaphore,
    mocker: MockerFixture,
) -> None:
    """fetch_papersが正しく引数を渡しているか確認する"""
    mock_api_response = httpx.Response(
        200, json=mock_dblp_response_data, request=httpx.Request("GET", "http://test")
    )

    async def mock_get_with_retry(*args: Any, **kwargs: Any) -> httpx.Response:
        return mock_api_response

    from crawler.utils import RobotGuard

    mocker.patch.object(RobotGuard, "load", return_value=None)
    mocker.patch.object(RobotGuard, "can_fetch", return_value=True)

    mock_func = mocker.patch(
        "crawler.repository.dblp_repository.get_with_retry", side_effect=mock_get_with_retry
    )

    repo = DBLPRepository(mock_client)
    await repo.fetch_papers(conf="recsys", year=2025, semaphore=semaphore)

    assert mock_func.call_count == 1
    call_args = mock_func.call_args
    # call_args[0] is positional args: (client, url)
    assert call_args[0][0] == mock_client
    # call_args[1] is keyword args: params, headers
    # headers is NOT passed
    assert "headers" not in call_args[1]
