"""Semantic Scholar API との通信を担当するリポジトリモジュール。"""

import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.models.paper import Paper
from crawler.infrastructure.http.http_retry_client import HttpRetryClient


class SemanticScholarRepository:
    """Semantic Scholar APIとの通信を担当するリポジトリクラス。"""

    # Semantic Scholar APIは最大500件までバッチで取得可能
    BATCH_SIZE = 500
    FIELDS = "externalIds,abstract,openAccessPdf,title,year,venue,authors,url"
    BASE_URL = "https://api.semanticscholar.org"
    PAPER_BATCH_SEARCH_PATH = "graph/v1/paper/batch"
    DEFAULT_SLEEP_SECONDS = 0.1
    DEFAULT_CONCURRENCY = 5

    def __init__(self, http: HttpRetryClient) -> None:
        """SemanticScholarRepositoryインスタンスを初期化します。

        Args:
            http: HTTPリクエストに使用するHttpRetryClientインスタンス。
        """
        self.http = http

    @classmethod
    def from_client(
        cls,
        client: httpx.AsyncClient,
        max_retry_count: int = 10,
    ) -> "SemanticScholarRepository":
        """Semantic Scholar API用に設定されたHttpRetryClientを持つリポジトリを生成します。

        Args:
            client: 基本となるAsyncClient
            max_retry_count: HTTP リクエストの最大リトライ回数。

        Returns:
            レート制限とリトライ機能を持つSemanticScholarRepositoryインスタンス
        """
        http_client = HttpRetryClient(
            client=client,
            max_retry_count=max_retry_count,
            limiter=AsyncLimiter(1, cls.DEFAULT_SLEEP_SECONDS),
            semaphore=asyncio.Semaphore(cls.DEFAULT_CONCURRENCY),
        )
        return cls(http=http_client)

    async def enrich_papers(
        self,
        papers: list[Paper],
        overwrite: bool = False,
    ) -> list[Paper]:
        """論文リストにSemantic Scholarのデータ（Abstract と PDF URL）を付与します。

        DOIを持つ論文のみが処理対象となります。

        Args:
            papers: 更新対象の論文リスト。
            overwrite: 既存のデータを上書きするかどうか。

        Returns:
            更新された論文リスト。
        """
        # DOIを持つ論文を抽出
        doi_map = {p.doi: p for p in papers if p.doi}
        if not doi_map:
            return papers

        dois = list(doi_map.keys())
        fetched_papers = await self.fetch_papers_batch(dois)
        fetched_map = {p.doi: p for p in fetched_papers if p.doi}

        for doi, paper in doi_map.items():
            fetched_paper = fetched_map.get(doi)
            if not fetched_paper:
                continue

            # Abstract
            if fetched_paper.abstract and (not paper.abstract or overwrite):
                paper.abstract = fetched_paper.abstract

            # PDF URL
            if fetched_paper.pdf_url and (not paper.pdf_url or overwrite):
                paper.pdf_url = fetched_paper.pdf_url

        return papers

    async def fetch_papers_batch(self, dois: list[str]) -> list[Paper]:
        """Semantic Scholar APIからバッチで論文データを取得します。

        Args:
            dois: DOIのリスト。

        Returns:
            Paperオブジェクトのリスト（取得できたもののみ）。
        """
        # バッチサイズごとに分割
        tasks: list[asyncio.Task[list[Paper] | None]] = []
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(dois), self.BATCH_SIZE):
                batch = dois[i : i + self.BATCH_SIZE]
                tasks.append(tg.create_task(self._fetch_single_batch(batch)))

        # 結果をフラット化
        papers: list[Paper] = []
        for task in tasks:
            result = task.result()
            if result is not None:
                papers.extend(result)
        return papers

    async def _fetch_single_batch(self, batch_dois: list[str]) -> list[Paper] | None:
        """Semantic Scholar APIからバッチでデータを取得します。

        Args:
            batch_dois: DOI リスト。

        Returns:
            Paper オブジェクトのリスト。エラー時は None。
        """
        try:
            payload = {"ids": [f"DOI:{doi}" for doi in batch_dois]}
            params = {"fields": self.FIELDS}
            resp = await self.http.post(
                f"{self.BASE_URL}/{self.PAPER_BATCH_SEARCH_PATH}",
                params=params,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            # レスポンスのパース
            papers = []
            for item in data:
                if item:  # item自体がNoneの場合がある（API仕様）
                    paper = self._parse_single_paper(item)
                    if paper:
                        papers.append(paper)
            return papers

        except httpx.HTTPStatusError as e:
            # 404 Not Foundは論文が存在しないケースとして扱う
            if e.response.status_code == 404:
                logger.debug(
                    "Semantic Scholar: papers not found (404) batch_size={size}",
                    size=len(batch_dois),
                )
            else:
                logger.warning(
                    "Semantic Scholar HTTP error: status={status} batch_size={size} error={error}",
                    status=e.response.status_code,
                    size=len(batch_dois),
                    error=repr(e),
                )
            return None
        except httpx.TimeoutException as e:
            logger.warning(
                "Semantic Scholar request timeout: batch_size={size} error={error}",
                size=len(batch_dois),
                error=repr(e),
            )
            return None
        except httpx.RequestError as e:
            logger.warning(
                "Semantic Scholar network error: batch_size={size} error={error}",
                size=len(batch_dois),
                error=repr(e),
            )
            return None
        except Exception as e:
            logger.error(
                "Semantic Scholar unexpected error: batch_size={size} error_type={error_type} error={error}",
                size=len(batch_dois),
                error_type=type(e).__name__,
                error=repr(e),
            )
            return None

    def _parse_single_paper(self, item: dict[str, Any]) -> Paper | None:
        """Semantic Scholar API レスポンスから Paper オブジェクトを生成します。

        Args:
            item: Semantic Scholar API レスポンスの論文データ。

        Returns:
            生成された Paper オブジェクト。パース失敗時は None。
        """
        if not item:
            return None

        doi = None
        external_ids = item.get("externalIds")
        if external_ids:
            doi = external_ids.get("DOI")

        abstract = item.get("abstract")

        pdf_url = None
        open_access_pdf = item.get("openAccessPdf")
        if open_access_pdf:
            pdf_url = open_access_pdf.get("url")

        title = item.get("title", "")
        year = item.get("year", 0)
        venue = item.get("venue", "")

        authors = []
        for author in item.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Paperオブジェクトの生成 (部分データ)
        return Paper(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            abstract=abstract,
            pdf_url=pdf_url,
        )

    async def check_url_exists(self, url: str) -> bool:
        """指定された URL が存在するか HEAD リクエストで確認します。

        Args:
            url: 存在確認する URL。

        Returns:
            ステータスコードが 200 の場合は True、それ以外または例外発生時は False。
        """
        try:
            resp = await self.http._client.head(url)
            return resp.status_code == 200
        except Exception:
            return False
