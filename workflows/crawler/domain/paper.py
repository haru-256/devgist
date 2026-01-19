from pydantic import BaseModel


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
        url: DBLP上の論文ページURL（オプション）
    """

    title: str
    authors: list[str]
    year: int
    venue: str
    doi: str | None = None
    type: str | None = None
    ee: str | None = None
    url: str | None = None
