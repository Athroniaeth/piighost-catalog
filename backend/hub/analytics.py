"""The catalog's traffic, forwarded to a self-hosted OpenPanel.

Two things use this catalog and only one of them has a browser. The site is
instrumented from the page, where OpenPanel can see a device and a session and
answer the questions a dashboard is for. The other is the piighost library: it
fetches a rendered `pipeline.toml` when a pipeline config names a `catalog:`
reference (`load_pipeline`, `catalogs = [...]`) or when Python code calls
`RegexDetector.from_catalog` or `piighost.catalog.pull`. Nothing there loads a
script, so the only place its calls can be observed is here, on the way out of
the API.

So this forwards exactly the calls the browser cannot speak for, and nothing
else. A request from a browser is skipped, because the page already sent its
own event and counting it twice would make every number on the dashboard wrong
in a way that looks plausible.

What is sent is the shape of the call and nothing more: the kind, the registry
object it named, whether the reference was pinned, and the status. The caller's
address and user agent are deliberately not forwarded, though OpenPanel accepts
both and would geolocate with them, because the promise the site makes about
the playground is worth more than a map. `backend/hub/usage.py` explains the
same reasoning for the counters kept on disk.

Sending happens on a bounded queue drained by a worker. A slow or unreachable
dashboard must never delay an answer to a caller, and never fail one: when the
queue is full an event is dropped, which is the correct trade for telemetry.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

API_URL_ENV_VAR = "OPENPANEL_API_URL"
CLIENT_ID_ENV_VAR = "OPENPANEL_CLIENT_ID"
CLIENT_SECRET_ENV_VAR = "OPENPANEL_CLIENT_SECRET"

#: Events held in memory while the worker is busy. A few hundred is more than a
#: rate-limited API can produce in the time one HTTP round trip takes.
QUEUE_SIZE = 512

#: Long enough to cross a slow link, short enough that a dead host does not pin
#: the worker for a minute while the queue fills behind it.
TIMEOUT_SECONDS = 5.0

USER_AGENT = "piighost-catalog-server/1.0"
"""Who sends the events: a name OpenPanel does not take for a bot."""

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class Analytics:
    """A fire-and-forget sender for the calls a browser cannot report."""

    url: str
    client_id: str
    client_secret: str
    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = field(
        default_factory=lambda: asyncio.Queue(QUEUE_SIZE)
    )
    task: asyncio.Task[None] | None = None
    dropped: int = 0

    @classmethod
    def from_env(cls) -> Analytics | None:
        """Configured or absent. There is no half-configured state.

        A client id without its secret would be refused by the track API on
        every event, so it is treated as not configured rather than as an error
        the operator discovers from a log three days later.
        """
        url = (os.getenv(API_URL_ENV_VAR) or "").rstrip("/")
        client_id = os.getenv(CLIENT_ID_ENV_VAR) or ""
        client_secret = os.getenv(CLIENT_SECRET_ENV_VAR) or ""
        if not (url and client_id and client_secret):
            return None
        return cls(url=url, client_id=client_id, client_secret=client_secret)

    def track(self, name: str, properties: dict[str, Any]) -> None:
        """Queue one event. Never raises, never blocks, never awaits."""
        try:
            self.queue.put_nowait((name, properties))
        except asyncio.QueueFull:
            self.dropped += 1

    def headers(self) -> dict[str, str]:
        """The credentials, and a user agent that names the catalog.

        OpenPanel classes a request whose user agent is httpx's default as a
        bot: it answers 202 and drops the event without a word. Every pull went
        that way until the catalog named itself.
        """
        return {
            "openpanel-client-id": self.client_id,
            "openpanel-client-secret": self.client_secret,
            "User-Agent": USER_AGENT,
        }

    async def run(self) -> None:
        """Drain the queue until cancelled."""
        async with httpx.AsyncClient(
            base_url=self.url, headers=self.headers(), timeout=TIMEOUT_SECONDS
        ) as client:
            try:
                while True:
                    name, properties = await self.queue.get()
                    await self._send(client, name, properties)
            except asyncio.CancelledError:
                # Whatever is already queued is worth one last attempt, but a
                # shutdown cannot wait on a dashboard that is not answering.
                while not self.queue.empty():
                    name, properties = self.queue.get_nowait()
                    await self._send(client, name, properties)
                raise

    async def _send(
        self, client: httpx.AsyncClient, name: str, properties: dict[str, Any]
    ) -> None:
        """One event. Any failure is logged and forgotten."""
        try:
            response = await client.post(
                "/track",
                json={
                    "type": "track",
                    "payload": {"name": name, "properties": properties},
                },
            )
            if response.status_code >= 400:
                # `event` is structlog's own key for the message, so the
                # event's name travels under another one.
                logger.warning(
                    "analytics rejected", status=response.status_code, tracked=name
                )
        except (TimeoutError, httpx.HTTPError) as error:
            logger.warning("analytics unreachable", error=str(error), tracked=name)
