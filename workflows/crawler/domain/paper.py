from pydantic import BaseModel


class Paper(BaseModel):
    """論文を表す"""

    title: str
    authors: list[str]
    year: int
    venue: str
    doi: str | None = None
    type: str | None = None
    ee: str | None = None
    url: str | None = None
