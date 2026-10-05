/**
 * What the site reports to a self-hosted OpenPanel, and nothing else.
 *
 * The event set is closed on purpose. Every property here is a shape, a count
 * or a duration; none of them can carry a text a visitor typed, a value a
 * pattern detected or a span of either. The site tells anyone who reads the
 * playground that their text is never written to a database, and analytics that
 * quietly broke that promise would be worse than no analytics. Adding a key
 * that could carry one means changing this type, in a diff someone reads.
 *
 * The SDK is bundled rather than loaded from openpanel.dev, and the events go
 * to a same-origin path that nginx forwards. Two things follow: the
 * Content-Security-Policy stays `script-src 'self'; connect-src 'self'`, which
 * is a property of this deployment worth keeping, and an ad blocker that drops
 * requests to openpanel.dev has nothing to drop, so the numbers are not quietly
 * missing whichever share of visitors runs one.
 */

import { OpenPanel } from "@openpanel/web";

export type AnalyticsEvent =
  | { name: "search"; props: { sort: string; kind: string; tags: number } }
  | {
      name: "playground_run";
      props: {
        source: "object" | "candidate";
        kept: number;
        elapsedMs: number;
      };
    }
  | { name: "chat_sent"; props: { turns: number; tokens: number } }
  | {
      name: "pipeline_copied";
      props: { form: string; memory: string; part: string };
    }
  | {
      name: "submission_checked";
      props: { kind: string; ok: boolean; findings: number };
    }
  | { name: "submission_forked"; props: { kind: string } };

/** Same origin, forwarded by nginx: nothing for a blocker to recognise. */
const DEFAULT_API_URL = "/api/op";

let panel: OpenPanel | null = null;

/**
 * Start the SDK, or do nothing at all.
 *
 * Without a client id there is no script, no request and no cookie, which is
 * the default in development and for anyone running the catalog themselves.
 */
export function startAnalytics(): void {
  const clientId = import.meta.env.VITE_OPENPANEL_CLIENT_ID;
  if (!clientId || panel) return;

  panel = new OpenPanel({
    clientId,
    apiUrl: (import.meta.env.VITE_OPENPANEL_API_URL || DEFAULT_API_URL).replace(
      /\/$/,
      "",
    ),
    // Screen views follow the history router on their own. Outgoing links are
    // left off: the only ones here go to GitHub and PyPI, and knowing that
    // someone left is not worth a listener on every anchor.
    trackScreenViews: true,
    trackOutgoingLinks: false,
    trackAttributes: false,
  });
}

/** Report one event. A no-op when analytics were never started. */
export function track(event: AnalyticsEvent): void {
  if (!panel) return;
  try {
    panel.track(event.name, event.props);
  } catch {
    // A dashboard being unreachable is not the visitor's problem.
  }
}
