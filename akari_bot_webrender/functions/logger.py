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
        self.log = logger.bind(name="WebRender")
        self.debug = self.log.debug
        self.info = self.log.info
        self.success = self.log.success
        self.warning = self.log.warning
        self.error = self.log.error
        self.critical = self.log.critical
        self.debug_flag = debug
        self.log_path = logs_path


        self.log.add(
            sys.stderr,
            format=basic_logger_format(),
            level="DEBUG" if debug else "INFO",
            colorize=True,
            filter=lambda record: record["extra"].get("name") == "WebRender",
        )

        if logs_path is not None:
            log_file_path = os.path.join(logs_path, f"webrender_{{time:YYYY-MM-DD}}.log")
            self.log.add(
                log_file_path,
                format=basic_logger_format(),
                retention="10 days",
                encoding="utf8",
                filter=lambda record: record["extra"].get("name") == "WebRender",
            )
        if debug:
            self.log.warning("Debug mode is enabled.")