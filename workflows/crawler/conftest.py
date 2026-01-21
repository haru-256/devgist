"""pytest configuration for loguru integration.

This module configures loguru to work with pytest's logging capture system,
ensuring that loguru log messages (including warnings) are properly displayed
in test output during test execution.
"""

import logging
from typing import TYPE_CHECKING

import pytest
from loguru import logger

if TYPE_CHECKING:
    from loguru import Message


def logging_sink(message: "Message") -> None:
    """Sink function that forwards loguru messages to Python's logging system.
    
    This allows pytest's log_cli to capture and display loguru logs.
    
    Args:
        message: The loguru Message object containing the log record
    """
    # Extract the log record from the message
    record = message.record
    
    # Map loguru level to Python logging level
    level_map = {
        "TRACE": logging.DEBUG,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "SUCCESS": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    level = level_map.get(record["level"].name, logging.INFO)
    
    # Get or create a logger for the module
    module_name = record["name"] or "__main__"
    py_logger = logging.getLogger(module_name)
    
    # Create a proper LogRecord with source location info
    log_record = py_logger.makeRecord(
        name=module_name,
        level=level,
        fn=record["file"].path,
        lno=record["line"],
        msg=record["message"],
        args=(),
        exc_info=None,
        func=record["function"],
    )
    
    # Emit the record
    py_logger.handle(log_record)


@pytest.fixture(scope="session", autouse=True)
def configure_loguru_for_pytest() -> None:
    """Configure loguru to integrate with pytest's logging system.
    
    This ensures that loguru messages are properly captured and displayed
    by pytest, making warnings and other log levels visible in test output.
    
    The configuration:
    1. Removes loguru's default stderr handler
    2. Adds a custom sink that forwards to Python's logging
    3. pytest's log_cli (configured in pyproject.toml) displays these logs
    """
    # Remove default loguru handler
    logger.remove()
    
    # Add sink that forwards to Python's logging system
    logger.add(
        logging_sink,
        format="{message}",
        level="DEBUG",
    )
