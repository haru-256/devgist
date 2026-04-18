import asyncio
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from aiolimiter import AsyncLimiter
from pytest_mock import MockerFixture

from crawler.domain.models.paper import FetchedPaperEnrichment, Paper, PaperEnrichment
from crawler.infrastructure.repositories.arxiv_repository import ArxivRepository, ArxivXMLParseError


@pytest.fixture
def headers() -> dict[str, str]:
    return {"User-Agent": "TestBot/1.0"}


@pytest.fixture
def mock_client(mocker: MockerFixture) -> httpx.AsyncClient:
    """Mock AsyncClient fixture."""
    return mocker.AsyncMock(spec=httpx.AsyncClient)


def test_parse_xml_valid(mock_client: httpx.AsyncClient) -> None:
    """正常なXMLから補完情報をパースできることをテスト"""
    repo = ArxivRepository.from_client(mock_client)
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
    assert paper.abstract == "The dominant sequence transduction models..."
    assert paper.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
    assert isinstance(paper, PaperEnrichment)


def test_parse_xml_no_entry(mock_client: httpx.AsyncClient) -> None:
    """エントリがない場合のパーステスト"""
    repo = ArxivRepository.from_client(mock_client)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""
    paper = repo._parse_xml(xml)
    assert paper is None


def test_parse_xml_missing_fields(mock_client: httpx.AsyncClient) -> None:
    """フィールドが欠けている場合のパーステスト"""
    repo = ArxivRepository.from_client(mock_client)
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
    assert paper.abstract is None
    assert paper.pdf_url is None


def test_parse_xml_invalid_raises_parse_error(mock_client: httpx.AsyncClient) -> None:
    """不正XMLを渡した場合に ArxivXMLParseError が送出されること。"""
    repo = ArxivRepository.from_client(mock_client)
    invalid_xml = "<feed><entry><title>broken</title></entry>"
    with pytest.raises(ArxivXMLParseError):
        repo._parse_xml(invalid_xml)


async def test_fetch_call_args(mock_client: httpx.AsyncClient, mocker: MockerFixture) -> None:
    """fetch_by_titleが正しく引数を渡しているか確認する"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
    mock_response.raise_for_status = Mock()

    repo = ArxivRepository.from_client(mock_client)
    mock_get = mocker.patch.object(repo.http, "get", return_value=mock_response)

    await repo.fetch_by_title("Test Title")

    assert mock_get.call_count == 1
    call_args = mock_get.call_args
    # url は第1位置引数
    assert "api/query" in call_args[0][0]
    # Header should ONLY contain Accept, as User-Agent is in client
    expected_headers = {"Accept": "application/atom+xml"}
    assert call_args[1]["headers"] == expected_headers


async def test_arxiv_rate_limit(
    mock_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """arXivのレート制限が守られていることを確認する"""
    rate_limit_seconds = 0.2
    min_interval_seconds = 0.18

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

    async def fake_get(*args: Any, **kwargs: Any) -> httpx.Response:
        call_times.append(asyncio.get_running_loop().time())
        return httpx.Response(200, text=xml, request=httpx.Request("GET", "http://test"))

    repo = ArxivRepository.from_client(mock_client)
    repo.http._limiter = AsyncLimiter(1, rate_limit_seconds)
    mock_client.get.side_effect = fake_get  # type: ignore[attr-defined]

    await asyncio.gather(
        repo.fetch_by_doi("10.1000/xyz123"),
        repo.fetch_by_title("Attention Is All You Need"),
    )

    assert len(call_times) == 2
    first, second = sorted(call_times)
    assert second - first >= min_interval_seconds


async def test_fetch_handles_http_status_error(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """HTTPStatusError 発生時に None を返すこと。"""
    mock_response = httpx.Response(500, request=httpx.Request("GET", "http://test"))

    repo = ArxivRepository.from_client(mock_client)
    mocker.patch.object(
        repo.http,
        "get",
        side_effect=httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("GET", "http://test"),
            response=mock_response,
        ),
    )

    result = await repo.fetch_by_doi("10.1000/xyz123")
    assert result is None


async def test_fetch_handles_timeout_exception(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """TimeoutException 発生時に None を返すこと。"""
    repo = ArxivRepository.from_client(mock_client)
    mocker.patch.object(repo.http, "get", side_effect=httpx.ReadTimeout("timed out"))

    result = await repo.fetch_by_title("Attention Is All You Need")
    assert result is None


async def test_fetch_handles_request_error(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """RequestError 発生時に None を返すこと。"""
    repo = ArxivRepository.from_client(mock_client)
    mocker.patch.object(repo.http, "get", side_effect=httpx.RequestError("network error"))

    result = await repo.fetch_by_doi("10.1000/xyz123")
    assert result is None


async def test_fetch_handles_xml_parse_error(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """XML パースエラー時に None を返すこと。"""
    mock_response = httpx.Response(
        200,
        text="<feed><entry><title>broken</title></entry>",
        request=httpx.Request("GET", "http://test"),
    )

    repo = ArxivRepository.from_client(mock_client)
    mocker.patch.object(repo.http, "get", return_value=mock_response)

    result = await repo.fetch_by_doi("10.1000/xyz123")
    assert result is None


async def test_fetch_handles_unexpected_parse_error(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """想定外のパースエラー時に None を返すこと。"""
    mock_response = httpx.Response(
        200,
        text="<?xml version='1.0' encoding='utf-8'?><feed xmlns='http://www.w3.org/2005/Atom'></feed>",
        request=httpx.Request("GET", "http://test"),
    )

    repo = ArxivRepository.from_client(mock_client)
    mocker.patch.object(repo.http, "get", return_value=mock_response)
    mocker.patch.object(repo, "_parse_xml", side_effect=RuntimeError("unexpected parse error"))

    result = await repo.fetch_by_title("Any Title")
    assert result is None


async def test_fetch_enrichments_runs_in_batches(
    mock_client: httpx.AsyncClient, mocker: MockerFixture
) -> None:
    """fetch_enrichments がバッチ処理されても全件処理されること。"""
    repo = ArxivRepository.from_client(mock_client)

    papers = [
        Paper(title=f"title-{i}", authors=[], year=2024, venue="v", doi=f"10.1000/{i}")
        for i in range(120)
    ]

    mock_enrich = mocker.patch.object(
        repo,
        "_fetch_single_paper_enrichment",
        return_value=FetchedPaperEnrichment(
            doi="10.1000/x",
            enrichment=PaperEnrichment(pdf_url="https://example.com/x.pdf"),
        ),
    )

    result = await repo.fetch_enrichments(papers)

    assert len(result) == 120
    assert mock_enrich.call_count == 120
