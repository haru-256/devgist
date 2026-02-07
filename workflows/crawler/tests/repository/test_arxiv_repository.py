import asyncio
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from aiolimiter import AsyncLimiter
from pytest_mock import MockerFixture

from crawler.repository.arxiv_repository import ArxivRepository


@pytest.fixture
def headers() -> dict[str, str]:
    return {"User-Agent": "TestBot/1.0"}


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


def test_parse_xml_valid(mock_client: httpx.AsyncClient) -> None:
    """正常なXMLのパーステスト"""
    repo = ArxivRepository(mock_client)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models...</summary>
    <published>2017-06-12T00:00:00Z</published>
    <link href="http://arxiv.org/abs/1706.03762v5" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/1706.03762v5" rel="related" type="application/pdf"/>
    <author>
      <name>Vaswani</name>
    </author>
  </entry>
</feed>
"""
    paper = repo._parse_xml(xml)
    assert paper is not None
    assert paper.title == "Attention Is All You Need"
    assert paper.abstract == "The dominant sequence transduction models..."
    assert paper.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
    assert paper.year == 2017
    assert paper.authors == ["Vaswani"]


def test_parse_xml_no_entry(mock_client: httpx.AsyncClient) -> None:
    """エントリがない場合のパーステスト"""
    repo = ArxivRepository(mock_client)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""
    paper = repo._parse_xml(xml)
    assert paper is None


def test_parse_xml_missing_fields(mock_client: httpx.AsyncClient) -> None:
    """フィールドが欠けている場合のパーステスト"""
    repo = ArxivRepository(mock_client)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <!-- No title, summary, authors, links -->
  </entry>
</feed>
"""
    paper = repo._parse_xml(xml)
    assert paper is not None
    # 欠けているフィールドはデフォルト値またはNone
    assert paper.title == ""
    assert paper.abstract is None
    assert paper.pdf_url is None


async def test_fetch_call_args(mock_client: httpx.AsyncClient, mocker: MockerFixture) -> None:
    """fetch_by_titleが正しく引数を渡しているか確認する"""
    repo = ArxivRepository(mock_client)
    sem = asyncio.Semaphore(1)

    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
    mock_response.raise_for_status = Mock()

    # AsyncMock for the return value of get_with_retry
    async def mock_get_with_retry(*args: Any, **kwargs: Any) -> httpx.Response:
        return mock_response

    mock_func = mocker.patch(
        "crawler.repository.arxiv_repository.get_with_retry", side_effect=mock_get_with_retry
    )

    await repo.fetch_by_title("Test Title", sem)

    # 呼び出し引数の検証
    assert mock_func.call_count == 1
    call_args = mock_func.call_args
    # call_args[0] is positional args: (client, url)
    assert call_args[0][0] == mock_client
    # call_args[1] is keyword args: params, headers
    assert "headers" in call_args[1]
    # Header should ONLY contain Accept, as User-Agent is in client
    expected_headers = {"Accept": "application/atom+xml"}
    assert call_args[1]["headers"] == expected_headers


async def test_arxiv_rate_limit(
    mock_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """arXivのレート制限が守られていることを確認する"""
    rate_limit_seconds = 0.2
    min_interval_seconds = 0.18

    repo = ArxivRepository(mock_client)
    repo.limiter = AsyncLimiter(1, rate_limit_seconds)

    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models...</summary>
    <published>2017-06-12T00:00:00Z</published>
    <link href="http://arxiv.org/abs/1706.03762v5" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/1706.03762v5" rel="related" type="application/pdf"/>
    <author>
      <name>Vaswani</name>
    </author>
  </entry>
</feed>
"""

    call_times: list[float] = []

    async def fake_get_with_retry(
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        call_times.append(asyncio.get_running_loop().time())
        return httpx.Response(200, text=xml)

    monkeypatch.setattr("crawler.repository.arxiv_repository.get_with_retry", fake_get_with_retry)

    sem = asyncio.Semaphore(10)
    await asyncio.gather(
        repo.fetch_by_doi("10.1000/xyz123", sem),
        repo.fetch_by_title("Attention Is All You Need", sem),
    )

    assert len(call_times) == 2
    first, second = sorted(call_times)
    assert second - first >= min_interval_seconds
