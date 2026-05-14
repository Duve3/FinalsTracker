import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

LOG_FORMAT = "[%(asctime)s.%(msecs)03d] [%(levelname)-8s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "tracker.log"
DEFAULT_LEVEL = logging.DEBUG
DEFAULT_CONSOLE_LEVEL = logging.INFO
DEFAULT_FILE_LEVEL = logging.DEBUG


class _ColoredFormatter(logging.Formatter):
    def __init__(self, msg: str, datefmt: str = None, use_color: bool = True):
        if datefmt is not None:
            super().__init__(msg, datefmt)
        else:
            super().__init__(msg)

        self.use_color = use_color
        RESET_SEQ = "\033[0m"
        COLOR_SEQ = "\033[38;5;%dm"
        BOLD_SEQ = "\033[1;38;5;%dm"
        # colors
        RED = 196
        GREEN = 190
        YELLOW = 220
        BLUE = 21
        MAGENTA = 201
        CYAN = 33
        WHITE = 231

        # formats
        self.FORMATS = {
            logging.DEBUG: (COLOR_SEQ % MAGENTA) + msg + RESET_SEQ,
            logging.INFO: (COLOR_SEQ % WHITE) + msg + RESET_SEQ,
            logging.WARNING: (COLOR_SEQ % YELLOW) + msg + RESET_SEQ,
            logging.ERROR: (COLOR_SEQ % RED) + msg + RESET_SEQ,
            logging.CRITICAL: (BOLD_SEQ % RED) + msg + RESET_SEQ
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, self.datefmt)
        d = formatter.format(record)
        # %(levelname)s (%(asctime)s) - %(name)s: %(message)s (Line: %(lineno)d [%(filename)s])
        # 'CRITICAL' '08/27 22:03:34' - 'main': 'We are going critical' (Line: '103' ['test.py'])
        return d


class _LogConfig:
    _initialized = False

    @classmethod
    def setup(
            cls,
            log_dir: str = DEFAULT_LOG_DIR,
            log_file: str = DEFAULT_LOG_FILE,
            console_level: int = DEFAULT_CONSOLE_LEVEL,
            file_level: int = DEFAULT_FILE_LEVEL,
            root_level: int = DEFAULT_LEVEL,
    ):
        if cls._initialized:
            return

        root = logging.getLogger()
        root.setLevel(root_level)

        if root.hasHandlers():
            root.handlers.clear()

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        coloredFormatter = _ColoredFormatter(LOG_FORMAT, LOG_DATE_FORMAT)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(coloredFormatter)
        root.addHandler(console_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        cls._initialized = True

        root.debug("Logging system initialized")
        root.info("Logging to console (level=%s) and file (level=%s)",
                  logging.getLevelName(console_level), logging.getLevelName(file_level))
        root.info("Log file: %s", log_path / log_file)

    @classmethod
    def reset(cls):
        cls._initialized = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(
        log_dir: Optional[str] = None,
        log_file: Optional[str] = None,
        console_level: Optional[int] = None,
        file_level: Optional[int] = None,
        root_level: Optional[int] = None,
):
    kwargs = {}
    if log_dir is not None:
        kwargs["log_dir"] = log_dir
    if log_file is not None:
        kwargs["log_file"] = log_file
    if console_level is not None:
        kwargs["console_level"] = console_level
    if file_level is not None:
        kwargs["file_level"] = file_level
    if root_level is not None:
        kwargs["root_level"] = root_level
    _LogConfig.setup(**kwargs)
