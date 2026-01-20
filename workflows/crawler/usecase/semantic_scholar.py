"""Semantic Scholar APIを使用して論文メタデータを充実させるモジュール。

このモジュールは、Semantic Scholar APIを使用して論文の要約（abstract）やPDF URLを取得し、
DBLPから取得した基本的な論文情報を充実させる機能を提供します。
バッチ処理により効率的に複数の論文を処理できます。
"""

import re
from typing import Any

import httpx
from loguru import logger

from domain.paper import Paper


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

    base_url = "https://api.semanticscholar.org"
    paper_search_api = "https://api.semanticscholar.org/graph/v1/paper"
    paper_batch_search_api = "https://api.semanticscholar.org/graph/v1/paper/batch"

    arxiv_abs_link_pattern = re.compile(r"https://arxiv\.org/abs/([\w.]+)")

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
            headers=self.headers, base_url=self.base_url, limits=limits, timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理。

        HTTPクライアントを適切にクローズします。
        """
        if self.client is not None:
            await self.client.aclose()

    async def enrich_papers(self, papers: list[Paper]) -> list[Paper]:
        """論文リストをSemantic Scholar APIから取得したメタデータで充実させます。

        各論文のDOIを使用してSemantic Scholar APIから要約やPDF URLを取得し、
        元の論文情報に追加します。DOIが存在しない論文や、APIから情報を取得できなかった
        論文は結果に含まれません。

        Args:
            papers: 充実させる論文のリスト（DOIが必須）

        Returns:
            メタデータで充実された論文のリスト

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
        data_list = await self._fetch_semantic_scholar_data(doi_list)

        # 元の論文とマッチングして充実
        enriched_papers: list[Paper] = []
        for data in data_list:
            try:
                original_paper = self._find_original_paper(
                    papers, data.get("externalIds", {}).get("DOI")
                )
                enriched_paper = await self._enrich_paper_metadata(original_paper, data)
                enriched_papers.append(enriched_paper)
            except ValueError as e:
                logger.warning(f"Skipping paper due to error: {e}")
                continue

        return enriched_papers

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
                raise ValueError(f"Paper '{paper.title}' must have a DOI")
            doi_list.append(paper.doi)
        return doi_list

    async def _fetch_semantic_scholar_data(self, dois: list[str]) -> list[dict[str, Any]]:
        """Semantic Scholar APIからバッチでデータを取得します。

        Args:
            dois: DOIのリスト

        Returns:
            APIレスポンスのデータリスト（Noneを除外済み）

        Raises:
            httpx.HTTPStatusError: APIリクエストが失敗した場合
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")

        params = {"fields": "externalIds,abstract,openAccessPdf"}
        payload = {"ids": [f"DOI:{doi}" for doi in dois]}

        resp = await self.client.post(self.paper_batch_search_api, params=params, json=payload)
        resp.raise_for_status()

        data: list[dict[str, Any] | None] = resp.json()
        # データが取得できない場合（None）を除外
        return [d for d in data if d is not None]

    def _find_original_paper(self, papers: list[Paper], doi: str | None) -> Paper:
        """DOIを使用して元の論文オブジェクトを検索します。

        Args:
            papers: 検索対象の論文リスト
            doi: 検索するDOI

        Returns:
            マッチした論文オブジェクト

        Raises:
            ValueError: 論文が見つからない、または複数見つかった場合
        """
        if doi is None:
            raise ValueError("DOI is None in API response")

        matched_papers = [p for p in papers if p.doi == doi]

        if len(matched_papers) == 0:
            raise ValueError(f"Paper with DOI '{doi}' not found in original list")
        if len(matched_papers) > 1:
            raise ValueError(f"Multiple papers with DOI '{doi}' found in original list")

        return matched_papers[0]

    async def _enrich_paper_metadata(self, paper: Paper, data: dict[str, Any]) -> Paper:
        """APIレスポンスから論文のメタデータを充実させます。

        元の論文オブジェクトのコピーを作成し、abstractやPDF URLを追加します。
        openAccessPdfが利用可能な場合はそのURLを、disclaimerにarXivリンクがある場合は
        arXivのPDF URLを設定します。

        Args:
            paper: 元の論文オブジェクト
            data: Semantic Scholar APIからのレスポンスデータ

        Returns:
            メタデータで充実された新しい論文オブジェクト
        """
        # 元のインスタンスを変更しないよう新規作成
        enriched_paper = Paper(**paper.model_dump())
        enriched_paper.abstract = data.get("abstract")

        # PDF URLの取得
        open_access_pdf = data.get("openAccessPdf")
        if open_access_pdf is not None:
            url = open_access_pdf.get("url")
            if url:
                enriched_paper.pdf_url = url

            # disclaimerにarXivリンクがある場合は試す
            disclaimer = open_access_pdf.get("disclaimer")
            if disclaimer:
                arxiv_pdf_url = await self._try_fetch_arxiv_pdf(disclaimer)
                if arxiv_pdf_url:
                    enriched_paper.pdf_url = arxiv_pdf_url

        return enriched_paper

    async def _try_fetch_arxiv_pdf(self, disclaimer: str) -> str | None:
        """disclaimerからarXivリンクを抽出し、PDF URLを取得します。

        disclaimerにarXivの抄録URLが含まれている場合、そのURLが有効か確認し、
        PDF URLに変換して返します。

        Args:
            disclaimer: Semantic Scholar APIのdisclaimerテキスト

        Returns:
            有効なarXiv PDF URL、または取得失敗時はNone
        """
        if self.client is None:
            return None

        match = self.arxiv_abs_link_pattern.search(disclaimer)
        if match is None:
            return None

        abstract_url = match.group(0)
        try:
            resp = await self.client.get(abstract_url)
            resp.raise_for_status()
            # 抄録ページが有効ならPDF URLに変換
            return abstract_url.replace("abs", "pdf")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch arXiv abstract at {abstract_url}: {e}")
            return None
