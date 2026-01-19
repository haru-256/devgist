import pytest
from pydantic import ValidationError

from domain.paper import Paper


def test_paper_creation_with_all_fields() -> None:
    """全フィールドを指定してPaperを作成できることをテスト"""
    paper = Paper(
        title="Test Paper Title",
        authors=["Author A", "Author B", "Author C"],
        year=2025,
        venue="RecSys",
        doi="10.1145/test",
        type="Conference and Workshop Papers",
        ee="https://doi.org/10.1145/test",
        url="https://dblp.org/rec/conf/recsys/test",
    )

    assert paper.title == "Test Paper Title"
    assert paper.authors == ["Author A", "Author B", "Author C"]
    assert paper.year == 2025
    assert paper.venue == "RecSys"
    assert paper.doi == "10.1145/test"
    assert paper.type == "Conference and Workshop Papers"
    assert paper.ee == "https://doi.org/10.1145/test"
    assert paper.url == "https://dblp.org/rec/conf/recsys/test"


def test_paper_creation_with_optional_fields_none() -> None:
    """オプショナルフィールドをNoneにしてPaperを作成できることをテスト"""
    paper = Paper(
        title="Test Paper",
        authors=["Author A"],
        year=2024,
        venue="KDD",
        doi=None,
        type=None,
        ee=None,
        url=None,
    )

    assert paper.title == "Test Paper"
    assert paper.authors == ["Author A"]
    assert paper.year == 2024
    assert paper.venue == "KDD"
    assert paper.doi is None
    assert paper.type is None
    assert paper.ee is None
    assert paper.url is None


def test_paper_creation_without_optional_fields() -> None:
    """オプショナルフィールドを省略してPaperを作成できることをテスト"""
    paper = Paper(
        title="Minimal Paper",
        authors=["Single Author"],
        year=2023,
        venue="SIGIR",
    )

    assert paper.title == "Minimal Paper"
    assert paper.authors == ["Single Author"]
    assert paper.year == 2023
    assert paper.venue == "SIGIR"
    assert paper.doi is None
    assert paper.type is None
    assert paper.ee is None
    assert paper.url is None


def test_paper_missing_required_title() -> None:
    """必須フィールドtitleが欠けている場合にValidationErrorが発生することをテスト"""
    with pytest.raises(ValidationError) as exc_info:
        Paper(  # type: ignore[call-arg]
            authors=["Author A"],
            year=2025,
            venue="RecSys",
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("title",) for error in errors)


def test_paper_missing_required_authors() -> None:
    """必須フィールドauthorsが欠けている場合にValidationErrorが発生することをテスト"""
    with pytest.raises(ValidationError) as exc_info:
        Paper(  # type: ignore[call-arg]
            title="Test Paper",
            year=2025,
            venue="RecSys",
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("authors",) for error in errors)


def test_paper_missing_required_year() -> None:
    """必須フィールドyearが欠けている場合にValidationErrorが発生することをテスト"""
    with pytest.raises(ValidationError) as exc_info:
        Paper(  # type: ignore[call-arg]
            title="Test Paper",
            authors=["Author A"],
            venue="RecSys",
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("year",) for error in errors)


def test_paper_missing_required_venue() -> None:
    """必須フィールドvenueが欠けている場合にValidationErrorが発生することをテスト"""
    with pytest.raises(ValidationError) as exc_info:
        Paper(  # type: ignore[call-arg]
            title="Test Paper",
            authors=["Author A"],
            year=2025,
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("venue",) for error in errors)


def test_paper_invalid_year_type() -> None:
    """yearが不正な型の場合にValidationErrorが発生することをテスト"""
    with pytest.raises(ValidationError) as exc_info:
        Paper(
            title="Test Paper",
            authors=["Author A"],
            year="not a number",  # type: ignore
            venue="RecSys",
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("year",) for error in errors)


def test_paper_empty_authors_list() -> None:
    """authorsが空リストの場合でもPaperを作成できることをテスト"""
    paper = Paper(
        title="No Authors Paper",
        authors=[],
        year=2025,
        venue="RecSys",
    )

    assert paper.authors == []


def test_paper_single_author() -> None:
    """著者が1人の場合のPaper作成をテスト"""
    paper = Paper(
        title="Single Author Paper",
        authors=["Solo Author"],
        year=2025,
        venue="WWW",
    )

    assert len(paper.authors) == 1
    assert paper.authors[0] == "Solo Author"


def test_paper_multiple_authors() -> None:
    """著者が複数人の場合のPaper作成をテスト"""
    authors = [f"Author {i}" for i in range(10)]
    paper = Paper(
        title="Many Authors Paper",
        authors=authors,
        year=2025,
        venue="CIKM",
    )

    assert len(paper.authors) == 10
    assert paper.authors == authors


def test_paper_serialization() -> None:
    """Paperが正しくシリアライズできることをテスト"""
    paper = Paper(
        title="Serialization Test",
        authors=["Author A", "Author B"],
        year=2025,
        venue="WSDM",
        doi="10.1145/serial",
    )

    data = paper.model_dump()

    assert data["title"] == "Serialization Test"
    assert data["authors"] == ["Author A", "Author B"]
    assert data["year"] == 2025
    assert data["venue"] == "WSDM"
    assert data["doi"] == "10.1145/serial"
    assert data["type"] is None
    assert data["ee"] is None
    assert data["url"] is None


def test_paper_deserialization() -> None:
    """辞書からPaperを正しくデシリアライズできることをテスト"""
    data: dict[str, object] = {
        "title": "Deserialization Test",
        "authors": ["Author X", "Author Y"],
        "year": 2024,
        "venue": "KDD",
        "doi": "10.1145/deserial",
        "type": "Journal Articles",
        "ee": "https://example.com",
        "url": "https://dblp.org/test",
    }

    paper = Paper(**data)  # type: ignore[arg-type]

    assert paper.title == data["title"]
    assert paper.authors == data["authors"]
    assert paper.year == data["year"]
    assert paper.venue == data["venue"]
    assert paper.doi == data["doi"]
    assert paper.type == data["type"]
    assert paper.ee == data["ee"]
    assert paper.url == data["url"]


def test_paper_equality() -> None:
    """同じ内容のPaperインスタンスが等価であることをテスト"""
    paper1 = Paper(
        title="Test",
        authors=["A"],
        year=2025,
        venue="RecSys",
    )

    paper2 = Paper(
        title="Test",
        authors=["A"],
        year=2025,
        venue="RecSys",
    )

    assert paper1 == paper2


def test_paper_inequality() -> None:
    """異なる内容のPaperインスタンスが等価でないことをテスト"""
    paper1 = Paper(
        title="Test1",
        authors=["A"],
        year=2025,
        venue="RecSys",
    )

    paper2 = Paper(
        title="Test2",
        authors=["A"],
        year=2025,
        venue="RecSys",
    )

    assert paper1 != paper2
