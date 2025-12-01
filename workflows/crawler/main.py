import asyncio
import xml.etree.ElementTree as ET

import httpx
import truststore
from loguru import logger

from libs import RobotGuard

# SSL: CERTIFICATE_VERIFY_FAILED の回避策
# macOS Keychainを利用し、中間証明書のチェーンを補完する
truststore.inject_into_ssl()


async def parse_medium_sitemaps(
    client: httpx.AsyncClient, sitemap_urls: list[str]
) -> list[dict[str, str | None]]:
    urls: list[dict[str, str | None]] = []
    for site_map in sitemap_urls:
        logger.debug(f"Found sitemap: {site_map}")
        resp = await client.get(site_map)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        logger.debug(f"Sitemap root tag: {root.tag}")
        namespaces = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        # 3. 名前空間プレフィックス (ns:) を付けて検索
        for url_tag in root.findall("ns:url", namespaces):
            # find も同様にプレフィックスが必要
            loc = url_tag.find("ns:loc", namespaces)
            if loc is None or loc.text is None:
                continue
            loc_text = loc.text
            lastmod = url_tag.find("ns:lastmod", namespaces)
            lastmod_text = lastmod.text if lastmod is not None else None

            urls.append({"url": loc_text, "lastmod": lastmod_text})
    return urls


async def fetch_content(
    sem: asyncio.Semaphore, client: httpx.AsyncClient, url: str, delay: float
) -> str:
    logger.debug(f"Fetch content from {url}")
    async with sem:
        logger.debug(f"Waiting for {delay} seconds before fetching {url}")
        await asyncio.sleep(delay)
        logger.debug(f"Starting fetch for {url}")
        resp = await client.get(url)
        resp.raise_for_status()
    return resp.text


async def parse_medium_article(
    sem: asyncio.Semaphore, client: httpx.AsyncClient, article_url: str
) -> None:
    logger.info(f"Processing article: {article_url}")
    content = await fetch_content(sem, client, article_url, delay=1)
    logger.debug(f"Fetched content length: {len(content)}")
    # TODO: ここで記事ページの解析処理を実装
    # 例: HTTPリクエストを送り、HTMLをパースして必要なデータを抽出する


async def parse_medium_articles(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    article_urls: list[str],
) -> None:
    tasks: list[asyncio.Task[None]] = []
    try:
        async with asyncio.TaskGroup() as tg:
            for article_url in article_urls:
                # TODO: クロール間隔の尊重
                tasks.append(tg.create_task(parse_medium_article(sem, client, article_url)))
    except* Exception as eg:
        logger.error(f"Error occurred during crawling: {eg}")
    for task in tasks:
        if not task.cancelled() and task.exception() is None:
            logger.info(f"Completed crawling: {task.get_name()}")


async def medium_crawl(headers: dict[str, str]) -> None:
    urls = ["https://netflixtechblog.com"]
    ignore_patterns = [
        "https://netflixtechblog.com/tagged",
    ]
    sem = asyncio.Semaphore(5)  # 同時接続数の制限

    for url in urls:
        robot_guard = RobotGuard(url, user_agent="ArchilogBot")
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            await robot_guard.load(client=client)
            article_urls = await parse_medium_sitemaps(
                client=client, sitemap_urls=robot_guard.get_sitemaps()
            )
            logger.debug(f"Found {len(article_urls)} article URLs in sitemaps.")
            valid_article_urls = [
                entry["url"]
                for entry in article_urls
                if entry["url"]
                and robot_guard.can_fetch(entry["url"])
                and not any(entry["url"].startswith(pattern) for pattern in ignore_patterns)
            ]
            logger.info(
                f"{len(valid_article_urls)} URLs are allowed to crawl after robots.txt check"
            )
            await parse_medium_articles(sem=sem, client=client, article_urls=valid_article_urls)


async def main() -> None:
    logger.info("Hello from crawler!")
    await medium_crawl(headers={"User-Agent": "ArchilogBot/1.0"})


if __name__ == "__main__":
    asyncio.run(main())
