"""Logger module."""

import logging
import sys


def create_logger(name):
    """Create a logger instance."""
    logger = logging.getLogger(name)
    # timestr = datetime.now().strftime("%Y%m%dT%H%M%S")
    # datestr = datetime.now().strftime("%Y%m%d")
    fmt = "%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s"
    logging.captureWarnings(True)
    logger.setLevel(20)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(20)
    console.setFormatter(logging.Formatter(fmt))
    logger.addHandler(console)
    return logger
