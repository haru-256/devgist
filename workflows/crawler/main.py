import asyncio
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from libs import RobotGuard


class Paper(BaseModel):
    """論文を表す"""

    title: str
    authors: list[str]
    year: int
    venue: str
    doi: str | None
    type: str | None
    ee: str | None
    url: str | None


async def recsys_crawl(headers: dict[str, str]) -> None:
    """RecSysカンファレンスのpaperのタイトルを収集する"""
    base_url = "https://dblp.org"

    year = 2024

    dblp_search_api = "https://dblp.org/search/publ/api"
    conf_query = "stream:conf/recsys:"
    year_query = f"year:{year}:"
    params = {
        "query": f"{conf_query}+{year_query}",
        "format": "json",
        "h": 1000,
    }

    # TODO: dblpからの検索は他のカンファレンスでも同様なので、以下のロジックはコアロジックとして外部に切り出す
    # TODO: ドメインデータとして、Paper Typeを定義する
    # search apiを使うとどのトラック(Industirial, Full, Short)で採用されたかの情報はない
    robot_guard = RobotGuard(base_url, user_agent="ArchilogBot")
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        await robot_guard.load(client=client)
        resp = await client.get(dblp_search_api, params=params)
        resp.raise_for_status()
        data: dict[str, dict] = resp.json()
        hits = data.get("result", {}).get("hits", {})
        num_hits = int(hits.get("@total", 0))
        if num_hits <= 0:
            raise ValueError("No hits found")

        papers: list[Paper] = []
        for hit in hits.get("hit", []):
            info: dict[str, Any] = hit.get("info", {})

            # 必須パラメータのvalidation
            title: str | None = info.get("title")
            year: str | None = info.get("year")
            venue: str | None = info.get("venue")
            if title is None:
                logger.error("Title is None")
                continue
            if year is None:
                logger.error("Year is None")
                continue
            if venue is None:
                logger.error("Venue is None")
                continue
            authors: list[str] = []
            _authors = info.get("authors", {}).get("author")
            if isinstance(_authors, list):
                authors.extend([author.get("text") for author in _authors])
            elif isinstance(_authors, dict):
                a = _authors.get("text")
                if a is not None:
                    authors.append(a)
            elif _authors is None:
                logger.error("Author is None")
                continue
            else:
                logger.error(f"Invalid author Type: {type(_authors)}")

            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=int(year),
                    venue=venue,
                    type=info.get("type"),
                    doi=info.get("doi"),
                    url=info.get("url"),
                    ee=info.get("ee"),
                )
            )


async def main() -> None:
    logger.info("Hello from crawler!")
    await recsys_crawl(headers={"User-Agent": "ArchilogBot/1.0"})


if __name__ == "__main__":
    asyncio.run(main())
