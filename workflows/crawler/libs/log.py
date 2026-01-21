import logging
import sys

from loguru import logger


def setup_logger() -> None:
    # 一度デフォルトの設定を消してから再設定
    logger.remove()
    logger.add(sys.stderr, level=logging.DEBUG)
