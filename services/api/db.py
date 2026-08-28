"""Single Supabase client instance. See BUILD_SPEC.md.

Loads .env for local dev - a no-op in deployment where the platform
(Railway) injects real environment variables directly, since
load_dotenv() never overrides variables that already exist.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client
