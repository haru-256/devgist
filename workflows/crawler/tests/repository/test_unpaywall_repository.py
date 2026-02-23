import asyncio
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.infrastructure.repositories.unpaywall_repository import UnpaywallRepository


@pytest.fixture
def semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_unpaywall_response() -> dict[str, Any]:
    """Sample Unpaywall API response."""
    return {
        "doi": "10.1145/test",
        "title": "Test Paper",
        "journal_name": "Test Journal",
        "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
    }


class TestUnpaywallRepository:
    """UnpaywallRepositoryのユニットテスト。"""

    async def test_init(self, mock_client: httpx.AsyncClient) -> None:
        """初期化時にclientが設定されること。"""
        repo = UnpaywallRepository(mock_client)
        assert repo.client == mock_client

    async def test_fetch_paper_success(
        self,
        mock_client: httpx.AsyncClient,
        mock_unpaywall_response: dict[str, Any],
        semaphore: asyncio.Semaphore,
        mocker: MockerFixture,
    ) -> None:
        """DOIで論文データが正常に取得できること。"""
        mock_response = httpx.Response(
            200,
            json=mock_unpaywall_response,
            request=httpx.Request("GET", "https://api.unpaywall.org/v2/10.1145/test"),
        )

        mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.get_with_retry",
            return_value=mock_response,
            autospec=True,
        )

        repo = UnpaywallRepository(mock_client)
        result = await repo.fetch_by_doi("10.1145/test", semaphore)

        assert result is not None
        assert result.doi == "10.1145/test"
        assert result.pdf_url == "https://example.com/paper.pdf"

    async def test_fetch_paper_not_found(
        self,
        mock_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        mocker: MockerFixture,
    ) -> None:
        """404エラーの場合、Noneが返されること。"""
        mock_response = httpx.Response(404, request=httpx.Request("GET", "http://test"))

        mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.get_with_retry",
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("GET", "http://test"),
                response=mock_response,
            ),
            autospec=True,
        )
        mock_logger = mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.logger.debug",
            autospec=True,
        )

        repo = UnpaywallRepository(mock_client)
        result = await repo.fetch_by_doi("10.1145/notfound", semaphore)

        assert result is None
        mock_logger.assert_called_with(
            "No paper found for DOI 10.1145/notfound on Unpaywall (404)."
        )

    async def test_fetch_paper_http_error(
        self,
        mock_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        mocker: MockerFixture,
    ) -> None:
        """HTTPエラーの場合、Noneが返されること。"""
        mock_response = httpx.Response(500, request=httpx.Request("GET", "http://test"))

        mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.get_with_retry",
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", "http://test"),
                response=mock_response,
            ),
            autospec=True,
        )
        mock_logger = mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.logger.warning",
            autospec=True,
        )

        repo = UnpaywallRepository(mock_client)
        result = await repo.fetch_by_doi("10.1145/test", semaphore)

        assert result is None
        mock_logger.assert_called()

    async def test_fetch_call_args(
        self,
        mock_client: httpx.AsyncClient,
        mock_unpaywall_response: dict[str, Any],
        semaphore: asyncio.Semaphore,
        mocker: MockerFixture,
    ) -> None:
        """fetch_by_doiが正しく引数を渡しているか確認する"""
        mock_response = httpx.Response(
            200,
            json=mock_unpaywall_response,
            request=httpx.Request("GET", "https://api.unpaywall.org/v2/10.1145/test"),
        )

        mock_func = mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.get_with_retry",
            return_value=mock_response,
            autospec=True,
        )

        repo = UnpaywallRepository(mock_client)
        await repo.fetch_by_doi("10.1145/test", semaphore)

        assert mock_func.call_count == 1
        call_args = mock_func.call_args
        # call_args[0] is positional args: (client, url)
        assert call_args[0][0] == mock_client
        # call_args[1] is keyword args: params, headers
        # headers is NOT passed
        assert "headers" not in call_args[1]
