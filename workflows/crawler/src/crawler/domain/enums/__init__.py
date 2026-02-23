from enum import StrEnum


class ConferenceName(StrEnum):
    RECSYS = "recsys"
    KDD = "kdd"
    WSDM = "wsdm"
    WWW = "www"
    SIGIR = "sigir"
    CIKM = "cikm"

    @classmethod
    def from_str(cls, value: str) -> "ConferenceName":
        lower = value.lower()
        if lower not in cls.__members__.values():
            raise ValueError(f"Invalid conference name: {value}")
        return cls(lower)
