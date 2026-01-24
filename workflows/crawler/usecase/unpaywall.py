import asyncio
from typing import Any

import httpx
from loguru import logger

from configs import EMAIL
from domain.paper import Paper
from libs.http_utils import get_with_retry


class UnpaywallSearch:
    DEFAULT_CONCURRENCY = 10
    BASE_URL = "https://api.unpaywall.org"
    PAPER_SEARCH_PATH = "v2"

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "UnpaywallSearch":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化します。

        Returns:
            初期化されたUnpaywallSearchインスタンス
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
        """論文リストに対してUnpaywallデータで情報を付与します。

        DOIを使用してUnpaywall APIから論文データを取得し、
        PDF URLなどのメタデータを追加します。

        Args:
            papers: 情報を付与する論文のリスト
            semaphore: 並列実行数を制限するセマフォ（デフォルト: None）
            overwrite: PDF URLを上書きするかどうか（デフォルト: False）

        Returns:
            情報が付与された論文のリスト。len(papers)とlen(return value)は等しい。

        Raises:
            RuntimeError: コンテキストマネージャー外で呼び出された場合
        """
        if self.client is None:
            raise RuntimeError(
                "UnpaywallSearch must be used as an async context manager (use 'async with')"
            )
        sem = semaphore or asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        # DOIリストを抽出
        doi_list = self._extract_dois(papers)

        # Unpaywallから論文データを取得
        data_list = await self._fetch_papers(doi_list, sem)
        data_map = {d["doi"]: d for d in data_list if d and d.get("doi")}
        # 元の論文リストをループして情報を付与
        for paper in papers:
            data = data_map.get(paper.doi)
            if not data:
                logger.warning(f"Skipping paper {paper.doi} due to missing data in API response")
                continue
            try:
                await self._enrich_paper_metadata(paper, data, overwrite=overwrite)
            except ValueError as e:
                logger.warning(f"Skipping enrichment for paper {paper.doi} due to error: {e}")

        return papers

    def _extract_dois(self, papers: list[Paper]) -> list[str]:
        """論文リストからDOIリストを抽出します。

        Args:
            papers: 論文のリスト

        Returns:
            DOIのリスト

        Raises:
            ValueError: いずれかの論文にDOIが存在しない場合
        """
        doi_list: list[str] = []
        for paper in papers:
            if paper.doi is None:
                raise ValueError(f"Paper '{paper.title}' has no DOI")
            doi_list.append(paper.doi)
        return doi_list

    async def _fetch_papers(
        self, doi_list: list[str], semaphore: asyncio.Semaphore | None = None
    ) -> list[dict[str, Any]]:
        """DOIリストから並列で論文データを取得します。

        Args:
            doi_list: 取得対象のDOIリスト
            semaphore: 並列実行数を制限するセマフォ

        Returns:
            取得した論文データのリスト。取得に失敗したデータは除外されます。

        Raises:
            RuntimeError: クライアントが初期化されていない場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")

        sem = semaphore or asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        # TaskGroup でバッチリクエストを並行実行
        tasks: list[asyncio.Task[dict[str, Any] | None]] = []
        async with asyncio.TaskGroup() as tg:
            for doi in doi_list:
                tasks.append(tg.create_task(self._fetch_paper(doi, sem, email=EMAIL)))

        # 各タスクの結果を取得
        results = [task.result() for task in tasks]
        return [r for r in results if r is not None]

    async def _fetch_paper(
        self, doi: str, sem: asyncio.Semaphore, email: str
    ) -> dict[str, Any] | None:
        """単一の論文データをAPIから取得します。

        Args:
            doi: 論文のDOI
            sem: 並列実行数を制限するセマフォ
            email: APIリクエストに必要なメールアドレス

        Returns:
            取得した論文データ。エラーが発生した場合はNone。

        Raises:
            RuntimeError: クライアントが初期化されていない場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")

        url = f"/{self.PAPER_SEARCH_PATH}/{doi}"

        try:
            async with sem:
                resp = await get_with_retry(self.client, url, params={"email": email})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            # 404 Not Foundは論文が存在しないケースとして扱う
            if e.response.status_code == 404:
                logger.debug(f"No paper found for DOI {doi} on Unpaywall (404).")
            else:
                logger.warning(f"Failed to fetch paper for DOI {doi}: {e}")
            return None

    async def _enrich_paper_metadata(
        self, paper: Paper, data: dict[str, Any], overwrite: bool = False
    ) -> Paper:
        """APIレスポンスから論文のメタデータを更新します。

        best_oa_location または oa_locations からPDFのURLを抽出し、
        論文オブジェクトに設定します。

        Args:
            paper: 更新対象の論文オブジェクト
            data: APIから取得した論文データ
            overwrite: PDF URLを上書きするかどうか。設定値がない場合は、overwriteによらず上書きし、設定値がある場合は、overwriteに従う。

        Returns:
            更新された論文オブジェクト
        """
        # 新しいPDF URLを取得
        new_url = (data.get("best_oa_location") or {}).get("url_for_pdf")
        if not new_url:
            for location in data.get("oa_locations", []):
                new_url = location.get("url_for_pdf")
                if new_url:
                    break

        if not new_url:
            return paper

        # 既にPDF URLが設定されている場合、overwriteがTrueのときのみ更新
        # 設定されていない場合は、常に更新
        if not paper.pdf_url or overwrite:
            paper.pdf_url = new_url

        return paper
