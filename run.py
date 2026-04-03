#!/usr/bin/env python
"""
Local development runner.
"""
import os
import shutil
from pathlib import Path

from app.env import load_app_env


def setup():
    """Prepare local development files."""
    env_file = Path(".env.local")
    if not env_file.exists():
        shutil.copy(".env.example", ".env.local")
        print("Created .env.local from .env.example. Update it before running locally.")

    Path("app/static/css").mkdir(parents=True, exist_ok=True)
    Path("app/static/js").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    setup()
    load_app_env()

    import uvicorn

    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
    )
