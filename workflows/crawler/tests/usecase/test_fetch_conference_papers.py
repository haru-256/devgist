from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from crawler.application.usecases.crawl_conference_papers import CrawlConferencePapers
from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import FetchedPaperEnrichment, Paper, PaperEnrichment
from crawler.domain.repositories.repository import (
    PaperDatalake,
    PaperEnrichmentProvider,
    PaperRetriever,
)


@pytest.fixture
def mock_dblp_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperRetriever)
    repo.fetch_papers = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_semantic_scholar_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnrichmentProvider)
    repo.fetch_enrichments = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_unpaywall_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnrichmentProvider)
    repo.fetch_enrichments = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_arxiv_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnrichmentProvider)
    repo.fetch_enrichments = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_datalake(mocker: MockerFixture) -> MagicMock:
    datalake = mocker.MagicMock(spec=PaperDatalake)
    datalake.save_papers = mocker.AsyncMock(return_value=[])
    return datalake


@pytest.mark.asyncio
async def test_execute_flow(
    mock_dblp_repo: MagicMock,
    mock_semantic_scholar_repo: MagicMock,
    mock_unpaywall_repo: MagicMock,
    mock_arxiv_repo: MagicMock,
    mock_datalake: MagicMock,
) -> None:
    """RecSysの論文取得フローが正しく実行されることを検証"""

    # 1. DBLPから取得される初期論文リスト
    initial_papers = [
        Paper(
            title="P1",
            authors=[],
            year=2024,
            venue="RecSys",
            doi="10.1145/1",
        ),
        Paper(title="P2", authors=[], year=2024, venue="RecSys", doi=None),  # No DOI
    ]
    mock_dblp_repo.fetch_papers.return_value = initial_papers

    mock_semantic_scholar_repo.fetch_enrichments.return_value = [
        FetchedPaperEnrichment(
            doi="10.1145/1",
            enrichment=PaperEnrichment(abstract="Abstract from S2"),
        )
    ]
    mock_unpaywall_repo.fetch_enrichments.return_value = [
        FetchedPaperEnrichment(
            doi="10.1145/1",
            enrichment=PaperEnrichment(pdf_url="https://example.com/p1.pdf"),
        )
    ]
    mock_arxiv_repo.fetch_enrichments.return_value = []

    usecase = CrawlConferencePapers(
        conf_name=ConferenceName.RECSYS,
        paper_retriever=mock_dblp_repo,
        paper_enrichers=[
            mock_semantic_scholar_repo,
            mock_unpaywall_repo,
            mock_arxiv_repo,
        ],
        paper_datalake=mock_datalake,
    )

    year = 2024

    result = await usecase.execute(year)

    # 検証

    # 1. DBLP Fetch (conf="recsys", year=2024, h=1000)
    mock_dblp_repo.fetch_papers.assert_called_once_with(conf="recsys", year=2024, h=1000)

    # 中間でDOIがない論文はフィルタリングされるべき (main.pyのロジックを踏襲)
    # initial_papers[1] has no DOI, so likely filtered out before enrichment

    expected_papers_for_enrich = [initial_papers[0]]
    mock_semantic_scholar_repo.fetch_enrichments.assert_called_once_with(expected_papers_for_enrich)
    mock_unpaywall_repo.fetch_enrichments.assert_called_once_with(expected_papers_for_enrich)
    mock_arxiv_repo.fetch_enrichments.assert_called_once_with(expected_papers_for_enrich)

    # 5. Datalake save_papers（最終的なenrich済み論文が保存されること）
    mock_datalake.save_papers.assert_called_once_with(
        [initial_papers[0]],
        papers_rep_name="recsys",
    )

    assert result == [initial_papers[0]]
    assert initial_papers[0].abstract == "Abstract from S2"
    assert initial_papers[0].pdf_url == "https://example.com/p1.pdf"


@pytest.mark.asyncio
async def test_execute_logs_fetch_result_with_conference_and_year(
    mock_dblp_repo: MagicMock,
    mock_datalake: MagicMock,
    mocker: MockerFixture,
) -> None:
    """DBLP取得後のログに学会名と年度の両方が含まれること"""
    mock_dblp_repo.fetch_papers.return_value = [
        Paper(title="P1", authors=[], year=2024, venue="RecSys", doi="10.1145/1"),
    ]

    mock_logger = mocker.patch("crawler.application.usecases.crawl_conference_papers.logger")

    usecase = CrawlConferencePapers(
        conf_name=ConferenceName.RECSYS,
        paper_retriever=mock_dblp_repo,
        paper_enrichers=[],
        paper_datalake=mock_datalake,
    )

    await usecase.execute(2024)

    mock_logger.info.assert_any_call("Fetched 1 papers from DBLP for RECSYS 2024")


@pytest.mark.asyncio
async def test_apply_enrichments_updates_all_papers_with_same_doi(
    mock_dblp_repo: MagicMock,
    mock_semantic_scholar_repo: MagicMock,
    mock_datalake: MagicMock,
) -> None:
    papers = [
        Paper(title="P1", authors=[], year=2024, venue="RecSys", doi="10.1145/1"),
        Paper(title="P1 duplicate", authors=[], year=2024, venue="RecSys", doi="10.1145/1"),
    ]
    mock_dblp_repo.fetch_papers.return_value = papers
    mock_semantic_scholar_repo.fetch_enrichments.return_value = [
        FetchedPaperEnrichment(
            doi="10.1145/1",
            enrichment=PaperEnrichment(abstract="Shared abstract"),
        )
    ]

    usecase = CrawlConferencePapers(
        conf_name=ConferenceName.RECSYS,
        paper_retriever=mock_dblp_repo,
        paper_enrichers=[mock_semantic_scholar_repo],
        paper_datalake=mock_datalake,
    )

    await usecase.execute(2024)

    assert papers[0].abstract == "Shared abstract"
    assert papers[1].abstract == "Shared abstract"


@pytest.mark.asyncio
async def test_apply_enrichments_can_overwrite_existing_values(
    mock_dblp_repo: MagicMock,
    mock_semantic_scholar_repo: MagicMock,
    mock_datalake: MagicMock,
) -> None:
    paper = Paper(
        title="P1",
        authors=[],
        year=2024,
        venue="RecSys",
        doi="10.1145/1",
        abstract="Original abstract",
    )
    mock_dblp_repo.fetch_papers.return_value = [paper]
    mock_semantic_scholar_repo.fetch_enrichments.return_value = [
        FetchedPaperEnrichment(
            doi="10.1145/1",
            enrichment=PaperEnrichment(abstract="Updated abstract"),
        )
    ]

    usecase = CrawlConferencePapers(
        conf_name=ConferenceName.RECSYS,
        paper_retriever=mock_dblp_repo,
        paper_enrichers=[mock_semantic_scholar_repo],
        paper_datalake=mock_datalake,
        overwrite_enrichments=True,
    )

    await usecase.execute(2024)

    assert paper.abstract == "Updated abstract"
