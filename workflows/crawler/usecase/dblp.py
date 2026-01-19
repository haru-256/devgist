"""DBLP APIを使用して学術論文情報を検索・取得するモジュール。

このモジュールは、DBLP Computer Science Bibliographyから
特定のカンファレンスと年度の論文情報を取得する機能を提供します。
robots.txtを尊重し、適切なレート制限を行いながらクロールを実行します。
"""

from typing import Any, Literal

import httpx
from loguru import logger

from domain.paper import Paper
from libs import RobotGuard


class DBLPSearch:
    """DBLP APIから論文情報を検索・取得するクラス。

    このクラスは非同期コンテキストマネージャーとして設計されており、
    `async with`文を使用して利用します。robots.txtを自動的にチェックし、
    クロールが許可されている場合のみAPIリクエストを実行します。

    Attributes:
        base_url: DBLPのベースURL
        search_api: DBLP検索APIのエンドポイント
        robot_guard: robots.txtをチェックするRobotGuardインスタンス
        headers: HTTPリクエストで使用するヘッダー
        client: 非同期HTTPクライアント（コンテキストマネージャー内でのみ有効）

    Example:
        >>> headers = {"User-Agent": "MyBot/1.0"}
        >>> async with DBLPSearch(headers) as search:
        ...     papers = await search.fetch_papers(conf="recsys", year=2025)
    """

    base_url = "https://dblp.org"
    search_api = "https://dblp.org/search/publ/api"

    def __init__(self, headers: dict[str, str]) -> None:
        """DBLPSearchインスタンスを初期化します。

        Args:
            headers: HTTPリクエストで使用するヘッダー辞書
        """
        self.robot_guard = RobotGuard(self.base_url, user_agent="ArchilogBot")
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DBLPSearch":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化し、robots.txtをロードします。

        Returns:
            初期化されたDBLPSearchインスタンス
        """
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
        """非同期コンテキストマネージャーの終了処理。

        HTTPクライアントを適切にクローズします。
        """
        if self.client is not None:
            await self.client.aclose()

    async def fetch_papers(
        self,
        conf: Literal["recsys", "kdd", "wsdm", "www", "sigir", "cikm"],
        year: int,
        h: int = 1000,
    ) -> list[Paper]:
        """指定されたカンファレンスと年度の論文情報を取得します。

        DBLP APIを使用して、特定のカンファレンスと年度に該当する
        論文のメタデータを取得します。robots.txtで許可されていない
        場合はPermissionErrorを発生させます。

        Args:
            conf: 対象カンファレンス名（recsys, kdd, wsdm, www, sigir, cikm）
            year: 対象年度
            h: 取得する最大論文数（デフォルト: 1000）

        Returns:
            取得した論文のリスト

        Raises:
            RuntimeError: コンテキストマネージャー外で呼び出された場合
            PermissionError: robots.txtでクロールが拒否されている場合
            httpx.HTTPStatusError: APIリクエストが失敗した場合
            httpx.RequestError: ネットワークエラーが発生した場合
            ValueError: レスポンスのパースに失敗した場合
        """
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
        """DBLP APIのレスポンスJSONから論文情報を抽出します。

        必須フィールド（title, authors, year, venue）が欠けている
        論文はスキップされます。

        Args:
            data: DBLP APIから返されたJSONレスポンス

        Returns:
            パースされた論文のリスト

        Raises:
            ValueError: 検索結果が0件の場合
        """
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
