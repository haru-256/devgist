import pytest
from pytest_mock import MockerFixture

from libs import RobotGuard


@pytest.fixture
def base_url() -> str:
    return "https://example.com"


@pytest.fixture
def guard(base_url: str) -> RobotGuard:
    return RobotGuard(base_url)


def test_init(guard: RobotGuard, base_url: str) -> None:
    assert guard.base_url == base_url
    assert guard.robots_txt_url == f"{base_url}/robots.txt"
    assert guard.loaded is False


async def test_load_success(guard: RobotGuard, mocker: MockerFixture) -> None:
    robots_txt = """
    User-agent: *
    Disallow: /private/
    Crawl-delay: 5
    Sitemap: https://example.com/sitemap.xml
    """
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = robots_txt

    mock_client = mocker.AsyncMock()
    mock_client.get.return_value = mock_response

    await guard.load(mock_client)

    assert guard.loaded is True
    mock_client.get.assert_awaited_once_with("https://example.com/robots.txt", timeout=10.0)

    # Check parsing
    assert guard.can_fetch("https://example.com/public/") is True
    assert guard.can_fetch("https://example.com/private/") is False
    assert guard.get_crawl_delay() == 5.0
    assert guard.get_sitemaps() == ["https://example.com/sitemap.xml"]


async def test_load_404(guard: RobotGuard, mocker: MockerFixture) -> None:
    mock_response = mocker.MagicMock()
    mock_response.status_code = 404

    mock_client = mocker.AsyncMock()
    mock_client.get.return_value = mock_response

    await guard.load(mock_client)

    assert guard.loaded is True
    # Should allow all
    assert guard.can_fetch("https://example.com/anywhere") is True


async def test_load_error_500(guard: RobotGuard, mocker: MockerFixture) -> None:
    mock_response = mocker.MagicMock()
    mock_response.status_code = 500

    mock_client = mocker.AsyncMock()
    mock_client.get.return_value = mock_response

    await guard.load(mock_client)

    assert guard.loaded is True
    # Should disallow all (safe side)
    assert guard.can_fetch("https://example.com/anywhere") is False


def test_not_loaded_raises(guard: RobotGuard) -> None:
    with pytest.raises(RuntimeError):
        guard.can_fetch("https://example.com")
    with pytest.raises(RuntimeError):
        guard.get_crawl_delay()
    with pytest.raises(RuntimeError):
        guard.get_sitemaps()
