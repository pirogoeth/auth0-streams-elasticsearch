# -*- coding: utf-8 -*-

import logging
import sys
from typing import List

from loguru import logger

from .settings import Settings


class InterceptHandler(logging.Handler):

    def emit(self, record):

        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def make_propagating_logger(path: str) -> logging.Logger:
    """ Make a logger which has no handlers attached, which means the messages
        will only propagate to the root logger.
    """

    logger = logging.getLogger(path)
    [logger.removeHandler(handler) for handler in logger.handlers]
    logger.setLevel(logging.DEBUG)

    return logger


def configure(settings: Settings):
    """ Install an intercepting handler on the root logger.
    """

    log_level = logging._nameToLevel.get(settings.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(InterceptHandler())
    root.addHandler(logging.NullHandler())

    logger.remove()
    logger.add(sys.stdout, format="{message}", serialize=True)
