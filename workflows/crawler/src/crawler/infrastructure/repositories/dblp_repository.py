import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper
from crawler.infrastructure.http.http_retry_client import HttpRetryClient
from crawler.utils import RobotGuard


class DBLPRepository:
    """DBLP APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://dblp.org"
    SEARCH_API = "https://dblp.org/search/publ/api"
    DEFAULT_SLEEP_SECONDS = 1
    DEFAULT_CONCURRENCY = 5
    RETRY_STATUSES = frozenset({429, 500})
    RETRY_EXCEPTIONS = (
        httpx.ReadError,
        httpx.RequestError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
    )

    def __init__(self, http: HttpRetryClient) -> None:
        """DBLPRepositoryインスタンスを初期化します。

        Args:
            http: HTTPリクエストに使用するHttpRetryClientインスタンス。
        """
        self.http = http
        self.robot_guard = RobotGuard(self.BASE_URL, user_agent="DevGistBot/1.0")

    @classmethod
    def from_client(
        cls,
        client: httpx.AsyncClient,
        max_retry_count: int = 10,
    ) -> "DBLPRepository":
        """DBLP API用に設定されたHttpRetryClientを持つリポジトリを生成します。"""
        http_client = HttpRetryClient(
            client,
            retry_statuses=cls.RETRY_STATUSES,
            retry_exceptions=cls.RETRY_EXCEPTIONS,
            max_retry_count=max_retry_count,
            limiter=AsyncLimiter(1, cls.DEFAULT_SLEEP_SECONDS),
            semaphore=asyncio.Semaphore(cls.DEFAULT_CONCURRENCY),
        )
        return cls(http=http_client)

    async def setup(self, client: httpx.AsyncClient) -> None:
        """リポジトリの初期化処理を実行します。

        robots.txt をロードします。この関数は使用前に一度呼び出す必要があります。
        """
        await self.robot_guard.load(client=client)

    async def fetch_papers(
        self,
        conf: ConferenceName,
        year: int,
        h: int = 1000,
    ) -> list[Paper]:
        """指定されたカンファレンスと年度の論文情報を取得します。

        Args:
            conf: 対象カンファレンス名。
            year: 対象年度。
            h: 取得する最大論文数。デフォルトは 1000。

        Returns:
            取得した Paper オブジェクトのリスト。

        Raises:
            PermissionError: robots.txt でクロールが拒否されている場合。
            httpx.HTTPStatusError: API リクエストが失敗した場合。
            httpx.RequestError: ネットワークレベルのエラーが発生した場合。
        """
        if not self.robot_guard.loaded:
            raise RuntimeError("DBLPRepository.setup() must be called before using the repository")

        # robots.txtのチェック
        if not self.robot_guard.can_fetch(self.SEARCH_API):
            raise PermissionError(f"Crawling {self.SEARCH_API} is not allowed by robots.txt")

        conf_query = f"stream:conf/{conf}:"
        year_query = f"year:{year}:"
        params: dict[str, str | int] = {
            "query": f"{conf_query}+{year_query}",
            "format": "json",
            "h": h,
        }

        try:
            resp = await self.http.get(self.SEARCH_API, params=params)

            resp.raise_for_status()
            data = resp.json()
            return self._parse_papers(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise

    def _parse_papers(self, data: dict[str, Any]) -> list[Paper]:
        """API レスポンスから Paper リストを生成します。

        Args:
            data: DBLP Search API のレスポンス（JSON デコード済み）。

        Returns:
            Paper オブジェクトのリスト。
        """
        try:
            hits_container = data["result"]["hits"]
            total = int(hits_container["@total"])
            if total == 0:
                logger.info("No papers found matching the criteria.")
                return []

            hits = hits_container.get("hit", [])
            papers = []
            for hit in hits:
                paper = self._parse_single_paper(hit)
                if paper:
                    papers.append(paper)
            return papers
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse DBLP response: {e}")
            return []

    def _parse_single_paper(self, hit: dict[str, Any]) -> Paper | None:
        """DBLP hit エントリから Paper オブジェクトを生成します。

        Args:
            hit: DBLP API レスポンスの hit 要素。

        Returns:
            生成された Paper オブジェクト。パース失敗時は None。
        """
        try:
            info = hit["info"]

            # 必須フィールドの検証
            title = info.get("title")
            if not title:
                return None

            authors_data = info.get("authors")
            authors = self._parse_authors(authors_data)

            year_str = info.get("year")
            if not year_str:
                return None
            year = int(year_str)

            venue = info.get("venue")
            if not venue:
                return None

            return Paper(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                doi=info.get("doi"),
                type=info.get("type"),
                ee=info.get("ee"),
            )
        except Exception as e:
            logger.warning(f"Failed to parse single paper from DBLP hit: {hit}. Error: {e}")
            return None

    def _parse_authors(self, authors_data: Any) -> list[str]:
        """著者データから著者名リストを抽出します。

        Args:
            authors_data: DBLP レスポンスの ``authors`` フィールド値。

        Returns:
            著者名の文字列リスト。
        """
        if not authors_data:
            return []

        # authors要素自体が辞書の場合（{"author": ...}）
        if isinstance(authors_data, dict):
            inner_author = authors_data.get("author")
            if not inner_author:
                return []

            # authorがリストの場合
            if isinstance(inner_author, list):
                return [
                    str(a.get("text"))
                    for a in inner_author
                    if isinstance(a, dict) and a.get("text")
                ]
            # authorが単一の辞書の場合
            elif isinstance(inner_author, dict):
                text = inner_author.get("text")
                return [text] if text else []

        return []
