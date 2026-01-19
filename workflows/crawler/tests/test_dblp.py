from typing import Any

import pytest
from pytest_mock import MockerFixture

from usecase.dblp import DBLPSearch


@pytest.fixture
def headers() -> dict[str, str]:
    return {"User-Agent": "ArchilogBot/1.0"}


@pytest.fixture
def mock_dblp_response() -> dict[str, Any]:
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


async def test_context_manager(headers: dict[str, str], mocker: MockerFixture) -> None:
    """コンテキストマネージャーとして使用できることをテスト"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = "User-agent: *\nAllow: /"

    mock_client_get = mocker.patch("httpx.AsyncClient.get", return_value=mock_response)
    mock_client_aclose = mocker.patch("httpx.AsyncClient.aclose")

    async with DBLPSearch(headers) as search:
        assert search.robot_guard.loaded is True

    mock_client_get.assert_called_once()
    mock_client_aclose.assert_called_once()


async def test_fetch_papers_success(
    headers: dict[str, str],
    mock_dblp_response: dict[str, Any],
    mocker: MockerFixture,
) -> None:
    """正常系: 論文データを取得できることをテスト"""
    # robots.txt用のモック
    mock_robots_response = mocker.MagicMock()
    mock_robots_response.status_code = 200
    mock_robots_response.text = "User-agent: *\nAllow: /"

    # API用のモック
    mock_api_response = mocker.MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = mock_dblp_response

    call_count = 0

    async def mock_get(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_robots_response
        return mock_api_response

    mocker.patch("httpx.AsyncClient.get", side_effect=mock_get)
    mocker.patch("httpx.AsyncClient.aclose")

    async with DBLPSearch(headers) as search:
        papers = await search.fetch_papers(conf="recsys", year=2025, h=100)

    assert len(papers) == 2
    assert papers[0].title == "Test Paper 1"
    assert papers[0].authors == ["Author A", "Author B"]
    assert papers[0].year == 2025
    assert papers[0].venue == "RecSys"
    assert papers[0].doi == "10.1145/test1"

    assert papers[1].title == "Test Paper 2"
    assert papers[1].authors == ["Author C"]
    assert papers[1].doi is None


async def test_fetch_papers_robots_disallow(headers: dict[str, str], mocker: MockerFixture) -> None:
    """robots.txtで拒否された場合にPermissionErrorが発生することをテスト"""
    mock_robots_response = mocker.MagicMock()
    mock_robots_response.status_code = 200
    mock_robots_response.text = "User-agent: *\nDisallow: /"

    mocker.patch("httpx.AsyncClient.get", return_value=mock_robots_response)
    mocker.patch("httpx.AsyncClient.aclose")

    async with DBLPSearch(headers) as search:
        with pytest.raises(PermissionError):
            await search.fetch_papers(conf="recsys", year=2025)


async def test_fetch_papers_http_error(headers: dict[str, str], mocker: MockerFixture) -> None:
    """HTTPエラーが発生した場合の挙動をテスト"""
    mock_robots_response = mocker.MagicMock()
    mock_robots_response.status_code = 200
    mock_robots_response.text = "User-agent: *\nAllow: /"

    mock_api_response = mocker.MagicMock()
    mock_api_response.status_code = 500
    mock_api_response.text = "Internal Server Error"

    def mock_raise_for_status() -> None:
        import httpx

        raise httpx.HTTPStatusError(
            "Server error", request=mocker.MagicMock(), response=mock_api_response
        )

    mock_api_response.raise_for_status = mock_raise_for_status

    call_count = 0

    async def mock_get(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_robots_response
        return mock_api_response

    mocker.patch("httpx.AsyncClient.get", side_effect=mock_get)
    mocker.patch("httpx.AsyncClient.aclose")

    async with DBLPSearch(headers) as search:
        with pytest.raises(Exception):  # httpx.HTTPStatusError
            await search.fetch_papers(conf="recsys", year=2025)


async def test_parse_paper_no_hits(headers: dict[str, str]) -> None:
    """ヒットが0件の場合にValueErrorが発生することをテスト"""
    empty_response = {"result": {"hits": {"@total": "0"}}}

    search = DBLPSearch(headers)
    with pytest.raises(ValueError, match="No hits found"):
        search._parse_paper(empty_response)


async def test_parse_paper_missing_required_fields(
    headers: dict[str, str], mocker: MockerFixture
) -> None:
    """必須フィールドが欠けている場合はスキップされることをテスト"""
    incomplete_response = {
        "result": {
            "hits": {
                "@total": "3",
                "hit": [
                    {
                        "info": {
                            "title": None,  # titleが欠けている
                            "authors": {"author": {"text": "Author A"}},
                            "year": "2025",
                            "venue": "RecSys",
                        }
                    },
                    {
                        "info": {
                            "title": "Valid Paper",
                            "authors": {"author": {"text": "Author B"}},
                            "year": None,  # yearが欠けている
                            "venue": "RecSys",
                        }
                    },
                    {
                        "info": {
                            "title": "Another Valid Paper",
                            "authors": {"author": {"text": "Author C"}},
                            "year": "2025",
                            "venue": "RecSys",
                        }
                    },
                ],
            }
        }
    }

    search = DBLPSearch(headers)
    papers = search._parse_paper(incomplete_response)

    # 有効な論文のみが含まれる
    assert len(papers) == 1
    assert papers[0].title == "Another Valid Paper"


def test_parse_authors_list() -> None:
    """著者がリスト形式の場合のパースをテスト"""
    search = DBLPSearch({"User-Agent": "test"})
    authors_data = {
        "author": [
            {"text": "Author A"},
            {"text": "Author B"},
            {"text": "Author C"},
        ]
    }
    authors = search._parse_authors(authors_data)
    assert authors == ["Author A", "Author B", "Author C"]


def test_parse_authors_single_dict() -> None:
    """著者が単一の辞書形式の場合のパースをテスト"""
    search = DBLPSearch({"User-Agent": "test"})
    authors_data = {"author": {"text": "Single Author"}}
    authors = search._parse_authors(authors_data)
    assert authors == ["Single Author"]


def test_parse_authors_none() -> None:
    """著者がNoneの場合のパースをテスト"""
    search = DBLPSearch({"User-Agent": "test"})
    authors_data = {"author": None}
    authors = search._parse_authors(authors_data)
    assert authors == []


def test_parse_authors_empty_dict() -> None:
    """著者が空の辞書の場合のパースをテスト"""
    search = DBLPSearch({"User-Agent": "test"})
    authors_data: dict[str, Any] = {}
    authors = search._parse_authors(authors_data)
    assert authors == []


def test_parse_authors_invalid_type() -> None:
    """著者が予期しない型の場合のパースをテスト"""
    search = DBLPSearch({"User-Agent": "test"})
    authors_data: dict[str, object] = {"author": "Invalid String"}
    authors = search._parse_authors(authors_data)
    assert authors == []
