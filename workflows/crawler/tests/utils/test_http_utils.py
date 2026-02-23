from typing import NoReturn

import httpx
import pytest
from pytest_mock import MockerFixture
from tenacity import stop_after_attempt

from crawler.infrastructure.http.http_utils import get_with_retry, is_rate_limit, post_with_retry


@pytest.mark.asyncio
async def test_is_rate_limit() -> None:
    response = httpx.Response(429)
    assert is_rate_limit(response) is True

    response = httpx.Response(200)
    assert is_rate_limit(response) is False

    response = httpx.Response(500)
    assert is_rate_limit(response) is False


@pytest.mark.asyncio
async def test_post_with_retry_success(mocker: MockerFixture) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    response = await post_with_retry(mock_client, "http://test.com", {}, {})

    assert response.status_code == 200
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_post_with_retry_backoff(mocker: MockerFixture) -> None:
    # Mock asyncio.sleep to verify it's called (and avoid real waiting)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    # Setup: 429 twice, then 200
    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_429, resp_200]

    response = await post_with_retry(mock_client, "http://test.com", {}, {})

    assert response.status_code == 200
    # Should be called 3 times (initial + 2 retries)
    assert mock_client.post.call_count == 3

    # Verify mock_sleep was called twice (once after each failure)
    assert mock_sleep.call_count == 2

    # Optional: We can check if sleep duration increases or is within range,
    # but since it's random/exponential, exact value check is tricky.
    # We just ensure backoff mechanism (sleep) is triggered.


@pytest.mark.asyncio
async def test_post_with_retry_exhausted(mocker: MockerFixture) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    # raise_for_status mock for final error handling
    def raise_err() -> NoReturn:
        raise httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("POST", "http://test.com"),
            response=resp_429,
        )

    resp_429.raise_for_status.side_effect = raise_err

    mock_client.post.return_value = resp_429

    # Override the retry condition temporarily for this test
    # tenacity evaluates decorators at import time, so we must mock the retry object itself
    mocker.patch.object(post_with_retry.retry, "stop", stop_after_attempt(2))  # type: ignore

    # Expect HTTPStatusError after retries exhausted (from log_and_raise_final_error)
    with pytest.raises(httpx.HTTPStatusError):
        await post_with_retry(mock_client, "http://test.com", {}, {})

    # Should stop after 2 attempts
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_post_no_retry_on_500(mocker: MockerFixture) -> None:
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

    # Should raise immediately without retry
    with pytest.raises(httpx.HTTPStatusError):
        await post_with_retry(mock_client, "http://test.com", {}, {})

    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_get_with_retry_backoff(mocker: MockerFixture) -> None:
    # Similar test for get_with_retry
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = httpx.Headers()
    resp_429.url = "http://test.com"

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.get.side_effect = [resp_429, resp_200]

    response = await get_with_retry(mock_client, "http://test.com")

    assert response.status_code == 200
    assert mock_client.get.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_retry_after_header_compliance(mocker: MockerFixture) -> None:
    # Mock asyncio.sleep to verify it's called with correct value
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    # 429 response with Retry-After: 15
    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.url = "http://test.com"
    resp_429.headers = httpx.Headers({"Retry-After": "15"})

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_200]

    response = await post_with_retry(mock_client, "http://test.com", {}, {})

    assert response.status_code == 200
    assert mock_client.post.call_count == 2

    # Should sleep for 15 seconds (Retry-After value)
    mock_sleep.assert_awaited_once_with(15.0)


@pytest.mark.asyncio
async def test_retry_after_header_missing_fallback(mocker: MockerFixture) -> None:
    # 429 response without Retry-After (should fallback to exponential backoff)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    resp_429 = mocker.MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.url = "http://test.com"
    resp_429.headers = httpx.Headers()
    # No Retry-After header

    resp_200 = mocker.MagicMock(spec=httpx.Response)
    resp_200.status_code = 200

    mock_client.post.side_effect = [resp_429, resp_200]

    await post_with_retry(mock_client, "http://test.com", {}, {})

    # Sleep should be called with some value (random exponential), check it's not 15 or 0
    # Just asserting it was called is mostly enough, but we can check if it's within min/max of the exp backoff
    assert mock_sleep.call_count == 1
    call_args = mock_sleep.await_args
    assert call_args
    wait_time = call_args[0][0]
    # Default exp backoff min=1, max=10
    assert 1.0 <= wait_time <= 10.0
