import os
import sys

from loguru import logger


def basic_logger_format():
    return (
        f"<cyan>[WebRender]</cyan>"
        "<yellow>[{name}:{function}:{line}]</yellow>"
        "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
        "<level>[{level}]:{message}</level>"
    )


class LoggingLogger:
    def __init__(self, debug: bool = False, logs_path: str = None):
        self.log = logger
        self.log.remove()
        self.debug = logger.debug
        self.info = logger.info
        self.success = logger.success
        self.warning = logger.warning
        self.error = logger.error
        self.critical = logger.critical
        self.debug_flag = debug

        if debug:
            self.log.warning("Debug mode is enabled.")

        self.log.add(
            sys.stderr,
            format=basic_logger_format(),
            level="DEBUG" if debug else "INFO",
            colorize=True,
        )

        if logs_path is not None:
            log_file_path = os.path.join(logs_path, f"webrender_{{time:YYYY-MM-DD}}.log")
            self.log.add(
                log_file_path,
                format=basic_logger_format(),
                retention="10 days",
                encoding="utf8",
            )