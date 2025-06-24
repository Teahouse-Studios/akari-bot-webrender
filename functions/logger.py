from loguru import logger


def basic_logger_format():
    return (
        f"<cyan>[WebRender]</cyan>"
        "<yellow>[{name}:{function}:{line}]</yellow>"
        "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
        "<level>[{level}]:{message}</level>"
    )


class LoggingLogger:
    def __init__(self, debug: bool = False):
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