from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from crawler.application.usecases.crawl_conference_papers import CrawlConferencePapers
from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper
from crawler.domain.repositories.repository import PaperDatalake, PaperEnricher, PaperRetriever


@pytest.fixture
def mock_dblp_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperRetriever)
    repo.fetch_papers = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_semantic_scholar_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnricher)
    repo.enrich_papers = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_unpaywall_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnricher)
    repo.enrich_papers = mocker.AsyncMock()
    return repo


@pytest.fixture
def mock_arxiv_repo(mocker: MockerFixture) -> MagicMock:
    repo = mocker.MagicMock(spec=PaperEnricher)
    repo.enrich_papers = mocker.AsyncMock()
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

    # 2. Enrich後の期待値 (モックが加工するわけではないが、フローの確認)
    # S2 Enrichment
    s2_enriched = [initial_papers[0]]  # DOIがあるものだけ処理される想定
    mock_semantic_scholar_repo.enrich_papers.return_value = s2_enriched

    # Unpaywall Enrichment
    unpaywall_enriched = s2_enriched
    mock_unpaywall_repo.enrich_papers.return_value = unpaywall_enriched

    # Arxiv Enrichment
    arxiv_enriched = unpaywall_enriched
    mock_arxiv_repo.enrich_papers.return_value = arxiv_enriched

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

    # 2. Semantic Scholar Enrich (filtered papers only)
    expected_papers_for_enrich = [initial_papers[0]]
    mock_semantic_scholar_repo.enrich_papers.assert_called_once()
    args, kwargs = mock_semantic_scholar_repo.enrich_papers.call_args
    assert args[0] == expected_papers_for_enrich
    assert kwargs["overwrite"] is False

    # 3. Unpaywall Enrich
    mock_unpaywall_repo.enrich_papers.assert_called_once()
    assert mock_unpaywall_repo.enrich_papers.call_args[0][0] == s2_enriched

    # 4. Arxiv Enrich
    mock_arxiv_repo.enrich_papers.assert_called_once()
    assert mock_arxiv_repo.enrich_papers.call_args[0][0] == unpaywall_enriched

    # 5. Datalake save_papers（最終的なenrich済み論文が保存されること）
    mock_datalake.save_papers.assert_called_once_with(
        arxiv_enriched,
        papers_rep_name="recsys",
    )

    # Result should be the final enriched papers
    assert result == arxiv_enriched
