"""
Logging configuration for the backend.
"""

import logging
import sys

log = logging.getLogger("zenvi_backend")

_configured = False

def setup_logging(level: str = "INFO"):
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    log.addHandler(handler)
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    _configured = True
