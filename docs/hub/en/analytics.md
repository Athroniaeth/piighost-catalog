# Measuring how the catalog is used

Two things use this catalog and only one has a browser. The site is instrumented
from the page, where OpenPanel sees a device and a session. The other is the
piighost library: it fetches a `pipeline.toml` when a pipeline config names a
`catalog:` reference (`load_pipeline`, `catalogs = [...]`) or when Python code
calls `RegexDetector.from_catalog` or `piighost.catalog.pull`. Nothing there
loads a script, so the only place its calls can be observed is on the way out
of the API.

Hence one client in the dashboard whose secret is only needed on one side, which
is the answer to the question you arrive with:

| | From the browser | From the server |
|---|---|---|
| Who speaks | the site, from the page | the API, for the library |
| Credentials | `clientId` alone | `clientId` **and** `clientSecret` |
| Where it lives | inlined in the bundle, public | a variable of the `api` service, never in the bundle |
| Variable | `VITE_OPENPANEL_CLIENT_ID` | `OPENPANEL_CLIENT_ID` + `OPENPANEL_CLIENT_SECRET` |

The track API requires a write client, and therefore a secret, for every request:
an id alone would be refused on every event. That is why the server side asks for
two values and the browser side for one.

## What did not change, which is the point

The CSP stays `script-src 'self'; connect-src 'self'`. Two decisions make that
possible:

- **The SDK is bundled** (`@openpanel/web`, 8 KB) instead of being loaded from
  `openpanel.dev`. No external script, so nothing to allow in `script-src`. The
  session replay module, rrweb and its weight, stays in a separate chunk that is
  never requested: it is not enabled.
- **Ingestion goes through `/api/op`**, which nginx relays to the self-hosted
  instance. Same origin, so nothing to allow in `connect-src`.

A side effect is worth as much as the CSP: an ad blocker that drops requests to
an analytics domain has nothing to recognise here. Without it the numbers would
be missing whichever share of visitors runs one, and there would be no way to
know which.

## What is sent

On the browser side the event set is **closed**, in
`frontend/src/lib/analytics.ts`. Every property is a shape, a count or a
duration. None of them can carry a typed text, a detected value or a span. The
site promises that a text sent to the playground is never written to a database;
analytics that broke that promise would be worth less than no analytics at all.
Adding a key that could carry one means changing that type, in a diff someone
reads.

On the server side, `backend/hub/analytics.py` sends the shape of the call: the
kind, the registry object it named, whether the reference was pinned, and the
status. The caller's address and user agent are **not** forwarded, though
OpenPanel accepts both and would geolocate with them.

A call from a browser is not forwarded by the server: the page already sent its
own event, and counting it twice would make every number on the dashboard wrong
in a way that still looks plausible.

## How this relates to the counters on disk

`backend/hub/usage.py` keeps counters in a SQLite file, and that is not the same
thing. They feed the pull count shown on the site, are aggregated to the hour by
construction, and survive with no outside dependency. OpenPanel gives what a
dashboard gives: series, funnels, retention. Both are kept, each for what it
does.

## Setting it up

1. In the OpenPanel dashboard, create the project. A write client comes with it,
   and its secret is shown once.
2. Fill `.env` from `.env.example`: `VITE_OPENPANEL_CLIENT_ID` for the browser,
   the `OPENPANEL_*` trio for the server, and `OPENPANEL_HOST` plus `SITE_URL`
   for the nginx relay. `SITE_URL` is the origin the relay presents to
   OpenPanel's allow list, so it has to match the deployment exactly, scheme
   included.
3. Rebuild. `VITE_OPENPANEL_CLIENT_ID` is inlined at build time by Vite, so it is
   a build argument: changing the variable without rebuilding changes nothing.

Without those variables nothing is loaded and nothing is sent. That is the
default in development and for anyone hosting the catalog themselves.
