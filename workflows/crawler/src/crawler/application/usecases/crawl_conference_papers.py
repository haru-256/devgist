"""学会論文の収集と情報補完ユースケース実装。

このモジュールは、指定された学会のある年度の論文情報を複数のソースから
取得し、段階的に情報を補完したのちにストレージに保存する処理フロー全体を
オーケストレーションします。
"""

from loguru import logger

from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper
from crawler.domain.repositories.repository import PaperDatalake, PaperEnricher, PaperRetriever


class CrawlConferencePapers:
    """指定された学会の論文情報を取得・補完・保存するユースケース。

    このクラスは以下の処理フローを実行します:
        1. 指定学会の論文一覧を Primary Retriever から取得
        2. DOI が存在しない論文をフィルタリング
        3. 複数の Enricher で段階的に論文情報を補完（著者情報、被引用数など）
        4. 補完済み論文をデータレイクに保存

    セマフォを使用した並列制御により、外部 API への過度なリクエスト送信を
    防ぎながら、複数のデータソースから効率的にデータを収集できます。

    Attributes:
        conf_name: 対象学会の名前。
        paper_retriever: 論文一覧を取得するリポジトリ（Primary Source）。
        paper_enrichers: 論文情報を補完するリポジトリのリスト。
            複数指定した場合、リスト順に段階的に処理されます。
        paper_datalake: 処理済み論文をストレージに保存するリポジトリ。
    """

    def __init__(
        self,
        conf_name: ConferenceName,
        paper_retriever: PaperRetriever,
        paper_enrichers: list[PaperEnricher],
        paper_datalake: PaperDatalake,
    ) -> None:
        """CrawlConferencePapers インスタンスを初期化します。

        Args:
            conf_name: 対象学会を表す ConferenceName 列挙値。
            paper_retriever: 論文一覧を第一情報源から取得するリポジトリ。
            paper_enrichers: 論文情報を段階的に補完するリポジトリのリスト。
                空リストの場合、補完処理はスキップされる。
            paper_datalake: 最終的な論文データを外部ストレージに保存するリポジトリ。
        """
        self.conf_name = conf_name
        self.paper_retriever = paper_retriever
        self.paper_enrichers = paper_enrichers
        self.paper_datalake = paper_datalake

    async def execute(self, year: int) -> list[Paper]:
        """指定された学会の指定年度の論文を取得・補完・保存します。

        以下の処理を順序立てて実行します:

            1. **取得フェーズ**: paper_retriever から指定年度の論文一覧を取得
            2. **フィルタリング**: DOI が存在しない論文を除外
            3. **補完フェーズ**: paper_enrichers リスト内の各リポジトリで
               段階的に論文情報を補完
            4. **保存フェーズ**: 補完済み論文をデータレイクに保存

        Args:
            year: 対象年度（例: 2024）。

        Returns:
            補完・保存処理を経た論文 Paper オブジェクトのリスト。
            DOI を持たない論文は含まれません。
        """
        # 1. 指定学会の論文一覧を取得
        logger.info(f"Fetching {self.conf_name.upper()} {year} papers from DBLP...")
        papers = await self.paper_retriever.fetch_papers(conf=self.conf_name, year=year, h=1000)
        logger.info(f"Fetched {len(papers)} papers from DBLP")

        # 2. DOI のない論文を除外 (これ以降の Enrich 処理で DOI が必要なため)
        papers = [p for p in papers if p.doi is not None]
        logger.info(f"Filtered to {len(papers)} papers with DOI")
        if not papers:
            logger.warning(f"No papers with DOI found for {self.conf_name.upper()} {year}.")
            return []

        # 3. 各リポジトリで情報を補完
        logger.info(
            f"Enriching {self.conf_name.upper()} {year} papers with {len(self.paper_enrichers)} enricher(s)..."
        )
        for paper_enricher in self.paper_enrichers:
            enricher_name = paper_enricher.__class__.__name__
            logger.info(f"Enriching {self.conf_name.upper()} {year} papers with {enricher_name}...")
            papers = await paper_enricher.enrich_papers(papers, overwrite=False)
            logger.debug(f"Enrichment by {enricher_name} completed.")

        # 4. 補完された論文をデータレイクに保存
        logger.info(f"Saving enriched {self.conf_name.upper()} {year} papers to datalake...")
        save_results = await self.paper_datalake.save_papers(
            papers, papers_rep_name=self.conf_name.value
        )
        logger.info(f"Saved {len([r for r in save_results if r.success])} batches successfully.")

        return papers
