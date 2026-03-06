"""クローラーのメインエントリーポイント。"""

import asyncio
from dataclasses import dataclass

import httpx
from google.cloud import storage
from loguru import logger

from crawler.application.usecases.crawl_conference_papers import CrawlConferencePapers
from crawler.domain.models.paper import Paper
from crawler.infrastructure.configs import Config, load_config
from crawler.infrastructure.http.http_client import create_http_client
from crawler.infrastructure.repositories import (
    ArxivRepository,
    DBLPRepository,
    SemanticScholarRepository,
    UnpaywallRepository,
)
from crawler.infrastructure.repositories.gcs_datalake import GCSDatalake
from crawler.utils.log import setup_logger


@dataclass(frozen=True)
class CrawlerDependencies:
    """クロール実行に必要な依存オブジェクト群。"""

    usecases: list[CrawlConferencePapers]


async def build_dependencies(client: httpx.AsyncClient, cfg: Config) -> CrawlerDependencies:
    """実行時依存を組み立てます。"""
    dblp_repo = DBLPRepository.from_client(client, max_retry_count=cfg.max_retry_count)
    await dblp_repo.setup(client)
    ss_repo = SemanticScholarRepository.from_client(client, max_retry_count=cfg.max_retry_count)
    unpaywall_repo = UnpaywallRepository.from_client(
        client,
        email=cfg.email,
        max_retry_count=cfg.max_retry_count,
    )
    arxiv_repo = ArxivRepository.from_client(client, max_retry_count=cfg.max_retry_count)

    storage_client = storage.Client(project=cfg.gcp_project_id)
    datalake = GCSDatalake(
        storage_client=storage_client,
        bucket_name=cfg.gcs_bucket_name,
    )

    usecases = [
        CrawlConferencePapers(
            conf_name=conf_name,
            paper_retriever=dblp_repo,
            paper_enrichers=[ss_repo, unpaywall_repo, arxiv_repo],
            paper_datalake=datalake,
        )
        for conf_name in cfg.conference_names
    ]
    return CrawlerDependencies(usecases=usecases)


async def run_crawl_task(
    usecase: CrawlConferencePapers,
    year: int,
) -> list[Paper]:
    """指定された年のクロールタスクを実行します。

    Args:
        usecase: 実行するユースケース。
        year: 対象年。

    Returns:
        取得・補完された論文リスト。
    """
    try:
        enriched_papers = await usecase.execute(year)
    except Exception as e:
        # 1タスク失敗で全体停止しないよう、失敗タスクは空結果として継続する
        logger.exception(
            f"Crawl task failed for {usecase.conf_name.upper()} {year}: {type(e).__name__}: {e}"
        )
        return []

    # 統計情報のログ出力
    total_papers_count = len(enriched_papers)
    if total_papers_count > 0:
        abs_pass_cnt = sum(p.abstract is not None for p in enriched_papers)
        pdf_pass_cnt = sum(p.pdf_url is not None for p in enriched_papers)
        logger.info(
            f"{usecase.conf_name.upper()} {year}, Total papers: {total_papers_count}, "
            f"Abstract pass rate: {abs_pass_cnt / total_papers_count:.4f} ({abs_pass_cnt}/{total_papers_count}), "
            f"PDF pass rate: {pdf_pass_cnt / total_papers_count:.4f} ({pdf_pass_cnt}/{total_papers_count})"
        )

    return enriched_papers


async def main(cfg: Config) -> None:
    """クローラーを実行します。"""
    logger.debug(f"Config: {cfg}")

    headers = {"User-Agent": "DevGistBot/1.0"}
    years = cfg.years

    logger.info(f"Starting crawl for years: {years}")

    # 共有HTTPクライアントを作成
    async with create_http_client(headers=headers) as client:
        dependencies = await build_dependencies(client, cfg)

        tasks = []
        async with asyncio.TaskGroup() as tg:
            for usecase in dependencies.usecases:
                for year in years:
                    tasks.append(tg.create_task(run_crawl_task(usecase, year)))
        enriched_papers: list[Paper] = [paper for task in tasks for paper in task.result()]

    logger.info(f"Total enriched papers: {len(enriched_papers)}")


if __name__ == "__main__":
    cfg = load_config()
    setup_logger(cfg.log_level)
    asyncio.run(main(cfg))
