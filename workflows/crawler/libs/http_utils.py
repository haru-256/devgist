from typing import Any, NoReturn

import httpx
from loguru import logger
from tenacity import (
    RetryCallState,
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_random_exponential,
)


def is_rate_limit(resp: httpx.Response) -> bool:
    """レスポンスがRate Limitエラー(429)かどうか判定します。"""
    return resp.status_code == 429


def log_and_raise_final_error(retry_state: RetryCallState) -> NoReturn:
    """リトライ回数超過時のエラーハンドリングを行います。"""
    attempt = retry_state.attempt_number
    if retry_state.outcome is None:
        raise ValueError("Retry state has no outcome")
    last_response: httpx.Response = retry_state.outcome.result()

    logger.error(
        f"Rate limit exceeded after {attempt} attempts: {last_response}, url: {last_response.url}"
    )

    last_response.raise_for_status()
    # NoReturn型を満たすための到達不能コード(通常は上記で例外が発生する)
    raise RuntimeError(f"Retry exhausted but response status was {last_response.status_code}")


def before_log(retry_state: RetryCallState) -> None:
    """リトライ前のロギングを行います。"""
    attempt = retry_state.attempt_number

    if attempt == 1:
        # retry_stateから安全にURLを取得
        if retry_state.kwargs and "url" in retry_state.kwargs:
            url = retry_state.kwargs["url"]
        elif len(retry_state.args) > 1:
            url = retry_state.args[1]
        else:
            url = "unknown"
        logger.info(f"Starting request to URL: {url}")
    else:
        if retry_state.outcome is None:
            logger.warning("Retry state has no outcome")
            return
        last_response = retry_state.outcome.result()
        logger.info(
            f"Attempt {attempt - 1} failed with status {last_response.status_code}, retrying..."
        )


def wait_retry_after(retry_state: RetryCallState) -> float:
    """Retry-Afterヘッダーを考慮した待機時間を計算します。

    Retry-Afterヘッダーが存在し、その値が数値形式（delay-seconds）である場合は
    その値を待機時間として使用します。HTTP-date形式のRetry-After値は現在
    サポートしておらず、その場合はValueErrorとして扱われ、指数バックオフに
    フォールバックします。Retry-Afterヘッダーが存在しない場合も同様に
    指数バックオフを使用します。
    """
    default_wait = wait_random_exponential(multiplier=0.5, min=1, max=10)(retry_state)

    if retry_state.outcome is None:
        return float(default_wait)

    result = retry_state.outcome.result()
    if isinstance(result, httpx.Response) and result.status_code == 429:
        retry_after = result.headers.get("Retry-After")
        if retry_after:
            try:
                wait_time = float(retry_after)
                logger.debug(f"Waiting for {wait_time}s (Retry-After)")
                return wait_time
            except ValueError:
                logger.warning(f"Invalid Retry-After header: {retry_after}")

    return float(default_wait)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_retry_after,
    retry=retry_if_result(is_rate_limit),
    before=before_log,
    retry_error_callback=log_and_raise_final_error,
)
async def post_with_retry(
    client: httpx.AsyncClient, url: str, params: dict[str, Any], json: dict[str, Any]
) -> httpx.Response:
    """指数バックオフとRate Limitリトライ付きでPOSTリクエストを送信します。

    Args:
        client: HTTPX非同期クライアント
        url: リクエストURL
        params: クエリパラメータ
        json: JSONボディ

    Returns:
        HTTPレスポンス

    Raises:
        httpx.HTTPStatusError: 429以外のHTTPエラーが発生した場合
        ValueError: リトライ状態が不正な場合
    """
    response = await client.post(url, params=params, json=json)
    # 200 OK: 成功、429: Rate limit（リトライ対象）
    # それ以外のステータスコードは即座にエラーとして扱う
    if response.status_code not in (200, 429):
        response.raise_for_status()

    return response


@retry(
    stop=stop_after_attempt(5),
    wait=wait_retry_after,
    retry=retry_if_result(is_rate_limit),
    before=before_log,
    retry_error_callback=log_and_raise_final_error,
)
async def get_with_retry(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None
) -> httpx.Response:
    """指数バックオフとRate Limitリトライ付きでGETリクエストを送信します。

    Args:
        client: HTTPX非同期クライアント
        url: リクエストURL
        params: クエリパラメータ（オプション）

    Returns:
        HTTPレスポンス

    Raises:
        httpx.HTTPStatusError: 429以外のHTTPエラーが発生した場合
        ValueError: リトライ状態が不正な場合
    """
    response = await client.get(url, params=params)
    # 200 OK: 成功、429: Rate limit（リトライ対象）
    # それ以外のステータスコードは即座にエラーとして扱う
    if response.status_code not in (200, 429):
        response.raise_for_status()

    return response
