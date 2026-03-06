"""arXiv API との通信を担当するリポジトリモジュール。"""

import asyncio
from xml.etree.ElementTree import ParseError as StdParseError

import defusedxml.ElementTree as ET
import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.models.paper import Paper
from crawler.infrastructure.http.http_retry_client import HttpRetryClient


class ArxivXMLParseError(Exception):
    """arXiv API レスポンスの XML パース失敗を表す例外。"""


class ArxivRepository:
    """arXiv APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://export.arxiv.org"
    # XMLの名前空間定義
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    DEFAULT_SLEEP_SECONDS = 5

    def __init__(self, http: HttpRetryClient) -> None:
        """ArxivRepositoryインスタンスを初期化します。

        Args:
            http: HTTPリクエストに使用するHttpRetryClientインスタンス。
        """
        self.http = http

    @classmethod
    def from_client(
        cls,
        client: httpx.AsyncClient,
        max_retry_count: int = 10,
    ) -> "ArxivRepository":
        """Arxiv API用に設定されたHttpRetryClientを持つリポジトリを生成します。

        Args:
            client: 基本となるAsyncClient
            max_retry_count: HTTP リクエストの最大リトライ回数。

        Returns:
            レート制限とリトライ機能を持つArxivRepositoryインスタンス
        """
        # arXivのレート制限（1リクエスト/3秒）と同時接続数1を管理する
        http_client = HttpRetryClient(
            client=client,
            max_retry_count=max_retry_count,
            limiter=AsyncLimiter(1, cls.DEFAULT_SLEEP_SECONDS),
            semaphore=asyncio.Semaphore(1),
        )
        return cls(http=http_client)

    async def enrich_papers(
        self,
        papers: list[Paper],
        overwrite: bool = False,
    ) -> list[Paper]:
        """論文リストにarXivのデータ（Abstract, PDF URL）を付与します。

        DOI検索を試し、失敗した場合はタイトル検索を試みます。
        並列タスク数を抑制するため、BATCH_SIZE 件ずつ処理します。

        Args:
            papers: 更新対象の論文リスト。
            overwrite: 既存のデータを上書きするかどうか。

        Returns:
            更新された論文リスト。
        """
        # arXiv は 1 リクエスト / 5 秒のレート制限があり、全件を一括で TaskGroup に
        # 投入するとタスクオブジェクトがメモリを圧迫しスケジューリングコストも増大する。
        # BATCH_SIZE 件ずつ TaskGroup を区切ることで同時生成タスク数を抑制しつつ、
        # 内側の limiter / semaphore によるレート制限は引き続き有効に機能する。
        BATCH_SIZE = 50
        for i in range(0, len(papers), BATCH_SIZE):
            batch = papers[i : i + BATCH_SIZE]
            async with asyncio.TaskGroup() as tg:
                for paper in batch:
                    tg.create_task(self._enrich_single_paper(paper, overwrite))
            logger.debug(
                f"arXiv enrichment progress: {min(i + BATCH_SIZE, len(papers))}/{len(papers)}"
            )
        return papers

    async def _enrich_single_paper(self, paper: Paper, overwrite: bool) -> None:
        """単一の論文をarXivデータで更新します。

        Args:
            paper: 更新対象の論文オブジェクト。
            overwrite: 既存のデータを上書きするかどうか。
        """
        fetched_paper = None
        if paper.doi:
            fetched_paper = await self.fetch_by_doi(paper.doi)

        if not fetched_paper and paper.title:
            fetched_paper = await self.fetch_by_title(paper.title)

        if fetched_paper:
            # Abstract
            if fetched_paper.abstract and (not paper.abstract or overwrite):
                paper.abstract = fetched_paper.abstract
            # PDF URL
            if fetched_paper.pdf_url and (not paper.pdf_url or overwrite):
                paper.pdf_url = fetched_paper.pdf_url

    async def fetch_by_doi(self, doi: str) -> Paper | None:
        """DOIを使用してarXiv APIから論文データを取得します。

        Args:
            doi: 論文のDOI。

        Returns:
            Paperオブジェクト（pdf_url, abstractなどの詳細を含む）。取得失敗時はNone。
        """
        return await self._fetch(f"doi:{doi}", context={"doi": doi})

    async def fetch_by_title(self, title: str) -> Paper | None:
        """タイトルを使用してarXiv APIから論文データを取得します。

        Args:
            title: 論文のタイトル。

        Returns:
            Paperオブジェクト（pdf_url, abstractなどの詳細を含む）。取得失敗時はNone。
        """
        # タイトルに含まれるダブルクォートをエスケープ
        escaped_title = title.replace('"', "")
        return await self._fetch(f'ti:"{escaped_title}"', context={"title": title})

    async def _fetch(self, query: str, context: dict[str, str] | None = None) -> Paper | None:
        """arXiv API を呼び出し、最初のヒット結果を返します。

        例外を HTTP エラー・XML パースエラー・想定外エラーの3種類に分類して
        ログ出力し、いずれの場合も None を返して後続処理を継続させます。

        Args:
            query: arXiv API クエリ文字列（例: ``doi:10.xxx`` や ``ti:"title"``）。
            context: ログ出力に含めるコンテキスト情報（例: ``{"doi": "10.xxx"}``）。

        Returns:
            パースされた Paper オブジェクト。取得失敗またはヒットなしの場合は None。
        """
        ctx = context or {}
        params = {"search_query": query, "start": 0, "max_results": 1}
        try:
            resp = await self.http.get(
                f"{self.BASE_URL}/api/query",
                params=params,
                headers={"Accept": "application/atom+xml"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "arXiv HTTP error: status={status} query={query} context={ctx}",
                status=e.response.status_code,
                query=query,
                ctx=ctx,
            )
            return None
        except httpx.TimeoutException as e:
            logger.warning(
                "arXiv request timeout: query={query} context={ctx} error={error}",
                query=query,
                ctx=ctx,
                error=repr(e),
            )
            return None
        except httpx.RequestError as e:
            logger.warning(
                "arXiv network error: query={query} context={ctx} error={error}",
                query=query,
                ctx=ctx,
                error=repr(e),
            )
            return None

        try:
            return self._parse_xml(resp.text)
        except ArxivXMLParseError as e:
            logger.warning(
                "arXiv XML parse error: query={query} context={ctx} error={error}",
                query=query,
                ctx=ctx,
                error=repr(e),
            )
            return None
        except Exception as e:
            logger.error(
                "arXiv unexpected error during parse: query={query} context={ctx} "
                "error_type={error_type} error={error}",
                query=query,
                ctx=ctx,
                error_type=type(e).__name__,
                error=repr(e),
            )
            return None

    def _parse_xml(self, xml_text: str) -> Paper | None:
        """arXiv API レスポンスから Paper オブジェクトを生成します。

        Args:
            xml_text: arXiv API から返された Atom 形式の XML 文字列。

        Returns:
            パースされた Paper オブジェクト。エントリが存在しない場合は None。

        Raises:
            ArxivXMLParseError: XML の構造が不正でパースに失敗した場合。
        """
        try:
            root = ET.fromstring(xml_text)
        except (StdParseError, Exception) as e:
            raise ArxivXMLParseError(f"Failed to parse arXiv XML response: {e}") from e

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
                    "Failed to parse published year from arXiv entry: text={text!r} error={error!r}",
                    text=published_tag.text,
                    error=exc,
                )

        # PDFリンク
        pdf_url = None
        for link in entry.findall("atom:link", self.NAMESPACES):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        return Paper(
            title=title,
            authors=authors,
            year=published_year,
            venue="arXiv",  # 仮設定
            abstract=summary,
            pdf_url=pdf_url,
        )
