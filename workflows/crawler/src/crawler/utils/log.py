import sys

from loguru import logger


def setup_logger(log_level: str = "DEBUG") -> None:
    """ロガーの初期設定を行います。

    デフォルトの設定をリセットし、標準エラー出力へ環境変数 ``LOG_LEVEL``
    に基づいたレベルでログを出力するよう再設定します。
    """
    # 一度デフォルトの設定を消してから再設定
    logger.remove()
    logger.add(sys.stderr, level=log_level)
