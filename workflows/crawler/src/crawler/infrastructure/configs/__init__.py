import os
from dataclasses import dataclass

from crawler.domain.enums import ConferenceName


@dataclass(frozen=True)
class Config:
    email: str
    log_level: str
    conference_names: list[ConferenceName]
    semaphore_size: int
    years: list[int]
    max_retry_count: int


config = Config(
    email=os.getenv("EMAIL", "crawler@haru256.dev"),
    log_level=os.getenv("LOG_LEVEL", "DEBUG").upper(),
    conference_names=[
        ConferenceName.from_str(name)
        for name in os.getenv("CONFERENCE_NAMES", "recsys,kdd,wsdm,www,sigir,cikm").split(",")
    ],
    semaphore_size=int(os.getenv("SEMAPHORE_SIZE", 3)),
    years=[int(year) for year in os.getenv("YEARS", "2025").split(",")],
    max_retry_count=int(os.getenv("MAX_RETRY_COUNT", 10)),
)
