from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger


class RobotGuard:
    """robots.txt の取得・解析を行い、クロール可否を判定するクラス。

    Webサイトの robots.txt を非同期で取得・パースし、指定された URL が
    クロール可能か判定します。Crawl-delay の設定や Sitemap の URL リストを
    取得する機能も提供します。

    Attributes:
        base_url: 対象サイトのベース URL。
        user_agent: クロールに使用する User-Agent 名。
        robots_txt_url: robots.txt の完全な URL。
        parser: robots.txt をパースするパーサー。
        loaded: robots.txt がロード済みかどうかを示すフラグ。
    """

    def __init__(self, base_url: str, user_agent: str = "*") -> None:
        """RobotGuard インスタンスを初期化します。

        Args:
            base_url: 対象サイトのベース URL（例: "https://example.com"）。
            user_agent: クロールに使用する User-Agent 名。デフォルトは "*"。
        """
        self.base_url = base_url
        self.user_agent = user_agent
        self.robots_txt_url = urljoin(base_url, "robots.txt")
        parser = RobotFileParser()
        parser.set_url(self.robots_txt_url)
        self.parser = parser
        self.loaded = False

    async def load(self, client: httpx.AsyncClient) -> None:
        """robots.txt を非同期で取得し、パーサーに読み込ませます。

        RobotFileParser は 307 リダイレクトに対応していないため、httpx で
        事前に取得してからパースします。レスポンスステータスに応じて以下の
        処理を行います。

        - 200: robots.txt をパースして読み込む。
        - 404: 全ての URL のクロールを許可。
        - その他: 安全のため全ての URL のクロールを拒否。

        Args:
            client: HTTP リクエストを送信するための非同期クライアント。

        Raises:
            httpx.HTTPError: HTTP 通信でエラーが発生した場合。
        """
        resp = await client.get(self.robots_txt_url, timeout=10.0)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            self.parser.parse(lines)
            logger.debug(f"Loaded robots.txt from {self.robots_txt_url}")
        elif resp.status_code == 404:
            self.parser.parse([])
            logger.debug("robots.txt not found (Allow all)")
        else:
            self.parser.parse(["User-agent: *", "Disallow: /"])
            logger.debug(f"Failed to load robots.txt: {resp.status_code}")
        self.loaded = True

    def _check_loaded(self) -> None:
        """robots.txt がロード済みかを確認します。

        Raises:
            RuntimeError: robots.txt がまだロードされていない場合。
        """
        if not self.loaded:
            logger.error("robots.txt not loaded yet.")
            raise RuntimeError("robots.txt not loaded yet.")

    def can_fetch(self, url: str) -> bool:
        """指定された URL がクロール可能か判定します。

        robots.txt のルールに基づいて、現在の User-Agent で指定された URL に
        アクセス可能かを判定します。

        Args:
            url: クロール可否を判定する URL。

        Returns:
            クロール可能な場合は True、不可能な場合は False。

        Raises:
            RuntimeError: robots.txt がまだロードされていない場合。
        """
        self._check_loaded()
        return self.parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self) -> int | None:
        """Crawl-delay（クロール間隔の待機時間）の設定を取得します。

        robots.txt で指定された Crawl-delay 設定を取得します。
        設定がない場合は None を返します。

        Returns:
            Crawl-delay（秒数）。設定がない場合は None。

        Raises:
            RuntimeError: robots.txt がまだロードされていない場合。
        """
        self._check_loaded()
        return self.parser.crawl_delay(self.user_agent)  # type: ignore

    def get_sitemaps(self) -> list[str]:
        """robots.txt で指定された Sitemap の URL リストを取得します。

        robots.txt に記載されている Sitemap 行から全ての URL を抽出して返します。

        Returns:
            Sitemap の URL リスト。Sitemap が存在しない場合は空リスト。

        Raises:
            RuntimeError: robots.txt がまだロードされていない場合。
        """
        self._check_loaded()
        return self.parser.sitemaps  # type: ignore
