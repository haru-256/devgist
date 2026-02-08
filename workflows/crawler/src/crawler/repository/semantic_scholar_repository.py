import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.paper import Paper
from crawler.utils.http_utils import post_with_retry


class SemanticScholarRepository:
    """Semantic Scholar APIとの通信を担当するリポジトリクラス。"""

    # Semantic Scholar APIは最大500件までバッチで取得可能
    BATCH_SIZE = 500
    FIELDS = "externalIds,abstract,openAccessPdf,title,year,venue,authors,url"
    BASE_URL = "https://api.semanticscholar.org"
    PAPER_BATCH_SEARCH_PATH = "graph/v1/paper/batch"
    DEFAULT_SLEEP_SECONDS = 0.1

    def __init__(self, client: httpx.AsyncClient, limiter: AsyncLimiter | None = None) -> None:
        """SemanticScholarRepositoryインスタンスを初期化します。

        Args:
            client: HTTPリクエストに使用するAsyncClientインスタンス
            limiter: レート制限を行うAsyncLimiterインスタンス。省略時はデフォルト設定を使用。
        """
        self.client = client
        if limiter:
            self.limiter = limiter
        else:
            self.limiter = AsyncLimiter(1, self.DEFAULT_SLEEP_SECONDS)

    async def enrich_papers(
        self,
        papers: list[Paper],
        semaphore: asyncio.Semaphore,
        overwrite: bool = False,
    ) -> list[Paper]:
        """論文リストにSemantic Scholarのデータ（Abstract と PDF URL）を付与します。

        DOIを持つ論文のみが処理対象となります。

        Args:
            papers: 更新対象の論文リスト
            semaphore: 並列実行数を制限するセマフォ
            overwrite: 既存のデータを上書きするかどうか

        Returns:
            更新された論文リスト
        """
        # DOIを持つ論文を抽出
        doi_map = {p.doi: p for p in papers if p.doi}
        if not doi_map:
            return papers

        dois = list(doi_map.keys())
        fetched_papers = await self.fetch_papers_batch(dois, sem=semaphore)
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

    async def fetch_papers_batch(self, dois: list[str], sem: asyncio.Semaphore) -> list[Paper]:
        """Semantic Scholar APIからバッチで論文データを取得します。

        Args:
            dois: DOIのリスト
            sem: 並列実行数を制限するセマフォ

        Returns:
            Paperオブジェクトのリスト（取得できたもののみ）

        Raises:
            RuntimeError: クライアントが初期化されていない場合
        """
        _sem = sem

        # バッチサイズごとに分割
        tasks: list[asyncio.Task[list[Paper] | None]] = []
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(dois), self.BATCH_SIZE):
                batch = dois[i : i + self.BATCH_SIZE]
                tasks.append(tg.create_task(self._fetch_single_batch(batch, _sem)))

        # 結果をフラット化
        papers: list[Paper] = []
        for task in tasks:
            result = task.result()
            if result is not None:
                papers.extend(result)
        return papers

    async def _fetch_single_batch(
        self, batch_dois: list[str], sem: asyncio.Semaphore
    ) -> list[Paper] | None:
        """Semantic Scholar APIから単一バッチでデータを取得します。

        Args:
            batch_dois: DOIのリスト
            sem: 並行実行数を制限するセマフォ

        Returns:
            Paperオブジェクトのリスト。取得エラー時はNone。
        """

        try:
            async with sem, self.limiter:
                payload = {"ids": [f"DOI:{doi}" for doi in batch_dois]}
                params = {"fields": self.FIELDS}
                resp = await post_with_retry(
                    self.client,
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
                logger.debug(f"No paper found for DOIs {batch_dois} on Semantic Scholar (404).")
            else:
                logger.warning(f"Failed to fetch paper for DOIs {batch_dois}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching S2 batch: {e}")
            return None

    def _parse_single_paper(self, item: dict[str, Any]) -> Paper | None:
        """APIレスポンスの単一項目をPaperオブジェクトに変換します。"""
        # 注意: Semantic Scholarの仕様では見つからないIDはnullで返る
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
        year = item.get("year") or 0
        venue = item.get("venue") or ""

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
        """指定されたURLが存在するか確認します。"""

        try:
            resp = await self.client.head(url)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def create_limiter() -> AsyncLimiter:
        return AsyncLimiter(1, SemanticScholarRepository.DEFAULT_SLEEP_SECONDS)
