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


async def recsys_crawl(
    headers: dict[str, str], year: int, semaphore: asyncio.Semaphore
) -> list[Paper]:
    """RecSysカンファレンスの論文情報を収集します。

    Args:
        headers: HTTPリクエストで使用するヘッダー辞書
        year: 論文の発表年
        semaphore: 各APIへのリクエスト並列数を制限するためのセマフォ
    """

    # 共有HTTPクライアントを作成
    async with create_http_client(headers=headers) as client:
        # リポジトリインスタンスを作成
        dblp_repo = DBLPRepository(client)
        await dblp_repo.initialize()  # RobotGuard setup

        ss_repo = SemanticScholarRepository(client)
        unpaywall_repo = UnpaywallRepository(client)
        arxiv_repo = ArxivRepository(client)

        # ユースケースの初期化
        usecase = FetchRecSysPapers(
            paper_retriever=dblp_repo,
            paper_enrichers=[ss_repo, unpaywall_repo, arxiv_repo],
        )

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
    sem = asyncio.Semaphore(3)
    # years = range(2010, 2026)
    years = range(2025, 2026)

    logger.info(f"Starting crawl for years: {years}")
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for year in years:
            tasks.append(tg.create_task(recsys_crawl(headers=headers, year=year, semaphore=sem)))
    enriched_papers = [paper for task in tasks for paper in task.result()]
    logger.info(f"Total enriched papers: {len(enriched_papers)}")


if __name__ == "__main__":
    setup_logger()
    asyncio.run(main())
