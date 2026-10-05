/**
 * The worker, as something a component can await.
 *
 * One worker for the page: Pyodide is thirteen megabytes and several seconds of
 * start-up, so it is created on the first run and kept. Nothing loads until
 * someone asks for it, which is why this is not started at boot.
 */

import type { FromWorker, Hit, ToWorker } from "./pyodide-worker";

export type { Hit };

export type Run = { hits: Hit[]; elapsedMs: number };

let worker: Worker | null = null;
let pending: ((message: FromWorker) => void) | null = null;

/** Whether the runtime has been fetched, for a component to show a hint. */
export const engine = $state({ loading: false, ready: false });

function ensure(): Worker {
  if (worker) return worker;
  worker = new Worker(new URL("./pyodide-worker.ts", import.meta.url), {
    type: "module",
  });
  worker.onmessage = (event: MessageEvent<FromWorker>) => {
    const answer = pending;
    pending = null;
    answer?.(event.data);
  };
  return worker;
}

function ask(message: ToWorker): Promise<FromWorker> {
  return new Promise((resolve) => {
    pending = resolve;
    ensure().postMessage(message);
  });
}

/**
 * Run a catalog over a text, in this tab.
 *
 * The catalog comes from the API, because flattening a group is the
 * registry's own rule and there must be one implementation of it. The text does
 * not: it stays here, which is the reason any of this exists.
 */
export async function run(
  patterns: Record<string, string>,
  text: string,
): Promise<Run> {
  engine.loading = !engine.ready;
  try {
    const answer = await ask({ type: "run", patterns, text });
    if (answer.type === "failed") throw new Error(answer.error);
    if (answer.type !== "ran") throw new Error("the engine answered nothing");
    engine.ready = true;
    return { hits: answer.hits, elapsedMs: answer.elapsedMs };
  } finally {
    engine.loading = false;
  }
}
