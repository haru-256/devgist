import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.configs import EMAIL
from crawler.domain.paper import Paper
from crawler.utils.http_utils import get_with_retry


class UnpaywallRepository:
    """Unpaywall APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://api.unpaywall.org"
    PAPER_SEARCH_PATH = "v2"
    DEFAULT_SLEEP_SECONDS = 0.1

    def __init__(self, client: httpx.AsyncClient, limiter: AsyncLimiter | None = None) -> None:
        """UnpaywallRepositoryインスタンスを初期化します。

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
        """論文リストにUnpaywallのデータを付与します。

        DOIを持つ論文のみが処理対象となります。

        Args:
            papers: 更新対象の論文リスト
            semaphore: 並列実行数を制限するセマフォ
            overwrite: 既存のデータを上書きするかどうか

        Returns:
            更新された論文リスト
        """
        # DOIを持つ論文のみ対象
        target_papers = [p for p in papers if p.doi]
        if not target_papers:
            return papers

        sem = semaphore

        async with asyncio.TaskGroup() as tg:
            for paper in target_papers:
                tg.create_task(self._enrich_single_paper(paper, sem, overwrite))

        return papers

    async def _enrich_single_paper(
        self, paper: Paper, sem: asyncio.Semaphore, overwrite: bool
    ) -> None:
        """単一の論文をUnpaywallデータで更新します。"""
        if not paper.doi:
            return

        fetched_paper = await self.fetch_by_doi(paper.doi, sem)
        if not fetched_paper:
            return

        # PDF URLの更新
        new_url = fetched_paper.pdf_url
        if new_url:
            if not paper.pdf_url or overwrite:
                paper.pdf_url = new_url

    async def fetch_by_doi(self, doi: str, sem: asyncio.Semaphore) -> Paper | None:
        """DOIを使用して論文データを取得します。

        Note:
            PaperEnricherプロトコルからは削除されましたが、内部ヘルパーとして維持、
            または個別のテスト用にpublicのままにしておきます。
        """

        url = f"{self.BASE_URL}/{self.PAPER_SEARCH_PATH}/{doi}"

        try:
            async with sem, self.limiter:
                resp = await get_with_retry(self.client, url, params={"email": EMAIL})
            resp.raise_for_status()
            data = resp.json()
            return self._parse_paper(data)
        except httpx.HTTPStatusError as e:
            # 404 Not Foundは論文が存在しないケースとして扱う
            if e.response.status_code == 404:
                logger.debug(f"No paper found for DOI {doi} on Unpaywall (404).")
            else:
                logger.warning(f"Failed to fetch paper for DOI {doi}: {e}")
            return None

    def _parse_paper(self, data: dict[str, Any]) -> Paper | None:
        """APIレスポンスからPaperオブジェクトを生成します。"""
        if not data:
            return None

        # PDF URLの取得ロジック
        pdf_url = None
        best_oa_location = data.get("best_oa_location")
        if best_oa_location:
            pdf_url = best_oa_location.get("url_for_pdf")

        if not pdf_url:
            oa_locations = data.get("oa_locations", [])
            for loc in oa_locations:
                url = loc.get("url_for_pdf")
                if url:
                    pdf_url = url
                    break

        # Paperオブジェクトの生成 (部分データ)
        doi = data.get("doi")
        if doi is None:
            logger.warning(f"Unpaywall response is missing 'doi' field. Response data: {data}")
            return None

        # Unpaywallからは主にPDF URLを取得する
        return Paper(
            title=str(data.get("title", "")),
            authors=[],  # Unpaywallのauthor構造は複雑なので今回は省略
            year=0,  # yearも取得可能だが省略
            venue="",  # venueも取得可能だが省略
            doi=doi,
            pdf_url=pdf_url,
        )

    @staticmethod
    def create_limiter() -> AsyncLimiter:
        return AsyncLimiter(1, UnpaywallRepository.DEFAULT_SLEEP_SECONDS)
