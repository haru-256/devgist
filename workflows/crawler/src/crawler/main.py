"""DBLPクローラーのメインエントリーポイント。

このモジュールは、DBLP APIを使用して学術論文情報を収集するクローラーの
実行エントリーポイントを提供します。
"""

import asyncio

from loguru import logger

from crawler.domain.paper import Paper
from crawler.repository import (
    ArxivRepository,
    DBLPRepository,
    SemanticScholarRepository,
    UnpaywallRepository,
)
from crawler.usecase.fetch_papers import FetchRecSysPapers
from crawler.utils.http_client import create_http_client
from crawler.utils.log import setup_logger

LIMITER_KEY_DBLP = "dblp"
LIMITER_KEY_SEMANTIC_SCHOLAR = "semantic_scholar"
LIMITER_KEY_UNPAYWALL = "unpaywall"
LIMITER_KEY_ARXIV = "arxiv"


async def run_crawl_task(
    usecase: FetchRecSysPapers,
    year: int,
    semaphore: asyncio.Semaphore,
) -> list[Paper]:
    """指定された年のクロールタスクを実行し、結果をログ出力します。

    Args:
        usecase: 実行するユースケース
        year: 対象年
        semaphore: 並列実行制限用セマフォ

    Returns:
        取得・補完された論文リスト
    """
    enriched_papers = await usecase.execute(year, semaphore)

    # 統計情報のログ出力
    total_papers_count = len(enriched_papers)
    if total_papers_count > 0:
        abs_pass_cnt = sum(p.abstract is not None for p in enriched_papers)
        pdf_pass_cnt = sum(p.pdf_url is not None for p in enriched_papers)
        logger.info(
            f"RecSys {year}, Total papers: {total_papers_count}, "
            f"Abstract pass rate: {abs_pass_cnt / total_papers_count:.4f} ({abs_pass_cnt}/{total_papers_count}), "
            f"PDF pass rate: {pdf_pass_cnt / total_papers_count:.4f} ({pdf_pass_cnt}/{total_papers_count})"
        )

    return enriched_papers


async def main() -> None:
    """クローラーの非同期エントリーポイント。

    ログメッセージを出力後、RecSysのクロール処理を実行します。
    """
    headers = {"User-Agent": "ArchilogBot/1.0"}
    sem = asyncio.Semaphore(100)
    years = range(2010, 2026)
    # years = range(2025, 2026)

    # 各サービスのレートリミッターを作成（全体で共有）
    limiters = {
        LIMITER_KEY_DBLP: DBLPRepository.create_limiter(),
        LIMITER_KEY_SEMANTIC_SCHOLAR: SemanticScholarRepository.create_limiter(),
        LIMITER_KEY_UNPAYWALL: UnpaywallRepository.create_limiter(),
        LIMITER_KEY_ARXIV: ArxivRepository.create_limiter(),
    }

    logger.info(f"Starting crawl for years: {years}")

    # 共有HTTPクライアントを作成
    async with create_http_client(headers=headers) as client:
        # 各リポジトリを初期化
        dblp_repo = DBLPRepository(client, limiter=limiters[LIMITER_KEY_DBLP])
        await dblp_repo.setup()
        ss_repo = SemanticScholarRepository(client, limiter=limiters[LIMITER_KEY_SEMANTIC_SCHOLAR])
        unpaywall_repo = UnpaywallRepository(client, limiter=limiters[LIMITER_KEY_UNPAYWALL])
        arxiv_repo = ArxivRepository(client, limiter=limiters[LIMITER_KEY_ARXIV])
        # ユースケースの初期化
        usecase = FetchRecSysPapers(
            paper_retriever=dblp_repo,
            paper_enrichers=[ss_repo, unpaywall_repo, arxiv_repo],
        )

        tasks = []
        async with asyncio.TaskGroup() as tg:
            for year in years:
                tasks.append(tg.create_task(run_crawl_task(usecase, year, sem)))
        enriched_papers = [paper for task in tasks for paper in task.result()]

    logger.info(f"Total enriched papers: {len(enriched_papers)}")


if __name__ == "__main__":
    setup_logger()
    asyncio.run(main())
