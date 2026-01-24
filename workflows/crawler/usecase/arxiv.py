import asyncio
from typing import Any

import defusedxml.ElementTree as ET
import httpx
from loguru import logger

from domain.paper import Paper
from libs.http_utils import get_with_retry


class ArxivSearch:
    """arXiv APIを使用して論文メタデータを取得・補完するクラス。"""

    DEFAULT_CONCURRENCY = 5  # arXivは短時間の大量リクエストに厳しいため控えめに設定
    BASE_URL = "http://export.arxiv.org/api/query"
    # XMLの名前空間定義
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ArxivSearch":
        """非同期コンテキストマネージャーのエントリーポイント。

        HTTPクライアントを初期化します。

        Returns:
            初期化されたArxivSearchインスタンス
        """
        self.client = httpx.AsyncClient(headers=self.headers, base_url=self.BASE_URL, timeout=30.0)
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
        """論文リストをarXivのデータで充実させます。

        DOIまたはタイトルを使用してarXiv APIから検索し、
        要約(abstract)とPDF URLを取得して論文情報に追加します。

        Args:
            papers: 情報を付与する論文のリスト
            semaphore: 並列実行数を制限するセマフォ（デフォルト: None）
            overwrite: 既存のデータを上書きするかどうか（デフォルト: False）

        Returns:
            情報が付与された論文のリスト

        Raises:
            RuntimeError: コンテキストマネージャー外で呼び出された場合
        """
        if self.client is None:
            raise RuntimeError("Use 'async with ArxivSearch(...)'.")

        sem = semaphore or asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async with asyncio.TaskGroup() as tg:
            for paper in papers:
                tg.create_task(self._enrich_single_paper(paper, sem, overwrite))

        return papers

    async def _enrich_single_paper(
        self, paper: Paper, sem: asyncio.Semaphore, overwrite: bool
    ) -> None:
        """単一の論文に対してDOIまたはタイトルで検索をかけ、メタデータを適用します。

        Args:
            paper: 対象の論文オブジェクト
            sem: セマフォ
            overwrite: 上書き許可フラグ
        """
        # 1. DOIで検索、ヒットしなければタイトルで検索を試みる
        data = None
        if paper.doi:
            data = await self._fetch_from_arxiv(f"doi:{paper.doi}", sem)

        if not data and paper.title:
            data = await self._fetch_from_arxiv(f'ti:"{paper.title.replace('"', '')}"', sem)

        if data:
            self._apply_metadata(paper, data, overwrite)

    async def _fetch_from_arxiv(self, query: str, sem: asyncio.Semaphore) -> dict[str, Any] | None:
        """arXiv APIを叩き、最初のヒット結果を返します。

        Args:
            query: arXiv APIクエリ文字列
            sem: セマフォ

        Returns:
            パースされた論文データ辞書。取得失敗やヒットなしの場合はNone。
        """
        if self.client is None:
            raise RuntimeError("Use 'async with ArxivSearch(...)'.")
        params = {"search_query": query, "start": 0, "max_results": 1}
        try:
            async with sem:
                # 既存の共通関数 get_with_retry を利用
                resp = await get_with_retry(self.client, "", params=params)
            resp.raise_for_status()
            return self._parse_xml(resp.text)
        except Exception as e:
            logger.warning(f"arXiv fetch error for {query}: {e}")
            return None

    def _parse_xml(self, xml_text: str) -> dict[str, Any] | None:
        """arXivのAtomリプライ(XML)を解析します。

        Args:
            xml_text: APIレスポンスのXML文字列

        Returns:
            抽出されたデータ辞書（abstract, pdf_url）。パース失敗時はNone。
        """
        root = ET.fromstring(xml_text)
        entry = root.find("atom:entry", self.NAMESPACES)
        if entry is None:
            return None

        summary_tag = entry.find("atom:summary", self.NAMESPACES)
        summary = None
        if summary_tag is not None:
            summary = summary_tag.text
        if summary:
            summary = summary.strip()

        result = {
            "abstract": summary,
            "pdf_url": None,
        }

        # PDFリンクの抽出
        for link in entry.findall("atom:link", self.NAMESPACES):
            if link.attrib.get("title") == "pdf":
                result["pdf_url"] = link.attrib.get("href")
                break

        return result

    def _apply_metadata(self, paper: Paper, data: dict[str, Any], overwrite: bool) -> None:
        """取得したデータをPaperオブジェクトに反映します。

        Args:
            paper: 更新対象の論文オブジェクト
            data: 適用するメタデータ
            overwrite: 上書き許可フラグ
        """
        if data.get("abstract") and (not paper.abstract or overwrite):
            paper.abstract = data["abstract"]
        if data.get("pdf_url") and (not paper.pdf_url or overwrite):
            paper.pdf_url = data["pdf_url"]
