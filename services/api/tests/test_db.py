from db import get_client


def test_get_client_returns_a_supabase_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    import db
    db._client = None  # reset the module-level singleton for this test

    client = get_client()

    assert client is not None


def test_get_client_returns_the_same_instance_on_repeat_calls(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    import db
    db._client = None

    first = get_client()
    second = get_client()

    assert first is second
