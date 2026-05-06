"""リトライポリシー付き HTTP クライアントモジュール。"""

import asyncio
from contextlib import AsyncExitStack
from typing import Any, Literal, TypeAlias

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
)

from crawler.infrastructure.http.http_utils import (
    before_log,
    log_and_raise_final_error,
    make_wait_retry_after,
)

HttpMethod: TypeAlias = Literal["GET", "POST", "HEAD"]


class HttpRetryClient:
    DEFAULT_RETRY_STATUSES: frozenset[int] = frozenset({429})
    DEFAULT_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (httpx.RequestError,)

    def __init__(
        self,
        client: httpx.AsyncClient,
        retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES,
        retry_exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRY_EXCEPTIONS,
        max_retry_count: int = 10,
        limiter: AsyncLimiter | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        """HttpRetryClient インスタンスを初期化します。

        リトライデコレータをここで一度だけ構築し、内部の実装メソッドをラップした
        実行用関数をインスタンス変数として保持します。

        Args:
            client: HTTP リクエストに使用する AsyncClient インスタンス。
            retry_statuses: リトライ対象とするステータスコードの集合。
                デフォルトは ``frozenset({429})``。
            retry_exceptions: リトライ対象とする例外型のタプル。
                デフォルトはネットワークエラー（``RequestError`` およびそのサブクラス）。
            max_retry_count: リクエストの最大リトライ回数。
            limiter: 1秒あたりのリクエスト数などを制限するリミッター。
            semaphore: 同時接続数を制限するセマフォ。
        """
        self._client = client
        self._limiter = limiter
        self._semaphore = semaphore
        self._retry_statuses = retry_statuses

        def _should_retry(resp: httpx.Response) -> bool:
            return resp.status_code in self._retry_statuses

        retry_dec = retry(
            stop=stop_after_attempt(max_retry_count),
            wait=make_wait_retry_after(retry_statuses),
            retry=retry_if_result(_should_retry) | retry_if_exception_type(retry_exceptions),
            before=before_log,
            retry_error_callback=log_and_raise_final_error,
        )

        # バインド済みメソッドをリトライデコレータでラップし、プライベート変数に保持する。
        # これにより呼び出しごとのクロージャ再生成を避けつつ、メソッドの上書きを防ぐ。
        self._request_with_retry = retry_dec(self._request_impl)

    async def _request_impl(
        self,
        method: HttpMethod,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """HTTP リクエストの実装（リトライなし）。

        retry_statuses に含まれるステータスコード以外は raise_for_status() を呼び出します。

        Args:
            method: HTTP メソッド。指定可能な値は ``"GET"``, ``"POST"``, ``"HEAD"``。
            url: リクエスト先 URL。
            params: クエリパラメータ。
            json: リクエストボディ。
            headers: 追加リクエストヘッダー。

        Returns:
            HTTP レスポンス。

        Raises:
            httpx.HTTPStatusError: 4xx/5xx かつ retry_statuses 対象外のステータスコードの場合。
            httpx.RequestError: ネットワークレベルのエラー。
        """
        async with AsyncExitStack() as stack:
            if self._semaphore:
                await stack.enter_async_context(self._semaphore)
            if self._limiter:
                await stack.enter_async_context(self._limiter)
            logger.debug(f"In Semaphore and Limiter, {method} request to URL: {url}")
            match method:
                case "GET":
                    response = await self._client.get(
                        url,
                        params=params,
                        headers=headers,
                    )
                case "POST":
                    response = await self._client.post(
                        url,
                        params=params,
                        json=json,
                        headers=headers,
                    )
                case "HEAD":
                    response = await self._client.head(
                        url,
                        params=params,
                        headers=headers,
                    )
                case _:
                    raise ValueError(f"Unsupported HTTP method: {method}")
        if response.status_code >= 400 and response.status_code not in self._retry_statuses:
            response.raise_for_status()
        return response

    async def request(
        self,
        method: HttpMethod,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """リトライ付きで HTTP リクエストを送信します。

        Args:
            method: HTTP メソッド。指定可能な値は ``"GET"``, ``"POST"``, ``"HEAD"``。
            url: リクエスト先 URL。
            params: クエリパラメータ。
            json: リクエストボディ。
            headers: 追加リクエストヘッダー。
        """
        logger.debug(
            f"Starting {method} request to URL: {url}, params: {params}, json: {json}, headers: {headers}"
        )
        res = await self._request_with_retry(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
        )
        logger.debug(
            f"Finished {method} request to URL: {url}, params: {params}, json: {json}, headers: {headers}"
        )
        return res

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """リトライ付きで GET リクエストを送信します。

        Args:
            url: リクエスト先 URL。
            params: クエリパラメータ。
            headers: 追加リクエストヘッダー。

        Returns:
            HTTP レスポンス。

        Raises:
            httpx.HTTPStatusError: HTTP エラーが発生した場合。
            BaseException: リトライ上限到達後も例外が発生し続けた場合。
        """
        return await self.request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """リトライ付きで POST リクエストを送信します。

        Args:
            url: リクエスト先 URL。
            params: クエリパラメータ。
            json: リクエストボディ。
            headers: 追加リクエストヘッダー。

        Returns:
            HTTP レスポンス。

        Raises:
            httpx.HTTPStatusError: HTTP エラーが発生した場合。
            BaseException: リトライ上限到達後も例外が発生し続けた場合。
        """
        return await self.request("POST", url, params=params, json=json, headers=headers)

    async def head(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """リトライ付きで HEAD リクエストを送信します。"""
        return await self.request("HEAD", url, params=params, headers=headers)
