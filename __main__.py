#!/usr/bin/env python3
"""
Entry point: run the Zenvi backend server.

Usage:
    python __main__.py
    # or
    uvicorn main:app --host 0.0.0.0 --port 8500 --reload
"""

import uvicorn
from config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        # Disable server-side WS ping/pong.  During long tool executions the
        # frontend cannot call recv() to answer pings, so Uvicorn would close
        # the connection after ws_ping_timeout.  TCP keepalive and our own
        # client-side pings are sufficient.
        ws_ping_interval=None,
        ws_ping_timeout=None,
    )


if __name__ == "__main__":
    main()
