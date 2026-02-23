"""ドメイン層のリポジトリインターフェース定義。

このモジュールは、インフラストラクチャ層(APIなど)へのアクセスのための
抽象インターフェースを提供します。入出力はドメインモデル(Paper)で行います。
"""

import asyncio
from typing import Protocol

from crawler.domain.enums import ConferenceName
from crawler.domain.models.paper import Paper


class PaperRetriever(Protocol):
    """論文データを取得するリポジトリのプロトコル。"""

    async def fetch_papers(
        self,
        conf: ConferenceName,
        year: int,
        semaphore: asyncio.Semaphore,
        h: int = 1000,
    ) -> list[Paper]: ...


class PaperEnricher(Protocol):
    """論文データを補完するリポジトリのプロトコル。"""

    async def enrich_papers(
        self,
        papers: list[Paper],
        semaphore: asyncio.Semaphore,
        overwrite: bool = False,
    ) -> list[Paper]: ...


class PaperDatalake(Protocol):
    """論文データを保存するリポジトリのプロトコル。"""

    async def save_papers(self, papers: list[Paper], semaphore: asyncio.Semaphore) -> None: ...
