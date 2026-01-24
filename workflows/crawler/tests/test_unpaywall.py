from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from domain.paper import Paper
from usecase.unpaywall import UnpaywallSearch


@pytest.fixture
def mock_paper() -> Paper:
    return Paper(
        title="Test Paper",
        authors=["Author 1"],
        year=2024,
        venue="Test Venue",
        doi="10.1234/test.DOI",
    )


@pytest.fixture
def unpaywall_search() -> UnpaywallSearch:
    headers = {"User-Agent": "TestBot/1.0"}
    return UnpaywallSearch(headers)


@pytest.mark.asyncio
async def test_init(unpaywall_search: UnpaywallSearch) -> None:
    assert unpaywall_search.headers == {"User-Agent": "TestBot/1.0"}
    assert unpaywall_search.client is None


@pytest.mark.asyncio
async def test_context_manager(unpaywall_search: UnpaywallSearch) -> None:
    async with unpaywall_search as us:
        assert isinstance(us.client, httpx.AsyncClient)
        assert us.client.base_url == "https://api.unpaywall.org"


@pytest.mark.asyncio
async def test_enrich_papers_success(unpaywall_search: UnpaywallSearch, mock_paper: Paper) -> None:
    mock_response_data: dict[str, Any] = {
        "doi": "10.1234/test.DOI",
        "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
    }

    with patch("usecase.unpaywall.get_with_retry", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_get.return_value = mock_response

        async with unpaywall_search:
            enriched_papers = await unpaywall_search.enrich_papers([mock_paper])

    assert len(enriched_papers) == 1
    assert enriched_papers[0].pdf_url == "https://example.com/paper.pdf"


@pytest.mark.asyncio
async def test_enrich_papers_success_oa_locations(
    unpaywall_search: UnpaywallSearch, mock_paper: Paper
) -> None:
    mock_response_data: dict[str, Any] = {
        "doi": "10.1234/test.DOI",
        "best_oa_location": None,
        "oa_locations": [{"url_for_pdf": "https://example.com/oa_paper.pdf"}],
    }

    with patch("usecase.unpaywall.get_with_retry", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_get.return_value = mock_response

        async with unpaywall_search:
            enriched_papers = await unpaywall_search.enrich_papers([mock_paper])

    assert len(enriched_papers) == 1
    assert enriched_papers[0].pdf_url == "https://example.com/oa_paper.pdf"


@pytest.mark.asyncio
async def test_enrich_papers_no_doi(unpaywall_search: UnpaywallSearch) -> None:
    paper_no_doi = Paper(
        title="No DOI Paper", authors=["Author"], year=2024, venue="Venue", doi=None
    )

    async with unpaywall_search:
        with pytest.raises(ValueError, match="has no DOI"):
            await unpaywall_search.enrich_papers([paper_no_doi])


@pytest.mark.asyncio
async def test_enrich_papers_api_error(
    unpaywall_search: UnpaywallSearch, mock_paper: Paper
) -> None:
    with patch("usecase.unpaywall.get_with_retry", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        mock_get.return_value = mock_response

        async with unpaywall_search:
            with pytest.raises(Exception):
                await unpaywall_search.enrich_papers([mock_paper])


@pytest.mark.asyncio
async def test_enrich_papers_missing_pdf(
    unpaywall_search: UnpaywallSearch, mock_paper: Paper
) -> None:
    mock_response_data: dict[str, Any] = {
        "doi": "10.1234/test.DOI",
        "best_oa_location": None,
        "oa_locations": [],
    }

    with patch("usecase.unpaywall.get_with_retry", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_get.return_value = mock_response

        async with unpaywall_search:
            enriched_papers = await unpaywall_search.enrich_papers([mock_paper])

    assert len(enriched_papers) == 1
    assert enriched_papers[0].pdf_url is None


@pytest.mark.asyncio
async def test_client_not_initialized(unpaywall_search: UnpaywallSearch, mock_paper: Paper) -> None:
    with pytest.raises(
        RuntimeError, match="UnpaywallSearch must be used as an async context manager"
    ):
        await unpaywall_search.enrich_papers([mock_paper])
