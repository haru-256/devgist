import asyncio
from typing import Any

import httpx
from loguru import logger

from crawler.configs import EMAIL
from crawler.domain.paper import Paper
from crawler.utils.http_utils import get_with_retry


class UnpaywallRepository:
    """Unpaywall APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://api.unpaywall.org"
    PAPER_SEARCH_PATH = "v2"

    def __init__(self, headers: dict[str, str]) -> None:
        """UnpaywallRepositoryインスタンスを初期化します。

        Args:
            headers: HTTPリクエストで使用するヘッダー辞書
        """
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "UnpaywallRepository":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化します。

        Returns:
            初期化されたUnpaywallRepositoryインスタンス
        """
        limits = httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=5.0,
        )
        self.client = httpx.AsyncClient(
            headers=self.headers, base_url=self.BASE_URL, limits=limits, timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理。

        HTTPクライアントを適切にクローズします。
        """
        if self.client is not None:
            await self.client.aclose()

    async def enrich_papers(
        self,
        papers: list[Paper],
        semaphore: asyncio.Semaphore | None = None,
        overwrite: bool = False,
    ) -> list[Paper]:
        """論文リストにUnpaywallのデータを付与します。

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

        sem = semaphore or asyncio.Semaphore(10)  # Default concurrency

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

    async def fetch_by_doi(self, doi: str, sem: asyncio.Semaphore | None = None) -> Paper | None:
        """DOIを使用して論文データを取得します。

        Note:
            PaperEnricherプロトコルからは削除されましたが、内部ヘルパーとして維持、
            または個別のテスト用にpublicのままにしておきます。
        """

        if self.client is None:
            raise RuntimeError("Client is not initialized")

        url = f"/{self.PAPER_SEARCH_PATH}/{doi}"

        try:
            if sem:
                async with sem:
                    resp = await get_with_retry(self.client, url, params={"email": EMAIL})
            else:
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
