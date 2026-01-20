"""DBLPクローラーのメインエントリーポイント。

このモジュールは、DBLP APIを使用して学術論文情報を収集するクローラーの
実行エントリーポイントを提供します。
"""

import asyncio

from loguru import logger

from usecase.dblp import DBLPSearch
from usecase.semantic_scholar import SemanticScholarSearch


async def recsys_crawl(headers: dict[str, str]) -> None:
    """RecSysカンファレンスの論文情報を収集します。

    2025年のRecSysカンファレンスで発表された論文のメタデータを
    DBLPから取得し、取得件数をログに出力します。

    Args:
        headers: HTTPリクエストで使用するヘッダー辞書
    """
    async with DBLPSearch(headers) as dblp_search_usecase:
        papers = await dblp_search_usecase.fetch_papers(conf="recsys", year=2025, h=1000)
        logger.info(f"Fetched {len(papers)} papers")

    total_papers_count = len(papers)
    async with SemanticScholarSearch(headers) as semantic_scholar_search_usecase:
        enriched_papers = await semantic_scholar_search_usecase.enrich_papers(papers)

    if total_papers_count > 0:
        abs_pass_cnt = sum(p.abstract is not None for p in enriched_papers)
        pdf_pass_cnt = sum(p.pdf_url is not None for p in enriched_papers)
        logger.info(
            f"Abstract pass rate: {abs_pass_cnt / total_papers_count:.4f}, {abs_pass_cnt}/{total_papers_count}"
        )
        logger.info(
            f"PDF pass rate: {pdf_pass_cnt / total_papers_count:.4f}, {pdf_pass_cnt}/{total_papers_count}"
        )


async def main() -> None:
    """クローラーの非同期エントリーポイント。

    ログメッセージを出力後、RecSysのクロール処理を実行します。
    """
    logger.info("Hello from crawler!")
    await recsys_crawl(headers={"User-Agent": "ArchilogBot/1.0"})


if __name__ == "__main__":
    asyncio.run(main())
