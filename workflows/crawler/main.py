"""DBLPクローラーのメインエントリーポイント。

このモジュールは、DBLP APIを使用して学術論文情報を収集するクローラーの
実行エントリーポイントを提供します。
"""

import asyncio

from loguru import logger

from domain.paper import Paper
from libs.log import setup_logger
from usecase.dblp import DBLPSearch
from usecase.semantic_scholar import SemanticScholarSearch


async def recsys_crawl(
    headers: dict[str, str], year: int, semaphore: asyncio.Semaphore
) -> list[Paper]:
    """RecSysカンファレンスの論文情報を収集します。

    2025年のRecSysカンファレンスで発表された論文のメタデータを
    DBLPから取得し、Semantic Scholarから要約やPDF URLを取得します。

    Args:
        headers: HTTPリクエストで使用するヘッダー辞書
        year: 論文の発表年
        semaphore: 各API(DBLP, Semantic Scholar)へのリクエスト並列数を制限するためのセマフォ
    """

    async with DBLPSearch(headers) as dblp_search_usecase:
        papers = await dblp_search_usecase.fetch_papers(
            conf="recsys", year=year, h=1000, semaphore=semaphore
        )
        logger.info(f"Fetched {len(papers)} papers")

    total_papers_count = len(papers)
    async with SemanticScholarSearch(headers) as semantic_scholar_search_usecase:
        enriched_papers = await semantic_scholar_search_usecase.enrich_papers(
            papers, semaphore=semaphore
        )

    if total_papers_count > 0:
        abs_pass_cnt = sum(p.abstract is not None for p in enriched_papers)
        pdf_pass_cnt = sum(p.pdf_url is not None for p in enriched_papers)
        logger.info(
            f"RecSys {year},  Total papers: {total_papers_count}, Abstract pass rate: {abs_pass_cnt / total_papers_count:.4f}, {abs_pass_cnt}/{total_papers_count}, PDF pass rate: {pdf_pass_cnt / total_papers_count:.4f}, {pdf_pass_cnt}/{total_papers_count}"
        )
    return enriched_papers


async def main() -> None:
    """クローラーの非同期エントリーポイント。

    ログメッセージを出力後、RecSysのクロール処理を実行します。
    """
    headers = {"User-Agent": "ArchilogBot/1.0"}
    sem = asyncio.Semaphore(3)
    years = range(2010, 2026)

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
