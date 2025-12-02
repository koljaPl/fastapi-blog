"""
Logging configuration with structured logging.
"""
import logging
import logging.config
import sys
from pathlib import Path

from app.config import LOGGING_CONFIG


def setup_logger(name: str) -> logging.Logger:
    """
    Setup logger with name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger
    """
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Configure logging
    logging.config.dictConfig(LOGGING_CONFIG)

    # Get logger
    logger = logging.getLogger(name)

    return logger


class StructuredLogger:
    """
    Structured logger for better log analysis.
    Adds context to log messages.
    """

    def __init__(self, name: str):
        self.logger = setup_logger(name)

    def log(self, level: int, message: str, **kwargs):
        """Log with additional context."""
        extra = {k: v for k, v in kwargs.items()}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Debug level log."""
        self.log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Info level log."""
        self.log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Warning level log."""
        self.log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Error level log."""
        self.log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Critical level log."""
        self.log(logging.CRITICAL, message, **kwargs)


# Request logging middleware
class RequestLogger:
    """Log HTTP requests."""

    def __init__(self, app):
        self.app = app
        self.logger = setup_logger("request")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            method = scope["method"]
            path = scope["path"]

            self.logger.info(f"{method} {path}")

        await self.app(scope, receive, send)