"""Semantic Scholar APIを使用して論文メタデータを充実させるモジュール。

このモジュールは、Semantic Scholar APIを使用して論文の要約（abstract）やPDF URLを取得し、
DBLPから取得した基本的な論文情報を充実させる機能を提供します。
バッチ処理により効率的に複数の論文を処理できます。
"""

import asyncio
import re
from typing import Any

import httpx
from loguru import logger

from domain.paper import Paper
from libs.http_utils import post_with_retry


class SemanticScholarSearch:
    """Semantic Scholar APIから論文メタデータを取得するクラス。

    このクラスは非同期コンテキストマネージャーとして設計されており、
    `async with`文を使用して利用します。Semantic Scholar APIのバッチエンドポイントを利用して、
    複数の論文に対してabstractやPDF URLなどの詳細情報を効率的に取得します。

    Attributes:
        base_url: Semantic Scholar APIのベースURL
        paper_search_api: 単一論文検索のエンドポイント
        paper_batch_search_api: バッチ検索のエンドポイント
        arxiv_abs_link_pattern: arXiv抄録URLのパターン
        headers: HTTPリクエストで使用するヘッダー
        client: 非同期HTTPクライアント（コンテキストマネージャー内でのみ有効）

    Example:
        >>> headers = {"User-Agent": "MyBot/1.0"}
        >>> async with SemanticScholarSearch(headers) as searcher:
        ...     enriched_papers = await searcher.enrich_papers(papers)
    """

    DEFAULT_CONCURRENCY = 10
    # Semantic Scholar APIは最大500件までバッチで取得可能
    SEMANTIC_SCHOLAR_BATCH_SIZE = 500
    SEMANTIC_SCHOLAR_FIELDS = "externalIds,abstract,openAccessPdf"
    BASE_URL = "https://api.semanticscholar.org"
    PAPER_SEARCH_PATH = "graph/v1/paper"
    PAPER_BATCH_SEARCH_PATH = "graph/v1/paper/batch"
    ARXIV_ABS_LINK_PATTERN = re.compile(r"https://arxiv\.org/abs/([\w./-]+)")

    def __init__(self, headers: dict[str, str]) -> None:
        """SemanticScholarSearchインスタンスを初期化します。

        Args:
            headers: HTTPリクエストで使用するヘッダー辞書
        """
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SemanticScholarSearch":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化します。

        Returns:
            初期化されたSemanticScholarSearchインスタンス
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
        """論文リストをSemantic Scholar APIから取得したメタデータで充実させます。

        各論文のDOIを使用してSemantic Scholar APIから要約やPDF URLを取得し、
        元の論文情報に追加します。DOIが存在しない論文や、APIから情報を取得できなかった
        論文は結果に含まれません。

        Args:
            papers: 充実させる論文のリスト（DOIが必須）
            semaphore: 並行実行数を制限するセマフォ（デフォルト: None）
            overwrite: PDF URLを上書きするかどうか（デフォルト: False）

        Returns:
            メタデータで充実された論文のリスト。len(papers)とlen(return value)は等しい。

        Raises:
            RuntimeError: コンテキストマネージャー外で呼び出された場合
            ValueError: いずれかの論文にDOIが存在しない場合
            httpx.HTTPStatusError: APIリクエストが失敗した場合
        """
        if self.client is None:
            raise RuntimeError(
                "SemanticScholarSearch must be used as an async context manager (use 'async with')"
            )

        # DOIリストを抽出
        doi_list = self._extract_dois(papers)

        # Semantic Scholar APIからデータを取得
        data_list = await self._fetch_papers(doi_list, semaphore=semaphore)
        data_map = {}
        for d in data_list:
            if not d:
                continue
            doi = d.get("doi") or d.get("externalIds", {}).get("DOI")
            if doi:
                data_map[doi] = d

        # 元の論文とマッチングして充実
        for paper in papers:
            data = data_map.get(paper.doi)
            if not data:
                logger.warning(f"Skipping paper {paper.doi} due to missing data in API response")
                continue
            try:
                await self._enrich_paper_metadata(paper, data, overwrite=overwrite)
            except ValueError as e:
                logger.warning(f"Skipping paper due to error during metadata enrichment: {e}")
                continue

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
        self, dois: list[str], semaphore: asyncio.Semaphore | None = None
    ) -> list[dict[str, Any]]:
        """Semantic Scholar APIからバッチでデータを取得します。

        Args:
            dois: DOIのリスト
            semaphore: 並行実行数を制限するセマフォ（デフォルト: None）

        Returns:
            APIレスポンスのデータリスト（Noneを除外済み）

        Raises:
            httpx.HTTPStatusError: APIリクエストが失敗した場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")

        # デフォルトのセマフォを設定（デフォルト引数でインスタンス化するとイベントループの問題が起きるため）
        sem = semaphore or asyncio.Semaphore(self.DEFAULT_CONCURRENCY)
        batch_size = self.SEMANTIC_SCHOLAR_BATCH_SIZE

        # TaskGroup でバッチリクエストを並行実行
        tasks: list[asyncio.Task[list[dict[str, Any]] | None]] = []
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(dois), batch_size):
                batch = dois[i : i + batch_size]
                tasks.append(tg.create_task(self._fetch_paper_batch(batch, sem)))

        flat_list: list[dict[str, Any]] = []
        for task in tasks:
            result = task.result()
            if result is not None:
                flat_list.extend(result)
        return flat_list

    async def _fetch_paper_batch(
        self, batch_dois: list[str], sem: asyncio.Semaphore
    ) -> list[dict[str, Any]] | None:
        """Semantic Scholar APIからバッチでデータを取得します。

        Args:
            batch_dois: DOIのリスト
            sem: 並行実行数を制限するセマフォ

        Returns:
            APIレスポンスのデータリスト（Noneを除外済み）

        Raises:
            httpx.HTTPStatusError: APIリクエストが失敗した場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")
        try:
            async with sem:
                payload = {"ids": [f"DOI:{doi}" for doi in batch_dois]}
                params = {"fields": self.SEMANTIC_SCHOLAR_FIELDS}
                resp = await post_with_retry(
                    self.client,
                    f"/{self.PAPER_BATCH_SEARCH_PATH}",
                    params=params,
                    json=payload,
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            # 404 Not Foundは論文が存在しないケースとして扱う
            if e.response.status_code == 404:
                logger.debug(f"No paper found for DOIs {batch_dois} on Semantic Scholar (404).")
            else:
                logger.warning(f"Failed to fetch paper for DOIs {batch_dois}: {e}")
            return None

    async def _enrich_paper_metadata(
        self, paper: Paper, data: dict[str, Any], overwrite: bool = False
    ) -> Paper:
        """APIレスポンスから論文のメタデータを充実させます。

        元の論文オブジェクトにabstractやPDF URLを追加します。
        openAccessPdfが利用可能な場合はそのURLを、disclaimerにarXivリンクがある場合は
        arXivのPDF URLを設定します。

        Args:
            paper: 元の論文オブジェクト
            data: Semantic Scholar APIからのレスポンスデータ
            overwrite: Abstract, PDF URLを上書きするかどうか。設定値がない場合は、overwriteによらず上書きし、設定値がある場合は、overwriteに従う。

        Returns:
            メタデータで充実された論文オブジェクト
        """
        # Abstract
        new_abstract = data.get("abstract")
        if new_abstract and (not paper.abstract or overwrite):
            paper.abstract = new_abstract

        # PDF URL
        new_pdf_url = await self._resolve_pdf_url(data)
        if new_pdf_url and (not paper.pdf_url or overwrite):
            paper.pdf_url = new_pdf_url

        return paper

    async def _resolve_pdf_url(self, data: dict[str, Any]) -> str | None:
        """APIレスポンスから最適なPDF URLを解決します。"""
        open_access_pdf = data.get("openAccessPdf")
        if not open_access_pdf:
            return None

        # openAccessPdf.url が利用可能な場合はそれを優先する
        url = open_access_pdf.get("url")
        if url:
            return url

        # disclaimerにarXivリンクがある場合は試す（URLがないときのフォールバック）
        disclaimer = open_access_pdf.get("disclaimer")
        if disclaimer:
            return await self._try_fetch_arxiv_pdf(disclaimer)

        return None

    async def _try_fetch_arxiv_pdf(self, disclaimer: str) -> str | None:
        """disclaimerからarXivリンクを抽出し、PDF URLを取得します。

        disclaimerにarXivの抄録URLが含まれている場合、そ のURLが有効か確認し、
        PDF URLに変換して返します。URLの存在確認にはHEADリクエストを使用し、
        ネットワーク通信量を削減します。

        Args:
            disclaimer: Semantic Scholar APIのdisclaimerテキスト

        Returns:
            有効なarXiv PDF URL、または取得失敗時はNone
        """
        if self.client is None:
            return None

        match = self.ARXIV_ABS_LINK_PATTERN.search(disclaimer)
        if match is None:
            return None

        abstract_url = match.group(0)
        try:
            # URLの存在確認のみなのでHEADリクエストを使用
            resp = await self.client.head(abstract_url)
            resp.raise_for_status()
            # 抄録ページが有効ならPDF URLに変換
            return abstract_url.replace("/abs/", "/pdf/")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch arXiv abstract at {abstract_url}: {e}")
            return None
