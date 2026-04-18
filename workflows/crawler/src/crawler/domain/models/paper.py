from pydantic import BaseModel


class PaperEnrichment(BaseModel):
    """外部ソースから得た論文補完情報を表す値オブジェクト。"""

    abstract: str | None = None
    pdf_url: str | None = None

    def is_empty(self) -> bool:
        """補完可能な情報を一切持たない場合に True を返します。"""
        return self.abstract is None and self.pdf_url is None


class Paper(BaseModel):
    """学術論文のメタデータを表すドメインモデル。

    DBLPなどの学術データベースから取得した論文情報を格納します。
    タイトル、著者、出版年、会場（カンファレンス/ジャーナル）は必須フィールドで、
    DOIやURLなどの詳細情報はオプションです。

    Attributes:
        title: 論文のタイトル
        authors: 著者名のリスト
        year: 出版年
        venue: 掲載会場（カンファレンス名やジャーナル名）
        doi: Digital Object Identifier（オプション）
        type: 論文の種類（例: "Conference and Workshop Papers"）（オプション）
        ee: 電子版へのリンク（オプション）
        pdf_url: PDF版へのリンク（オプション）
        abstract: 論文の要約（オプション）
    """

    title: str
    authors: list[str]
    year: int
    venue: str
    doi: str | None = None
    type: str | None = None
    ee: str | None = None
    pdf_url: str | None = None
    abstract: str | None = None

    def apply_enrichment(
        self,
        enrichment: PaperEnrichment,
        overwrite: bool = False,
    ) -> None:
        """補完情報を現在の論文へ反映します。"""
        if enrichment.abstract and (self.abstract is None or overwrite):
            self.abstract = enrichment.abstract

        if enrichment.pdf_url and (self.pdf_url is None or overwrite):
            self.pdf_url = enrichment.pdf_url


class FetchedPaperEnrichment(BaseModel):
    """論文識別子と補完情報を組にした取得結果。"""

    doi: str
    enrichment: PaperEnrichment
