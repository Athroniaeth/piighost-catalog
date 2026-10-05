"""The sender that forwards what a browser cannot report for itself."""

import asyncio

import httpx
import pytest

from backend.hub.analytics import (
    API_URL_ENV_VAR,
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    QUEUE_SIZE,
    Analytics,
)


class TestConfiguration:
    def test_absent_without_every_credential(self, monkeypatch) -> None:
        """A client id with no secret is refused on every event, so it is not
        a configuration, it is a mistake to report at startup rather than in a
        log three days later."""
        monkeypatch.setenv(API_URL_ENV_VAR, "https://op.example.com")
        monkeypatch.setenv(CLIENT_ID_ENV_VAR, "abc")
        monkeypatch.delenv(CLIENT_SECRET_ENV_VAR, raising=False)
        assert Analytics.from_env() is None

    def test_present_with_all_three(self, monkeypatch) -> None:
        monkeypatch.setenv(API_URL_ENV_VAR, "https://op.example.com/")
        monkeypatch.setenv(CLIENT_ID_ENV_VAR, "abc")
        monkeypatch.setenv(CLIENT_SECRET_ENV_VAR, "shh")
        analytics = Analytics.from_env()
        assert analytics is not None
        # The trailing slash would make every URL a double slash.
        assert analytics.url == "https://op.example.com"


class TestQueue:
    def test_track_drops_rather_than_blocks(self) -> None:
        """Telemetry must never be the reason a response waits."""
        analytics = Analytics(url="u", client_id="i", client_secret="s")
        for index in range(QUEUE_SIZE + 5):
            analytics.track("pull", {"n": index})
        assert analytics.queue.qsize() == QUEUE_SIZE
        assert analytics.dropped == 5


class TestSending:
    async def test_posts_the_track_envelope_with_the_credentials(
        self, monkeypatch
    ) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(202, json={"status": "ok"})

        analytics = Analytics(
            url="https://op.example.com", client_id="abc", client_secret="shh"
        )
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            base_url=analytics.url,
            headers=analytics.headers(),
        ) as client:
            await analytics._send(client, "pull", {"object": "piighost/fr-default"})

        assert len(seen) == 1
        request = seen[0]
        assert str(request.url) == "https://op.example.com/track"
        assert request.headers["openpanel-client-id"] == "abc"
        assert request.headers["openpanel-client-secret"] == "shh"
        # httpx's default agent is a bot to OpenPanel, which drops its events.
        assert not request.headers["user-agent"].startswith("python-httpx")
        body = request.read().decode()
        assert '"type":"track"' in body.replace(" ", "")
        assert "fr-default" in body

    async def test_an_unreachable_dashboard_is_not_an_error(self) -> None:
        """A dead host must not raise into the request that triggered it."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("nope", request=request)

        analytics = Analytics(
            url="https://op.example.com", client_id="a", client_secret="b"
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=analytics.url
        ) as client:
            await analytics._send(client, "pull", {})

    async def test_a_rejection_is_not_an_error_either(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "bad client"})

        analytics = Analytics(
            url="https://op.example.com", client_id="a", client_secret="b"
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=analytics.url
        ) as client:
            await analytics._send(client, "pull", {})

    async def test_cancelling_drains_what_is_queued(self) -> None:
        sent: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request.read().decode())
            return httpx.Response(202)

        analytics = Analytics(
            url="https://op.example.com", client_id="a", client_secret="b"
        )
        # Patch the client the worker builds, so the worker itself is exercised.
        real = httpx.AsyncClient

        def fake(**kwargs) -> httpx.AsyncClient:
            kwargs["transport"] = httpx.MockTransport(handler)
            return real(**kwargs)

        import backend.hub.analytics as module

        module.httpx.AsyncClient = fake  # type: ignore[assignment]
        try:
            analytics.track("pull", {"object": "a/b"})
            analytics.track("pull", {"object": "c/d"})
            task = asyncio.create_task(analytics.run())
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            module.httpx.AsyncClient = real  # type: ignore[assignment]

        assert len(sent) == 2


class TestForwarding:
    """What the response hook decides to hand the dashboard."""

    async def test_the_library_is_forwarded_and_a_browser_is_not(self, client) -> None:
        """A page reports itself through the web SDK. Forwarding its API calls
        too would double every number on the dashboard, plausibly."""
        from backend.app import ANALYTICS_KEY

        analytics = Analytics(url="u", client_id="i", client_secret="s")
        client.app.state[ANALYTICS_KEY] = analytics
        try:
            await client.get(
                "/api/v1/refs/piighost/child/latest/pipeline.toml",
                headers={"user-agent": "piighost-hub/1.7.2"},
            )
            await client.get(
                "/api/v1/refs/piighost/child/latest/pipeline.toml",
                headers={"user-agent": "Mozilla/5.0 (X11; Linux x86_64)"},
            )
        finally:
            client.app.state.pop(ANALYTICS_KEY, None)

        queued = [analytics.queue.get_nowait() for _ in range(analytics.queue.qsize())]
        assert len(queued) == 1
        name, properties = queued[0]
        assert name == "pull"
        assert properties == {
            "object": "piighost/child",
            "selector": "latest",
            "client": "piighost",
            "status": 200,
        }

    async def test_nothing_outside_the_registry_is_forwarded(self, client) -> None:
        from backend.app import ANALYTICS_KEY

        analytics = Analytics(url="u", client_id="i", client_secret="s")
        client.app.state[ANALYTICS_KEY] = analytics
        try:
            await client.get("/api/health", headers={"user-agent": "curl/8"})
        finally:
            client.app.state.pop(ANALYTICS_KEY, None)
        assert analytics.queue.qsize() == 0
