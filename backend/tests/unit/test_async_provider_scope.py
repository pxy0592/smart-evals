import asyncio


def test_provider_scope_closes_before_loop_and_uses_fresh_provider(monkeypatch):
    import evaluation_db

    providers = []

    class Provider:
        def __init__(self):
            self.loop = None
            self.closed = False
            providers.append(self)

        async def read(self):
            self.loop = asyncio.get_running_loop()
            return id(self.loop)

        async def close(self):
            assert asyncio.get_running_loop() is self.loop
            self.closed = True

    monkeypatch.setattr(
        evaluation_db,
        "_connection_provider",
        lambda _connection_id: ({"id": "connection"}, Provider()),
    )

    first_connection, first_loop = evaluation_db._run_connection_provider_operation(
        "connection", lambda _connection, provider: provider.read()
    )
    second_connection, second_loop = evaluation_db._run_connection_provider_operation(
        "connection", lambda _connection, provider: provider.read()
    )

    assert first_connection["id"] == second_connection["id"] == "connection"
    assert first_loop != second_loop
    assert len(providers) == 2
    assert all(provider.closed for provider in providers)
