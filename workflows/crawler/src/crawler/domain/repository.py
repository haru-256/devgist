"""ドメイン層のリポジトリインターフェース定義。

このモジュールは、インフラストラクチャ層(APIなど)へのアクセスのための
抽象インターフェースを提供します。入出力はドメインモデル(Paper)で行います。
"""

import asyncio
from typing import Literal, Protocol

from .paper import Paper


class PaperRetriever(Protocol):
    """論文データを取得するリポジトリのプロトコル。"""

    async def fetch_papers(
        self,
        conf: Literal["recsys", "kdd", "wsdm", "www", "sigir", "cikm"],
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
