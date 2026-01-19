import asyncio

from loguru import logger

from usecase.dblp import DBLPSearch


async def recsys_crawl(headers: dict[str, str]) -> None:
    """RecSysカンファレンスのpaperのタイトルを収集する"""
    async with DBLPSearch(headers) as dblp_search_usecase:
        papers = await dblp_search_usecase.fetch_papers(conf="recsys", year=2025, h=1000)
        logger.info(f"Fetched {len(papers)} papers")


async def main() -> None:
    logger.info("Hello from crawler!")
    await recsys_crawl(headers={"User-Agent": "ArchilogBot/1.0"})


if __name__ == "__main__":
    asyncio.run(main())
