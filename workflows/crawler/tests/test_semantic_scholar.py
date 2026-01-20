from typing import Any

import pytest
from pytest_mock import MockerFixture

from domain.paper import Paper
from usecase.semantic_scholar import SemanticScholarSearch


@pytest.fixture
def headers() -> dict[str, str]:
    return {"User-Agent": "TestBot/1.0"}


@pytest.fixture
def sample_papers() -> list[Paper]:
    """テスト用の論文リスト"""
    return [
        Paper(
            title="Test Paper 1",
            authors=["Author A", "Author B"],
            year=2025,
            venue="RecSys",
            doi="10.1145/test1",
        ),
        Paper(
            title="Test Paper 2",
            authors=["Author C"],
            year=2025,
            venue="RecSys",
            doi="10.1145/test2",
        ),
    ]


@pytest.fixture
def mock_semantic_scholar_response() -> list[dict[str, Any]]:
    """Semantic Scholar APIのレスポンスモック"""
    return [
        {
            "externalIds": {"DOI": "10.1145/test1"},
            "abstract": "This is the abstract for test paper 1.",
            "openAccessPdf": {
                "url": "https://example.com/paper1.pdf",
                "disclaimer": None,
            },
        },
        {
            "externalIds": {"DOI": "10.1145/test2"},
            "abstract": "This is the abstract for test paper 2.",
            "openAccessPdf": None,
        },
    ]


async def test_context_manager(headers: dict[str, str], mocker: MockerFixture) -> None:
    """コンテキストマネージャーとして使用できることをテスト"""
    mock_client_aclose = mocker.patch("httpx.AsyncClient.aclose")

    async with SemanticScholarSearch(headers) as search:
        assert search.client is not None

    mock_client_aclose.assert_called_once()


async def test_enrich_papers_success(
    headers: dict[str, str],
    sample_papers: list[Paper],
    mock_semantic_scholar_response: list[dict[str, Any]],
    mocker: MockerFixture,
) -> None:
    """正常系: 論文データを充実できることをテスト"""
    mock_api_response = mocker.MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = mock_semantic_scholar_response

    mocker.patch("httpx.AsyncClient.post", return_value=mock_api_response)
    mocker.patch("httpx.AsyncClient.aclose")

    async with SemanticScholarSearch(headers) as search:
        enriched_papers = await search.enrich_papers(sample_papers)

    assert len(enriched_papers) == 2
    assert enriched_papers[0].abstract == "This is the abstract for test paper 1."
    assert enriched_papers[0].pdf_url == "https://example.com/paper1.pdf"
    assert enriched_papers[1].abstract == "This is the abstract for test paper 2."
    assert enriched_papers[1].pdf_url is None  # openAccessPdfがNone


async def test_enrich_papers_with_partial_data(
    headers: dict[str, str],
    sample_papers: list[Paper],
    mocker: MockerFixture,
) -> None:
    """データの一部がNoneの場合の挙動をテスト"""
    partial_response = [
        {
            "externalIds": {"DOI": "10.1145/test1"},
            "abstract": "Abstract 1",
            "openAccessPdf": None,
        },
        None,  # test2のデータが取得できなかった
    ]

    mock_api_response = mocker.MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = partial_response

    mocker.patch("httpx.AsyncClient.post", return_value=mock_api_response)
    mocker.patch("httpx.AsyncClient.aclose")

    async with SemanticScholarSearch(headers) as search:
        enriched_papers = await search.enrich_papers(sample_papers)

    # Noneのデータは除外される
    assert len(enriched_papers) == 1
    assert enriched_papers[0].title == "Test Paper 1"
    assert enriched_papers[0].abstract == "Abstract 1"


async def test_enrich_papers_outside_context_manager(
    headers: dict[str, str], sample_papers: list[Paper]
) -> None:
    """コンテキストマネージャー外で呼び出すとエラーになることをテスト"""
    search = SemanticScholarSearch(headers)

    with pytest.raises(RuntimeError, match="must be used as an async context manager"):
        await search.enrich_papers(sample_papers)


def test_extract_dois(headers: dict[str, str], sample_papers: list[Paper]) -> None:
    """DOI抽出が正しく動作することをテスト"""
    search = SemanticScholarSearch(headers)
    dois = search._extract_dois(sample_papers)

    assert dois == ["10.1145/test1", "10.1145/test2"]


def test_extract_dois_with_missing_doi(headers: dict[str, str]) -> None:
    """DOIが欠けている論文がある場合にエラーが発生することをテスト"""
    papers = [
        Paper(title="Paper 1", authors=["A"], year=2025, venue="RecSys", doi="10.1145/test1"),
        Paper(title="Paper 2", authors=["B"], year=2025, venue="RecSys", doi=None),
    ]

    search = SemanticScholarSearch(headers)

    with pytest.raises(ValueError, match="must have a DOI"):
        search._extract_dois(papers)


def test_find_original_paper(headers: dict[str, str], sample_papers: list[Paper]) -> None:
    """DOIから元の論文を正しく検索できることをテスト"""
    search = SemanticScholarSearch(headers)
    paper = search._find_original_paper(sample_papers, "10.1145/test1")

    assert paper.title == "Test Paper 1"
    assert paper.doi == "10.1145/test1"


def test_find_original_paper_not_found(headers: dict[str, str], sample_papers: list[Paper]) -> None:
    """存在しないDOIの場合にエラーが発生することをテスト"""
    search = SemanticScholarSearch(headers)

    with pytest.raises(ValueError, match="not found in original list"):
        search._find_original_paper(sample_papers, "10.1145/nonexistent")


