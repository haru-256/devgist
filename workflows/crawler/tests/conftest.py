import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """
    pytestの初期化処理の非常に早い段階で実行されるフック。
    ここでpytest全体に適用したい環境変数を設定する。
    """
    os.environ["GCS_BUCKET_NAME"] = "test-bucket"
