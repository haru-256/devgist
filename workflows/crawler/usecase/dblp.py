from typing import Any, Literal

import httpx
from loguru import logger

from domain.paper import Paper
from libs import RobotGuard


class DBLPSearch:
    base_url = "https://dblp.org"
    search_api = "https://dblp.org/search/publ/api"

    def __init__(self, headers: dict[str, str]) -> None:
        self.robot_guard = RobotGuard(self.base_url, user_agent="ArchilogBot")
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DBLPSearch":
        limits = httpx.Limits(
            max_connections=100,  # 全体で保持する最大接続数
            max_keepalive_connections=20,  # アイドル状態で維持する最大接続数
            keepalive_expiry=5.0,  # アイドル接続を保持する秒数
        )
        self.client = httpx.AsyncClient(
            headers=self.headers, base_url=self.base_url, limits=limits, timeout=30.0
        )
        await self.robot_guard.load(client=self.client)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.client is not None:
            await self.client.aclose()

    async def fetch_papers(
        self,
        conf: Literal["recsys", "kdd", "wsdm", "www", "sigir", "cikm"],
        year: int,
        h: int = 1000,
    ) -> list[Paper]:
        if self.client is None:
            raise RuntimeError(
                "DBLPSearch must be used as an async contex manager (use 'async with')"
            )
        if not self.robot_guard.loaded:
            await self.robot_guard.load(client=self.client)

        # robots.txtのチェック
        if not self.robot_guard.can_fetch(self.search_api):
            raise PermissionError(f"Crawling {self.search_api} is not allowed by robots.txt")

        conf_query = f"stream:conf/{conf}:"
        year_query = f"year:{year}:"
        params: dict[str, str | int] = {
            "query": f"{conf_query}+{year_query}",
            "format": "json",
            "h": h,
        }

        try:
            resp = await self.client.get(self.search_api, params=params)
            resp.raise_for_status()
            papers = self._parse_paper(resp.json())
            return papers
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise
        except ValueError as e:
            logger.error(f"JSON parse or validation error: {e}")
            raise

    def _parse_paper(self, data: dict[str, Any]) -> list[Paper]:
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
            authors = self._parse_authors(info.get("authors", {}))
            if not authors:
                logger.error(f"No valid authors found for paper: {title}")
                continue

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
        return papers

    def _parse_authors(self, authors_data: dict[str, Any]) -> list[str]:
        """著者情報をパースする

        Args:
            authors_data: APIレスポンスの著者データ

        Returns:
            著者名のリスト
        """
        authors: list[str] = []
        _authors = authors_data.get("author")

        if isinstance(_authors, list):
            authors.extend([author.get("text") for author in _authors if author.get("text")])
        elif isinstance(_authors, dict):
            author_text = _authors.get("text")
            if author_text is not None:
                authors.append(author_text)
        elif _authors is not None:
            logger.warning(f"Unexpected author type: {type(_authors)}")

        return authors
