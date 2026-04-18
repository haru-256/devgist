import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from crawler.domain.models.paper import FetchedPaperEnrichment, Paper, PaperEnrichment
from crawler.infrastructure.http.http_retry_client import HttpRetryClient


class UnpaywallRepository:
    """Unpaywall APIとの通信を担当するリポジトリクラス。"""

    BASE_URL = "https://api.unpaywall.org"
    PAPER_SEARCH_PATH = "v2"
    DEFAULT_SLEEP_SECONDS = 0.1
    DEFAULT_CONCURRENCY = 5
    DEFAULT_EMAIL = "crawler@haru256.dev"

    def __init__(self, http: HttpRetryClient, email: str = DEFAULT_EMAIL) -> None:
        """UnpaywallRepositoryインスタンスを初期化します。

        Args:
            http: HTTPリクエストに使用するHttpRetryClientインスタンス。
            email: Unpaywall API に渡す問い合わせ用メールアドレス。
        """
        self.http = http
        self.email = email

    @classmethod
    def from_client(
        cls,
        client: httpx.AsyncClient,
        email: str = DEFAULT_EMAIL,
        max_retry_count: int = 10,
    ) -> "UnpaywallRepository":
        """Unpaywall API用に設定されたHttpRetryClientを持つリポジトリを生成します。

        Args:
            client: 基本となるAsyncClient
            email: Unpaywall API に渡す問い合わせ用メールアドレス。
            max_retry_count: HTTP リクエストの最大リトライ回数。

        Returns:
            レート制限とリトライ機能を持つUnpaywallRepositoryインスタンス
        """
        http_client = HttpRetryClient(
            client=client,
            max_retry_count=max_retry_count,
            limiter=AsyncLimiter(1, cls.DEFAULT_SLEEP_SECONDS),
            semaphore=asyncio.Semaphore(cls.DEFAULT_CONCURRENCY),
        )
        return cls(http=http_client, email=email)

    async def fetch_enrichments(self, papers: list[Paper]) -> list[FetchedPaperEnrichment]:
        """論文リストに対応する Unpaywall 補完情報を取得します。"""
        # DOIを持つ論文のみ対象
        target_papers = [p for p in papers if p.doi]
        if not target_papers:
            return []

        # 全件を一括で TaskGroup に投入するとタスクオブジェクトがメモリを圧迫し
        # スケジューリングコストも増大する。BATCH_SIZE 件ずつ TaskGroup を区切ることで
        # 同時生成タスク数を抑制しつつ、内側の limiter / semaphore によるレート制限は
        # 引き続き有効に機能する。
        BATCH_SIZE = 50
        enrichments: list[FetchedPaperEnrichment] = []
        for i in range(0, len(target_papers), BATCH_SIZE):
            batch = target_papers[i : i + BATCH_SIZE]
            tasks: list[asyncio.Task[FetchedPaperEnrichment | None]] = []
            async with asyncio.TaskGroup() as tg:
                for paper in batch:
                    tasks.append(tg.create_task(self._fetch_single_paper_enrichment(paper)))
            for task in tasks:
                result = task.result()
                if result is not None:
                    enrichments.append(result)
            logger.debug(
                f"Unpaywall enrichment progress: {min(i + BATCH_SIZE, len(target_papers))}/{len(target_papers)}"
            )

        return enrichments

    async def _fetch_single_paper_enrichment(self, paper: Paper) -> FetchedPaperEnrichment | None:
        """単一の論文に対する Unpaywall 補完情報を取得します。

        DOI で Unpaywall を検索し、取得できた PDF URL を論文オブジェクトに反映します。

        Args:
            paper: 更新対象の論文オブジェクト。
        """
        if not paper.doi:
            return None

        enrichment = await self.fetch_by_doi(paper.doi)
        if not enrichment:
            logger.debug(f"Unpaywall: no data found for doi={paper.doi!r}")
            return None

        return FetchedPaperEnrichment(doi=paper.doi, enrichment=enrichment)

    async def fetch_by_doi(self, doi: str) -> PaperEnrichment | None:
        """DOI を使用して Unpaywall API から論文補完情報を取得します。

        Args:
            doi: 論文の DOI。

        Returns:
            取得した PDF URL などを含む PaperEnrichment オブジェクト。取得失敗時は None。
        """
        url = f"{self.BASE_URL}/{self.PAPER_SEARCH_PATH}/{doi}"

        try:
            resp = await self.http.get(url, params={"email": self.email})
            resp.raise_for_status()
            data = resp.json()
            return self._parse_paper(data)
        except httpx.HTTPStatusError as e:
            # 404 Not Foundは論文が存在しないケースとして扱う
            if e.response.status_code == 404:
                logger.debug(f"No paper found for DOI {doi} on Unpaywall (404).")
            else:
                logger.warning(
                    "Unpaywall HTTP error: status={status} doi={doi} error={error}",
                    status=e.response.status_code,
                    doi=doi,
                    error=repr(e),
                )
            return None
        except httpx.TimeoutException as e:
            logger.warning(
                "Unpaywall request timeout: doi={doi} error={error}",
                doi=doi,
                error=repr(e),
            )
            return None
        except httpx.RequestError as e:
            logger.warning(
                "Unpaywall network error: doi={doi} error={error}",
                doi=doi,
                error=repr(e),
            )
            return None
        except Exception as e:
            logger.error(
                "Unpaywall unexpected error: doi={doi} error_type={error_type} error={error}",
                doi=doi,
                error_type=type(e).__name__,
                error=repr(e),
            )
            return None

    def _parse_paper(self, data: dict[str, Any]) -> PaperEnrichment | None:
        """Unpaywall API レスポンスから PaperEnrichment を生成します。

        Args:
            data: Unpaywall API レスポンス。

        Returns:
            PaperEnrichment オブジェクト。パース失敗時は None。
        """
        if not data:
            return None

        # PDF URLの取得ロジック
        pdf_url = None
        best_oa_location = data.get("best_oa_location")
        if best_oa_location:
            pdf_url = best_oa_location.get("url_for_pdf")

        if not pdf_url:
            oa_locations = data.get("oa_locations", [])
            for loc in oa_locations:
                url = loc.get("url_for_pdf")
                if url:
                    pdf_url = url
                    break

        if data.get("doi") is None:
            logger.warning(f"Unpaywall response is missing 'doi' field. Response data: {data}")
            return None

        return PaperEnrichment(
            pdf_url=pdf_url,
        )
