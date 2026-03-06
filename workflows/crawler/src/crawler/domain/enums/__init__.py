from enum import StrEnum


class ConferenceName(StrEnum):
    """学術カンファレンス名を表す列挙型。

    文字列との比較が可能な StrEnum として定義されており、
    環境変数などの文字列から安全に変換できます。
    """

    RECSYS = "recsys"
    KDD = "kdd"
    WSDM = "wsdm"
    WWW = "www"
    SIGIR = "sigir"
    CIKM = "cikm"

    @classmethod
    def from_str(cls, value: str) -> "ConferenceName":
        """文字列から ConferenceName を生成します。

        Args:
            value: カンファレンス名の文字列（大文字・小文字不問）。

        Returns:
            対応する ConferenceName インスタンス。

        Raises:
            ValueError: 未定義のカンファレンス名が渡された場合。
        """
        lower = value.lower()
        if lower not in cls.__members__.values():
            raise ValueError(f"Invalid conference name: {value}")
        return cls(lower)
