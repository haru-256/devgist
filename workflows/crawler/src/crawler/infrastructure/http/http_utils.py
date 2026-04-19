"""HTTP ユーティリティ関数モジュール。

リトライ処理で共通利用されるヘルパー関数を提供します。
"""

from typing import NoReturn

import httpx
from loguru import logger
from tenacity import (
    RetryCallState,
    wait_random_exponential,
)


def log_and_raise_final_error(retry_state: RetryCallState) -> NoReturn:
    """リトライ回数超過時にエラーログを出力し、例外を送出します。

    例外によるリトライ上限到達と、ステータスコードによるリトライ上限到達の
    両方に対応しています。

    Args:
        retry_state: tenacity のリトライ状態オブジェクト。

    Raises:
        BaseException: 例外によるリトライ上限到達の場合、その例外を再送出します。
        httpx.HTTPStatusError: レスポンスによるリトライ上限到達の場合に送出します。
        RuntimeError: リトライ上限到達後もレスポンスが正常な場合（想定外）に送出します。
    """
    attempt = retry_state.attempt_number
    if retry_state.outcome is None:
        raise ValueError("Retry state has no outcome")

    exc = retry_state.outcome.exception()
    if exc is not None:
        # 例外でリトライ上限に達した場合
        logger.error(
            f"Request failed after {attempt} attempts with exception: {type(exc).__name__}: {exc}"
        )
        raise exc

    # ステータスコードでリトライ上限に達した場合
    last_response: httpx.Response = retry_state.outcome.result()
    logger.error(
        f"Request failed after {attempt} attempts: {last_response}, url: {last_response.url}"
    )
    last_response.raise_for_status()
    raise RuntimeError(f"Retry exhausted but response status was {last_response.status_code}")


def before_log(retry_state: RetryCallState) -> None:
    """リトライ時にリクエスト状況をログ出力します。

    初回リクエスト（attempt=1）はログしません。
    リトライ時（attempt>1）のみ WARNING を出力します。

    Args:
        retry_state: tenacity のリトライ状態オブジェクト。
    """
    attempt = retry_state.attempt_number

    if attempt == 1:
        return

    if retry_state.outcome is None:
        logger.warning("Retry state has no outcome")
        return

    exc = retry_state.outcome.exception()
    if exc is not None:
        logger.warning(
            f"Attempt {attempt - 1} failed with exception {type(exc).__name__}: {exc}, retrying..."
        )
        return

    last_response: httpx.Response = retry_state.outcome.result()
    logger.warning(
        f"Attempt {attempt - 1} failed with status {last_response.status_code}, retrying..."
    )


def wait_retry_after(retry_state: RetryCallState) -> float:
    """リトライ時の待機時間を決定します。

    Retry-After ヘッダーがあればそれを使用し、なければ指数バックオフを適用します。

    Args:
        retry_state: tenacity のリトライ状態オブジェクト。

    Returns:
        次のリトライまでの待機時間（秒）。
    """
    if retry_state.outcome is not None and retry_state.outcome.exception() is None:
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

    return wait_random_exponential(multiplier=1, min=1, max=10)(retry_state)
