"""
main.py — Point d'entrée du Dashboard Queen V1.
Lance le serveur uvicorn sur le port 8080.
"""

import os
import sys
import uvicorn

sys.path.insert(0, "/app")


def main():
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    reload_flag = os.getenv("DASHBOARD_RELOAD", "false").lower() == "true"
    workers = int(os.getenv("DASHBOARD_WORKERS", "1"))

    uvicorn.run(
        "dashboard.backend.api:app",
        host=host,
        port=port,
        reload=reload_flag,
        workers=workers,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
