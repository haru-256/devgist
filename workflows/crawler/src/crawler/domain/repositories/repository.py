"""ドメイン層のリポジトリインターフェース定義。

このモジュールは、インフラストラクチャ層(API、外部ストレージなど)へのアクセスのための
抽象インターフェースを提供します。入出力はドメインモデル(Paper)で行います。
"""

from dataclasses import dataclass
from typing import Protocol

from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import FetchedPaperEnrichment, Paper


class PaperRetriever(Protocol):
    """論文データを取得するリポジトリのプロトコル。

    外部APIやデータベースから論文情報を検索・取得するインターフェースを定義します。
    """

    async def fetch_papers(
        self,
        conf: ConferenceName,
        year: int,
        h: int = 1000,
    ) -> list[Paper]:
        """指定された学会の論文データを取得します。

        Args:
            conf: 対象となる学会の名前。
            year: 取得対象の年度。
            h: APIの検索結果の最大件数（デフォルト: 1000）。

        Returns:
            取得した論文オブジェクトのリスト。
        """
        ...


class PaperEnrichmentProvider(Protocol):
    """論文補完情報を取得するリポジトリのプロトコル。

    既に取得した論文データに対して、外部ソースから追加情報を取得し、
    論文識別子と補完情報の組として返すインターフェースを定義します。
    """

    async def fetch_enrichments(self, papers: list[Paper]) -> list[FetchedPaperEnrichment]:
        """論文データに対する補完情報を取得します。

        Args:
            papers: 補完対象の論文オブジェクトのリスト。

        Returns:
            論文識別子と補完情報の取得結果リスト。
        """
        ...


@dataclass(frozen=True)
class SaveResult:
    """ストレージへのデータ保存結果を表すデータクラス。

    Google Cloud Storage などの外部ストレージに論文データを保存した際の
    結果を保持します。

    Attributes:
        success: 保存処理の成否。成功時は True、失敗時は False。
        blob_name: 保存先の GCS Blob 名（オブジェクトキー）。
            保存失敗時も blob_name が記録される場合があります。None の場合は
            ファイル名が確定しなかったことを示します。
        error_message: 保存処理失敗時のエラーメッセージ。成功時は None。
    """

    success: bool
    blob_name: str | None = None
    error_message: str | None = None


class PaperDatalake(Protocol):
    """論文データを保存するリポジトリのプロトコル。

    論文データをバッチ分割し、外部ストレージに永続化するインターフェースを定義します。
    """

    async def save_papers(self, papers: list[Paper], papers_rep_name: str) -> list[SaveResult]:
        """論文データをストレージに保存します。

        Args:
            papers: 保存対象の論文オブジェクトのリスト。
            papers_rep_name: ファイル名のプレフィックスに使用するリポジトリ名。

        Returns:
            各バッチの保存結果を表す SaveResult オブジェクトのリスト。
        """
        ...
