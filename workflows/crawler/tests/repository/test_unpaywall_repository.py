from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.domain.models.paper import FetchedPaperEnrichment, Paper, PaperEnrichment
from crawler.infrastructure.http.http_retry_client import HttpRetryClient
from crawler.infrastructure.repositories.unpaywall_repository import UnpaywallRepository


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
        """初期化時に client と HttpRetryClient が設定されること。"""
        repo = UnpaywallRepository.from_client(mock_client)
        assert repo.http._client == mock_client
        assert isinstance(repo.http, HttpRetryClient)

    async def test_fetch_paper_success(
        self,
        mock_client: httpx.AsyncClient,
        mock_unpaywall_response: dict[str, Any],
        mocker: MockerFixture,
    ) -> None:
        """DOIで論文データが正常に取得できること。"""
        mock_response = httpx.Response(
            200,
            json=mock_unpaywall_response,
            request=httpx.Request("GET", "https://api.unpaywall.org/v2/10.1145/test"),
        )

        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(repo.http, "get", return_value=mock_response)

        result = await repo.fetch_by_doi("10.1145/test")

        assert result is not None
        assert result.pdf_url == "https://example.com/paper.pdf"
        assert isinstance(result, PaperEnrichment)

    async def test_fetch_paper_not_found(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """404エラーの場合、Noneが返されること。"""
        mock_response = httpx.Response(404, request=httpx.Request("GET", "http://test"))

        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(
            repo.http,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("GET", "http://test"),
                response=mock_response,
            ),
        )
        mock_logger = mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.logger.debug",
            autospec=True,
        )

        result = await repo.fetch_by_doi("10.1145/notfound")

        assert result is None
        mock_logger.assert_called_with(
            "No paper found for DOI 10.1145/notfound on Unpaywall (404)."
        )

    async def test_fetch_paper_http_error(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """HTTPエラーの場合、Noneが返されること。"""
        mock_response = httpx.Response(500, request=httpx.Request("GET", "http://test"))

        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(
            repo.http,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", "http://test"),
                response=mock_response,
            ),
        )
        mock_logger = mocker.patch(
            "crawler.infrastructure.repositories.unpaywall_repository.logger.warning",
            autospec=True,
        )

        result = await repo.fetch_by_doi("10.1145/test")

        assert result is None
        mock_logger.assert_called()

    async def test_fetch_paper_timeout_error(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """TimeoutException の場合、Noneが返されること。"""
        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(repo.http, "get", side_effect=httpx.ReadTimeout("timeout"))

        result = await repo.fetch_by_doi("10.1145/test")

        assert result is None

    async def test_fetch_paper_request_error(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """RequestError の場合、Noneが返されること。"""
        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(repo.http, "get", side_effect=httpx.RequestError("network error"))

        result = await repo.fetch_by_doi("10.1145/test")

        assert result is None

    async def test_fetch_paper_unexpected_error(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """想定外エラーの場合、Noneが返されること。"""
        repo = UnpaywallRepository.from_client(mock_client)
        mocker.patch.object(repo.http, "get", side_effect=RuntimeError("unexpected error"))

        result = await repo.fetch_by_doi("10.1145/test")

        assert result is None

    async def test_fetch_call_args(
        self,
        mock_client: httpx.AsyncClient,
        mock_unpaywall_response: dict[str, Any],
        mocker: MockerFixture,
    ) -> None:
        """fetch_by_doiが正しく引数を渡しているか確認する"""
        mock_response = httpx.Response(
            200,
            json=mock_unpaywall_response,
            request=httpx.Request("GET", "https://api.unpaywall.org/v2/10.1145/test"),
        )

        repo = UnpaywallRepository.from_client(mock_client)
        mock_get = mocker.patch.object(repo.http, "get", return_value=mock_response)

        await repo.fetch_by_doi("10.1145/test")

        assert mock_get.call_count == 1
        call_args = mock_get.call_args
        # url は第1位置引数
        assert "10.1145/test" in call_args[0][0]
        # headers は渡さない
        assert "headers" not in call_args[1]

    async def test_fetch_enrichments_runs_in_batches(
        self,
        mock_client: httpx.AsyncClient,
        mocker: MockerFixture,
    ) -> None:
        """fetch_enrichments がバッチ処理でも DOI あり論文を全件処理すること。"""
        repo = UnpaywallRepository.from_client(mock_client)

        papers = [
            Paper(title=f"title-{i}", authors=[], year=2024, venue="v", doi=f"10.1000/{i}")
            for i in range(120)
        ]
        papers.append(Paper(title="no-doi", authors=[], year=2024, venue="v", doi=None))

        mock_enrich = mocker.patch.object(
            repo,
            "_fetch_single_paper_enrichment",
            return_value=FetchedPaperEnrichment(
                doi="10.1000/x",
                enrichment=PaperEnrichment(pdf_url="https://example.com/x.pdf"),
            ),
        )

        result = await repo.fetch_enrichments(papers)

        assert len(result) == 120
        # DOI あり 120 件のみ対象
        assert mock_enrich.call_count == 120
