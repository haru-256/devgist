from typing import NoReturn

import httpx
import pytest
from pytest_mock import MockerFixture

from crawler.infrastructure.http.http_retry_client import HttpRetryClient

# ---------------------------------------------------------------------------
# POST – 成功 / リトライ / 上限超過
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_success(mocker: MockerFixture) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    http = HttpRetryClient(mock_client)
    response = await http.post("http://test.com", params={}, json={})

    assert response.status_code == 200
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_post_retries_on_429(mocker: MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_429, resp_200]

    http = HttpRetryClient(mock_client)
    response = await http.post("http://test.com", params={}, json={})

    assert response.status_code == 200
    assert mock_client.post.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_post_exhausted_on_429(mocker: MockerFixture) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    def raise_err() -> NoReturn:
        raise httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("POST", "http://test.com"),
            response=resp_429,
        )

    resp_429.raise_for_status.side_effect = raise_err
    mock_client.post.return_value = resp_429

    http = HttpRetryClient(mock_client, max_retry_count=2)
    with pytest.raises(httpx.HTTPStatusError):
        await http.post("http://test.com", params={}, json={})

    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_post_no_retry_on_500_by_default(mocker: MockerFixture) -> None:
    """デフォルトの retry_statuses={429} では 500 はリトライされず即例外。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_500 = mocker.MagicMock(spec=httpx.Response)
    resp_500.status_code = 500

    def raise_err() -> NoReturn:
        raise httpx.HTTPStatusError(
            "500 Server Error",
            request=httpx.Request("POST", "http://test.com"),
            response=resp_500,
        )

    resp_500.raise_for_status.side_effect = raise_err
    mock_client.post.return_value = resp_500

    http = HttpRetryClient(mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        await http.post("http://test.com", params={}, json={})

    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_post_retries_on_request_error(mocker: MockerFixture) -> None:
    """デフォルトの retry_exceptions に含まれる RequestError はリトライされること。"""
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [httpx.RequestError("Connection error"), resp_200]

    http = HttpRetryClient(mock_client)
    response = await http.post("http://test.com", params={}, json={})

    assert response.status_code == 200
    assert mock_client.post.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_post_exception_exhausted(mocker: MockerFixture) -> None:
    """例外でリトライ上限に達した場合、その例外が再送出されること。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.RequestError("Connection error")

    http = HttpRetryClient(mock_client, max_retry_count=2)
    with pytest.raises(httpx.RequestError):
        await http.post("http://test.com", params={}, json={})

    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_post_no_retry_on_non_retry_exception(mocker: MockerFixture) -> None:
    """retry_exceptions に含まれない例外はリトライされず即送出されること。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = ValueError("Unexpected error")

    http = HttpRetryClient(mock_client, retry_exceptions=())
    with pytest.raises(ValueError):
        await http.post("http://test.com", params={}, json={})

    assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# GET – 成功 / リトライ / 上限超過 / 500 リトライ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_retries_on_429(mocker: MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.get.side_effect = [resp_429, resp_200]

    http = HttpRetryClient(mock_client)
    response = await http.get("http://test.com")

    assert response.status_code == 200
    assert mock_client.get.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_get_exhausted_on_429(mocker: MockerFixture) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    def raise_err() -> NoReturn:
        raise httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "http://test.com"),
            response=resp_429,
        )

    resp_429.raise_for_status.side_effect = raise_err
    mock_client.get.return_value = resp_429

    http = HttpRetryClient(mock_client, max_retry_count=2)
    with pytest.raises(httpx.HTTPStatusError):
        await http.get("http://test.com")

    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_get_retries_on_500_when_configured(mocker: MockerFixture) -> None:
    """retry_statuses に 500 を含めた場合（DBLP 向け）、500 レスポンスをリトライすること。"""
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_500 = mocker.MagicMock(spec=httpx.Response)
    resp_500.status_code = 500
    resp_500.headers = httpx.Headers()
    resp_500.url = "http://test.com"

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.get.side_effect = [resp_500, resp_200]

    http = HttpRetryClient(mock_client, retry_statuses=frozenset({429, 500}))
    response = await http.get("http://test.com")

    assert response.status_code == 200
    assert mock_client.get.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_get_no_retry_on_500_by_default(mocker: MockerFixture) -> None:
    """デフォルトの retry_statuses={429} では 500 はリトライされず即例外。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_500 = mocker.MagicMock(spec=httpx.Response)
    resp_500.status_code = 500

    def raise_err() -> NoReturn:
        raise httpx.HTTPStatusError(
            "500 Server Error",
            request=httpx.Request("GET", "http://test.com"),
            response=resp_500,
        )

    resp_500.raise_for_status.side_effect = raise_err
    mock_client.get.return_value = resp_500

    http = HttpRetryClient(mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        await http.get("http://test.com")

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_get_retries_on_request_error(mocker: MockerFixture) -> None:
    """デフォルトの retry_exceptions に含まれる RequestError はリトライされること。"""
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.get.side_effect = [httpx.RequestError("Connection error"), resp_200]

    http = HttpRetryClient(mock_client)
    response = await http.get("http://test.com")

    assert response.status_code == 200
    assert mock_client.get.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_get_exception_exhausted(mocker: MockerFixture) -> None:
    """例外でリトライ上限に達した場合、その例外が再送出されること。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Connection error")

    http = HttpRetryClient(mock_client, max_retry_count=2)
    with pytest.raises(httpx.RequestError):
        await http.get("http://test.com")

    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_get_no_retry_on_non_retry_exception(mocker: MockerFixture) -> None:
    """retry_exceptions に含まれない例外はリトライされず即送出されること。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = ValueError("Unexpected error")

    http = HttpRetryClient(mock_client, retry_exceptions=())
    with pytest.raises(ValueError):
        await http.get("http://test.com")

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_head_success(mocker: MockerFixture) -> None:
    """HEAD リクエストが AsyncClient.head に委譲されること。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_client.head.return_value = mock_response

    http = HttpRetryClient(mock_client)
    response = await http.head("http://test.com")

    assert response.status_code == 200
    assert mock_client.head.call_count == 1


# ---------------------------------------------------------------------------
# Retry-After ヘッダー準拠 / 指数バックオフ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_after_header_compliance(mocker: MockerFixture) -> None:
    """Retry-After ヘッダーが存在する場合、その値で sleep すること。"""
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.url = "http://test.com"
    resp_429.headers = httpx.Headers({"Retry-After": "15"})

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_200]

    http = HttpRetryClient(mock_client)
    response = await http.post("http://test.com", params={}, json={})

    assert response.status_code == 200
    assert mock_client.post.call_count == 2
    mock_sleep.assert_awaited_once_with(15.0)


@pytest.mark.asyncio
async def test_retry_after_header_missing_fallback(mocker: MockerFixture) -> None:
    """Retry-After ヘッダーがない場合、指数バックオフで sleep すること。"""
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.url = "http://test.com"
    resp_429.headers = httpx.Headers()

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_200]

    http = HttpRetryClient(mock_client)
    await http.post("http://test.com", params={}, json={})

    assert mock_sleep.call_count == 1
    call_args = mock_sleep.await_args
    assert call_args
    wait_time = call_args[0][0]
    assert 1.0 <= wait_time <= 10.0
