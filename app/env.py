"""
Environment loading helpers.
"""
import os

from dotenv import load_dotenv


def load_app_env() -> None:
    """Load local env files without overriding Vercel-provided env vars."""
    is_vercel = os.getenv("VERCEL") == "1"

    load_dotenv(".env", override=False)
    if not is_vercel:
        load_dotenv(".env.local", override=True)
