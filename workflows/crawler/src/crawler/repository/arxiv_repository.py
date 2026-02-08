import asyncio

import defusedxml.ElementTree as ET
import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.paper import Paper
from crawler.utils.http_utils import get_with_retry


class ArxivRepository:
    """arXiv APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://export.arxiv.org"
    # XMLの名前空間定義
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    DEFAULT_SLEEP_SECONDS = 1.0

    def __init__(self, client: httpx.AsyncClient, limiter: AsyncLimiter | None = None) -> None:
        """ArxivRepositoryインスタンスを初期化します。

        Args:
            client: HTTPリクエストに使用するAsyncClientインスタンス
            limiter: レート制限を行うAsyncLimiterインスタンス。省略時はデフォルト設定を使用。
        """
        self.client = client
        # arXivのレート制限（1リクエスト/秒）を管理するリミッター
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
        """論文リストにarXivのデータ（Abstract, PDF URL）を付与します。

        DOI検索を試し、失敗した場合はタイトル検索を試みます。

        Args:
            papers: 更新対象の論文リスト
            semaphore: 並列実行数を制限するセマフォ
            overwrite: 既存のデータを上書きするかどうか

        Returns:
            更新された論文リスト
        """
        async with asyncio.TaskGroup() as tg:
            for paper in papers:
                tg.create_task(self._enrich_single_paper(paper, semaphore, overwrite))
        return papers

    async def _enrich_single_paper(
        self, paper: Paper, sem: asyncio.Semaphore, overwrite: bool
    ) -> None:
        """単一の論文をarXivデータで更新します。"""
        # 1. DOIで検索、ヒットしなければタイトルで検索を試みる
        fetched_paper = None
        if paper.doi:
            fetched_paper = await self.fetch_by_doi(paper.doi, sem)

        if not fetched_paper and paper.title:
            fetched_paper = await self.fetch_by_title(paper.title, sem)

        if fetched_paper:
            # Abstract
            if fetched_paper.abstract and (not paper.abstract or overwrite):
                paper.abstract = fetched_paper.abstract
            # PDF URL
            if fetched_paper.pdf_url and (not paper.pdf_url or overwrite):
                paper.pdf_url = fetched_paper.pdf_url

    async def fetch_by_doi(self, doi: str, sem: asyncio.Semaphore) -> Paper | None:
        """DOIを使用してarXiv APIから論文データを取得します。

        Args:
            doi: 論文のDOI
            sem: 並列実行数を制限するセマフォ

        Returns:
            Paperオブジェクト（pdf_url, abstractなどの詳細を含む）。取得失敗時はNone。
        """
        return await self._fetch(f"doi:{doi}", sem)

    async def fetch_by_title(self, title: str, sem: asyncio.Semaphore) -> Paper | None:
        """タイトルを使用してarXiv APIから論文データを取得します。

        Args:
            title: 論文のタイトル
            sem: 並列実行数を制限するセマフォ

        Returns:
            Paperオブジェクト（pdf_url, abstractなどの詳細を含む）。取得失敗時はNone。
        """
        # タイトルに含まれるダブルクォートをエスケープ
        escaped_title = title.replace('"', "")
        return await self._fetch(f'ti:"{escaped_title}"', sem)

    async def _fetch(self, query: str, sem: asyncio.Semaphore) -> Paper | None:
        """arXiv APIを叩き、最初のヒット結果を返します。

        Args:
            query: arXiv APIクエリ文字列
            sem: セマフォ

        Returns:
            パースされたPaperオブジェクト。取得失敗やヒットなしの場合はNone。

        """
        params = {"search_query": query, "start": 0, "max_results": 1}
        try:
            async with sem, self.limiter:
                resp = await get_with_retry(
                    self.client,
                    f"{self.BASE_URL}/api/query",
                    params=params,
                    headers={"Accept": "application/atom+xml"},
                )
            resp.raise_for_status()
            return self._parse_xml(resp.text)
        except Exception as e:
            logger.warning(f"arXiv fetch error for {query}: {e}")
            return None

    def _parse_xml(self, xml_text: str) -> Paper | None:
        """arXivのAtomリプライ(XML)を解析し、Paperオブジェクトを生成します。

        注意: 取得できる情報は部分的なもの（主にabstractとpdf_url）です。
        """
        root = ET.fromstring(xml_text)
        entry = root.find("atom:entry", self.NAMESPACES)
        if entry is None:
            return None

        # タイトル
        title_tag = entry.find("atom:title", self.NAMESPACES)
        title = title_tag.text.strip() if title_tag is not None and title_tag.text else ""

        # 著者 (リスト)
        authors = []
        for author in entry.findall("atom:author", self.NAMESPACES):
            name_tag = author.find("atom:name", self.NAMESPACES)
            if name_tag is not None and name_tag.text:
                authors.append(name_tag.text.strip())

        # 要約
        summary_tag = entry.find("atom:summary", self.NAMESPACES)
        summary = None
        if summary_tag is not None and summary_tag.text:
            summary = summary_tag.text.strip()

        # 公開年
        published_tag = entry.find("atom:published", self.NAMESPACES)
        published_year = 0
        if published_tag is not None and published_tag.text:
            try:
                published_year = int(published_tag.text[:4])
            except ValueError as exc:
                logger.warning(
                    "Failed to parse published year from arXiv entry: text={!r}, error={!r}",
                    published_tag.text,
                    exc,
                )

        # PDFリンク
        pdf_url = None
        for link in entry.findall("atom:link", self.NAMESPACES):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        # Paperオブジェクトの生成
        # 注意: 元のPaperデータとマージするために使用される一時的なオブジェクト
        return Paper(
            title=title,
            authors=authors,
            year=published_year,
            venue="arXiv",  # 仮設定
            abstract=summary,
            pdf_url=pdf_url,
        )

    @staticmethod
    def create_limiter() -> AsyncLimiter:
        return AsyncLimiter(1, ArxivRepository.DEFAULT_SLEEP_SECONDS)
