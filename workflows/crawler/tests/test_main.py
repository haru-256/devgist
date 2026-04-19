from unittest.mock import AsyncMock

import pytest

from crawler.application.usecases.crawl_conference_papers import CrawlConferencePapers
from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper
from crawler.main import run_crawl_task


@pytest.mark.asyncio
async def test_run_crawl_task_returns_empty_when_usecase_fails() -> None:
    """単一タスク失敗時に例外を外へ伝播せず、空結果で継続できることを確認する。"""
    usecase = AsyncMock(spec=CrawlConferencePapers)
    usecase.conf_name = ConferenceName.RECSYS
    usecase.execute.side_effect = RuntimeError("boom")

    result = await run_crawl_task(usecase, 2025)

    assert result == []
    usecase.execute.assert_awaited_once_with(2025)


@pytest.mark.asyncio
async def test_run_crawl_task_returns_enriched_papers_on_success() -> None:
    """正常時にはユースケース結果をそのまま返すことを確認する。"""
    papers = [
        Paper(
            title="P1",
            authors=["A"],
            year=2025,
            venue="RecSys",
            doi="10.1145/test",
            abstract="abstract",
            pdf_url="https://example.com/p1.pdf",
        )
    ]

    usecase = AsyncMock(spec=CrawlConferencePapers)
    usecase.conf_name = ConferenceName.RECSYS
    usecase.execute.return_value = papers

    result = await run_crawl_task(usecase, 2025)

    assert result == papers
    usecase.execute.assert_awaited_once_with(2025)
