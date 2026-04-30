import os
from dataclasses import dataclass
from functools import lru_cache

from crawler.domain.enums import ConferenceName


@dataclass(frozen=True)
class Config:
    """クローラーの設定を保持するデータクラス。

    環境変数から読み込んだ設定値を不変オブジェクトとして保持します。

    Attributes:
        email: Unpaywall API などに使用するメールアドレス。
        log_level: ログ出力レベル（例: "DEBUG", "INFO"）。
        conference_names: クロール対象のカンファレンス名リスト。
        years: クロール対象年のリスト。
        max_retry_count: HTTP リクエストの最大リトライ回数。
        data_lake_bucket_name: 論文データを保存するデータレイクの GCS バケット名。
        data_lake_project_id: データレイクを保持する GCP プロジェクト ID。
    """

    email: str
    log_level: str
    conference_names: list[ConferenceName]
    years: list[int]
    max_retry_count: int
    data_lake_bucket_name: str
    data_lake_project_id: str


def _get_data_lake_bucket_name() -> str:
    """データレイクの GCS バケット名を環境変数から取得します。

    Returns:
        環境変数 ``DATA_LAKE_BUCKET_NAME`` の値。

    Raises:
        ValueError: 環境変数 ``DATA_LAKE_BUCKET_NAME`` が設定されていない場合。
    """
    data_lake_bucket_name = os.getenv("DATA_LAKE_BUCKET_NAME")
    if data_lake_bucket_name is None:
        raise ValueError("DATA_LAKE_BUCKET_NAME environment variable is not set.")
    return data_lake_bucket_name


@lru_cache(maxsize=1)
def load_config() -> Config:
    """環境変数から設定を読み込みます。"""
    return Config(
        email=os.getenv("EMAIL", "crawler@haru256.dev"),
        log_level=os.getenv("LOG_LEVEL", "DEBUG").upper(),
        conference_names=[
            ConferenceName.from_str(name.strip())
            for name in os.getenv("CONFERENCE_NAMES", "recsys,kdd,wsdm,www,sigir,cikm").split(",")
            if name.strip()
        ],
        years=[int(year.strip()) for year in os.getenv("YEARS", "2025").split(",") if year.strip()],
        max_retry_count=int(os.getenv("MAX_RETRY_COUNT", 10)),
        data_lake_project_id=os.getenv("DATA_LAKE_PROJECT_ID", "devgist"),
        data_lake_bucket_name=_get_data_lake_bucket_name(),
    )
