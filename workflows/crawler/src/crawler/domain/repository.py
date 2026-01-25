"""ドメイン層のリポジトリインターフェース定義。

このモジュールは、インフラストラクチャ層（APIなど）へのアクセスのための
抽象インターフェースを提供します。入出力はドメインモデル（Paper）で行います。
"""

import asyncio
from typing import Any, Literal, Protocol

from .paper import Paper


class PaperRetriever(Protocol):
    """論文リスト取得リポジトリのインターフェース。

    検索条件に基づいて論文のリスト（Paperオブジェクト）を取得します。
    """

    async def __aenter__(self) -> "PaperRetriever":
        """非同期コンテキストマネージャーのエントリーポイント。"""
        ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理。"""
        ...

    async def fetch_papers(
        self,
        conf: Literal["recsys", "kdd", "wsdm", "www", "sigir", "cikm"],
        year: int,
        h: int = 1000,
        semaphore: asyncio.Semaphore | None = None,
    ) -> list[Paper]:
        """指定されたカンファレンスと年度の論文情報を取得します。

        Args:
            conf: 対象カンファレンス名
            year: 対象年度
            h: 取得する最大論文数
            semaphore: 並列実行数を制限するセマフォ

        Returns:
            Paperオブジェクトのリスト
        """
        ...


class PaperEnricher(Protocol):
    """論文詳細取得リポジトリのインターフェース。

    外部APIを使用して論文の情報を充実（Enrich）させます。
    """

    async def __aenter__(self) -> "PaperEnricher":
        """非同期コンテキストマネージャーのエントリーポイント。"""
        ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理。"""
        ...

    async def enrich_papers(
        self,
        papers: list[Paper],
        semaphore: asyncio.Semaphore | None = None,
        overwrite: bool = False,
    ) -> list[Paper]:
        """論文リストに外部データを付与して更新します。

        Args:
            papers: 更新対象の論文リスト
            semaphore: 並列実行数を制限するセマフォ
            overwrite: 既存のデータを上書きするかどうか

        Returns:
            更新された論文リスト
        """
        ...
