import asyncio
from typing import Any, Literal

import httpx
from loguru import logger

from crawler.domain.paper import Paper
from crawler.utils import RobotGuard
from crawler.utils.http_utils import get_with_retry


class DBLPRepository:
    """DBLP APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://dblp.org"
    SEARCH_API = "https://dblp.org/search/publ/api"

    def __init__(self, headers: dict[str, str]) -> None:
        """DBLPRepositoryインスタンスを初期化します。

        Args:
            headers: HTTPリクエストで使用するヘッダー辞書
        """
        self.robot_guard = RobotGuard(self.BASE_URL, user_agent="ArchilogBot")
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DBLPRepository":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化し、robots.txtをロードします。

        Returns:
            初期化されたDBLPRepositoryインスタンス
        """
        limits = httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=5.0,
        )
        self.client = httpx.AsyncClient(
            headers=self.headers, base_url=self.BASE_URL, limits=limits, timeout=30.0
        )
        await self.robot_guard.load(client=self.client)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理。

        HTTPクライアントを適切にクローズします。
        """
        if self.client is not None:
            await self.client.aclose()

    async def fetch_papers(
        self,
        conf: Literal["recsys", "kdd", "wsdm", "www", "sigir", "cikm"],
        year: int,
        semaphore: asyncio.Semaphore,
        h: int = 1000,
    ) -> list[Paper]:
        """指定されたカンファレンスと年度の論文情報を取得します。

        Args:
            conf: 対象カンファレンス名
            year: 対象年度
            h: 取得する最大論文数（デフォルト: 1000）
            semaphore: 並列実行数を制限するセマフォ

        Returns:
            Paperオブジェクトのリスト

        Raises:
            RuntimeError: クライアントが初期化されていない場合
            PermissionError: robots.txtでクロールが拒否されている場合
            httpx.HTTPStatusError: APIリクエストが失敗した場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")
        if not self.robot_guard.loaded:
            await self.robot_guard.load(client=self.client)

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
            # セマフォを使用してリクエスト並列数を制御
            request_coro = get_with_retry(self.client, self.SEARCH_API, params=params)
            async with semaphore:
                resp = await request_coro

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
        """APIレスポンスからPaperオブジェクトのリストを生成します。"""
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
        """単一の論文データをパースしてPaperオブジェクトを生成します。"""
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
        """著者データをパースしてリスト化します。"""
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
