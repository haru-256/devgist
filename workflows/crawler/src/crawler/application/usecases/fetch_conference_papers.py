import asyncio

from loguru import logger

from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper
from crawler.domain.repositories.repository import PaperEnricher, PaperRetriever


class FetchConferencePapers:
    """指定されたカンファレンスの論文情報を収集し、情報を充実させる汎用ユースケース。"""

    def __init__(
        self,
        conf_name: ConferenceName,
        paper_retriever: PaperRetriever,
        paper_enrichers: list[PaperEnricher],
    ) -> None:
        """FetchConferencePapersインスタンスを初期化します。

        Args:
            conf_name: 対象カンファレンス名 (例: "recsys", "sigir")
            paper_retriever: 論文一覧を取得するリポジトリ
            paper_enrichers: 論文情報を補完するリポジトリのリスト
        """
        self.conf_name = conf_name
        self.paper_retriever = paper_retriever
        self.paper_enrichers = paper_enrichers

    async def execute(self, year: int, semaphore: asyncio.Semaphore) -> list[Paper]:
        """指定された年・カンファレンスの論文を取得し、詳細情報を付与します。

        Args:
            year: 対象年
            semaphore: 並列実行制限用セマフォ

        Returns:
            情報が付与された論文リスト
        """
        # 1. DBLPから論文一覧を取得
        logger.info(f"Fetching {self.conf_name.upper()} {year} papers from DBLP...")
        papers = await self.paper_retriever.fetch_papers(
            conf=self.conf_name, year=year, h=1000, semaphore=semaphore
        )
        logger.info(f"Fetched {len(papers)} papers from DBLP")

        # DOIのない論文は除外 (これ以降のEnrich処理でDOIが必要なため)
        papers = [p for p in papers if p.doi is not None]
        logger.info(f"Filtered out {len(papers)} papers without DOI")
        if not papers:
            return []

        # 2. 各リポジトリで情報を補完
        for paper_enricher in self.paper_enrichers:
            logger.info(
                f"Enriching {self.conf_name.upper()} {year} papers with {paper_enricher.__class__.__name__}..."
            )
            papers = await paper_enricher.enrich_papers(
                papers, semaphore=semaphore, overwrite=False
            )

        return papers