def test_find_original_paper_none_doi(headers: dict[str, str], sample_papers: list[Paper]) -> None:
    """DOIがNoneの場合にエラーが発生することをテスト"""
    search = SemanticScholarSearch(headers)

    with pytest.raises(ValueError, match="DOI is None"):
        search._find_original_paper(sample_papers, None)


def test_find_original_paper_multiple_found(headers: dict[str, str]) -> None:
    """同じDOIの論文が複数ある場合にエラーが発生することをテスト"""
    duplicate_papers = [
        Paper(title="Paper 1", authors=["A"], year=2025, venue="RecSys", doi="10.1145/dup"),
        Paper(title="Paper 2", authors=["B"], year=2025, venue="RecSys", doi="10.1145/dup"),
    ]

    search = SemanticScholarSearch(headers)

    with pytest.raises(ValueError, match="Multiple papers"):
        search._find_original_paper(duplicate_papers, "10.1145/dup")


async def test_enrich_paper_metadata_with_abstract_and_pdf(
    headers: dict[str, str],
) -> None:
    """abstract とPDF URLの両方がある場合のメタデータ充実をテスト"""
    paper = Paper(title="Test", authors=["A"], year=2025, venue="RecSys", doi="10.1145/test")
    data = {
        "abstract": "Test abstract",
        "openAccessPdf": {"url": "https://example.com/test.pdf", "disclaimer": None},
    }

    search = SemanticScholarSearch(headers)
    enriched = await search._enrich_paper_metadata(paper, data)

    assert enriched.abstract == "Test abstract"
    assert enriched.pdf_url == "https://example.com/test.pdf"
    # 元のオブジェクトは変更されていない
    assert paper.abstract is None
    assert paper.pdf_url is None


async def test_enrich_paper_metadata_with_abstract_only(headers: dict[str, str]) -> None:
    """abstractのみがある場合のメタデータ充実をテスト"""
    paper = Paper(title="Test", authors=["A"], year=2025, venue="RecSys", doi="10.1145/test")
    data = {"abstract": "Test abstract", "openAccessPdf": None}

    search = SemanticScholarSearch(headers)
    enriched = await search._enrich_paper_metadata(paper, data)

    assert enriched.abstract == "Test abstract"
    assert enriched.pdf_url is None


async def test_enrich_paper_metadata_with_arxiv(
    headers: dict[str, str], mocker: MockerFixture
) -> None:
    """disclaimerにarXivリンクがある場合のメタデータ充実をテスト"""
    paper = Paper(title="Test", authors=["A"], year=2025, venue="RecSys", doi="10.1145/test")
    data = {
        "abstract": "Test abstract",
        "openAccessPdf": {
            "url": None,
            "disclaimer": "Available at https://arxiv.org/abs/2401.12345",
        },
    }

    mock_arxiv_response = mocker.MagicMock()
    mock_arxiv_response.status_code = 200
    mock_arxiv_response.raise_for_status = mocker.MagicMock()

    mock_get = mocker.patch("httpx.AsyncClient.get", return_value=mock_arxiv_response)

    async with SemanticScholarSearch(headers) as search:
        enriched = await search._enrich_paper_metadata(paper, data)

    assert enriched.pdf_url == "https://arxiv.org/pdf/2401.12345"
    mock_get.assert_called_once_with("https://arxiv.org/abs/2401.12345")


async def test_try_fetch_arxiv_pdf_success(headers: dict[str, str], mocker: MockerFixture) -> None:
    """arXiv PDF URLを正常に取得できることをテスト"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mocker.MagicMock()

    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    async with SemanticScholarSearch(headers) as search:
        pdf_url = await search._try_fetch_arxiv_pdf("Available at https://arxiv.org/abs/2401.12345")

    assert pdf_url == "https://arxiv.org/pdf/2401.12345"


async def test_try_fetch_arxiv_pdf_no_match(headers: dict[str, str]) -> None:
    """arXivリンクがない場合にNoneを返すことをテスト"""
    async with SemanticScholarSearch(headers) as search:
        pdf_url = await search._try_fetch_arxiv_pdf("No arXiv link here")

    assert pdf_url is None


async def test_try_fetch_arxiv_pdf_http_error(
    headers: dict[str, str], mocker: MockerFixture
) -> None:
    """arXivへのアクセスが失敗した場合にNoneを返すことをテスト"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 404

    def mock_raise_for_status() -> None:
        import httpx

        raise httpx.HTTPStatusError("Not found", request=mocker.MagicMock(), response=mock_response)

    mock_response.raise_for_status = mock_raise_for_status

    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    async with SemanticScholarSearch(headers) as search:
        pdf_url = await search._try_fetch_arxiv_pdf("Available at https://arxiv.org/abs/9999.99999")

    assert pdf_url is None


async def test_enrich_papers_api_error(
    headers: dict[str, str], sample_papers: list[Paper], mocker: MockerFixture
) -> None:
    """APIエラーが発生した場合の挙動をテスト"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 500

    def mock_raise_for_status() -> None:
        import httpx

        raise httpx.HTTPStatusError(
            "Server error", request=mocker.MagicMock(), response=mock_response
        )

    mock_response.raise_for_status = mock_raise_for_status

    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)
    mocker.patch("httpx.AsyncClient.aclose")

    async with SemanticScholarSearch(headers) as search:
        with pytest.raises(Exception):  # httpx.HTTPStatusError
            await search.enrich_papers(sample_papers)
